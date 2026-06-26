"""
Lab catalog and session routes.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.config import get_settings
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.lab import Challenge, ChallengeSubmission, LabAccessMode, LabSession, LabSessionStatus, Room
from ..models.user import User
from ..models.user_limits import UserLimits
from ..schemas.lab import (
    ActiveLabSessionResponse,
    ChallengeSubmitRequest,
    ChallengeSubmitResponse,
    LabSessionResponse,
    LabSessionStopResponse,
    RoomDetailResponse,
    RoomProgressResponse,
    RoomListResponse,
)
from ..services.container_manager import get_container_manager


router = APIRouter(prefix="/labs", tags=["Labs"])


def get_lab_container_manager():
    """Dependency wrapper so tests can replace Docker orchestration."""
    return get_container_manager()


@router.get("/rooms", response_model=list[RoomListResponse])
async def list_rooms(db: AsyncSession = Depends(get_db)):
    """List published rooms available to learners."""
    result = await db.execute(
        select(Room)
        .options(selectinload(Room.template), selectinload(Room.challenges))
        .where(Room.is_published.is_(True))
        .order_by(Room.title)
    )
    rooms = result.scalars().all()

    return [
        RoomListResponse(
            id=room.id,
            slug=room.slug,
            title=room.title,
            difficulty=room.difficulty,
            description=room.description,
            access_mode=room.template.access_mode,
            challenge_count=len(room.challenges),
        )
        for room in rooms
    ]


@router.get("/rooms/{slug}", response_model=RoomDetailResponse)
async def get_room(slug: str, db: AsyncSession = Depends(get_db)):
    """Get published room details by slug."""
    result = await db.execute(
        select(Room)
        .options(selectinload(Room.template), selectinload(Room.challenges))
        .where(Room.slug == slug, Room.is_published.is_(True))
    )
    room = result.scalar_one_or_none()

    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found",
        )

    return room




@router.post("/challenges/{challenge_id}/submit", response_model=ChallengeSubmitResponse)
async def submit_challenge_flag(
    challenge_id: str,
    submission: ChallengeSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a flag for one challenge and award points once."""
    result = await db.execute(select(Challenge).where(Challenge.id == challenge_id))
    challenge = result.scalar_one_or_none()

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found",
        )

    solved_result = await db.execute(
        select(ChallengeSubmission).where(
            ChallengeSubmission.user_id == current_user.id,
            ChallengeSubmission.challenge_id == challenge.id,
            ChallengeSubmission.is_correct.is_(True),
        )
    )
    solved = solved_result.scalar_one_or_none()

    if solved:
        return ChallengeSubmitResponse(
            challenge_id=challenge.id,
            correct=True,
            already_solved=True,
            points_awarded=0,
            message="Challenge already solved",
        )

    submitted_flag = submission.flag.strip()
    if submitted_flag != challenge.flag:
        return ChallengeSubmitResponse(
            challenge_id=challenge.id,
            correct=False,
            already_solved=False,
            points_awarded=0,
            message="Incorrect flag",
        )

    db.add(
        ChallengeSubmission(
            user_id=current_user.id,
            challenge_id=challenge.id,
            submitted_flag=submitted_flag,
            is_correct=True,
            points_awarded=challenge.points,
        )
    )
    await db.commit()

    return ChallengeSubmitResponse(
        challenge_id=challenge.id,
        correct=True,
        already_solved=False,
        points_awarded=challenge.points,
        message="Correct flag submitted",
    )


