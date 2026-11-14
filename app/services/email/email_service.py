import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
)


def send_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> None:
    """Send an email through Brevo SMTP."""

    required_settings = {
        "SMTP_USERNAME": SMTP_USERNAME,
        "SMTP_PASSWORD": SMTP_PASSWORD,
        "SMTP_FROM_EMAIL": SMTP_FROM_EMAIL,
    }

    missing = [
        name for name, value in required_settings.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            f"Missing SMTP configuration: {', '.join(missing)}"
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM_EMAIL))
    message["To"] = to_email

    message.set_content(body_text)

    if body_html:
        message.add_alternative(body_html, subtype="html")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()

            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)

    except (smtplib.SMTPException, OSError) as exc:
        raise RuntimeError(f"Email delivery failed: {exc}") from exc