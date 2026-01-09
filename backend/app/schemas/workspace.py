"""
Pydantic schemas for Workspace-related API requests and responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from ..models.workspace import WorkspaceStatus


class WorkspaceStartRequest(BaseModel):
    """Request to start a new workspace."""
    pass  # No parameters needed, uses current user context


class WorkspaceStopRequest(BaseModel):
    """Request to stop a workspace."""
    force: bool = Field(default=False, description="Force stop without cleanup warning")


class WorkspaceResponse(BaseModel):
    """Response containing workspace information."""
    id: str
    user_id: str
    container_id: str
    container_name: str
    status: str
    access_url: Optional[str] = None
    access_port: Optional[int] = None
    started_at: datetime
    expires_at: datetime
    stopped_at: Optional[datetime] = None
    time_remaining_seconds: Optional[int] = None
    
    class Config:
        from_attributes = True


class WorkspaceStatusResponse(BaseModel):
    """Response for workspace status check."""
    has_active_workspace: bool
    workspace: Optional[WorkspaceResponse] = None
    message: str


class WorkspaceStartResponse(BaseModel):
    """Response after starting a workspace."""
    success: bool
    workspace: Optional[WorkspaceResponse] = None
    message: str
    access_url: Optional[str] = None


class WorkspaceStopResponse(BaseModel):
    """Response after stopping a workspace."""
    success: bool
    message: str
    had_unsaved_changes: bool = False
