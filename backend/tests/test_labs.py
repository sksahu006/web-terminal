import pytest
from sqlalchemy import select

from app.models.lab import (
    Challenge,
    LabAccessMode,
    LabSession,
    LabSessionStatus,
    LabTemplate,
    Room,
)
from app.main import app
from app.routers.labs import get_lab_container_manager
from app.services.seed_labs import seed_default_labs


pytestmark = pytest.mark.asyncio


class FakeContainerManager:
    def __init__(self):
        self.created = []
        self.stopped = []
        self.removed = []
        self.statuses = {}

    def create_lab_container(
        self,
        user_id,
        room_slug,
        image,
        limits,
        exposed_port=7681,
        github_token=None,
    ):
        self.created.append(
            {
                "user_id": user_id,
                "room_slug": room_slug,
                "image": image,
                "memory": limits.memory,
                "cpu": limits.cpu,
                "exposed_port": exposed_port,
                "github_token": github_token,
            }
        )
        return {
            "container_id": "container-123",
            "container_name": "lab-linux-basics",
            "access_port": 32768,
        }

    def get_container_status(self, container_id):
        return self.statuses.get(container_id, {"running": True})

    def stop_container(self, container_id, timeout=10):
        self.stopped.append({"container_id": container_id, "timeout": timeout})
        return True

    def remove_container(self, container_id, force=True):
        self.removed.append({"container_id": container_id, "force": force})
        return True


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
    fake_manager = FakeContainerManager()
    app.dependency_overrides[get_lab_container_manager] = lambda: fake_manager

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
    assert body["status"] == "running"
    assert body["access_mode"] == "terminal"
    assert body["attacker_container_id"] == "container-123"
    assert body["access_url"] == "http://test:32768"


async def test_seed_default_labs_is_idempotent(db_session):
    await seed_default_labs(db_session)
    await seed_default_labs(db_session)

    linux_result = await db_session.execute(select(Room).where(Room.slug == "linux-basics"))
    linux_rooms = linux_result.scalars().all()
    web_result = await db_session.execute(select(Room).where(Room.slug == "web-basics"))
    web_rooms = web_result.scalars().all()

    assert len(linux_rooms) == 1
    assert linux_rooms[0].title == "Linux Basics"
    assert linux_rooms[0].template.access_mode == "terminal"

    assert len(web_rooms) == 1
    assert web_rooms[0].title == "Web Basics"
    assert web_rooms[0].template.access_mode == "web_target"
    assert web_rooms[0].template.image == "workspace-dev:latest|web-basics-target:latest"
    assert [challenge.title for challenge in web_rooms[0].challenges] == [
        "Read the Target Homepage",
        "Find the Debug Flag",
    ]


async def test_start_room_uses_template_image_and_user_limits(client, db_session, current_user):
    fake_manager = FakeContainerManager()
    app.dependency_overrides[get_lab_container_manager] = lambda: fake_manager

    template = LabTemplate(
        name="Custom Terminal",
        access_mode=LabAccessMode.TERMINAL.value,
        image="custom-terminal:latest",
        default_port=9000,
    )
    room = Room(
        slug="custom-terminal",
        title="Custom Terminal",
        difficulty="easy",
        description="A custom terminal lab.",
        is_published=True,
        template=template,
    )
    db_session.add(room)
    await db_session.commit()

    response = await client.post("/labs/rooms/custom-terminal/start")

    assert response.status_code == 201
    assert fake_manager.created == [
        {
            "user_id": current_user.id,
            "room_slug": "custom-terminal",
            "image": "custom-terminal:latest",
            "memory": 1024,
            "cpu": 1.0,
            "exposed_port": 9000,
            "github_token": None,
        }
    ]


async def test_start_room_rejects_existing_active_lab_session(client, db_session, current_user):
    app.dependency_overrides[get_lab_container_manager] = lambda: FakeContainerManager()

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
    await db_session.flush()
    db_session.add(
        LabSession(
            user_id=current_user.id,
            room_id=room.id,
            status=LabSessionStatus.RUNNING.value,
            access_mode=LabAccessMode.TERMINAL.value,
        )
    )
    await db_session.commit()

    response = await client.post("/labs/rooms/linux-basics/start")

    assert response.status_code == 409
    assert response.json()["detail"] == "You already have an active lab session. Stop it first."


