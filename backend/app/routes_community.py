"""Comments, reports, votes and moderation. Open to guests; see app/community.py."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth, community
from app.db import get_session
from app.models import Comment, User
from app.presence import presence
from app.schemas import CommentIn, CommentOut, CommentsOut, ModerationItem, ReportIn, VoteOut

router = APIRouter(prefix="/api")
Session = Annotated[AsyncSession, Depends(get_session)]
TargetKind = Literal["article", "tool"]
VoteKind = Literal["article", "tool", "comment"]


def _refuse(exc: community.CommunityError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


@router.get("/comments/{kind}/{target_id}", response_model=CommentsOut)
async def list_comments(
    kind: TargetKind,
    target_id: int,
    session: Session,
    viewer: auth.MaybeUser,
    x_viewer_id: Annotated[str | None, Header()] = None,
) -> CommentsOut:
    """A post's chat room. An open chat window polls this with a random per-tab
    X-Viewer-Id, which also counts it toward "N here now"."""
    rows = list(
        (
            await session.execute(
                select(Comment)
                .where(Comment.target_kind == kind, Comment.target_id == target_id)
                .order_by(Comment.created_at)
            )
        ).scalars()
    )
    ids = [c.id for c in rows]
    votes = await community.vote_counts(session, "comment", ids)
    mine = await community.my_votes(session, viewer, "comment", ids)
    admin = viewer is not None and auth.is_admin(viewer)

    def out(c: Comment) -> CommentOut:
        readable = c.status == "visible" or (admin and c.status == "hidden")
        return CommentOut(
            id=c.id,
            parent_id=c.parent_id,
            author=c.user.handle if c.status != "removed" else "[removed]",
            body=c.body if readable else None,
            status=c.status,
            created_at=c.created_at,
            votes=votes.get(c.id, 0),
            voted=c.id in mine,
            mine=viewer is not None and c.user_id == viewer.id,
        )

    by_id = {c.id: out(c) for c in rows}
    top: list[CommentOut] = []
    for c in rows:
        if c.parent_id and c.parent_id in by_id:
            by_id[c.parent_id].replies.append(by_id[c.id])
        else:
            top.append(by_id[c.id])
    # Best first; a thread whose top comment was removed but has replies stays in place.
    top.sort(key=lambda c: (c.status != "visible", -c.votes, c.created_at))
    top = [c for c in top if c.status != "removed" or c.replies]
    visible = sum(1 for c in rows if c.status == "visible")
    here = presence.touch(f"{kind}:{target_id}", x_viewer_id)
    return CommentsOut(count=visible, comments=top, here=here)


@router.post("/comments", response_model=CommentOut, status_code=201)
async def create_comment(body: CommentIn, session: Session, user: auth.CurrentUser) -> CommentOut:
    if body.target_kind not in ("article", "tool"):
        raise HTTPException(422, "comments go on articles or tools")
    try:
        comment = await community.post_comment(
            session,
            user,
            body.target_kind,
            body.target_id,
            body.body,
            body.parent_id,
            datetime.now(UTC),
        )
    except community.CommunityError as exc:
        raise _refuse(exc) from exc
    await session.commit()
    return CommentOut(
        id=comment.id,
        parent_id=comment.parent_id,
        author=user.handle,
        body=comment.body,
        status=comment.status,
        created_at=comment.created_at,
        votes=0,
        voted=False,
        mine=True,
    )


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(comment_id: int, session: Session, user: auth.CurrentUser) -> None:
    try:
        await community.remove_own_comment(session, user, comment_id)
    except community.CommunityError as exc:
        raise _refuse(exc) from exc
    await session.commit()


@router.post("/comments/{comment_id}/report", status_code=202)
async def report(comment_id: int, body: ReportIn, session: Session, user: auth.CurrentUser) -> dict:
    try:
        hidden = await community.report_comment(session, user, comment_id, body.reason)
    except community.CommunityError as exc:
        raise _refuse(exc) from exc
    await session.commit()
    return {"ok": True, "hidden": hidden}


@router.post("/votes/{kind}/{target_id}", response_model=VoteOut)
async def vote(kind: VoteKind, target_id: int, session: Session, user: auth.CurrentUser) -> VoteOut:
    try:
        voted = await community.toggle_vote(session, user, kind, target_id)
    except community.CommunityError as exc:
        raise _refuse(exc) from exc
    await session.commit()
    counts = await community.vote_counts(session, kind, [target_id])
    return VoteOut(voted=voted, votes=counts.get(target_id, 0))


@router.get("/votes/{kind}/{target_id}", response_model=VoteOut)
async def vote_state(
    kind: VoteKind, target_id: int, session: Session, viewer: auth.MaybeUser
) -> VoteOut:
    counts = await community.vote_counts(session, kind, [target_id])
    mine = await community.my_votes(session, viewer, kind, [target_id])
    return VoteOut(voted=target_id in mine, votes=counts.get(target_id, 0))


# --- moderation ------------------------------------------------------------------


async def admin_user(user: auth.CurrentUser) -> User:
    if not auth.is_admin(user):
        raise HTTPException(403, "moderators only")
    return user


Admin = Annotated[User, Depends(admin_user)]


@router.get("/mod/queue", response_model=list[ModerationItem])
async def moderation_queue(session: Session, _: Admin) -> list[ModerationItem]:
    rows = await session.execute(
        select(Comment)
        .where(
            (Comment.status == "hidden")
            | ((Comment.status == "visible") & (Comment.report_count > 0))
        )
        .order_by(Comment.status.desc(), Comment.report_count.desc(), Comment.created_at.desc())
        .limit(200)
    )
    return [
        ModerationItem(
            id=c.id,
            target_kind=c.target_kind,
            target_id=c.target_id,
            author=c.user.handle,
            author_id=c.user_id,
            body=c.body,
            status=c.status,
            report_count=c.report_count,
            created_at=c.created_at,
        )
        for c in rows.scalars()
    ]


@router.post("/mod/comments/{comment_id}/{action}", status_code=204)
async def moderate(
    comment_id: int, action: Literal["restore", "remove"], session: Session, _: Admin
) -> None:
    values = (
        {"status": "visible", "report_count": 0} if action == "restore" else {"status": "removed"}
    )
    result = await session.execute(update(Comment).where(Comment.id == comment_id).values(**values))
    if result.rowcount == 0:
        raise HTTPException(404, "comment not found")
    await session.commit()


@router.post("/mod/users/{user_id}/ban", status_code=204)
async def ban(user_id: int, session: Session, moderator: Admin) -> None:
    """Stops posting and voting, and removes their comments."""
    if user_id == moderator.id:
        raise HTTPException(422, "you can't ban yourself")
    result = await session.execute(
        update(User).where(User.id == user_id).values(banned_at=datetime.now(UTC))
    )
    if result.rowcount == 0:
        raise HTTPException(404, "user not found")
    await session.execute(
        update(Comment).where(Comment.user_id == user_id).values(status="removed")
    )
    await session.commit()
