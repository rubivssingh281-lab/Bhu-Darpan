"""Application configuration, loaded from environment / .env file."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the Backend directory (one level up from app/)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_int(name: str, default: int, minimum: int | None = None,
              maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class Settings:
    """Runtime settings with sensible defaults so the app runs with zero config."""

    def __init__(self) -> None:
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = _env_int("PORT", 8000, 1, 65535)

        self.jwt_secret: str = os.getenv(
            "JWT_SECRET", "bhu-darpan-dev-secret-change-me"
        )
        self.jwt_algorithm: str = "HS256"
        self.jwt_expire_minutes: int = _env_int("JWT_EXPIRE_MINUTES", 1440, 1)

        self.mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.db_name: str = os.getenv("DB_NAME", "bhudarpan")

        self.seg_clusters: int = _env_int("SEG_CLUSTERS", 6, 1)

        # Near-real-time refresh & memory envelope: Render Free tier has a strict 512 MB RAM cap.
        is_render = os.getenv("RENDER", "").lower() in ("1", "true", "yes")
        self.low_memory_mode: bool = os.getenv(
            "LOW_MEMORY", "true" if is_render else "false"
        ).lower() in ("1", "true", "yes")
        default_img_dim = 512 if self.low_memory_mode else 900
        self.max_image_dim: int = _env_int("MAX_IMAGE_DIM", default_img_dim, 1)

        default_refresh = "0" if is_render else "6"
        self.auto_refresh_hours: float = max(
            0.0, _env_float("AUTO_REFRESH_HOURS", float(default_refresh))
        )

        # --- Email / OTP (SMTP) --------------------------------------------- #
        self.app_name: str = os.getenv("APP_NAME", "Bhū-Darpan")
        self.smtp_host: str = os.getenv("SMTP_HOST", "").strip()
        self.smtp_port: int = _env_int("SMTP_PORT", 587, 1, 65535)
        self.smtp_user: str = os.getenv("SMTP_USER", "").strip()
        self.smtp_pass: str = os.getenv("SMTP_PASS", "").strip()
        self.smtp_from: str = os.getenv("SMTP_FROM", "").strip() or self.smtp_user
        self.smtp_use_ssl: bool = os.getenv("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")
        self.smtp_starttls: bool = os.getenv("SMTP_STARTTLS", "true").lower() in ("1", "true", "yes")
        self.otp_expire_minutes: int = _env_int("OTP_EXPIRE_MINUTES", 10, 1)
        # Anti-abuse: throttle how often a code can be (re)sent to one address.
        self.otp_resend_cooldown_seconds: int = _env_int(
            "OTP_RESEND_COOLDOWN_SECONDS", 30, 0
        )
        self.otp_max_sends: int = _env_int("OTP_MAX_SENDS", 6, 1)
        self.otp_max_attempts: int = _env_int("OTP_MAX_ATTEMPTS", 5, 1)
        # When SMTP isn't configured, the API returns the OTP in the response and
        # logs it to the console so the app is fully demo-able offline.
        self.otp_dev_mode: bool = os.getenv("OTP_DEV_MODE", "").lower() in ("1", "true", "yes")

        # --- Weather news headlines (optional third-party) ---------------- #
        self.news_provider: str = os.getenv("NEWS_PROVIDER", "newsapi").strip().lower()
        self.news_api_key: str = os.getenv("NEWS_API_KEY", "").strip()

        # --- Firebase Web Auth (server-side token verification) ----------- #
        self.firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "bhu-darpan").strip()
        self.firebase_api_key: str = os.getenv("FIREBASE_API_KEY", "").strip()

        self.base_dir: Path = BASE_DIR
        self.storage_dir: Path = BASE_DIR / "storage"
        self.uploads_dir: Path = self.storage_dir / "uploads"
        self.masks_dir: Path = self.storage_dir / "masks"
        self.reports_dir: Path = self.storage_dir / "reports"

        origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8010")
        self.cors_origins: list[str] = [o.strip() for o in origins.split(",") if o.strip()]
        self.cors_origin_regex: str | None = os.getenv("CORS_ORIGIN_REGEX", r"^https:\/\/.*\.vercel\.app$")

        # Ensure storage directories exist
        for d in (self.uploads_dir, self.masks_dir, self.reports_dir):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_pass)

    @property
    def news_configured(self) -> bool:
        return bool(self.news_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
