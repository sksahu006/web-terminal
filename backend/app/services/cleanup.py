"""
Background cleanup service for terminating idle and expired containers.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.database import get_db_context
from ..models.lab import LabSession, LabSessionStatus
from ..models.workspace import Workspace, WorkspaceStatus
from ..services.container_manager import get_container_manager

logger = logging.getLogger(__name__)

IDLE_TIMEOUT_MINUTES = 30


async def cleanup_idle_sessions_and_workspaces(db: AsyncSession) -> None:
    """
    Query the database for idle/expired workspaces and lab sessions,
    stop their respective Docker containers, and mark them as stopped in the DB.
    """
    now = datetime.utcnow()
    idle_cutoff = now - timedelta(minutes=IDLE_TIMEOUT_MINUTES)
    lab_session_max_runtime = timedelta(seconds=get_settings().default_max_runtime)
    container_manager = get_container_manager()

    # 1. Clean up active workspaces that are expired or idle
    try:
        active_workspaces_query = select(Workspace).where(
            Workspace.status.in_([WorkspaceStatus.STARTING.value, WorkspaceStatus.RUNNING.value])
        )
        result = await db.execute(active_workspaces_query)
        workspaces = result.scalars().all()

        for ws in workspaces:
            is_expired = now > ws.expires_at
            is_idle = ws.last_active < idle_cutoff

            if is_expired or is_idle:
                reason = "expired" if is_expired else "idle"
                logger.info(f"Auto-stopping {reason} workspace {ws.id} for user {ws.user_id}")
                
                # Stop and remove container in background thread, catching exceptions
                try:
                    await asyncio.to_thread(container_manager.remove_container, ws.container_id, force=True)
                except Exception as e:
                    logger.error(f"Error removing workspace container {ws.container_id}: {e}", exc_info=True)
                
                # Update DB state regardless of Docker success/failure
                ws.status = WorkspaceStatus.STOPPED.value
                ws.stopped_at = now
    except Exception as e:
        logger.error(f"Error cleaning up workspaces: {e}", exc_info=True)

    # 2. Clean up active lab sessions that are idle
    try:
        active_sessions_query = select(LabSession).where(
            LabSession.status.in_([LabSessionStatus.STARTING.value, LabSessionStatus.RUNNING.value])
        )
        result = await db.execute(active_sessions_query)
        sessions = result.scalars().all()

        for session in sessions:
            is_idle = session.last_active < idle_cutoff
            is_over_runtime = now - session.started_at > lab_session_max_runtime

            if is_idle or is_over_runtime:
                reason = "idle" if is_idle else "over max runtime"
                logger.info(f"Auto-stopping {reason} lab session {session.id} for user {session.user_id}")

                # Stop and remove all associated containers
                container_ids = []
                if session.attacker_container_id:
                    container_ids.append(session.attacker_container_id)
                if session.target_container_ids:
                    container_ids.extend(
                        cid.strip()
                        for cid in session.target_container_ids.split(",")
                        if cid.strip()
                    )

                tasks = [
                    asyncio.to_thread(container_manager.remove_container, cid, force=True)
                    for cid in container_ids
                ]
                try:
                    await asyncio.gather(*tasks)
                except Exception as e:
                    logger.error(f"Error removing idle lab session containers: {e}", exc_info=True)

                if session.docker_network:
                    try:
                        await asyncio.to_thread(container_manager.remove_session_network, session.docker_network)
                    except Exception as e:
                        logger.error(f"Error removing lab session network: {e}", exc_info=True)

                # Update DB state regardless of Docker success/failure
                session.status = LabSessionStatus.STOPPED.value
                session.stopped_at = now
    except Exception as e:
        logger.error(f"Error cleaning up lab sessions: {e}", exc_info=True)

    # Commit all updates
    await db.commit()


async def start_periodic_cleanup_task() -> asyncio.Task:
    """
    Launch the periodic cleanup loop as a background task.
    """
    async def cleanup_loop():
        logger.info("Starting background periodic cleanup loop")
        while True:
            try:
                await asyncio.sleep(60)  # Run cleanup check every 60 seconds
                async with get_db_context() as db:
                    await cleanup_idle_sessions_and_workspaces(db)
            except asyncio.CancelledError:
                logger.info("Background periodic cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in background cleanup loop: {e}", exc_info=True)

    return asyncio.create_task(cleanup_loop())
