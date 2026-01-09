"""
Admin router for managing users and their resource limits.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from ..core.database import get_db
from ..core.security import get_current_admin_user
from ..models.user import User
from ..models.user_limits import UserLimits
from ..models.workspace import Workspace, WorkspaceStatus
from ..schemas.admin import (
    AdminUserListResponse,
    AdminUserDetailResponse,
    AdminUpdateLimitsRequest,
    AdminUpdateLimitsResponse,
    AdminStatsResponse
)
from ..schemas.user import UserResponse, UserLimitsResponse

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user)
):
    """
    Get platform statistics for admin dashboard.
    """
    # Total users
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar() or 0
    
    # Active workspaces
    active_workspaces_result = await db.execute(
        select(func.count(Workspace.id)).where(
            Workspace.status.in_([WorkspaceStatus.STARTING.value, WorkspaceStatus.RUNNING.value])
        )
    )
    active_workspaces = active_workspaces_result.scalar() or 0
    
    # Workspaces created today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_workspaces_result = await db.execute(
        select(func.count(Workspace.id)).where(Workspace.started_at >= today_start)
    )
    total_workspaces_today = today_workspaces_result.scalar() or 0
    
    return AdminStatsResponse(
        total_users=total_users,
        active_workspaces=active_workspaces,
        total_workspaces_today=total_workspaces_today
    )


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user)
):
    """
    List all users in the system.
    """
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    return AdminUserListResponse(
        users=[UserResponse.model_validate(user) for user in users],
        total_count=len(users)
    )


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
async def get_user_detail(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user)
):
    """
    Get detailed information about a specific user.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get user limits
    limits_result = await db.execute(
        select(UserLimits).where(UserLimits.user_id == user_id)
    )
    limits = limits_result.scalar_one_or_none()
    
    # Check for active workspace
    active_workspace_result = await db.execute(
        select(Workspace).where(
            Workspace.user_id == user_id,
            Workspace.status.in_([WorkspaceStatus.STARTING.value, WorkspaceStatus.RUNNING.value])
        )
    )
    has_active = active_workspace_result.scalar_one_or_none() is not None
    
    # Total workspaces count
    total_workspaces_result = await db.execute(
        select(func.count(Workspace.id)).where(Workspace.user_id == user_id)
    )
    total_workspaces = total_workspaces_result.scalar() or 0
    
    return AdminUserDetailResponse(
        user=UserResponse.model_validate(user),
        limits=UserLimitsResponse.model_validate(limits) if limits else None,
        has_active_workspace=has_active,
        total_workspaces_created=total_workspaces
    )


@router.get("/users/{user_id}/limits", response_model=UserLimitsResponse)
async def get_user_limits(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user)
):
    """
    Get resource limits for a specific user.
    """
    result = await db.execute(
        select(UserLimits).where(UserLimits.user_id == user_id)
    )
    limits = result.scalar_one_or_none()
    
    if not limits:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User limits not found"
        )
    
    return limits


@router.put("/users/{user_id}/limits", response_model=AdminUpdateLimitsResponse)
async def update_user_limits(
    user_id: str,
    request: AdminUpdateLimitsRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user)
):
    """
    Update resource limits for a specific user.
    Changes apply to new workspace sessions only.
    """
    # Check user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get or create limits
    limits_result = await db.execute(
        select(UserLimits).where(UserLimits.user_id == user_id)
    )
    limits = limits_result.scalar_one_or_none()
    
    if not limits:
        limits = UserLimits(user_id=user_id)
        db.add(limits)
    
    # Update only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(limits, field, value)
    
    await db.commit()
    await db.refresh(limits)
    
    return AdminUpdateLimitsResponse(
        success=True,
        message="User limits updated successfully",
        limits=UserLimitsResponse.model_validate(limits)
    )
