"""Guests, handles, comments, reports and votes: participation without sign-up.

Anyone can comment and vote. The first time they act, they get a guest account
with a handle like hanging-1234, kept in a long-lived cookie. Abuse is handled
by filters at write time, per-visitor rate limits, and community reports that
hide a comment until a moderator reviews it.
"""

import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, Comment, CommentReport, Tool, User, Vote
from app.scraping.relevance import is_safe_for_work

HANDLE_PREFIX = "hanging-"
AUTO_HANDLE = re.compile(r"^hanging-\d+$")
HANDLE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,23}$")
RESERVED_HANDLES = re.compile(
    r"^(admin|administrator|mod|moderator|hangingai|hanging-ai|staff|support|system|root)$"
)

REPORTS_TO_HIDE = 3  # distinct reporters before a comment is hidden pending review
MAX_LINKS = 2  # spam lives on links
MAX_COMMENTS_PER_HOUR = 20
COMMENT_MAX_CHARS = 2000
_LINK = re.compile(r"https?://|www\.", re.IGNORECASE)


class CommunityError(Exception):
    """A user-facing reason an action was refused."""

    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


# --- handles ---------------------------------------------------------------------


async def new_handle(session: AsyncSession) -> str:
    """hanging-1234; when four digits get crowded, longer numbers keep names unique."""
    for digits in (4, 4, 4, 5, 5, 6, 6, 8):
        candidate = (
            f"{HANDLE_PREFIX}{secrets.randbelow(9 * 10 ** (digits - 1)) + 10 ** (digits - 1)}"
        )
        if await session.scalar(select(User.id).where(User.handle == candidate)) is None:
            return candidate
    raise RuntimeError("could not find a free handle")


def clean_handle(raw: str) -> str:
    handle = raw.strip().lower().replace(" ", "-")
    if not HANDLE_PATTERN.match(handle):
        raise CommunityError("names are 3–24 characters: letters, digits, - and _")
    if RESERVED_HANDLES.match(handle) or not is_safe_for_work(handle.replace("-", " ")):
        raise CommunityError("that name isn't available")
    return handle


async def rename(session: AsyncSession, user: User, raw: str) -> None:
    handle = clean_handle(raw)
    taken = await session.scalar(select(User.id).where(User.handle == handle, User.id != user.id))
    if taken:
        raise CommunityError("that name is taken", status=409)
    user.handle = handle


# --- comments --------------------------------------------------------------------


async def _target_exists(session: AsyncSession, kind: str, target_id: int) -> bool:
    model = {"article": Article, "tool": Tool}.get(kind)
    return model is not None and await session.get(model, target_id) is not None


def _check_body(body: str) -> str:
    body = body.strip()
    if not body:
        raise CommunityError("write something first")
    if len(body) > COMMENT_MAX_CHARS:
        raise CommunityError(f"comments are at most {COMMENT_MAX_CHARS} characters")
    if len(_LINK.findall(body)) > MAX_LINKS:
        raise CommunityError(f"at most {MAX_LINKS} links per comment")
    if not is_safe_for_work(body):
        raise CommunityError("keep it safe for work")
    return body


async def post_comment(
    session: AsyncSession,
    user: User,
    kind: str,
    target_id: int,
    body: str,
    parent_id: int | None,
    now: datetime,
) -> Comment:
    if user.banned_at:
        raise CommunityError("you can't post right now", status=403)
    body = _check_body(body)
    if not await _target_exists(session, kind, target_id):
        raise CommunityError("nothing to comment on here", status=404)
    if parent_id is not None:
        parent = await session.get(Comment, parent_id)
        if parent is None or (parent.target_kind, parent.target_id) != (kind, target_id):
            raise CommunityError("that comment doesn't exist", status=404)
        parent_id = parent.parent_id or parent.id  # threads stay one level deep

    recent = (
        select(func.count())
        .select_from(Comment)
        .where(Comment.user_id == user.id, Comment.created_at > now - timedelta(hours=1))
    )
    if await session.scalar(recent) >= MAX_COMMENTS_PER_HOUR:
        raise CommunityError("you're commenting a lot; take a short break", status=429)
    duplicate = await session.scalar(
        select(Comment.id).where(
            Comment.user_id == user.id,
            Comment.body == body,
            Comment.created_at > now - timedelta(days=1),
        )
    )
    if duplicate:
        raise CommunityError("you already posted that", status=409)

    comment = Comment(
        target_kind=kind,
        target_id=target_id,
        parent_id=parent_id,
        user_id=user.id,
        body=body,
        created_at=now,
    )
    session.add(comment)
    await session.flush()
    return comment