@router.get("/rooms/{slug}/progress", response_model=RoomProgressResponse)
async def get_room_progress(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return solved challenge and point progress for a room."""
    result = await db.execute(
        select(Room)
        .options(selectinload(Room.challenges))
        .where(Room.slug == slug, Room.is_published.is_(True))
    )
    room = result.scalar_one_or_none()

    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found",
        )

    submission_result = await db.execute(
        select(ChallengeSubmission).where(
            ChallengeSubmission.user_id == current_user.id,
            ChallengeSubmission.is_correct.is_(True),
        )
    )
    solved_by_challenge_id = {
        submission.challenge_id: submission for submission in submission_result.scalars().all()
    }

    challenges = []
    earned_points = 0
    solved_challenges = 0

    for challenge in room.challenges:
        solved = challenge.id in solved_by_challenge_id
        if solved:
            solved_challenges += 1
            earned_points += solved_by_challenge_id[challenge.id].points_awarded
        challenges.append(
            {
                "challenge_id": challenge.id,
                "title": challenge.title,
                "points": challenge.points,
                "solved": solved,
            }
        )

    return RoomProgressResponse(
        room_id=room.id,
        slug=room.slug,
        total_challenges=len(room.challenges),
        solved_challenges=solved_challenges,
        total_points=sum(challenge.points for challenge in room.challenges),
        earned_points=earned_points,
        challenges=challenges,
    )
@router.get("/sessions/active", response_model=ActiveLabSessionResponse)
async def get_active_lab_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    container_manager = Depends(get_lab_container_manager),
):
    """Return the authenticated user's active lab session, if one exists."""
    result = await db.execute(
        select(LabSession).where(
            LabSession.user_id == current_user.id,
            LabSession.status.in_(
                [LabSessionStatus.STARTING.value, LabSessionStatus.RUNNING.value]
            ),
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        return ActiveLabSessionResponse(
            has_active_session=False,
            session=None,
            message="No active lab session",
        )

    if session.attacker_container_id:
        container_status = container_manager.get_container_status(session.attacker_container_id)
        if not container_status or not container_status.get("running"):
            session.status = LabSessionStatus.STOPPED.value
            session.stopped_at = datetime.utcnow()
            await db.commit()
            return ActiveLabSessionResponse(
                has_active_session=False,
                session=None,
                message="Previous lab session has stopped",
            )

    return ActiveLabSessionResponse(
        has_active_session=True,
        session=session,
        message="Lab session is running",
    )


@router.post("/sessions/{session_id}/stop", response_model=LabSessionStopResponse)
async def stop_lab_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    container_manager = Depends(get_lab_container_manager),
):
    """Stop and remove a running lab container for the authenticated user."""
    result = await db.execute(
        select(LabSession).where(
            LabSession.id == session_id,
            LabSession.user_id == current_user.id,
            LabSession.status.in_(
                [LabSessionStatus.STARTING.value, LabSessionStatus.RUNNING.value]
            ),
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active lab session not found",
        )

    session.status = LabSessionStatus.STOPPING.value
    await db.commit()

    container_ids = []
    if session.attacker_container_id:
        container_ids.append(session.attacker_container_id)
    if session.target_container_ids:
        container_ids.extend(
            container_id.strip()
            for container_id in session.target_container_ids.split(",")
            if container_id.strip()
        )

    for container_id in container_ids:
        container_manager.stop_container(container_id)
        container_manager.remove_container(container_id)

    session.status = LabSessionStatus.STOPPED.value
    session.stopped_at = datetime.utcnow()
    await db.commit()
    await db.refresh(session)

    return LabSessionStopResponse(
        success=True,
        message="Lab session stopped successfully",
        session=session,
    )
@router.post(
    "/rooms/{slug}/start",
    response_model=LabSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_room(
    slug: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    container_manager = Depends(get_lab_container_manager),
):
    """Start a terminal lab room and persist its session metadata."""
    result = await db.execute(
        select(Room)
        .options(selectinload(Room.template))
        .where(Room.slug == slug, Room.is_published.is_(True))
    )
    room = result.scalar_one_or_none()

    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found",
        )



    active_result = await db.execute(
        select(LabSession).where(
            LabSession.user_id == current_user.id,
            LabSession.status.in_(
                [LabSessionStatus.STARTING.value, LabSessionStatus.RUNNING.value]
            ),
        )
    )
    if active_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active lab session. Stop it first.",
        )

    limits_result = await db.execute(
        select(UserLimits).where(UserLimits.user_id == current_user.id)
    )
    limits = limits_result.scalar_one_or_none()

    if not limits:
        limits = UserLimits(user_id=current_user.id)
        db.add(limits)
        await db.flush()

    exposed_port = room.template.default_port or 7681
    _settings = get_settings()
    # Use X-Forwarded-Host (set by Nginx/proxy) → PROXY_DOMAIN env → localhost
    hostname = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("x-real-ip")
        or _settings.proxy_domain
        or "localhost"
    )

    try:
        if room.template.access_mode == LabAccessMode.TERMINAL.value:
            container_info = container_manager.create_lab_container(
                user_id=current_user.id,
                room_slug=room.slug,
                image=room.template.image,
                limits=limits,
                exposed_port=exposed_port,
                github_token=None,
            )
            attacker_container_id = container_info["container_id"]
            attacker_container_name = container_info["container_name"]
            target_container_ids = None
            access_port = container_info["access_port"]
        elif room.template.access_mode == LabAccessMode.WEB_TARGET.value:
            image_parts = [part.strip() for part in room.template.image.split("|", 1)]
            if len(image_parts) != 2:
                raise ValueError("Web target templates must use 'attacker_image|target_image'")
            container_info = container_manager.create_web_target_lab(
                user_id=current_user.id,
                room_slug=room.slug,
                attacker_image=image_parts[0],
                target_image=image_parts[1],
                limits=limits,
                attacker_port=exposed_port,
                target_port=8000,
                github_token=None,
            )
            attacker_container_id = container_info["attacker_container_id"]
            attacker_container_name = container_info["attacker_container_name"]
            target_container_ids = container_info["target_container_id"]
            access_port = container_info["access_port"]
        else:
            raise ValueError("Only terminal and web-target labs are supported in this phase.")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create lab container: {str(exc)}",
        ) from exc

    access_url = f"http://{hostname}:{access_port}"

    session = LabSession(
        user_id=current_user.id,
        room_id=room.id,
        status=LabSessionStatus.RUNNING.value,
        access_mode=room.template.access_mode,
        attacker_container_id=attacker_container_id,
        target_container_ids=target_container_ids,
        network_name=attacker_container_name,
        access_url=access_url,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return session





