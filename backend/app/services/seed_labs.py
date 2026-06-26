"""
Prototype lab seed data for fresh SQLite databases.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.lab import Challenge, LabAccessMode, LabTemplate, Room


async def _room_exists(db: AsyncSession, slug: str) -> bool:
    result = await db.execute(select(Room.id).where(Room.slug == slug))
    return result.scalar_one_or_none() is not None


async def seed_default_labs(db: AsyncSession) -> None:
    """Create starter rooms once, without blocking future seed additions."""
    changed = False

    if not await _room_exists(db, "linux-basics"):
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
        changed = True

    if not await _room_exists(db, "web-basics"):
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
            description="Attack a small intentionally vulnerable web target from your terminal lab.",
            is_published=True,
            template=template,
        )
        room.challenges.extend(
            [
                Challenge(
                    title="Read the Target Homepage",
                    prompt="Start the room, open the terminal, run `curl $TARGET_URL`, and submit the flag shown on the homepage.",
                    flag="flag{web_target_reachable}",
                    points=10,
                    sort_order=1,
                ),
                Challenge(
                    title="Find the Debug Flag",
                    prompt="Query `$TARGET_URL/debug?show=flag` and submit the debug flag.",
                    flag="flag{debug_endpoint_found}",
                    points=15,
                    sort_order=2,
                ),
            ]
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "kali-terminal"):
        template = LabTemplate(
            name="Kali Terminal",
            access_mode=LabAccessMode.TERMINAL.value,
            image="kali-terminal:latest",
            default_port=7681,
        )
        room = Room(
            slug="kali-terminal",
            title="Kali Linux Terminal",
            difficulty="medium",
            description="A Kali Linux environment with nmap, netcat, curl, python3, and standard recon tools.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Scan the Target",
                prompt="Run `nmap -sn 172.0.0.0/24` and find the live host. Submit the IP as the flag.",
                flag="flag{kali_recon_complete}",
                points=20,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "browser-desktop"):
        template = LabTemplate(
            name="Browser Desktop",
            # We use TERMINAL mode because the backend treats it as a single container
            # serving HTTP (noVNC) on the exposed port, exactly like ttyd does.
            access_mode=LabAccessMode.TERMINAL.value,
            image="browser-desktop:latest",
            default_port=6080, # noVNC port
        )
        room = Room(
            slug="browser-desktop",
            title="GUI Desktop Lab",
            difficulty="medium",
            description="A lightweight Linux desktop environment accessed directly in your browser. Includes Firefox.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Browse the Web",
                prompt="Open Firefox within the virtual desktop, navigate to the target, and submit the flag.",
                flag="flag{gui_desktop_active}",
                points=30,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if changed:
        await db.commit()

