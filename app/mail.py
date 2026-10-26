"""Envío de correo opcional. Sin SMTP configurado solo se registra en log."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def send_mail(*, to: str, subject: str, body: str) -> bool:
    """Devuelve True si se envió por SMTP. False si solo se logueó."""
    to = (to or "").strip()
    if not to:
        return False

    if not smtp_configured():
        logger.info(
            "SMTP no configurado — correo a %s · %s\n%s",
            to,
            subject,
            body,
        )
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user or "noreply@siete.app"
    msg["To"] = to
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_tls:
                smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:
        logger.exception("Error enviando correo a %s", to)
        raise
