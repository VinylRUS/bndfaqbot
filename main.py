from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import get_settings
from database.session import create_tables
from database.repositories.category_repo import CategoryRepository
from database.repositories.role_repo import RoleRepository
from database.session import async_session_factory
from services.user_service import UserService
from bot.middlewares.db_session_middleware import DbSessionMiddleware
from bot.middlewares.role_middleware import RoleMiddleware
from bot.routers.user_router import user_router
from bot.routers.operator_router import operator_router
from bot.routers.admin_router import admin_router


async def seed_database() -> None:
    """Create default roles, categories and admin users if they don't exist."""
    async with async_session_factory() as session:
        role_repo = RoleRepository(session)
        for role_name in ["admin", "operator", "user"]:
            from database.models.role import RoleEnum
            await role_repo.get_or_create(RoleEnum(role_name))

        cat_repo = CategoryRepository(session)
        await cat_repo.seed_defaults()

        settings = get_settings()
        user_service = UserService(session)
        for admin_id in settings.admin_ids:
            await user_service.ensure_admin(admin_id)

        await session.commit()


async def wait_for_database(max_retries: int = 10, delay: float = 3.0) -> None:
    """Wait for PostgreSQL to become available with retries."""
    from sqlalchemy import text
    from database.session import async_engine

    logger = logging.getLogger(__name__)
    settings = get_settings()

    for attempt in range(1, max_retries + 1):
        try:
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection OK (%s:%s)", settings.db_host, settings.db_port)
            return
        except Exception as e:
            logger.warning("DB attempt %d/%d failed: %s", attempt, max_retries, e)
            if attempt < max_retries:
                await asyncio.sleep(delay)
            else:
                raise


async def main() -> None:
    # Basic logging first so validators can log too
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)

    from config.settings import ENV_FILE
    logger.info(".env expected at: %s (exists=%s)", ENV_FILE, ENV_FILE.exists())

    try:
        settings = get_settings()
    except Exception as e:
        logger.error("Failed to load settings: %s", e)
        logger.error("Make sure .env exists at %s with a valid BOT_TOKEN", ENV_FILE)
        sys.exit(1)

    # Reconfigure logging with user's level
    logging.getLogger().setLevel(
        getattr(logging, settings.log_level.upper(), logging.INFO)
    )

    logger.info("Starting HelpDesk bot...")
    logger.info("DB: %s:%s/%s", settings.db_host, settings.db_port, settings.db_name)

    # 1. Wait for database
    await wait_for_database()

    # 2. Create tables (idempotent — safe to run every time)
    await create_tables()
    logger.info("Tables verified.")

    # 3. Seed default data
    await seed_database()
    logger.info("Seed data verified.")

    # 4. Init bot
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    storage = MemoryStorage()

    # 5. Setup dispatcher
    dp = Dispatcher(storage=storage)
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.message.middleware(RoleMiddleware())
    dp.callback_query.middleware(RoleMiddleware())

    dp.include_router(user_router)
    dp.include_router(operator_router)
    dp.include_router(admin_router)

    # 6. Start polling
    # aiogram automatically injects the Bot instance into handler data["bot"]
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
