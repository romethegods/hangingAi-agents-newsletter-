"""Arena API. Battles are blind until voted; the stream is the owner's only."""

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth
from app.arena import service
from app.arena.registry import MODELS_BY_SLUG, enabled_models
from app.config import get_settings
from app.db import SessionLocal, get_session
from app.models import ArenaBattle
from app.schemas import (
    ArenaModelOut,
    ArenaStatusOut,
    BattleIn,
    BattleOut,
    GalleryBattleOut,
    StandingOut,
    VoteIn,
)

router = APIRouter(prefix="/api/arena")
Session = Annotated[AsyncSession, Depends(get_session)]
# Overridable in tests, which use their own database.
session_factory = SessionLocal


def _model(slug: str) -> ArenaModelOut:
    m = MODELS_BY_SLUG[slug]
    return ArenaModelOut(slug=m.slug, name=m.name, maker=m.maker, open_weights=m.open_weights)


def _out(battle: ArenaBattle, viewer_id: int | None) -> BattleOut:
    revealed = battle.status == "voted"
    return BattleOut(
        id=battle.id,
        prompt=battle.prompt,
        status=battle.status,
        response_a=battle.response_a,
        response_b=battle.response_b,
        error=battle.error,
        vote=battle.vote,
        created_at=battle.created_at,
        mine=battle.user_id == viewer_id,
        public=battle.public,
        model_a=_model(battle.model_a) if revealed else None,
        model_b=_model(battle.model_b) if revealed else None,
        rating_change_a=battle.rating_change_a if revealed else None,
        rating_change_b=battle.rating_change_b if revealed else None,
        identity_leak=battle.identity_leak if revealed else False,
    )


def _refuse(exc: service.ArenaError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


@router.get("/status", response_model=ArenaStatusOut)
async def status(session: Session, viewer: auth.MaybeUser) -> ArenaStatusOut:
    settings = get_settings()
    models = len(enabled_models(settings))
    left = (
        await service.battles_left(session, viewer, datetime.now(UTC), settings) if viewer else None
    )
    return ArenaStatusOut(
        open=models >= 2,
        models=models,
        battles_left=left,
        battles_per_day=settings.arena_battles_per_day,
    )


@router.post("/battles", response_model=BattleOut, status_code=201)
async def create(body: BattleIn, session: Session, user: auth.CurrentUser) -> BattleOut:
    try:
        battle = await service.create_battle(session, user, body.prompt, datetime.now(UTC))
    except service.ArenaError as exc:
        raise _refuse(exc) from exc
    await session.commit()
    return _out(battle, user.id)


@router.get("/battles/{battle_id}", response_model=BattleOut)
async def get_battle(battle_id: int, session: Session, viewer: auth.MaybeUser) -> BattleOut:
    battle = await session.get(ArenaBattle, battle_id)
    viewer_id = viewer.id if viewer else None
    if battle is None or (battle.user_id != viewer_id and not battle.public):
        raise HTTPException(404, "battle not found")
    return _out(battle, viewer_id)


@router.get("/battles/{battle_id}/stream")
async def stream(battle_id: int, user: auth.CurrentUser) -> StreamingResponse:
    """Server-sent events: both answers arrive token by token, side by side."""
    events = service.run_battle(session_factory, battle_id, user.id)
    try:
        first = await anext(events)  # surfaces "not yours / already ran" as a normal HTTP error
    except service.ArenaError as exc:
        raise _refuse(exc) from exc

    async def body():
        yield f"data: {json.dumps(first)}\n\n"
        async for event in events:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # proxies must not buffer
    )


@router.post("/battles/{battle_id}/vote", response_model=BattleOut)
async def cast_vote(
    battle_id: int, body: VoteIn, session: Session, user: auth.CurrentUser
) -> BattleOut:
    try:
        result = await service.vote(session, user, battle_id, body.choice, datetime.now(UTC))
    except service.ArenaError as exc:
        raise _refuse(exc) from exc
    await session.commit()
    return _out(result.battle, user.id)


@router.post("/battles/{battle_id}/share", response_model=BattleOut)
async def share(battle_id: int, session: Session, user: auth.CurrentUser) -> BattleOut:
    battle = await session.get(ArenaBattle, battle_id)
    if battle is None or battle.user_id != user.id:
        raise HTTPException(404, "battle not found")
    if battle.status != "voted":
        raise HTTPException(409, "vote first; shared battles show which models fought")
    battle.public = True
    await session.commit()
    return _out(battle, user.id)


@router.get("/leaderboard", response_model=list[StandingOut])
async def leaderboard(session: Session) -> list[StandingOut]:
    return [
        StandingOut(
            **_model(s.model.slug).model_dump(),
            rating=round(s.rating, 1),
            battles=s.battles,
            wins=s.wins,
            losses=s.losses,
            ties=s.ties,
            win_rate=round((s.wins + s.ties / 2) / s.battles, 3) if s.battles else None,
            provisional=s.provisional,
        )
        for s in await service.leaderboard(session)
    ]


@router.get("/gallery", response_model=list[GalleryBattleOut])
async def gallery(session: Session, limit: int = 12) -> list[GalleryBattleOut]:
    rows = await session.execute(
        select(ArenaBattle)
        .where(ArenaBattle.public.is_(True), ArenaBattle.status == "voted")
        .order_by(ArenaBattle.voted_at.desc())
        .limit(min(max(limit, 1), 50))
    )
    return [
        GalleryBattleOut(
            id=b.id,
            prompt=b.prompt if len(b.prompt) <= 200 else b.prompt[:199] + "…",
            vote=b.vote,
            model_a=_model(b.model_a),
            model_b=_model(b.model_b),
            voted_at=b.voted_at,
        )
        for b in rows.scalars()
    ]
