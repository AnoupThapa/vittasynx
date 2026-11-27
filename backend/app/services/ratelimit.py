"""Fixed-window rate limiting stored in PostgreSQL, so limits hold across several app instances.

Keys never contain raw secrets: emails are hashed before use.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


def client_ip(request: Request) -> str:
    if get_settings().trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def hashed(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()[:32]


def hit(db: Session, key: str, limit: int, window_seconds: int) -> None:
    """Count one attempt; raise 429 when the limit for the current window is exceeded.

    The counter is committed in its own statement so failed requests still count.
    """
    if not get_settings().rate_limit_enabled:
        return
    now = datetime.now(timezone.utc)
    window = datetime.fromtimestamp(int(now.timestamp()) // window_seconds * window_seconds, timezone.utc)
    count = db.execute(
        text(
            "INSERT INTO rate_limit_hits (key, window_start, count) VALUES (:k, :w, 1) "
            "ON CONFLICT (key, window_start) DO UPDATE SET count = rate_limit_hits.count + 1 "
            "RETURNING count"
        ),
        {"k": key[:200], "w": window},
    ).scalar_one()
    db.commit()
    if count > limit:
        retry = window_seconds - (int(now.timestamp()) % window_seconds)
        raise RateLimited("Too many attempts. Please wait and try again.", details={"retry_after_seconds": retry})


def cleanup(db: Session, older_than_seconds: int = 86400) -> int:
    res = db.execute(text("DELETE FROM rate_limit_hits WHERE window_start < now() - make_interval(secs => :s)"),
                     {"s": older_than_seconds})
    db.commit()
    return res.rowcount
