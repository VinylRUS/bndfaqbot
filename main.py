from __future__ import annotations

import asyncio
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import get_settings
from database.session import create_tables, async_session_factory
from database.repositories.category_repo import CategoryRepository
from database.repositories.role_repo import RoleRepository
from database.repositories.user_repo import UserRepository
from database.repositories.bot_setting_repo import BotSettingRepository
from services.user_service import UserService
from bot.middlewares.db_session_middleware import DbSessionMiddleware
from bot.middlewares.role_middleware import RoleMiddleware
from bot.routers.user_router import user_router
from bot.routers.operator_router import operator_router
from bot.routers.admin_router import admin_router
from bot.routers.timesheet_router import timesheet_router


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


async def check_timesheet_reminders(bot: Bot) -> None:
    """Periodic check for timesheet reminders."""
    from services.timesheet_service import TimesheetService
    from database.models.timesheet_period import EmployeeType

    logger = logging.getLogger(__name__)
    try:
        async with async_session_factory() as session:
            ts_service = TimesheetService(session)
            reminders = await ts_service.get_periods_for_reminder()

            # 2 days before deadline — remind all users
            for period in reminders.get("two_days_before", []):
                users = await ts_service.get_users_for_period(period.id)
                for user in users:
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            f"⏰ Напоминание: через 2 дня дедлайн сдачи часов "
                            f"({period.deadline.strftime('%d.%m.%Y')}). "
                            f"Период: {period.start_date.strftime('%d.%m')}–{period.end_date.strftime('%d.%m')}",
                        )
                    except Exception:
                        pass

            # Deadline day — remind all users
            for period in reminders.get("deadline_day", []):
                users = await ts_service.get_users_for_period(period.id)
                for user in users:
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            f"🚨 Сегодня дедлайн сдачи часов! "
                            f"Период: {period.start_date.strftime('%d.%m')}–{period.end_date.strftime('%d.%m')}",
                        )
                    except Exception:
                        pass

            # Half day before — remind only non-submitters
            for period in reminders.get("half_day_before", []):
                status = await ts_service.get_submission_status(period.id)
                for user in status.get("missing", []):
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            f"⚠ Осталось менее 12 часов до дедлайна! "
                            f"Сдайте часы за период {period.start_date.strftime('%d.%m')}–{period.end_date.strftime('%d.%m')}",
                        )
                    except Exception:
                        pass

    except Exception as e:
        logger.error("Timesheet reminder error: %s", e)


async def main() -> None:
    # ── Logging setup: console + daily-rotating file ─────────────
    log_format = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    log_dir = os.environ.get("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "bot.log")

    # File handler: rotate every midnight, keep 7 days
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(logging.Formatter(log_format))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[console_handler, file_handler],
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
    dp.include_router(timesheet_router)

    # 6. Start periodic reminder task
    reminder_task = asyncio.create_task(_reminder_loop(bot))

    # 7. Start polling
    try:
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()
        await bot.session.close()


async def _reminder_loop(bot: Bot) -> None:
    """Background task that checks reminders every 30 minutes."""
    while True:
        await asyncio.sleep(1800)  # 30 minutes
        await check_timesheet_reminders(bot)


if __name__ == "__main__":
    asyncio.run(main())
