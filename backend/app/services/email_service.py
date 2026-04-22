"""Minimal SMTP client for non-Slack digest delivery.

Designed as a best-effort fallback: if SMTP environment is not configured,
``send_email`` raises ``EmailNotConfigured`` — the caller records the event
as "skipped" and can fall back to in-app-only digests.

Env vars:
- ``CB_SMTP_HOST``           (required)
- ``CB_SMTP_PORT``           (default 587)
- ``CB_SMTP_USER`` / ``CB_SMTP_PASSWORD`` (optional)
- ``CB_SMTP_FROM``           (default: CB_SMTP_USER)
- ``CB_SMTP_USE_TLS``        (default "true")
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("collective_brain.email")


class EmailNotConfigured(RuntimeError):
    """Raised when CB_SMTP_HOST is not set — caller treats as soft-skip."""


def _is_configured() -> bool:
    return bool(os.environ.get("CB_SMTP_HOST"))


def send_email(
    *,
    to: str | list[str],
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> dict:
    """Send a single email via SMTP. Returns a small result dict.

    Raises ``EmailNotConfigured`` if no SMTP host is set.
    """
    if not _is_configured():
        raise EmailNotConfigured("CB_SMTP_HOST is not set")

    host = os.environ["CB_SMTP_HOST"]
    port = int(os.environ.get("CB_SMTP_PORT", "587"))
    user = os.environ.get("CB_SMTP_USER")
    password = os.environ.get("CB_SMTP_PASSWORD")
    sender = os.environ.get("CB_SMTP_FROM") or user or "no-reply@collective-brain.dev"
    use_tls = os.environ.get("CB_SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")

    recipients = [to] if isinstance(to, str) else list(to)
    if not recipients:
        raise ValueError("send_email requires at least one recipient")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(host, port, timeout=15) as client:
        client.ehlo()
        if use_tls:
            client.starttls()
            client.ehlo()
        if user and password:
            client.login(user, password)
        client.send_message(msg)

    logger.info(
        "Email digest delivered via SMTP host=%s port=%d recipients=%d",
        host,
        port,
        len(recipients),
    )
    return {"ok": True, "recipients": recipients, "host": host}
