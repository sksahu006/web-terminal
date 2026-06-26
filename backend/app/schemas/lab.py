"""
Pydantic schemas for lab catalog and session APIs.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LabTemplateResponse(BaseModel):
    """Runtime template details shown on room detail."""

    id: str
    name: str
    access_mode: str
    image: str
    startup_command: Optional[str] = None
    default_port: Optional[int] = None

    class Config:
        from_attributes = True


class ChallengeResponse(BaseModel):
    """Public challenge data without the flag answer."""

    id: str
    title: str
    prompt: str
    points: int
    sort_order: int

    class Config:
        from_attributes = True


class RoomListResponse(BaseModel):
    """Compact room card data for catalogs."""

    id: str
    slug: str
    title: str
    difficulty: str
    description: str
    access_mode: str
    challenge_count: int


class RoomDetailResponse(BaseModel):
    """Full room detail with template and challenge prompts."""

    id: str
    slug: str
    title: str
    difficulty: str
    description: str
    template: LabTemplateResponse
    challenges: list[ChallengeResponse]

    class Config:
        from_attributes = True


class LabSessionResponse(BaseModel):
    """Lab session metadata returned after starting a room."""

    id: str
    user_id: str
    room_id: str
    status: str
    access_mode: str
    attacker_container_id: Optional[str] = None
    target_container_ids: Optional[str] = None
    network_name: Optional[str] = None
    access_url: Optional[str] = None
    started_at: datetime
    stopped_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ActiveLabSessionResponse(BaseModel):
    """Current active lab session status for the authenticated user."""

    has_active_session: bool
    session: Optional[LabSessionResponse] = None
    message: str


class LabSessionStopResponse(BaseModel):
    """Response returned after stopping a lab session."""

    success: bool
    message: str
    session: Optional[LabSessionResponse] = None

class ChallengeSubmitRequest(BaseModel):
    """Flag submission payload."""

    flag: str


class ChallengeSubmitResponse(BaseModel):
    """Result of a flag submission."""

    challenge_id: str
    correct: bool
    already_solved: bool
    points_awarded: int
    message: str


class ChallengeProgressResponse(BaseModel):
    """Progress for one challenge in a room."""

    challenge_id: str
    title: str
    points: int
    solved: bool


class RoomProgressResponse(BaseModel):
    """Progress summary for one room."""

    room_id: str
    slug: str
    total_challenges: int
    solved_challenges: int
    total_points: int
    earned_points: int
    challenges: list[ChallengeProgressResponse]


