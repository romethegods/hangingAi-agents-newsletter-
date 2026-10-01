"""Outgoing email. Provider-neutral: plain SMTP works with Resend, Postmark,
SES, Mailgun and most others, so switching providers is a config change."""

import asyncio
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Protocol

from app.config import Settings, get_settings


@dataclass(slots=True)
class Message:
    to: str
    subject: str
    text: str
    html: str
    headers: dict[str, str] = field(default_factory=dict)

    def to_email(self, sender: str) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = self.to
        msg["Subject"] = self.subject
        msg["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1].rstrip(">"))
        for name, value in self.headers.items():
            msg[name] = value
        msg.set_content(self.text)
        msg.add_alternative(self.html, subtype="html")
        return msg


class EmailSender(Protocol):
    async def send(self, message: Message) -> None: ...


class OutboxSender:
    """Development: write each email to a folder instead of sending it."""

    def __init__(self, directory: str, sender: str) -> None:
        self.directory = Path(directory)
        self.sender = sender

    async def send(self, message: Message) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        safe_to = "".join(c if c.isalnum() else "_" for c in message.to)
        email = message.to_email(self.sender)
        (self.directory / f"{stamp}-{safe_to}.eml").write_bytes(bytes(email))
        (self.directory / f"{stamp}-{safe_to}.html").write_text(message.html, encoding="utf-8")


class SmtpSender:
    def __init__(self, settings: Settings) -> None:
        if not settings.smtp_host:
            raise ValueError("EMAIL_BACKEND=smtp needs SMTP_HOST")
        self.settings = settings

    def _send_blocking(self, message: Message) -> None:
        s = self.settings
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if s.smtp_username:
                smtp.login(s.smtp_username, s.smtp_password or "")
            smtp.send_message(message.to_email(s.email_from))

    async def send(self, message: Message) -> None:
        await asyncio.to_thread(self._send_blocking, message)


def get_sender(settings: Settings | None = None) -> EmailSender:
    settings = settings or get_settings()
    if settings.email_backend == "smtp":
        return SmtpSender(settings)
    return OutboxSender(settings.outbox_dir, settings.email_from)
