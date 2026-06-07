from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import get_settings
from database.models.base import Base

logger = logging.getLogger(__name__)


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=300,
    )


async_engine: AsyncEngine = _build_engine()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevent MissingGreenlet on lazy loads after commit
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def migrate_schema() -> None:
    """Migrate existing FK constraints from users.id to users.telegram_id.

    This is a one-time migration. Call it manually if upgrading from
    an older schema. It is NO LONGER auto-executed on every startup
    to avoid unnecessary DDL operations on a live database.
    """
    # Step 1: Drop old FK constraints (must be done before ALTER COLUMN)
    fk_migrations = [
        "ALTER TABLE audit_logs DROP CONSTRAINT IF EXISTS audit_logs_user_id_fkey",
        "ALTER TABLE ratings DROP CONSTRAINT IF EXISTS ratings_user_id_fkey",
        "ALTER TABLE tickets DROP CONSTRAINT IF EXISTS tickets_author_id_fkey",
        "ALTER TABLE tickets DROP CONSTRAINT IF EXISTS tickets_operator_id_fkey",
        "ALTER TABLE ticket_messages DROP CONSTRAINT IF EXISTS ticket_messages_sender_id_fkey",
    ]

    # Step 2: Alter column types from INTEGER to BIGINT
    type_migrations = [
        "ALTER TABLE audit_logs ALTER COLUMN user_id TYPE BIGINT",
        "ALTER TABLE ratings ALTER COLUMN user_id TYPE BIGINT",
        "ALTER TABLE tickets ALTER COLUMN author_id TYPE BIGINT",
        "ALTER TABLE tickets ALTER COLUMN operator_id TYPE BIGINT",
        "ALTER TABLE ticket_messages ALTER COLUMN sender_id TYPE BIGINT",
    ]

    # Step 3: Create new FK constraints referencing users.telegram_id
    new_fk_migrations = [
        (
            "audit_logs_user_id_fkey",
            "ALTER TABLE audit_logs ADD CONSTRAINT audit_logs_user_id_fkey "
            "FOREIGN KEY (user_id) REFERENCES users(telegram_id)",
        ),
        (
            "ratings_user_id_fkey",
            "ALTER TABLE ratings ADD CONSTRAINT ratings_user_id_fkey "
            "FOREIGN KEY (user_id) REFERENCES users(telegram_id)",
        ),
        (
            "tickets_author_id_fkey",
            "ALTER TABLE tickets ADD CONSTRAINT tickets_author_id_fkey "
            "FOREIGN KEY (author_id) REFERENCES users(telegram_id)",
        ),
        (
            "tickets_operator_id_fkey",
            "ALTER TABLE tickets ADD CONSTRAINT tickets_operator_id_fkey "
            "FOREIGN KEY (operator_id) REFERENCES users(telegram_id)",
        ),
        (
            "ticket_messages_sender_id_fkey",
            "ALTER TABLE ticket_messages ADD CONSTRAINT ticket_messages_sender_id_fkey "
            "FOREIGN KEY (sender_id) REFERENCES users(telegram_id)",
        ),
    ]

    async with async_engine.begin() as conn:
        # Drop old FKs
        for sql in fk_migrations:
            try:
                await conn.execute(text(sql))
            except Exception as e:
                logger.warning("FK drop skipped: %s", e)

        # Alter column types
        for sql in type_migrations:
            try:
                await conn.execute(text(sql))
                logger.info("Altered column type: %s", sql.split("ALTER COLUMN")[1].strip().split()[0])
            except Exception as e:
                logger.warning("Type alteration skipped (may already be BIGINT): %s", e)

        # Create new FKs
        for name, sql in new_fk_migrations:
            try:
                await conn.execute(text(sql))
                logger.info("Created FK %s → users.telegram_id", name)
            except Exception as e:
                logger.warning("FK creation skipped: %s", e)

    logger.info("Schema migration completed.")


async def create_tables() -> None:
    # Import all models so Base.metadata knows about them
    import database.models.user  # noqa: F401
    import database.models.role  # noqa: F401
    import database.models.ticket  # noqa: F401
    import database.models.ticket_message  # noqa: F401
    import database.models.faq  # noqa: F401
    import database.models.auto_answer  # noqa: F401
    import database.models.rating  # noqa: F401
    import database.models.audit_log  # noqa: F401
    import database.models.category  # noqa: F401
    import database.models.quick_reply  # noqa: F401
    import database.models.timesheet_period  # noqa: F401
    import database.models.timesheet_entry  # noqa: F401
    import database.models.bot_setting  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Add new columns to existing tables (safe — uses IF NOT EXISTS pattern)
    await _migrate_v7()


async def _migrate_v7() -> None:
    """Add new columns for v7 features to existing tables.

    This is safe to run on every startup — it checks column existence.
    """
    column_additions = [
        # User table — timesheet fields
        ("users", "full_name", "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)"),
        ("users", "employee_type", "ALTER TABLE users ADD COLUMN IF NOT EXISTS employee_type VARCHAR(20)"),
        ("users", "workplace", "ALTER TABLE users ADD COLUMN IF NOT EXISTS workplace VARCHAR(100) DEFAULT 'Производство'"),
        ("users", "collects_hours", "ALTER TABLE users ADD COLUMN IF NOT EXISTS collects_hours BOOLEAN DEFAULT FALSE"),
        # Ticket messages — attachment fields
        ("ticket_messages", "file_id", "ALTER TABLE ticket_messages ADD COLUMN IF NOT EXISTS file_id VARCHAR(500)"),
        ("ticket_messages", "file_type", "ALTER TABLE ticket_messages ADD COLUMN IF NOT EXISTS file_type VARCHAR(20)"),
    ]

    async with async_engine.begin() as conn:
        for table, column, sql in column_additions:
            try:
                # Check if column exists
                result = await conn.execute(text(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name = '{table}' AND column_name = '{column}'"
                ))
                if result.scalar_one_or_none() is None:
                    await conn.execute(text(sql))
                    logger.info("Added column %s.%s", table, column)
            except Exception as e:
                logger.warning("Column migration %s.%s skipped: %s", table, column, e)

    # Alter ticket_messages.text to allow empty (default="")
    try:
        async with async_engine.begin() as conn:
            await conn.execute(text(
                "ALTER TABLE ticket_messages ALTER COLUMN text SET DEFAULT ''"
            ))
    except Exception as e:
        logger.warning("ticket_messages.text default skipped: %s", e)
