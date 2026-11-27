"""Email delivery behind an adapter.

- dev_outbox: stores messages in the database (local development only; refused in staging/production).
- smtp: sends through any SMTP provider (e.g. a free-tier transactional email service) using the
  standard library only. Credentials come from environment variables, never from code.
"""
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import EmailOutbox


class EmailDeliveryError(RuntimeError):
    pass


def send_email(db: Session, to: str, subject: str, body: str) -> None:
    s = get_settings()
    if s.email_backend == "dev_outbox":
        db.add(EmailOutbox(to_address=to, subject=subject, body=body))
        return
    if s.email_backend == "smtp":
        _send_smtp(to, subject, body)
        return
    raise RuntimeError(f"Email backend '{s.email_backend}' is not implemented")


def _send_smtp(to: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain="vittasynx")
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_username:
                smtp.login(s.smtp_username, s.smtp_password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        # The recipient and subject are safe to log; the body may contain a token, so it is not.
        raise EmailDeliveryError(f"Could not send email '{subject}'") from exc
