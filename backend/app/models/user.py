"""
User model for storing local and optional GitHub identity data.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


class User(Base):
    """User model representing authenticated users."""
    
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    github_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
        index=True
    )
    github_username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    github_access_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    limits: Mapped[Optional["UserLimits"]] = relationship(
        "UserLimits",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    workspaces: Mapped[list["Workspace"]] = relationship(
        "Workspace",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    lab_sessions: Mapped[list["LabSession"]] = relationship(
        "LabSession",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    challenge_submissions: Mapped[list["ChallengeSubmission"]] = relationship(
        "ChallengeSubmission",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        display_name = self.username or self.github_username or self.email or self.id
        return f"<User {display_name} ({self.id})>"
