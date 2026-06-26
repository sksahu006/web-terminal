"""
Pydantic schemas for User-related API requests and responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    """Base user schema with common fields."""

    username: Optional[str] = None
    email: Optional[str] = None
    github_username: Optional[str] = None
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a GitHub user (internal use)."""

    github_id: Optional[str] = None
    github_access_token: Optional[str] = None


class UserRegisterRequest(BaseModel):
    """Email/password registration payload."""

    email: str
    password: str = Field(min_length=6, max_length=128)
    username: str = Field(min_length=2, max_length=50)


class UserLoginRequest(BaseModel):
    """Email/password login payload."""

    email: str
    password: str = Field(min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    """Refresh token payload."""

    refresh_token: str


class UserResponse(UserBase):
    """Schema for user response in API."""

    id: str
    github_id: Optional[str] = None
    is_admin: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuthTokenResponse(BaseModel):
    """JWT auth response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenRefreshResponse(BaseModel):
    """Refresh response containing a new access token."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


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


UserWithLimits.model_rebuild()

