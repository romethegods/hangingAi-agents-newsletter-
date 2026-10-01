"""Passwordless sign-in: one-time email links, then a session token.

Only SHA-256 hashes of tokens are stored, so a leaked database can't be used
to sign in. Links are single-use and expire after `login_link_minutes`.
Signing in and signing up are the same step.
"""

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlencode

from fastapi import Depends, Header, HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.community import merge_guest, new_handle
from app.config import get_settings
from app.db import get_session
from app.email import Message
from app.models import LoginToken, User, UserSession
from app.rendering import render

EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
MAX_LINKS_PER_WINDOW = 3  # per address per link lifetime; stops mail-bombing one inbox


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email: str) -> str | None:
    email = email.strip().lower()
    return email if len(email) <= 320 and EMAIL_PATTERN.match(email) else None


def safe_next(path: str | None) -> str:
    """Only same-site relative paths, so a sign-in link can't redirect off-site."""
    if path and path.startswith("/") and not path.startswith("//") and "\\" not in path:
        return path
    return "/brief"


async def create_login_link(
    session: AsyncSession, email: str, next_path: str | None, now: datetime
) -> Message | None:
    """The sign-in email to send, or None if this address has asked too often."""
    settings = get_settings()
    window = timedelta(minutes=settings.login_link_minutes)
    recent = await session.scalar(
        select(func.count())
        .select_from(LoginToken)
        .where(LoginToken.email == email, LoginToken.created_at > now - window)
    )
    if recent >= MAX_LINKS_PER_WINDOW:
        return None

    token = secrets.token_urlsafe(32)
    session.add(
        LoginToken(
            token_hash=hash_token(token), email=email, created_at=now, expires_at=now + window
        )
    )
    link = f"{settings.site_url}/auth/verify?" + urlencode(
        {"token": token, "next": safe_next(next_path)}
    )
    context = {"link": link, "minutes": settings.login_link_minutes, "site_url": settings.site_url}
    return Message(
        to=email,
        subject="Your HangingAi sign-in link",
        text=render("login.txt", context),
        html=render("login.html", context),
    )


@dataclass(slots=True)
class NewSession:
    token: str
    expires_at: datetime
    user: User


def _new_session(session: AsyncSession, user: User, now: datetime, days: int) -> NewSession:
    token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(days=days)
    session.add(UserSession(token_hash=hash_token(token), user_id=user.id, expires_at=expires_at))
    return NewSession(token=token, expires_at=expires_at, user=user)


async def create_guest(session: AsyncSession, now: datetime) -> NewSession:
    """A guest account: a handle like hanging-1234 and a long-lived session, no email."""
    user = User(handle=await new_handle(session), created_at=now)
    session.add(user)
    await session.flush()
    return _new_session(session, user, now, get_settings().guest_session_days)


async def redeem_login_link(
    session: AsyncSession, token: str, now: datetime, current: User | None = None
) -> NewSession | None:
    """Finish an email sign-in. A guest who does this keeps everything they did:
    a new email is attached to their guest account; an email that already has an
    account absorbs the guest's follows, votes and comments."""
    # Atomically claim the token: a link works exactly once, even if clicked twice at once.
    email = await session.scalar(
        update(LoginToken)
        .where(
            LoginToken.token_hash == hash_token(token),
            LoginToken.used_at.is_(None),
            LoginToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(LoginToken.email)
    )
    if email is None:
        return None

    existing = await session.scalar(select(User).where(User.email == email))
    guest = current if current is not None and current.is_guest else None
    if existing is None and guest is not None:
        guest.email = email
        user = guest
    elif existing is None:
        user = User(handle=await new_handle(session), email=email, created_at=now)
        session.add(user)
        await session.flush()
    else:
        if guest is not None:
            await merge_guest(session, guest, existing)
        user = existing
    return _new_session(session, user, now, get_settings().session_days)


async def end_session(session: AsyncSession, token: str) -> None:
    await session.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


async def current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    token = _bearer(authorization)
    if token:
        found = await session.scalar(
            select(UserSession).where(
                UserSession.token_hash == hash_token(token),
                UserSession.expires_at > datetime.now(UTC),
            )
        )
        if found:
            return found.user
    raise HTTPException(401, "sign in required", headers={"WWW-Authenticate": "Bearer"})


CurrentUser = Annotated[User, Depends(current_user)]


async def optional_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    """Reading is open to everyone; this just tells us who's asking, if anyone."""
    try:
        return await current_user(session, authorization)
    except HTTPException:
        return None


MaybeUser = Annotated[User | None, Depends(optional_user)]


def is_admin(user: User) -> bool:
    return bool(user.email) and user.email in {e.lower() for e in get_settings().admin_emails}


# --- unsubscribe links: must work from an email without signing in ------------


def unsubscribe_signature(user_id: int) -> str:
    key = get_settings().secret_key.encode()
    digest = hmac.new(key, f"unsubscribe:{user_id}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:18]).decode()


def unsubscribe_url(user_id: int) -> str:
    query = urlencode({"u": user_id, "t": unsubscribe_signature(user_id)})
    return f"{get_settings().site_url}/unsubscribe?{query}"


def one_click_unsubscribe_url(user_id: int) -> str:
    """List-Unsubscribe target that mail clients POST to (/api shares the site domain)."""
    query = urlencode({"u": user_id, "t": unsubscribe_signature(user_id)})
    return f"{get_settings().site_url}/api/unsubscribe/one-click?{query}"


def check_unsubscribe(user_id: int, signature: str) -> bool:
    return hmac.compare_digest(unsubscribe_signature(user_id), signature)
