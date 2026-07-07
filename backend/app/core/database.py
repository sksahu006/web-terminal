"""
Database configuration and session management.
Uses SQLAlchemy async with aiosqlite for SQLite database.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

os.makedirs("data", exist_ok=True)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def create_db_and_tables():
    """Create all database tables and add prototype columns for older SQLite DBs."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        if settings.database_url.startswith("sqlite"):
            result = await conn.execute(text("PRAGMA table_info(users)"))
            existing_columns = {row[1] for row in result.fetchall()}
            local_auth_columns = {
                "email": "VARCHAR(255)",
                "username": "VARCHAR(255)",
                "password_hash": "VARCHAR(255)",
            }
            for column_name, column_type in local_auth_columns.items():
                if column_name not in existing_columns:
                    await conn.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))

            # Dynamic migrations for lab_sessions
            result_labs = await conn.execute(text("PRAGMA table_info(lab_sessions)"))
            existing_labs_columns = {row[1] for row in result_labs.fetchall()}
            if "last_active" not in existing_labs_columns:
                await conn.execute(text("ALTER TABLE lab_sessions ADD COLUMN last_active DATETIME"))
                await conn.execute(text("UPDATE lab_sessions SET last_active = CURRENT_TIMESTAMP"))
            if "docker_network" not in existing_labs_columns:
                await conn.execute(text("ALTER TABLE lab_sessions ADD COLUMN docker_network VARCHAR(120)"))

            # Dynamic migrations for lab_templates (per-container minimal resource footprint)
            result_templates = await conn.execute(text("PRAGMA table_info(lab_templates)"))
            existing_template_columns = {row[1] for row in result_templates.fetchall()}
            template_columns = {
                "target_port": "INTEGER DEFAULT 8000",
                "attacker_cpu": "REAL DEFAULT 0.25",
                "attacker_memory": "INTEGER DEFAULT 256",
                "target_cpu": "REAL DEFAULT 0.25",
                "target_memory": "INTEGER DEFAULT 256",
            }
            for column_name, column_def in template_columns.items():
                if column_name not in existing_template_columns:
                    await conn.execute(text(f"ALTER TABLE lab_templates ADD COLUMN {column_name} {column_def}"))

            # Dynamic migrations for workspaces
            result_workspaces = await conn.execute(text("PRAGMA table_info(workspaces)"))
            existing_workspaces_columns = {row[1] for row in result_workspaces.fetchall()}
            if "last_active" not in existing_workspaces_columns:
                await conn.execute(text("ALTER TABLE workspaces ADD COLUMN last_active DATETIME"))
                await conn.execute(text("UPDATE workspaces SET last_active = CURRENT_TIMESTAMP"))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    Yields a session and ensures it's closed after use.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions.
    Useful for background tasks and non-request contexts.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
