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
