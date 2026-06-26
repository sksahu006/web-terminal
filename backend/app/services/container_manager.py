"""
Container Manager Service for Docker container lifecycle management.
Handles creation, monitoring, and cleanup of workspace containers.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import docker
from docker.errors import NotFound, APIError

from ..core.config import get_settings
from ..models.user_limits import UserLimits

logger = logging.getLogger(__name__)
settings = get_settings()


class ContainerManager:
    """
    Manages Docker container lifecycle for user workspaces.
    Ensures resource limits are enforced and containers are ephemeral.
    """
    
    def __init__(self):
        """Initialize Docker client."""
        self.client = docker.from_env()
        self._ensure_network()
    
    def _ensure_network(self):
        """Ensure the workspace network exists."""
        try:
            self.client.networks.get(settings.docker_network)
        except NotFound:
            logger.info(f"Creating Docker network: {settings.docker_network}")
            self.client.networks.create(
                settings.docker_network,
                driver="bridge"
            )
    
    def create_container(
        self,
        user_id: str,
        limits: UserLimits,
        github_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new workspace container with resource limits.
        
        Args:
            user_id: Unique user identifier
            limits: User's resource limits
            github_token: Optional GitHub token for repo access
            
        Returns:
            Dict with container_id, container_name, access_port
        """
        container_name = f"workspace-{user_id[:8]}"
        
        # Check if container already exists
        try:
            existing = self.client.containers.get(container_name)
            if existing.status == "running":
                raise ValueError(f"Container {container_name} is already running")
            else:
                # Remove stopped container
                existing.remove(force=True)
        except NotFound:
            pass
        
        # Environment variables for the container
        env_vars = {
            "USER_ID": user_id,
            "WORKSPACE_TYPE": "ephemeral",
        }
        
        if github_token:
            env_vars["GITHUB_TOKEN"] = github_token
        
        # Resource limits - enforced at container level
        # Memory in bytes (limits.memory is in MB)
        mem_limit = f"{limits.memory}m"
        
        # CPU quota (limits.cpu is in cores)
        # Docker uses nano CPUs (1 CPU = 1e9 nano CPUs)
        nano_cpus = int(limits.cpu * 1e9)
        
        # Create container with strict resource limits
        # We let Docker assign a random available host port by passing None/0
        container = self.client.containers.run(
            image=settings.workspace_image,
            name=container_name,
            detach=True,
            remove=False,  # We'll remove manually after cleanup
            environment=env_vars,
            network=settings.docker_network,
            ports={"7681/tcp": ("0.0.0.0", None)},  # Random port on all interfaces
            mem_limit=mem_limit,
            nano_cpus=nano_cpus,
            pids_limit=256,
            privileged=False,
            read_only=False,
            volumes={},
            labels={
                "workspace.user_id": user_id,
                "workspace.type": "ephemeral",
                "workspace.created": datetime.utcnow().isoformat(),
            }
        )
        
        # Reload container to get the assigned port
        container.reload()
        
        if container.status == "exited":
            logs = container.logs().decode("utf-8")
            raise RuntimeError(f"Workspace container failed to start. Logs: {logs}")
            
        port_bindings = container.attrs.get("NetworkSettings", {}).get("Ports", {})
        if not port_bindings or "7681/tcp" not in port_bindings or not port_bindings["7681/tcp"]:
            raise RuntimeError(f"Port 7681/tcp was not bound. Container status: {container.status}")
            
        access_port = int(port_bindings["7681/tcp"][0]["HostPort"])
        
        logger.info(f"Created container {container_name} for user {user_id} on port {access_port}")
        
        return {
            "container_id": container.id,
            "container_name": container_name,
            "access_port": access_port,
        }

    def create_lab_container(
        self,
        user_id: str,
        room_slug: str,
        image: str,
        limits: UserLimits,
        exposed_port: int = 7681,
        github_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a terminal lab container from a lab template image.

        Args:
            user_id: Unique user identifier
            room_slug: Slug of the lab room being started
            image: Docker image to run for this lab
            limits: User's resource limits
            exposed_port: Container port that serves the lab access UI
            github_token: Optional GitHub token for repo access

        Returns:
            Dict with container_id, container_name, access_port
        """
        safe_slug = re.sub(r"[^a-zA-Z0-9_.-]", "-", room_slug)[:32]
        container_name = f"lab-{user_id[:8]}-{safe_slug}"

        try:
            existing = self.client.containers.get(container_name)
            if existing.status == "running":
                raise ValueError(f"Container {container_name} is already running")
            existing.remove(force=True)
        except NotFound:
            pass

        env_vars = {
            "USER_ID": user_id,
            "LAB_ROOM_SLUG": room_slug,
            "WORKSPACE_TYPE": "lab",
        }

        if github_token:
            env_vars["GITHUB_TOKEN"] = github_token

        mem_limit = f"{limits.memory}m"
        nano_cpus = int(limits.cpu * 1e9)
        port_key = f"{exposed_port}/tcp"

        container = self.client.containers.run(
            image=image,
            name=container_name,
            detach=True,
            remove=False,
            environment=env_vars,
            network=settings.docker_network,
            ports={port_key: ("0.0.0.0", None)},  # Random port on all interfaces
            mem_limit=mem_limit,
            nano_cpus=nano_cpus,
            pids_limit=256,
            privileged=False,
            read_only=False,
            # No tty/stdin_open — ttyd manages its own PTY per client connection
            volumes={},
            labels={
                "lab.user_id": user_id,
                "lab.room_slug": room_slug,
                "lab.type": "terminal",
                "lab.created": datetime.utcnow().isoformat(),
            }
        )

        import time
        # Poll until container reaches a stable state
        # Transient: created, restarting  |  Terminal: running, exited, dead, removing
        TERMINAL_STATES = {"running", "exited", "dead", "removing"}
        for attempt in range(10):
            time.sleep(1)
            container.reload()
            logger.info(
                f"[{attempt+1}/10] Container {container_name} status={container.status}"
            )
            if container.status in TERMINAL_STATES:
                break

        if container.status != "running":
            logs = container.logs().decode("utf-8", errors="replace")
            container.remove(force=True)
            raise RuntimeError(
                f"Lab container failed to reach running state "
                f"(status={container.status}). Logs:\n{logs}"
            )

        port_bindings = container.attrs.get("NetworkSettings", {}).get("Ports", {})
        if not port_bindings or port_key not in port_bindings or not port_bindings[port_key]:
            raise RuntimeError(f"Port {port_key} was not bound. Container status: {container.status}")

        access_port = int(port_bindings[port_key][0]["HostPort"])

        logger.info(
            f"Created lab container {container_name} for user {user_id} "
            f"room {room_slug} on port {access_port}"
        )

        return {
            "container_id": container.id,
            "container_name": container_name,
            "access_port": access_port,
        }
    

    def create_web_target_lab(
        self,
        user_id: str,
        room_slug: str,
        attacker_image: str,
        target_image: str,
        limits: UserLimits,
        attacker_port: int = 7681,
        target_port: int = 8000,
        github_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a web-target lab: one private target container plus one ttyd attacker container.
        """
        safe_slug = re.sub(r"[^a-zA-Z0-9_.-]", "-", room_slug)[:28]
        prefix = f"lab-{user_id[:8]}-{safe_slug}"
        attacker_name = f"{prefix}-attacker"
        target_name = f"{prefix}-target"

        for container_name in [attacker_name, target_name]:
            try:
                existing = self.client.containers.get(container_name)
                if existing.status == "running":
                    raise ValueError(f"Container {container_name} is already running")
                existing.remove(force=True)
            except NotFound:
                pass

        mem_limit = f"{limits.memory}m"
        nano_cpus = int(limits.cpu * 1e9)

        target_container = self.client.containers.run(
            image=target_image,
            name=target_name,
            detach=True,
            remove=False,
            environment={
                "LAB_ROOM_SLUG": room_slug,
                "LAB_TARGET_PORT": str(target_port),
            },
            network=settings.docker_network,
            mem_limit=mem_limit,
            nano_cpus=nano_cpus,
            pids_limit=256,
            privileged=False,
            read_only=False,
            volumes={},
            labels={
                "lab.user_id": user_id,
                "lab.room_slug": room_slug,
                "lab.type": "web-target",
                "lab.role": "target",
                "lab.created": datetime.utcnow().isoformat(),
            }
        )

        target_url = f"http://{target_name}:{target_port}"
        env_vars = {
            "USER_ID": user_id,
            "LAB_ROOM_SLUG": room_slug,
            "WORKSPACE_TYPE": "lab",
            "TARGET_URL": target_url,
        }

        if github_token:
            env_vars["GITHUB_TOKEN"] = github_token

        attacker_port_key = f"{attacker_port}/tcp"
        attacker_container = self.client.containers.run(
            image=attacker_image,
            name=attacker_name,
            detach=True,
            remove=False,
            environment=env_vars,
            network=settings.docker_network,
            ports={attacker_port_key: None},
            mem_limit=mem_limit,
            nano_cpus=nano_cpus,
            pids_limit=256,
            privileged=False,
            read_only=False,
            volumes={},
            labels={
                "lab.user_id": user_id,
                "lab.room_slug": room_slug,
                "lab.type": "web-target",
                "lab.role": "attacker",
                "lab.created": datetime.utcnow().isoformat(),
            }
        )

        attacker_container.reload()
        
        if attacker_container.status == "exited":
            logs = attacker_container.logs().decode("utf-8")
            raise RuntimeError(f"Attacker container failed to start. Logs: {logs}")
            
        port_bindings = attacker_container.attrs.get("NetworkSettings", {}).get("Ports", {})
        if not port_bindings or attacker_port_key not in port_bindings or not port_bindings[attacker_port_key]:
            raise RuntimeError(f"Port {attacker_port_key} was not bound. Container status: {attacker_container.status}")
            
        access_port = int(port_bindings[attacker_port_key][0]["HostPort"])

        return {
            "attacker_container_id": attacker_container.id,
            "attacker_container_name": attacker_name,
            "target_container_id": target_container.id,
            "target_container_name": target_name,
            "access_port": access_port,
            "target_url": target_url,
        }

    def get_container_status(self, container_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a container.
        
        Returns:
            Dict with status info or None if not found
        """
        try:
            container = self.client.containers.get(container_id)
            return {
                "id": container.id,
                "name": container.name,
                "status": container.status,
                "running": container.status == "running",
            }
        except NotFound:
            return None
        except APIError as e:
            logger.error(f"Error getting container status: {e}")
            return None
    
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """
        Stop a container gracefully.
        
        Args:
            container_id: Docker container ID
            timeout: Seconds to wait before force kill
            
        Returns:
            True if stopped successfully
        """
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info(f"Stopped container {container_id}")
            return True
        except NotFound:
            logger.warning(f"Container {container_id} not found")
            return True  # Already gone
        except APIError as e:
            logger.error(f"Error stopping container: {e}")
            return False
    
    def remove_container(self, container_id: str, force: bool = True) -> bool:
        """
        Remove a container completely.
        
        Args:
            container_id: Docker container ID
            force: Force remove even if running
            
        Returns:
            True if removed successfully
        """
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=force)
            logger.info(f"Removed container {container_id}")
            return True
        except NotFound:
            return True  # Already gone
        except APIError as e:
            logger.error(f"Error removing container: {e}")
            return False
    
    def cleanup_expired_containers(self) -> int:
        """
        Clean up containers that have expired based on labels.
        Should be called periodically.
        
        Returns:
            Number of containers cleaned up
        """
        cleaned = 0
        
        try:
            containers = self.client.containers.list(
                filters={"label": "workspace.type=ephemeral"}
            )
            
            for container in containers:
                labels = container.labels
                created_str = labels.get("workspace.created")
                
                if created_str:
                    created = datetime.fromisoformat(created_str)
                    # Default max runtime
                    max_runtime = settings.default_max_runtime
                    
                    if datetime.utcnow() > created + timedelta(seconds=max_runtime):
                        logger.info(f"Cleaning up expired container: {container.name}")
                        container.stop(timeout=5)
                        container.remove(force=True)
                        cleaned += 1
        except APIError as e:
            logger.error(f"Error during cleanup: {e}")
        
        return cleaned


# Singleton instance
_container_manager: Optional[ContainerManager] = None


def get_container_manager() -> ContainerManager:
    """Get or create the container manager singleton."""
    global _container_manager
    if _container_manager is None:
        _container_manager = ContainerManager()
    return _container_manager