async def remove_own_comment(session: AsyncSession, user: User, comment_id: int) -> None:
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.user_id != user.id:
        raise CommunityError("that comment isn't yours", status=404)
    comment.status = "removed"  # keeps replies in place; the text is gone


async def report_comment(
    session: AsyncSession, user: User, comment_id: int, reason: str | None
) -> bool:
    """Returns True when this report hid the comment."""
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.status == "removed":
        raise CommunityError("that comment doesn't exist", status=404)
    if comment.user_id == user.id:
        raise CommunityError("you can't report your own comment")
    inserted = await session.scalar(
        insert(CommentReport)
        .values(comment_id=comment_id, user_id=user.id, reason=(reason or "")[:200] or None)
        .on_conflict_do_nothing()
        .returning(CommentReport.comment_id)
    )
    if inserted is None:
        return False  # one report per person
    count = await session.scalar(
        update(Comment)
        .where(Comment.id == comment_id)
        .values(report_count=Comment.report_count + 1)
        .returning(Comment.report_count)
    )
    if count >= REPORTS_TO_HIDE and comment.status == "visible":
        await session.execute(
            update(Comment).where(Comment.id == comment_id).values(status="hidden")
        )
        return True
    return False


# --- votes -----------------------------------------------------------------------


async def toggle_vote(session: AsyncSession, user: User, kind: str, target_id: int) -> bool:
    """Upvote, or remove the upvote if it's already there. Returns the new state."""
    if user.banned_at:
        raise CommunityError("you can't vote right now", status=403)
    if kind == "comment":
        if await session.get(Comment, target_id) is None:
            raise CommunityError("that comment doesn't exist", status=404)
    elif not await _target_exists(session, kind, target_id):
        raise CommunityError("nothing to vote on here", status=404)
    added = await session.scalar(
        insert(Vote)
        .values(user_id=user.id, target_kind=kind, target_id=target_id)
        .on_conflict_do_nothing()
        .returning(Vote.user_id)
    )
    if added is None:
        await session.execute(
            Vote.__table__.delete().where(
                Vote.user_id == user.id, Vote.target_kind == kind, Vote.target_id == target_id
            )
        )
        return False
    return True


async def vote_counts(session: AsyncSession, kind: str, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = await session.execute(
        select(Vote.target_id, func.count())
        .where(Vote.target_kind == kind, Vote.target_id.in_(ids))
        .group_by(Vote.target_id)
    )
    return {target_id: count for target_id, count in rows}


async def comment_counts(session: AsyncSession, kind: str, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = await session.execute(
        select(Comment.target_id, func.count())
        .where(Comment.target_kind == kind, Comment.target_id.in_(ids), Comment.status == "visible")
        .group_by(Comment.target_id)
    )
    return {target_id: count for target_id, count in rows}


async def my_votes(session: AsyncSession, user: User | None, kind: str, ids: list[int]) -> set[int]:
    if user is None or not ids:
        return set()
    rows = await session.execute(
        select(Vote.target_id).where(
            Vote.user_id == user.id, Vote.target_kind == kind, Vote.target_id.in_(ids)
        )
    )
    return set(rows.scalars())


# --- merging a guest into an existing account --------------------------------------


@dataclass(slots=True)
class MergeResult:
    follows: int
    votes: int
    comments: int


async def merge_guest(session: AsyncSession, guest: User, into: User) -> MergeResult:
    """A guest signed in with an email that already has an account: keep everything."""
    from app.models import Follow  # local import: avoids a cycle with brief/auth modules

    follows = await session.execute(
        insert(Follow)
        .from_select(
            ["user_id", "kind", "target", "created_at"],
            select(
                func.cast(into.id, Follow.user_id.type),
                Follow.kind,
                Follow.target,
                Follow.created_at,
            ).where(Follow.user_id == guest.id),
        )
        .on_conflict_do_nothing()
    )
    votes = await session.execute(
        insert(Vote)
        .from_select(
            ["user_id", "target_kind", "target_id", "created_at"],
            select(
                func.cast(into.id, Vote.user_id.type),
                Vote.target_kind,
                Vote.target_id,
                Vote.created_at,
            ).where(Vote.user_id == guest.id),
        )
        .on_conflict_do_nothing()
    )
    comments = await session.execute(
        update(Comment).where(Comment.user_id == guest.id).values(user_id=into.id)
    )
    # A name the guest chose beats an account's still-automatic hanging-1234 name.
    keep_guest_name = AUTO_HANDLE.match(into.handle) and not AUTO_HANDLE.match(guest.handle)
    chosen = guest.handle
    await session.delete(guest)  # cascades its leftover follows/votes/sessions
    if keep_guest_name:
        await session.flush()  # free the guest's handle before reusing it
        into.handle = chosen
    return MergeResult(follows.rowcount, votes.rowcount, comments.rowcount)