async def test_get_active_lab_session_returns_running_session(client, db_session, current_user):
    fake_manager = FakeContainerManager()
    fake_manager.statuses["container-123"] = {"running": True}
    app.dependency_overrides[get_lab_container_manager] = lambda: fake_manager

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
    await db_session.flush()
    session = LabSession(
        user_id=current_user.id,
        room_id=room.id,
        status=LabSessionStatus.RUNNING.value,
        access_mode=LabAccessMode.TERMINAL.value,
        attacker_container_id="container-123",
        access_url="http://test:32768",
    )
    db_session.add(session)
    await db_session.commit()

    response = await client.get("/labs/sessions/active")

    assert response.status_code == 200
    body = response.json()
    assert body["has_active_session"] is True
    assert body["session"]["id"] == session.id
    assert body["session"]["status"] == "running"
    assert body["message"] == "Lab session is running"


async def test_get_active_lab_session_marks_dead_container_stopped(client, db_session, current_user):
    fake_manager = FakeContainerManager()
    fake_manager.statuses["dead-container"] = {"running": False}
    app.dependency_overrides[get_lab_container_manager] = lambda: fake_manager

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
    await db_session.flush()
    session = LabSession(
        user_id=current_user.id,
        room_id=room.id,
        status=LabSessionStatus.RUNNING.value,
        access_mode=LabAccessMode.TERMINAL.value,
        attacker_container_id="dead-container",
    )
    db_session.add(session)
    await db_session.commit()

    response = await client.get("/labs/sessions/active")

    assert response.status_code == 200
    body = response.json()
    assert body["has_active_session"] is False
    assert body["session"] is None
    assert body["message"] == "Previous lab session has stopped"
    await db_session.refresh(session)
    assert session.status == LabSessionStatus.STOPPED.value


async def test_stop_lab_session_stops_container_and_marks_session_stopped(client, db_session, current_user):
    fake_manager = FakeContainerManager()
    app.dependency_overrides[get_lab_container_manager] = lambda: fake_manager

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
    await db_session.flush()
    session = LabSession(
        user_id=current_user.id,
        room_id=room.id,
        status=LabSessionStatus.RUNNING.value,
        access_mode=LabAccessMode.TERMINAL.value,
        attacker_container_id="container-123",
    )
    db_session.add(session)
    await db_session.commit()

    response = await client.post(f"/labs/sessions/{session.id}/stop")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["message"] == "Lab session stopped successfully"
    assert fake_manager.stopped == [{"container_id": "container-123", "timeout": 10}]
    assert fake_manager.removed == [{"container_id": "container-123", "force": True}]
    await db_session.refresh(session)
    assert session.status == LabSessionStatus.STOPPED.value
    assert session.stopped_at is not None



