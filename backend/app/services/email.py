"""Email delivery behind an adapter. Only the development outbox exists today; a real provider
(SMTP or API) must be configured before staging/production (Settings.validate_for_runtime refuses otherwise)."""
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import EmailOutbox


def send_email(db: Session, to: str, subject: str, body: str) -> None:
    backend = get_settings().email_backend
    if backend == "dev_outbox":
        db.add(EmailOutbox(to_address=to, subject=subject, body=body))
        return
    raise RuntimeError(f"Email backend '{backend}' is not implemented")
