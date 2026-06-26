# Lab Platform Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the current workspace prototype into the first slice of a TryHackMe-style lab platform using SQLite-backed room, challenge, lab template, and lab session data.

**Architecture:** Keep the existing FastAPI, async SQLAlchemy, SQLite, Docker, and ttyd foundation. Phase 1 is catalog and session metadata only: define lab domain models and public/authenticated APIs without changing container orchestration yet.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2 async ORM, SQLite through `aiosqlite`, pytest/httpx added for backend tests.

---

## File Structure

- Create `backend/app/models/lab.py`: SQLAlchemy models and enum values for rooms, challenges, lab templates, and lab sessions.
- Create `backend/app/schemas/lab.py`: Pydantic response/request schemas for lab catalog and session APIs.
- Create `backend/app/routers/labs.py`: FastAPI routes for listing rooms, viewing room detail, and creating session metadata.
- Modify `backend/app/models/user.py`: add `lab_sessions` relationship.
- Modify `backend/app/models/__init__.py`: import lab models so table creation registers them.
- Modify `backend/app/main.py`: include the new labs router.
- Modify `backend/requirements.txt`: add test dependencies if missing.
- Create `backend/tests/conftest.py`: isolated async SQLite test database and FastAPI test client setup.
- Create `backend/tests/test_labs.py`: API tests for room listing, detail, and session creation.

---

### Task 1: Add Lab Domain Models

**Files:**
- Create: `backend/app/models/lab.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_labs.py`

- [ ] **Step 1: Write failing model/API tests**

Create `backend/tests/conftest.py` with an isolated SQLite database and auth override:

```python
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import get_current_user
from app.main import app
from app.models.user import User


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, future=True)
    TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def current_user(db_session):
    user = User(
        github_id="12345",
        github_username="phase1-user",
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def client(db_session, current_user):
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()
```

Create `backend/tests/test_labs.py` with tests for expected Phase 1 behavior:

```python
import pytest

from app.models.lab import Challenge, LabAccessMode, LabTemplate, Room


pytestmark = pytest.mark.asyncio


async def test_list_rooms_returns_published_rooms(client, db_session):
    template = LabTemplate(
        name="Terminal Basics",
        access_mode=LabAccessMode.TERMINAL.value,
        image="workspace-dev:latest",
    )
    room = Room(
        slug="linux-basics",
        title="Linux Basics",
        difficulty="easy",
        description="Learn basic Linux commands.",
        is_published=True,
        template=template,
    )
    db_session.add(room)
    await db_session.commit()

    response = await client.get("/labs/rooms")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": room.id,
            "slug": "linux-basics",
            "title": "Linux Basics",
            "difficulty": "easy",
            "description": "Learn basic Linux commands.",
            "access_mode": "terminal",
            "challenge_count": 0,
        }
    ]


async def test_get_room_detail_includes_challenges(client, db_session):
    template = LabTemplate(
        name="Web App Basics",
        access_mode=LabAccessMode.WEB_TARGET.value,
        image="vulnerable-fastapi:latest",
    )
    room = Room(
        slug="web-basics",
        title="Web Basics",
        difficulty="easy",
        description="Attack a tiny vulnerable web app.",
        is_published=True,
        template=template,
    )
    room.challenges.append(
        Challenge(
            title="Find the flag",
            prompt="Read the homepage source.",
            flag="flag{phase_one}",
            points=10,
            sort_order=1,
        )
    )
    db_session.add(room)
    await db_session.commit()

    response = await client.get("/labs/rooms/web-basics")

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "web-basics"
    assert body["template"]["access_mode"] == "web_target"
    assert body["challenges"][0]["title"] == "Find the flag"
    assert "flag" not in body["challenges"][0]


async def test_start_room_creates_lab_session_metadata(client, db_session, current_user):
    template = LabTemplate(
        name="Terminal Basics",
        access_mode=LabAccessMode.TERMINAL.value,
        image="workspace-dev:latest",
    )
    room = Room(
        slug="linux-basics",
        title="Linux Basics",
        difficulty="easy",
        description="Learn basic Linux commands.",
        is_published=True,
        template=template,
    )
    db_session.add(room)
    await db_session.commit()

    response = await client.post("/labs/rooms/linux-basics/start")

    assert response.status_code == 201
    body = response.json()
    assert body["room_id"] == room.id
    assert body["user_id"] == current_user.id
    assert body["status"] == "starting"
    assert body["access_mode"] == "terminal"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest tests/test_labs.py -v
```

Expected: tests fail because `app.models.lab` and `/labs/*` routes do not exist yet.

- [ ] **Step 3: Add lab models**

Create `backend/app/models/lab.py`:

```python
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


class LabAccessMode(str, Enum):
    TERMINAL = "terminal"
    WEB_TARGET = "web_target"
    DESKTOP = "desktop"
    MULTI_MACHINE = "multi_machine"


class LabSessionStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class LabTemplate(Base):
    __tablename__ = "lab_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    access_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    image: Mapped[str] = mapped_column(String(255), nullable=False)
    startup_command: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    default_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    rooms: Mapped[list["Room"]] = relationship("Room", back_populates="template")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id: Mapped[str] = mapped_column(String(36), ForeignKey("lab_templates.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    template: Mapped["LabTemplate"] = relationship("LabTemplate", back_populates="rooms")
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
    __tablename__ = "challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    flag: Mapped[str] = mapped_column(String(255), nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    room: Mapped["Room"] = relationship("Room", back_populates="challenges")


class LabSession(Base):
    __tablename__ = "lab_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=LabSessionStatus.STARTING.value, nullable=False)
    access_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    network_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    attacker_container_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_container_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="lab_sessions")
    room: Mapped["Room"] = relationship("Room", back_populates="sessions")
```

