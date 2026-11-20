import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


def send_email(to_email: str, subject: str, body: str) -> None:
    if not all((settings.smtp_host, settings.smtp_username, settings.smtp_password, settings.smtp_from_email)):
        raise RuntimeError("SMTP is not configured. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD and SMTP_FROM_EMAIL.")

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=20) as server:
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
