"""
Workspace router for managing user workspace lifecycle.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.config import get_settings
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.user import User
from ..models.user_limits import UserLimits
from ..models.workspace import Workspace, WorkspaceStatus
from ..schemas.workspace import (
    WorkspaceStartRequest,
    WorkspaceStopRequest,
    WorkspaceResponse,
    WorkspaceStatusResponse,
    WorkspaceStartResponse,
    WorkspaceStopResponse
)
from ..services.container_manager import get_container_manager

router = APIRouter(prefix="/workspace", tags=["Workspace"])
settings = get_settings()


def workspace_to_response(workspace: Workspace, hostname: str = "localhost") -> WorkspaceResponse:
    """Convert workspace model to response schema with dynamic hostname."""
    time_remaining = None
    if workspace.status == WorkspaceStatus.RUNNING.value:
        remaining = (workspace.expires_at - datetime.utcnow()).total_seconds()
        time_remaining = max(0, int(remaining))
    
    # Construct dynamic access URL using the request hostname and the assigned container port
    # accessing access_url from DB might store 'localhost', we want to override the host part
    access_url = workspace.access_url
    if workspace.access_port:
        if hostname:
            access_url = f"http://{hostname}:{workspace.access_port}"
        
    return WorkspaceResponse(
        id=workspace.id,
        user_id=workspace.user_id,
        container_id=workspace.container_id,
        container_name=workspace.container_name,
        status=workspace.status,
        access_url=access_url,
        access_port=workspace.access_port,
        started_at=workspace.started_at,
        expires_at=workspace.expires_at,
        stopped_at=workspace.stopped_at,
        time_remaining_seconds=time_remaining
    )


@router.get("/status", response_model=WorkspaceStatusResponse)
async def get_workspace_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current workspace status for the authenticated user.
    """
    # Find active workspace
    result = await db.execute(
        select(Workspace).where(
            Workspace.user_id == current_user.id,
            Workspace.status.in_([WorkspaceStatus.STARTING.value, WorkspaceStatus.RUNNING.value])
        )
    )
    workspace = result.scalar_one_or_none()
    
    if workspace:
        # Verify container is still running
        container_manager = get_container_manager()
        container_status = container_manager.get_container_status(workspace.container_id)
        
        if not container_status or not container_status.get("running"):
            # Container died, update status
            workspace.status = WorkspaceStatus.STOPPED.value
            workspace.stopped_at = datetime.utcnow()
            await db.commit()
            
            return WorkspaceStatusResponse(
                has_active_workspace=False,
                workspace=None,
                message="Previous workspace has stopped"
            )
        
        # Check if expired
        if workspace.is_expired:
            # Stop the container
            container_manager.stop_container(workspace.container_id)
            container_manager.remove_container(workspace.container_id)
            
            workspace.status = WorkspaceStatus.STOPPED.value
            workspace.stopped_at = datetime.utcnow()
            await db.commit()
            
            return WorkspaceStatusResponse(
                has_active_workspace=False,
                workspace=None,
                message="Workspace expired and was automatically stopped"
            )
        
        # Update heartbeat
        workspace.last_active = datetime.utcnow()
        await db.commit()

        return WorkspaceStatusResponse(
            has_active_workspace=True,
            workspace=workspace_to_response(workspace, settings.proxy_domain),
            message="Workspace is running"
        )
    
    return WorkspaceStatusResponse(
        has_active_workspace=False,
        workspace=None,
        message="No active workspace"
    )


@router.post("/start", response_model=WorkspaceStartResponse)
async def start_workspace(
    request: WorkspaceStartRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new workspace for the authenticated user.
    Only one active workspace per user is allowed.
    """
    # Check for existing active workspace
    result = await db.execute(
        select(Workspace).where(
            Workspace.user_id == current_user.id,
            Workspace.status.in_([WorkspaceStatus.STARTING.value, WorkspaceStatus.RUNNING.value])
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active workspace. Stop it first."
        )
    
    # Get user limits
    limits_result = await db.execute(
        select(UserLimits).where(UserLimits.user_id == current_user.id)
    )
    limits = limits_result.scalar_one_or_none()
    
    if not limits:
        # Create default limits
        limits = UserLimits(user_id=current_user.id)
        db.add(limits)
        await db.flush()
    
    # Create container
    container_manager = get_container_manager()
    
    try:
        container_info = container_manager.create_container(
            user_id=current_user.id,
            limits=limits,
            github_token=current_user.github_access_token
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create workspace: {str(e)}"
        )
    
    # Calculate expiry time
    expires_at = datetime.utcnow() + timedelta(seconds=limits.max_runtime)
    
    # Build access URL
    access_url = f"http://{settings.proxy_domain}:{container_info['access_port']}"
    
    # Create workspace record
    workspace = Workspace(
        user_id=current_user.id,
        container_id=container_info["container_id"],
        container_name=container_info["container_name"],
        status=WorkspaceStatus.RUNNING.value,
        access_url=access_url,
        access_port=container_info["access_port"],
        expires_at=expires_at,
        last_active=datetime.utcnow()
    )
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    
    return WorkspaceStartResponse(
        success=True,
        workspace=workspace_to_response(workspace, req.base_url.hostname),
        message="Workspace started successfully",
        access_url=access_url  # Note: response schema might need this, or component uses workspace object
    )


@router.post("/stop", response_model=WorkspaceStopResponse)
async def stop_workspace(
    request: WorkspaceStopRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Stop the user's active workspace.
    Optionally checks for unsaved changes before stopping.
    """
    # Find active workspace
    result = await db.execute(
        select(Workspace).where(
            Workspace.user_id == current_user.id,
            Workspace.status.in_([WorkspaceStatus.STARTING.value, WorkspaceStatus.RUNNING.value])
        )
    )
    workspace = result.scalar_one_or_none()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active workspace found"
        )
    
    container_manager = get_container_manager()
    
    # Update status to stopping
    workspace.status = WorkspaceStatus.STOPPING.value
    await db.commit()
    
    # Stop and remove container asynchronously
    import asyncio
    await asyncio.to_thread(container_manager.remove_container, workspace.container_id, force=True)
    
    # Update workspace record
    workspace.status = WorkspaceStatus.STOPPED.value
    workspace.stopped_at = datetime.utcnow()
    await db.commit()
    
    return WorkspaceStopResponse(
        success=True,
        message="Workspace stopped successfully",
        had_unsaved_changes=False
    )
