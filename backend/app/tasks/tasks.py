import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.send_welcome_email", bind=True, max_retries=3)
def send_welcome_email(self, user_id: int, email: str):
    """
    Send a welcome email when SMTP is configured.
    Without SMTP settings, log a demo message so the Celery flow can be tested.
    """
    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        logger.info(
            "SMTP is not configured. Demo welcome email for user_id=%s email=%s",
            user_id,
            email,
        )
        return {"status": "skipped", "reason": "SMTP is not configured"}

    message = EmailMessage()
    message["Subject"] = "Welcome!"
    message["From"] = settings.SMTP_FROM
    message["To"] = email
    message.set_content(
        "Welcome! Your account has been created successfully."
    )

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)

    logger.info("Welcome email sent to %s (user_id=%s)", email, user_id)
    return {"status": "sent", "email": email}
