"""
UserLimits model for storing per-user resource limits.
Admin-configurable limits applied at container creation.
"""

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from ..core.config import get_settings

settings = get_settings()


class UserLimits(Base):
    """Resource limits for a user's workspace container."""
    
    __tablename__ = "user_limits"
    
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )
    cpu: Mapped[float] = mapped_column(
        Float,
        default=settings.default_cpu_limit,
        nullable=False
    )
    memory: Mapped[int] = mapped_column(
        Integer,
        default=settings.default_memory_limit,
        nullable=False,
        comment="Memory limit in MB"
    )
    disk: Mapped[int] = mapped_column(
        Integer,
        default=settings.default_disk_limit,
        nullable=False,
        comment="Disk limit in GB"
    )
    max_runtime: Mapped[int] = mapped_column(
        Integer,
        default=settings.default_max_runtime,
        nullable=False,
        comment="Maximum runtime in seconds"
    )
    
    # Relationship
    user: Mapped["User"] = relationship(
        "User",
        back_populates="limits"
    )
    
    def __repr__(self) -> str:
        return f"<UserLimits user={self.user_id} cpu={self.cpu} mem={self.memory}MB>"
