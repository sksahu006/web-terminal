"""
Container Manager Service for Docker container lifecycle management.
Handles creation, monitoring, and cleanup of workspace containers.
"""

import asyncio
import logging
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
            ports={"7681/tcp": None},  # Request random port
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
        port_bindings = container.attrs["NetworkSettings"]["Ports"]
        # Format: [{'HostIp': '0.0.0.0', 'HostPort': '32768'}]
        access_port = int(port_bindings["7681/tcp"][0]["HostPort"])
        
        logger.info(f"Created container {container_name} for user {user_id} on port {access_port}")
        
        return {
            "container_id": container.id,
            "container_name": container_name,
            "access_port": access_port,
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
    
    def check_git_status(self, container_id: str) -> Dict[str, Any]:
        """
        Check if container has uncommitted git changes.
        
        Returns:
            Dict with has_changes and optionally the status output
        """
        try:
            container = self.client.containers.get(container_id)
            
            # Run git status in the container
            exit_code, output = container.exec_run(
                ["sh", "-c", "cd /workspace && git status --porcelain 2>/dev/null || echo ''"],
                demux=True
            )
            
            stdout = output[0].decode() if output[0] else ""
            
            return {
                "has_changes": len(stdout.strip()) > 0,
                "status_output": stdout.strip()
            }
        except NotFound:
            return {"has_changes": False, "status_output": ""}
        except APIError as e:
            logger.error(f"Error checking git status: {e}")
            return {"has_changes": False, "status_output": ""}
    
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
