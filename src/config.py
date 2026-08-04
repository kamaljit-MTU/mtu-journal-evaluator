"""
MTU Journal Evaluator - Environment Configuration
"""
import os
from typing import Optional


class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_THIS_TO_A_STRONG_RANDOM_SECRET_IN_PRODUCTION")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

    # Database
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "evaluations.db")

    # Admin credentials (for initial setup)
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "mtu_admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "MTU@2026!ChangeMe!")

    # App config
    APP_NAME: str = "MTU Journal Evaluator"
    APP_VERSION: str = "1.1.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Committee email for manual review correspondence
    COMMITTEE_EMAIL: str = os.getenv("COMMITTEE_EMAIL", "mtujournal@gmail.com")

    # Telegram notification config
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")

    # Free database providers often use postgres:// instead of postgresql://
    @property
    def database_url(self) -> Optional[str]:
        if self.DATABASE_URL:
            # Normalize postgres:// to postgresql:// for SQLAlchemy
            return self.DATABASE_URL.replace("postgres://", "postgresql://")
        return None

    @property
    def use_postgresql(self) -> bool:
        return self.database_url is not None and self.database_url.startswith("postgresql")


settings = Settings()
