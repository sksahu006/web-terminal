"""
Workspace model for tracking active container sessions.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


class WorkspaceStatus(str, Enum):
    """Possible states of a workspace container."""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class Workspace(Base):
    """Active workspace session tracking."""
    
    __tablename__ = "workspaces"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    container_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True
    )
    container_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=WorkspaceStatus.STARTING.value,
        nullable=False
    )
    access_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    access_port: Mapped[Optional[int]] = mapped_column(
        nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )
    stopped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    # Relationship
    user: Mapped["User"] = relationship(
        "User",
        back_populates="workspaces"
    )
    
    @property
    def is_active(self) -> bool:
        """Check if workspace is currently active."""
        return self.status in [WorkspaceStatus.STARTING.value, WorkspaceStatus.RUNNING.value]
    
    @property
    def is_expired(self) -> bool:
        """Check if workspace has exceeded its runtime limit."""
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self) -> str:
        return f"<Workspace {self.id} user={self.user_id} status={self.status}>"
