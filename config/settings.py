from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = where .env lives (1 level up from this file)
#   config/settings.py  →  project_root/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Log .env location so the user can verify it's found
_logger = logging.getLogger(__name__)
if ENV_FILE.exists():
    _logger.info(".env file found: %s", ENV_FILE)
else:
    _logger.warning(".env file NOT found at %s — using env vars only", ENV_FILE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Telegram
    bot_token: str

    @field_validator("bot_token", mode="before")
    @classmethod
    def _clean_token(cls, v: str) -> str:
        """Strip whitespace, quotes and validate Telegram token format."""
        if not v:
            raise ValueError(
                "BOT_TOKEN is empty! Set it in .env or as an environment variable."
            )
        v = v.strip().strip('"').strip("'").strip()
        # Telegram bot token format: <digits>:<35+ alphanumeric chars>
        if not re.match(r"^\d{1,10}:[A-Za-z0-9_-]{35,}$", v):
            raise ValueError(
                f"BOT_TOKEN does not match Telegram format (got: {v[:8]}...). "
                "Make sure you copied the full token from @BotFather."
            )
        return v

    # PostgreSQL
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "helpdesk"
    db_user: str = "helpdesk"
    db_password: str = "helpdesk_secret"

    # Application
    admin_telegram_ids: str = ""  # comma-separated list of Telegram IDs
    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def admin_ids(self) -> List[int]:
        if not self.admin_telegram_ids:
            return []
        return [
            int(x.strip())
            for x in self.admin_telegram_ids.split(",")
            if x.strip().isdigit()
        ]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
