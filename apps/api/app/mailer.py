import logging
import smtplib
from email.message import EmailMessage

from .config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    """Sends a plain-text email over SMTP, or — if smtp_host is unset (the
    default) — just logs it. That fallback keeps password-reset usable in
    dev/CI without any mail server configured, at the cost of the link only
    being visible in the server log rather than delivered; set SMTP_HOST
    (and friends) in production so it actually reaches the user's inbox.
    """
    if not settings.smtp_host:
        logger.warning('SMTP_HOST not set; email to %s not sent. Subject: %s\n%s', to, subject, body)
        return
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = settings.smtp_from
    msg['To'] = to
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)
