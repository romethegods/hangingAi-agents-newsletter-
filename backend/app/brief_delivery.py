"""Turn composed briefs into emails and send them once per user per local day."""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import one_click_unsubscribe_url, unsubscribe_url
from app.brief import BriefContent, compose_brief
from app.config import get_settings
from app.email import EmailSender, Message
from app.models import Brief, BriefItem, User
from app.rendering import render

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
STALE_PENDING = timedelta(minutes=15)  # a crash mid-send leaves "pending"; retry after this

_TYPE_STYLE = {
    "paper": ("Paper", "#b93b1a", "#ffffff"),
    "model": ("Model", "#e0a526", "#171614"),
    "news": ("News", "#2d4bb3", "#ffffff"),
}
_DEMO_LABEL = {"video": "Video demo", "embed": "Video demo", "gif": "GIF demo", "app": "Live app"}


def local_date(user: User, now: datetime) -> date:
    return now.astimezone(ZoneInfo(user.timezone)).date()


def is_due(user: User, now: datetime) -> bool:
    return user.brief_enabled and now.astimezone(ZoneInfo(user.timezone)).hour >= user.brief_hour


def _compact(n: float) -> str:
    for size, suffix in ((1e6, "M"), (1e3, "K")):
        if n >= size:
            return f"{n / size:.1f}".rstrip("0").rstrip(".") + suffix
    return str(round(n))


def _ago(then: datetime | None, now: datetime) -> str:
    if then is None:
        return "recently"
    hours = (now - then).total_seconds() / 3600
    if hours < 1:
        return "just now"
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours // 24)}d ago"


def _clip(text: str | None, limit: int) -> str | None:
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def build_message(user: User, brief: BriefContent, now: datetime) -> Message:
    site = get_settings().site_url
    local_now = now.astimezone(ZoneInfo(user.timezone))
    lead = brief.releases[0].tool.full_name.split("/")[-1] if brief.releases else None
    subject = (
        f"{lead} shipped {brief.releases[0].tag}, plus your AI brief"
        if lead
        else "Your AI brief for today"
    )
    topics = ", ".join(f"#{t}" for t in brief.followed_topics[:3])
    context = {
        "subject": subject,
        "dateline": local_now.strftime("%A, %B %-d, %Y"),
        "preheader": (
            f"{len(brief.releases)} releases · {len(brief.rising)} rising tools"
            f" · {len(brief.reads)} must-reads"
        ),
        "greeting": (
            f"Good morning. Here's what moved in {topics or 'the tools you follow'}."
            if brief.personalized
            else "Good morning. Follow a few tools or topics and this brief becomes yours."
        ),
        "rising_heading": f"Rising in {topics}" if topics else "Rising tools",
        "releases": [
            {
                "tool": r.tool.full_name,
                "tag": r.tag,
                "url": r.url,
                "when": _ago(r.published_at, now),
                "notes": _clip(r.notes, 180),
            }
            for r in brief.releases
        ],
        "rising": [
            {
                "name": t.title or t.full_name,
                "url": f"{site}/tools/{t.id}",
                "velocity": _compact(t.star_velocity),
                "description": _clip(t.description, 140),
            }
            for t in brief.rising
        ],
        "reads": [
            {
                "title": a.title,
                "url": f"{site}/item/{a.id}",
                "summary": _clip(a.summary, 160),
                "meta": f"{a.source.name} · {_ago(a.published_at, now)}",
                "type_label": _TYPE_STYLE.get(a.content_type, _TYPE_STYLE["news"])[0],
                "type_color": _TYPE_STYLE.get(a.content_type, _TYPE_STYLE["news"])[1],
                "type_text": _TYPE_STYLE.get(a.content_type, _TYPE_STYLE["news"])[2],
                "matched": a.id in brief.matched_article_ids,
            }
            for a in brief.reads
        ],
        "demo": (
            {
                "name": brief.demo.title or brief.demo.full_name,
                "url": f"{site}/tools/{brief.demo.id}",
                "image": brief.demo.preview_image_url
                if brief.demo.preview_image_url
                and "opengraph.githubassets.com" not in brief.demo.preview_image_url
                else None,
                "label": _DEMO_LABEL.get(brief.demo.demo_kind or "", "Demo"),
                "description": _clip(brief.demo.description, 140),
            }
            if brief.demo
            else None
        ),
        "brief_url": f"{site}/brief",
        "settings_url": f"{site}/brief#settings",
        "unsubscribe_url": unsubscribe_url(user.id),
        "cta": "Open your brief" if brief.personalized else "Pick what to follow",
        "hour_label": f"{user.brief_hour % 12 or 12} {'am' if user.brief_hour < 12 else 'pm'}",
        "timezone": user.timezone,
    }
    return Message(
        to=user.email,
        subject=subject,
        text=render("brief.txt", context),
        html=render("brief.html", context),
        headers={
            # RFC 8058 one-click unsubscribe (Gmail and Yahoo require it for bulk senders).
            "List-Unsubscribe": f"<{one_click_unsubscribe_url(user.id)}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )


async def _claim(session: AsyncSession, user: User, today: date, now: datetime) -> int | None:
    """Reserve today's brief for this user: its id, or None if it isn't ours to send."""
    brief_id = await session.scalar(
        insert(Brief)
        .values(user_id=user.id, brief_date=today, status="pending", attempts=1, created_at=now)
        .on_conflict_do_nothing(constraint="uq_briefs_user_date")
        .returning(Brief.id)
    )
    if brief_id is not None:
        return brief_id
    # Already exists: retry only failures (or a crashed send), a bounded number of times.
    return await session.scalar(
        update(Brief)
        .where(
            Brief.user_id == user.id,
            Brief.brief_date == today,
            Brief.attempts < MAX_ATTEMPTS,
            (Brief.status == "failed")
            | ((Brief.status == "pending") & (Brief.created_at < now - STALE_PENDING)),
        )
        .values(attempts=Brief.attempts + 1, status="pending", created_at=now)
        .returning(Brief.id)
    )


@dataclass(slots=True)
class DeliveryStats:
    sent: int = 0
    failed: int = 0
    skipped: int = 0


async def send_due_briefs(
    session_factory: async_sessionmaker, sender: EmailSender, now: datetime
) -> DeliveryStats:
    stats = DeliveryStats()
    async with session_factory() as session:
        # Guests read their brief on the site; only accounts with an email get it mailed.
        users = list(
            (
                await session.execute(
                    select(User).where(User.brief_enabled.is_(True), User.email.is_not(None))
                )
            ).scalars()
        )

    for user in users:
        if not is_due(user, now):
            continue
        today = local_date(user, now)
        async with session_factory() as session, session.begin():
            brief_id = await _claim(session, user, today, now)
        if brief_id is None:
            stats.skipped += 1
            continue

        try:
            async with session_factory() as session:
                content = await compose_brief(session, user, now)
                message = build_message(user, content, now)
            await sender.send(message)
        except Exception as exc:
            log.exception("brief for user %s failed", user.id)
            async with session_factory() as session, session.begin():
                await session.execute(
                    update(Brief)
                    .where(Brief.id == brief_id)
                    .values(status="failed", error=str(exc)[:2000])
                )
            stats.failed += 1
            continue

        async with session_factory() as session, session.begin():
            await session.execute(
                update(Brief)
                .where(Brief.id == brief_id)
                .values(status="sent", sent_at=now, error=None)
            )
            if items := content.items():
                await session.execute(
                    insert(BriefItem)
                    .values([{"brief_id": brief_id, "kind": k, "ref_id": i} for k, i in items])
                    .on_conflict_do_nothing()
                )
        stats.sent += 1
    return stats
