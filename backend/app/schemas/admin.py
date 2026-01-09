"""
Pydantic schemas for Admin API operations.
"""

from typing import List, Optional

from pydantic import BaseModel

from .user import UserResponse, UserLimitsResponse, UserLimitsUpdate


class AdminUserListResponse(BaseModel):
    """Response containing list of all users for admin."""
    users: List[UserResponse]
    total_count: int


class AdminUserDetailResponse(BaseModel):
    """Detailed user information for admin."""
    user: UserResponse
    limits: Optional[UserLimitsResponse] = None
    has_active_workspace: bool = False
    total_workspaces_created: int = 0


class AdminUpdateLimitsRequest(UserLimitsUpdate):
    """Request to update a user's resource limits."""
    pass


class AdminUpdateLimitsResponse(BaseModel):
    """Response after updating user limits."""
    success: bool
    message: str
    limits: Optional[UserLimitsResponse] = None


class AdminStatsResponse(BaseModel):
    """Platform statistics for admin dashboard."""
    total_users: int
    active_workspaces: int
    total_workspaces_today: int
