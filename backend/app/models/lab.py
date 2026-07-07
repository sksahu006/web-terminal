"""
Lab catalog and session models for challenge rooms.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .user import User

from ..core.database import Base


class LabAccessMode(str, Enum):
    """Ways a learner can access a lab environment."""

    TERMINAL = "terminal"
    WEB_TARGET = "web_target"
    DESKTOP = "desktop"
    MULTI_MACHINE = "multi_machine"


class LabSessionStatus(str, Enum):
    """Possible states of a lab session."""

    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class LabTemplate(Base):
    """Reusable runtime definition for one or more rooms."""

    __tablename__ = "lab_templates"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    access_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    image: Mapped[str] = mapped_column(String(255), nullable=False)
    startup_command: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    default_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Internal port the target container listens on (WEB_TARGET labs only).
    target_port: Mapped[int] = mapped_column(Integer, default=8000, nullable=False)
    # Minimal per-container resource footprint, tuned independently for the
    # ttyd attacker shell (light) vs. the vulnerable target app (light-to-moderate).
    attacker_cpu: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    attacker_memory: Mapped[int] = mapped_column(Integer, default=256, nullable=False)
    target_cpu: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    target_memory: Mapped[int] = mapped_column(Integer, default=256, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    rooms: Mapped[list["Room"]] = relationship(
        "Room",
        back_populates="template",
    )


class Room(Base):
    """A published challenge room learners can start."""

    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("lab_templates.id"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    template: Mapped["LabTemplate"] = relationship(
        "LabTemplate",
        back_populates="rooms",
    )
    challenges: Mapped[list["Challenge"]] = relationship(
        "Challenge",
        back_populates="room",
        cascade="all, delete-orphan",
        order_by="Challenge.sort_order",
    )
    sessions: Mapped[list["LabSession"]] = relationship(
        "LabSession",
        back_populates="room",
        cascade="all, delete-orphan",
    )


class Challenge(Base):
    """One flag-bearing task inside a room."""

    __tablename__ = "challenges"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    flag: Mapped[str] = mapped_column(String(255), nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    room: Mapped["Room"] = relationship(
        "Room",
        back_populates="challenges",
    )
    submissions: Mapped[list["ChallengeSubmission"]] = relationship(
        "ChallengeSubmission",
        back_populates="challenge",
        cascade="all, delete-orphan",
    )


class LabSession(Base):
    """A learner's active or historical attempt at a room."""

    __tablename__ = "lab_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=LabSessionStatus.STARTING.value,
        nullable=False,
    )
    access_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    network_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    # Dedicated Docker bridge network isolating this session's attacker+target
    # pair from every other session (WEB_TARGET labs only). None for TERMINAL labs,
    # which share the flat workspace network since there's no private target to protect.
    docker_network: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    attacker_container_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    target_container_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    last_active: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(
        "User",
        back_populates="lab_sessions",
    )
    room: Mapped["Room"] = relationship(
        "Room",
        back_populates="sessions",
    )

class ChallengeSubmission(Base):
    """Tracks a user's solved challenge and awarded points."""

    __tablename__ = "challenge_submissions"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_user_challenge_submission"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    challenge_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    submitted_flag: Mapped[str] = mapped_column(String(255), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="challenge_submissions")
    challenge: Mapped["Challenge"] = relationship("Challenge", back_populates="submissions")

