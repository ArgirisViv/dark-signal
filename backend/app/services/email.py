import smtplib
from email.message import EmailMessage
from app.core.config import settings


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        raise RuntimeError("SMTP settings are not configured")

    from_addr = settings.SMTP_FROM
    recipient = to_email
    subject_line = subject
    if settings.SMTP_SANDBOX_MODE and settings.SMTP_SANDBOX_RECIPIENT:
        recipient = settings.SMTP_SANDBOX_RECIPIENT
        subject_line = f"[SANDBOX] {subject} (original: {to_email})"

    message = EmailMessage()
    message["Subject"] = subject_line
    message["From"] = from_addr
    message["To"] = recipient
    message.set_content(text_body or "")

    if html_body:
        message.add_alternative(html_body, subtype="html")

    if settings.SMTP_SSL:
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)

    try:
        if settings.SMTP_TLS and not settings.SMTP_SSL:
            server.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(message)
    finally:
        server.quit()