async def test_submit_correct_flag_awards_points_once(client, db_session, current_user):
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
    challenge = Challenge(
        title="Find the flag",
        prompt="Read the flag file.",
        flag="flag{phase_four}",
        points=25,
        sort_order=1,
    )
    room.challenges.append(challenge)
    db_session.add(room)
    await db_session.commit()

    response = await client.post(
        f"/labs/challenges/{challenge.id}/submit",
        json={"flag": "flag{phase_four}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "challenge_id": challenge.id,
        "correct": True,
        "already_solved": False,
        "points_awarded": 25,
        "message": "Correct flag submitted",
    }


async def test_submit_correct_flag_again_does_not_award_duplicate_points(client, db_session, current_user):
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
    challenge = Challenge(
        title="Find the flag",
        prompt="Read the flag file.",
        flag="flag{phase_four}",
        points=25,
        sort_order=1,
    )
    room.challenges.append(challenge)
    db_session.add(room)
    await db_session.commit()

    await client.post(
        f"/labs/challenges/{challenge.id}/submit",
        json={"flag": "flag{phase_four}"},
    )
    response = await client.post(
        f"/labs/challenges/{challenge.id}/submit",
        json={"flag": "flag{phase_four}"},
    )

    assert response.status_code == 200
    assert response.json()["correct"] is True
    assert response.json()["already_solved"] is True
    assert response.json()["points_awarded"] == 0
    assert response.json()["message"] == "Challenge already solved"


async def test_submit_wrong_flag_returns_incorrect_without_points(client, db_session):
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
    challenge = Challenge(
        title="Find the flag",
        prompt="Read the flag file.",
        flag="flag{phase_four}",
        points=25,
        sort_order=1,
    )
    room.challenges.append(challenge)
    db_session.add(room)
    await db_session.commit()

    response = await client.post(
        f"/labs/challenges/{challenge.id}/submit",
        json={"flag": "wrong"},
    )

    assert response.status_code == 200
    assert response.json()["correct"] is False
    assert response.json()["already_solved"] is False
    assert response.json()["points_awarded"] == 0
    assert response.json()["message"] == "Incorrect flag"


async def test_get_room_progress_returns_solved_counts_and_points(client, db_session):
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
    first = Challenge(
        title="First flag",
        prompt="Find first.",
        flag="flag{one}",
        points=10,
        sort_order=1,
    )
    second = Challenge(
        title="Second flag",
        prompt="Find second.",
        flag="flag{two}",
        points=15,
        sort_order=2,
    )
    room.challenges.extend([first, second])
    db_session.add(room)
    await db_session.commit()

    await client.post(f"/labs/challenges/{first.id}/submit", json={"flag": "flag{one}"})

    response = await client.get("/labs/rooms/linux-basics/progress")

    assert response.status_code == 200
    assert response.json() == {
        "room_id": room.id,
        "slug": "linux-basics",
        "total_challenges": 2,
        "solved_challenges": 1,
        "total_points": 25,
        "earned_points": 10,
        "challenges": [
            {
                "challenge_id": first.id,
                "title": "First flag",
                "points": 10,
                "solved": True,
            },
            {
                "challenge_id": second.id,
                "title": "Second flag",
                "points": 15,
                "solved": False,
            },
        ],
    }


async def test_start_web_target_room_launches_attacker_and_target(client, db_session, current_user):
    class FakeWebTargetManager(FakeContainerManager):
        def __init__(self):
            super().__init__()
            self.web_targets = []

        def create_web_target_lab(
            self,
            user_id,
            room_slug,
            attacker_image,
            target_image,
            limits,
            attacker_port=7681,
            target_port=8000,
            github_token=None,
        ):
            self.web_targets.append(
                {
                    "user_id": user_id,
                    "room_slug": room_slug,
                    "attacker_image": attacker_image,
                    "target_image": target_image,
                    "attacker_port": attacker_port,
                    "target_port": target_port,
                    "memory": limits.memory,
                    "cpu": limits.cpu,
                    "github_token": github_token,
                }
            )
            return {
                "attacker_container_id": "attacker-123",
                "attacker_container_name": "lab-web-basics-attacker",
                "target_container_id": "target-123",
                "target_container_name": "lab-web-basics-target",
                "access_port": 32769,
                "target_url": "http://lab-web-basics-target:8000",
            }

    fake_manager = FakeWebTargetManager()
    app.dependency_overrides[get_lab_container_manager] = lambda: fake_manager

    template = LabTemplate(
        name="Web Target Basics",
        access_mode=LabAccessMode.WEB_TARGET.value,
        image="workspace-dev:latest|web-basics-target:latest",
        default_port=7681,
    )
    room = Room(
        slug="web-basics",
        title="Web Basics",
        difficulty="easy",
        description="Attack a tiny vulnerable web target.",
        is_published=True,
        template=template,
    )
    db_session.add(room)
    await db_session.commit()

    response = await client.post("/labs/rooms/web-basics/start")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "running"
    assert body["access_mode"] == "web_target"
    assert body["attacker_container_id"] == "attacker-123"
    assert body["access_url"] == "http://test:32769"
    assert fake_manager.web_targets == [
        {
            "user_id": current_user.id,
            "room_slug": "web-basics",
            "attacker_image": "workspace-dev:latest",
            "target_image": "web-basics-target:latest",
            "attacker_port": 7681,
            "target_port": 8000,
            "memory": 1024,
            "cpu": 1.0,
            "github_token": None,
        }
    ]


async def test_stop_web_target_room_removes_attacker_and_target(client, db_session, current_user):
    fake_manager = FakeContainerManager()
    app.dependency_overrides[get_lab_container_manager] = lambda: fake_manager

    template = LabTemplate(
        name="Web Target Basics",
        access_mode=LabAccessMode.WEB_TARGET.value,
        image="workspace-dev:latest|web-basics-target:latest",
    )
    room = Room(
        slug="web-basics",
        title="Web Basics",
        difficulty="easy",
        description="Attack a tiny vulnerable web target.",
        is_published=True,
        template=template,
    )
    db_session.add(room)
    await db_session.flush()
    session = LabSession(
        user_id=current_user.id,
        room_id=room.id,
        status=LabSessionStatus.RUNNING.value,
        access_mode=LabAccessMode.WEB_TARGET.value,
        attacker_container_id="attacker-123",
        target_container_ids="target-123",
    )
    db_session.add(session)
    await db_session.commit()

    response = await client.post(f"/labs/sessions/{session.id}/stop")

    assert response.status_code == 200
    assert fake_manager.stopped == [
        {"container_id": "attacker-123", "timeout": 10},
        {"container_id": "target-123", "timeout": 10},
    ]
    assert fake_manager.removed == [
        {"container_id": "attacker-123", "force": True},
        {"container_id": "target-123", "force": True},
    ]

