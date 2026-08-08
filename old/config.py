"""
NHPC Weather Warning System — Centralized Configuration.

Uses pydantic-settings to load, validate, and expose all application
configuration from environment variables and .env files. Replaces
scattered constants and the hand-rolled .env parser.

Usage:
    from config import get_settings
    settings = get_settings()
    print(settings.APP_PORT)

Every setting has a sensible default so the system starts with zero
configuration (matching current behavior). Adding a .env file or
setting environment variables overrides defaults.
"""

import os
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    # Graceful fallback: if pydantic-settings is not installed,
    # provide a minimal dataclass-based config so existing code
    # doesn't break during the transition period.
    import warnings
    warnings.warn(
        "pydantic-settings not installed. Using fallback configuration. "
        "Install with: pip install pydantic-settings>=2.0",
        stacklevel=2,
    )

    class BaseSettings:  # type: ignore[no-redef]
        """Minimal fallback when pydantic-settings is unavailable."""

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    Field = lambda default=None, **kw: default  # type: ignore[assignment, misc]


# -----------------------------------------------------------------------
# Workspace root (directory containing this file)
# -----------------------------------------------------------------------
_WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))


class Settings(BaseSettings):
    """Application configuration loaded from environment / .env file.

    All settings have defaults matching the current hardcoded values
    so that the system behaves identically with zero configuration.
    """

    # --- Application ---
    APP_PORT: int = Field(default=8000, description="HTTP server port")
    APP_ENV: str = Field(
        default="development",
        description="Environment: 'development' or 'production'",
    )

    # --- Logging ---
    LOG_LEVEL: str = Field(default="INFO", description="Log level: DEBUG/INFO/WARNING/ERROR/CRITICAL")
    LOG_FORMAT: str = Field(
        default="text",
        description="Log format: 'text' (colored for dev) or 'json' (structured for prod)",
    )
    LOG_FILE: str = Field(
        default="",
        description="Log file path. Empty = stdout only.",
    )

    # --- Database ---
    DB_PATH: str = Field(
        default=os.path.join(_WORKSPACE_DIR, "data", "nhpc_weather.db"),
        description="SQLite database file path",
    )
    DB_CLEANUP_DAYS: int = Field(
        default=90,
        description="Delete forecast data older than this many days",
    )
    DB_BACKUP_RETAIN: int = Field(
        default=7,
        description="Number of database backups to retain",
    )

    # --- IMD API ---
    IMD_BASE_URL: str = Field(
        default="https://mausamgram.imd.gov.in",
        description="IMD Mausamgram API base URL",
    )
    IMD_REQUEST_TIMEOUT: int = Field(
        default=10,
        description="HTTP request timeout in seconds for IMD API calls",
    )
    IMD_MAX_RETRIES: int = Field(
        default=2,
        description="Maximum retry attempts for failed IMD requests",
    )
    IMD_RETRY_BACKOFF: float = Field(
        default=1.5,
        description="Exponential backoff base for IMD request retries",
    )
    IMD_CACHE_TTL: int = Field(
        default=1800,
        description="In-memory forecast cache TTL in seconds (default 30 min)",
    )

    # --- Input Validation (Geographic Bounds) ---
    LAT_MIN: float = Field(default=5.0, description="Minimum latitude (India bounds)")
    LAT_MAX: float = Field(default=40.0, description="Maximum latitude (India bounds)")
    LON_MIN: float = Field(default=65.0, description="Minimum longitude (India bounds)")
    LON_MAX: float = Field(default=100.0, description="Maximum longitude (India bounds)")
    NAME_MAX_LENGTH: int = Field(default=200, description="Maximum length for user-provided names")

    # --- Alert Thresholds ---
    ALERT_RAIN_3H_RED: float = Field(default=50.0, description="3-hour rainfall RED threshold (mm)")
    ALERT_RAIN_3H_ORANGE: float = Field(default=30.0, description="3-hour rainfall ORANGE threshold (mm)")
    ALERT_RAIN_3H_YELLOW: float = Field(default=15.0, description="3-hour rainfall YELLOW threshold (mm)")
    ALERT_RAIN_24H_RED: float = Field(default=204.5, description="24-hour rainfall RED threshold (mm)")
    ALERT_RAIN_24H_ORANGE: float = Field(default=115.6, description="24-hour rainfall ORANGE threshold (mm)")
    ALERT_RAIN_24H_YELLOW: float = Field(default=64.5, description="24-hour rainfall YELLOW threshold (mm)")
    ALERT_GUST_RED: float = Field(default=25.0, description="Wind gust RED threshold (m/s)")
    ALERT_GUST_ORANGE: float = Field(default=20.0, description="Wind gust ORANGE threshold (m/s)")
    ALERT_GUST_YELLOW: float = Field(default=15.0, description="Wind gust YELLOW threshold (m/s)")

    # --- Rate Limiting ---
    RATE_LIMIT_RPM: int = Field(
        default=60,
        description="Maximum API requests per minute per IP (0 = disabled)",
    )

    # --- Notifications (Telegram) ---
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram Bot API token")
    TELEGRAM_CHAT_ID: str = Field(default="", description="Telegram chat/channel ID")

    # --- Notifications (Slack) ---
    SLACK_WEBHOOK_URL: str = Field(default="", description="Slack incoming webhook URL")

    # --- Notifications (Email/SMTP) ---
    SMTP_SERVER: str = Field(default="", description="SMTP server hostname")
    SMTP_PORT: int = Field(default=587, description="SMTP server port")
    SMTP_USER: str = Field(default="", description="SMTP authentication username")
    SMTP_PASSWORD: str = Field(default="", description="SMTP authentication password")
    SMTP_SENDER: str = Field(default="", description="Email sender address")
    ALERT_RECIPIENT_EMAIL: str = Field(default="", description="Alert recipient email address")

    # --- Scraper ---
    SCRAPER_INTERVAL_HOURS: int = Field(
        default=6,
        description="Forecast scraper run interval in hours",
    )

    # --- Derived Paths (not from env) ---
    @property
    def WORKSPACE_DIR(self) -> str:
        return _WORKSPACE_DIR

    @property
    def WEB_DIR(self) -> str:
        return os.path.join(_WORKSPACE_DIR, "web")

    @property
    def DATA_DIR(self) -> str:
        return os.path.join(_WORKSPACE_DIR, "data")

    @property
    def KML_PATH(self) -> str:
        return os.path.join(_WORKSPACE_DIR, "Catchment_NHPC.KML")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    model_config = {
        "env_file": os.path.join(_WORKSPACE_DIR, ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",  # Don't fail on unknown env vars
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns the singleton application settings instance.

    Settings are loaded once from environment variables and the .env
    file, then cached for the lifetime of the process. Call this
    function from any module that needs configuration values.
    """
    return Settings()