- [ ] **Step 4: Wire model imports and user relationship**

Modify `backend/app/models/user.py` to add:

```python
    lab_sessions: Mapped[list["LabSession"]] = relationship(
        "LabSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
```

Modify `backend/app/models/__init__.py`:

```python
from .lab import Challenge, LabSession, LabTemplate, Room
from .user import User
from .user_limits import UserLimits
from .workspace import Workspace

__all__ = [
    "User",
    "UserLimits",
    "Workspace",
    "LabTemplate",
    "Room",
    "Challenge",
    "LabSession",
]
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend
pytest tests/test_labs.py -v
```

Expected: import errors are gone, route tests still fail because `/labs/*` is not implemented.

---

### Task 2: Add Lab Schemas And Routes

**Files:**
- Create: `backend/app/schemas/lab.py`
- Create: `backend/app/routers/labs.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_labs.py`

- [ ] **Step 1: Create schemas**

Create `backend/app/schemas/lab.py`:

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LabTemplateResponse(BaseModel):
    id: str
    name: str
    access_mode: str
    image: str
    startup_command: Optional[str] = None
    default_port: Optional[int] = None

    class Config:
        from_attributes = True


class ChallengeResponse(BaseModel):
    id: str
    title: str
    prompt: str
    points: int
    sort_order: int

    class Config:
        from_attributes = True


class RoomListResponse(BaseModel):
    id: str
    slug: str
    title: str
    difficulty: str
    description: str
    access_mode: str
    challenge_count: int


class RoomDetailResponse(BaseModel):
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
    id: str
    user_id: str
    room_id: str
    status: str
    access_mode: str
    network_name: Optional[str] = None
    access_url: Optional[str] = None
    started_at: datetime
    stopped_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Create labs router**

Create `backend/app/routers/labs.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..core.security import get_current_user
from ..models.lab import LabSession, LabSessionStatus, Room
from ..models.user import User
from ..schemas.lab import LabSessionResponse, RoomDetailResponse, RoomListResponse


router = APIRouter(prefix="/labs", tags=["Labs"])


@router.get("/rooms", response_model=list[RoomListResponse])
async def list_rooms(db: AsyncSession = Depends(get_db)):
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


@router.post("/rooms/{slug}/start", response_model=LabSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_room(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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

    session = LabSession(
        user_id=current_user.id,
        room_id=room.id,
        status=LabSessionStatus.STARTING.value,
        access_mode=room.template.access_mode,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return session
```

- [ ] **Step 3: Include router**

Modify `backend/app/main.py` imports:

```python
from .routers import auth, admin, workspace, labs
```

Add:

```python
app.include_router(labs.router)
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd backend
pytest tests/test_labs.py -v
```

Expected: all three Phase 1 tests pass.

---

### Task 3: Add Prototype Seed Data

**Files:**
- Create: `backend/app/services/seed_labs.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_labs.py`

- [ ] **Step 1: Add failing seed test**

Append to `backend/tests/test_labs.py`:

```python
from sqlalchemy import select

from app.services.seed_labs import seed_default_labs


async def test_seed_default_labs_is_idempotent(db_session):
    await seed_default_labs(db_session)
    await seed_default_labs(db_session)

    result = await db_session.execute(select(Room).where(Room.slug == "linux-basics"))
    rooms = result.scalars().all()

    assert len(rooms) == 1
    assert rooms[0].title == "Linux Basics"
    assert rooms[0].template.access_mode == "terminal"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest tests/test_labs.py::test_seed_default_labs_is_idempotent -v
```

Expected: fails because `app.services.seed_labs` does not exist.

- [ ] **Step 3: Implement seed service**

Create `backend/app/services/seed_labs.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.lab import Challenge, LabAccessMode, LabTemplate, Room


async def seed_default_labs(db: AsyncSession) -> None:
    result = await db.execute(
        select(Room)
        .options(selectinload(Room.template))
        .where(Room.slug == "linux-basics")
    )
    existing = result.scalar_one_or_none()

    if existing:
        return

    template = LabTemplate(
        name="Terminal Basics",
        access_mode=LabAccessMode.TERMINAL.value,
        image="workspace-dev:latest",
        default_port=7681,
    )
    room = Room(
        slug="linux-basics",
        title="Linux Basics",
        difficulty="easy",
        description="A first terminal-only room for practicing Linux navigation and flag discovery.",
        is_published=True,
        template=template,
    )
    room.challenges.append(
        Challenge(
            title="Read the Welcome Flag",
            prompt="Start the room and find the flag in the workspace.",
            flag="flag{linux_basics_started}",
            points=10,
            sort_order=1,
        )
    )
    db.add(room)
    await db.commit()
```

- [ ] **Step 4: Call seed on startup**

Modify `backend/app/main.py`:

```python
from .core.database import create_db_and_tables, get_db_context
from .services.seed_labs import seed_default_labs
```

Inside lifespan after `await create_db_and_tables()`:

```python
    async with get_db_context() as db:
        await seed_default_labs(db)
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend
pytest tests/test_labs.py -v
```

Expected: all Phase 1 tests pass.

---

## Self-Review

- Spec coverage: Phase 1 covers SQLite-backed rooms, challenges, lab templates, and lab sessions. It deliberately does not launch Docker lab containers yet; that belongs to Phase 2.
- Placeholder scan: No placeholders remain in implementation steps.
- Type consistency: The plan consistently uses `LabAccessMode`, `LabSessionStatus`, `Room`, `Challenge`, `LabTemplate`, and `LabSession` across models, schemas, routes, and tests.
