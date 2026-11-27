"""Centralised configuration. Values come from environment variables (see .env.example)."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VX_", env_file=".env", extra="ignore")

    # Fail-safe default: an unconfigured deployment is treated as production and refuses unsafe settings.
    environment: str = "production"  # development | test | staging | production
    database_url: str = "postgresql+psycopg://vittasynx:devpassword@localhost:5432/vittasynx"

    # Sessions
    session_cookie_name: str = "vx_session"
    csrf_cookie_name: str = "vx_csrf"
    session_idle_minutes: int = 60
    session_absolute_hours: int = 12
    cookie_secure: bool = False  # must be True outside local development

    # Login protection
    max_failed_logins: int = 10
    lockout_minutes: int = 15

    # Rate limiting (per IP and per account). Behind a trusted proxy set trust_forwarded_for=true.
    rate_limit_enabled: bool = True
    trust_forwarded_for: bool = False
    login_limit_per_ip: int = 30          # per 15 minutes
    login_limit_per_account: int = 10     # per 15 minutes
    register_limit_per_ip: int = 10       # per hour
    reset_limit_per_ip: int = 10          # per hour
    reset_limit_per_account: int = 3      # per hour
    mfa_limit_per_session: int = 10       # per 15 minutes
    accept_invite_limit_per_ip: int = 20  # per hour

    # MFA (decision D-18)
    require_mfa_for_privileged: bool = True

    # Files and imports
    file_storage_dir: str = "./var/files"
    max_upload_bytes: int = 5 * 1024 * 1024
    max_import_rows: int = 20_000
    max_xlsx_uncompressed_bytes: int = 50 * 1024 * 1024

    # Email: "dev_outbox" stores messages in the database (local development only); "smtp" sends them.
    email_backend: str = "dev_outbox"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    email_from: str = "Vittasynx <no-reply@localhost>"

    # File storage: "local" (private directory) or "database" (PostgreSQL, for hosts without persistent disk).
    storage_backend: str = "local"
    app_base_url: str = "http://localhost:3000"

    # CORS: the frontend proxies /api, so normally empty.
    cors_origins: list[str] = []

    @field_validator("environment")
    @classmethod
    def _env(cls, v: str) -> str:
        allowed = {"development", "test", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {sorted(allowed)}")
        return v

    def validate_for_runtime(self) -> None:
        """Refuse unsafe configuration outside development/test."""
        if self.environment in {"staging", "production"}:
            if not self.cookie_secure:
                raise RuntimeError("VX_COOKIE_SECURE must be true in staging/production")
            if self.email_backend == "dev_outbox":
                raise RuntimeError("dev_outbox email backend is not allowed in staging/production")
            if self.email_backend == "smtp" and not self.smtp_host:
                raise RuntimeError("VX_SMTP_HOST is required when VX_EMAIL_BACKEND=smtp")
            if "devpassword" in self.database_url:
                raise RuntimeError("Development database credentials are not allowed in staging/production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
