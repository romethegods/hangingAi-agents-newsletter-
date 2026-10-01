"""Accounts, follows and the daily brief."""

from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth, community
from app.brief import compose_brief
from app.db import get_session
from app.email import get_sender
from app.models import Follow, Tool, User
from app.schemas import (
    BriefArticle,
    BriefOut,
    FollowsOut,
    LoginRequest,
    ReleaseOut,
    SessionOut,
    SettingsIn,
    ToolOut,
    UnsubscribeRequest,
    UserOut,
    VerifyRequest,
)

router = APIRouter(prefix="/api")
Session = Annotated[AsyncSession, Depends(get_session)]
TOPIC_SLUG_MAX = 64


@router.post("/auth/request-link", status_code=202)
async def request_link(body: LoginRequest, session: Session) -> dict:
    """Always answers the same way, so it can't be used to learn who has an account."""
    email = auth.normalize_email(body.email)
    if email is None:
        raise HTTPException(422, "enter a valid email address")
    message = await auth.create_login_link(session, email, body.next, datetime.now(UTC))
    await session.commit()
    if message is not None:
        await get_sender().send(message)
    return {"ok": True}


@router.post("/guest", response_model=SessionOut, status_code=201)
async def guest(session: Session) -> SessionOut:
    """Called the first time a visitor follows, votes or comments; no sign-up."""
    created = await auth.create_guest(session, datetime.now(UTC))
    await session.commit()
    return SessionOut(
        session_token=created.token,
        expires_at=created.expires_at,
        user=UserOut.model_validate(created.user),
    )


@router.post("/auth/verify", response_model=SessionOut)
async def verify(body: VerifyRequest, session: Session, current: auth.MaybeUser) -> SessionOut:
    created = await auth.redeem_login_link(session, body.token, datetime.now(UTC), current)
    if created is None:
        raise HTTPException(400, "this sign-in link is invalid, used or expired")
    await session.commit()
    return SessionOut(
        session_token=created.token,
        expires_at=created.expires_at,
        user=UserOut.model_validate(created.user),
    )


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, session: Session, user: auth.CurrentUser) -> None:
    token = auth._bearer(request.headers.get("authorization"))
    if token:
        await auth.end_session(session, token)
        await session.commit()


@router.get("/me", response_model=UserOut)
async def me(user: auth.CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(body: SettingsIn, session: Session, user: auth.CurrentUser) -> User:
    values = body.model_dump(exclude_none=True)
    if "timezone" in values and values["timezone"] not in available_timezones():
        raise HTTPException(422, "unknown timezone")
    if (handle := values.pop("handle", None)) is not None:
        try:
            await community.rename(session, user, handle)
        except community.CommunityError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
    if values:
        await session.execute(update(User).where(User.id == user.id).values(**values))
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/me/follows", response_model=FollowsOut)
async def follows(session: Session, user: auth.CurrentUser) -> FollowsOut:
    rows = (
        await session.execute(select(Follow.kind, Follow.target).where(Follow.user_id == user.id))
    ).all()
    tool_ids = [int(t) for k, t in rows if k == "tool" and t.isdigit()]
    tools = (
        await session.execute(select(Tool).where(Tool.id.in_(tool_ids)).order_by(Tool.stars.desc()))
    ).scalars()
    return FollowsOut(
        tools=[ToolOut.model_validate(t) for t in tools],
        topics=sorted(t for k, t in rows if k == "topic"),
    )


async def _target(session: AsyncSession, kind: str, target: str) -> str:
    if kind == "tool":
        if not target.isdigit() or await session.get(Tool, int(target)) is None:
            raise HTTPException(404, "tool not found")
        return target
    if kind == "topic":
        slug = target.strip().lower()
        if not slug or len(slug) > TOPIC_SLUG_MAX or not all(c.isalnum() or c == "-" for c in slug):
            raise HTTPException(422, "topics are lowercase letters, digits and dashes")
        return slug
    raise HTTPException(404, "you can follow a tool or a topic")


@router.put("/me/follows/{kind}/{target}", status_code=204)
async def follow(kind: str, target: str, session: Session, user: auth.CurrentUser) -> None:
    target = await _target(session, kind, target)
    await session.execute(
        insert(Follow).values(user_id=user.id, kind=kind, target=target).on_conflict_do_nothing()
    )
    await session.commit()


@router.delete("/me/follows/{kind}/{target}", status_code=204)
async def unfollow(kind: str, target: str, session: Session, user: auth.CurrentUser) -> None:
    await session.execute(
        delete(Follow).where(
            Follow.user_id == user.id, Follow.kind == kind, Follow.target == target.lower()
        )
    )
    await session.commit()


@router.get("/me/brief", response_model=BriefOut)
async def my_brief(session: Session, user: auth.CurrentUser) -> BriefOut:
    """Today's brief, composed live. The emailed copy is the same composition."""
    brief = await compose_brief(session, user, datetime.now(UTC))
    return BriefOut(
        personalized=brief.personalized,
        followed_topics=brief.followed_topics,
        releases=[ReleaseOut.model_validate(r) for r in brief.releases],
        rising=[ToolOut.model_validate(t) for t in brief.rising],
        reads=[
            BriefArticle.model_validate(a).model_copy(
                update={"matched": a.id in brief.matched_article_ids}
            )
            for a in brief.reads
        ],
        demo=ToolOut.model_validate(brief.demo) if brief.demo else None,
    )


async def _unsubscribe(session: AsyncSession, user_id: int, signature: str) -> None:
    if not auth.check_unsubscribe(user_id, signature):
        raise HTTPException(400, "this unsubscribe link is invalid")
    await session.execute(update(User).where(User.id == user_id).values(brief_enabled=False))
    await session.commit()


@router.post("/unsubscribe", status_code=204)
async def unsubscribe(body: UnsubscribeRequest, session: Session) -> None:
    await _unsubscribe(session, body.u, body.t)


@router.post("/unsubscribe/one-click", status_code=204)
async def unsubscribe_one_click(session: Session, u: int, t: str) -> None:
    """RFC 8058: mail clients POST here directly when the reader hits "Unsubscribe".

    The body is always "List-Unsubscribe=One-Click"; the signed query identifies the user.
    """
    await _unsubscribe(session, u, t)
