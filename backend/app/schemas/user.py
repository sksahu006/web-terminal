"""
Pydantic schemas for User-related API requests and responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    """Base user schema with common fields."""
    github_username: str
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user (internal use)."""
    github_id: str
    github_access_token: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response in API."""
    id: str
    github_id: str
    is_admin: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserWithLimits(UserResponse):
    """User response including resource limits."""
    limits: Optional["UserLimitsResponse"] = None


class UserLimitsBase(BaseModel):
    """Base schema for user resource limits."""
    cpu: float = Field(default=1.0, ge=0.1, le=16.0, description="CPU cores")
    memory: int = Field(default=1024, ge=256, le=32768, description="Memory in MB")
    disk: int = Field(default=5, ge=1, le=100, description="Disk in GB")
    max_runtime: int = Field(default=3600, ge=300, le=86400, description="Max runtime in seconds")


class UserLimitsCreate(UserLimitsBase):
    """Schema for creating user limits."""
    pass


class UserLimitsUpdate(BaseModel):
    """Schema for updating user limits (all fields optional)."""
    cpu: Optional[float] = Field(None, ge=0.1, le=16.0)
    memory: Optional[int] = Field(None, ge=256, le=32768)
    disk: Optional[int] = Field(None, ge=1, le=100)
    max_runtime: Optional[int] = Field(None, ge=300, le=86400)


class UserLimitsResponse(UserLimitsBase):
    """Schema for user limits response."""
    user_id: str
    
    class Config:
        from_attributes = True


# Update forward references
UserWithLimits.model_rebuild()
