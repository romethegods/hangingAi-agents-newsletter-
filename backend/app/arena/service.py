"""Arena battles: create, run (both models at once), vote, rank.

Cost controls, all enforced before any model is called:
- prompts are length-capped and SFW-filtered, answers are token-capped
- each visitor gets `arena_battles_per_day` battles (failed ones don't count)
- the whole site stops at `arena_daily_budget_usd`, counting the worst case of
  the battle about to start, so the cap can't be overshot
"""

import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.arena import rating
from app.arena.providers import ProviderError, Usage, cost_usd, stream_answer
from app.arena.registry import MODELS, MODELS_BY_SLUG, ArenaModel, enabled_models
from app.config import Settings, get_settings
from app.models import ArenaBattle, ArenaModelStat, User
from app.scraping.relevance import is_safe_for_work

STALE_STREAMING = timedelta(minutes=5)


class ArenaError(Exception):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


# --- identity leaks -------------------------------------------------------------------

_NAMES = sorted(
    {w for m in MODELS for w in (m.name.split()[0], m.maker.split()[0])}
    | {
        "Claude",
        "Anthropic",
        "ChatGPT",
        "GPT",
        "OpenAI",
        "Gemini",
        "Gemma",
        "Google",
        "Llama",
        "Meta",
        "Qwen",
        "Alibaba",
        "DeepSeek",
        "GLM",
        "Zhipu",
        "Mistral",
        "Kimi",
        "Moonshot",
    },
    key=len,
    reverse=True,
)
# Self-identification only ("I'm Claude", "developed by Google"); merely
# discussing a model, which prompts often ask for, isn't a leak.
_SELF_ID = re.compile(
    r"\b(?:I am|I'm|my name is|as an? (?:AI|assistant|language model)[^.]{0,30}?"
    r"|(?:made|created|developed|built|trained) by)"
    r"\s+(?:an? |the )?(?:AI )?(?:model )?(?:called |named )?"
    rf"({'|'.join(map(re.escape, _NAMES))})\b",
    re.IGNORECASE,
)


def leaked_identity(*answers: str | None) -> bool:
    return any(_SELF_ID.search(a or "") for a in answers)


# --- creating ----------------------------------------------------------------------


def _day_start(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


async def battles_left(session: AsyncSession, user: User, now: datetime, settings: Settings) -> int:
    used = await session.scalar(
        select(func.count())
        .select_from(ArenaBattle)
        .where(
            ArenaBattle.user_id == user.id,
            ArenaBattle.created_at >= _day_start(now),
            ArenaBattle.status != "failed",
        )
    )
    return max(0, settings.arena_battles_per_day - used)


async def spent_today(session: AsyncSession, now: datetime) -> float:
    return float(
        await session.scalar(
            select(func.coalesce(func.sum(ArenaBattle.cost_usd), 0)).where(
                ArenaBattle.created_at >= _day_start(now)
            )
        )
    )


def worst_case_cost(a: ArenaModel, b: ArenaModel, prompt: str, settings: Settings) -> float:
    prompt_tokens = len(prompt) // 3 + 200  # generous: system prompt + tokenizer slack
    return sum(cost_usd(m, Usage(prompt_tokens, settings.arena_max_output_tokens)) for m in (a, b))


async def create_battle(
    session: AsyncSession, user: User, prompt: str, now: datetime
) -> ArenaBattle:
    settings = get_settings()
    if user.banned_at:
        raise ArenaError("you can't use the Arena right now", 403)
    prompt = prompt.strip()
    if not prompt:
        raise ArenaError("type a prompt first")
    if len(prompt) > settings.arena_max_prompt_chars:
        raise ArenaError(f"prompts are at most {settings.arena_max_prompt_chars} characters")
    if not is_safe_for_work(prompt):
        raise ArenaError("keep it safe for work")

    models = enabled_models(settings)
    if len(models) < 2:
        raise ArenaError("the Arena needs at least two models; it isn't open yet", 503)
    if await battles_left(session, user, now, settings) <= 0:
        raise ArenaError(
            f"that's your {settings.arena_battles_per_day} battles for today; come back tomorrow",
            429,
        )

    stats = {s.slug: s for s in (await session.execute(select(ArenaModelStat))).scalars()}
    a, b = rating.pick_pair(
        models, [stats[m.slug].battles if m.slug in stats else 0 for m in models]
    )
    if (
        await spent_today(session, now) + worst_case_cost(a, b, prompt, settings)
        > settings.arena_daily_budget_usd
    ):
        raise ArenaError("the Arena has hit today's budget; it reopens at midnight UTC", 503)

    battle = ArenaBattle(
        user_id=user.id, prompt=prompt, model_a=a.slug, model_b=b.slug, created_at=now
    )
    session.add(battle)
    await session.flush()
    return battle


# --- running ----------------------------------------------------------------------------


@dataclass(slots=True)
class _Side:
    text: str = ""
    usage: Usage | None = None
    error: str | None = None


async def run_battle(
    session_factory: async_sessionmaker, battle_id: int, user_id: int
) -> AsyncIterator[dict]:
    """Stream both answers as events: {"side", "text"} deltas, then {"side", "done"}
    or {"side", "error"}, then {"status"}. Only the battle's owner can run it, once."""
    now = datetime.now(UTC)
    async with session_factory() as session, session.begin():
        battle = await session.scalar(
            update(ArenaBattle)
            .where(
                ArenaBattle.id == battle_id,
                ArenaBattle.user_id == user_id,
                (ArenaBattle.status == "pending")
                # A stream whose connection died mid-way can be restarted.
                | (
                    (ArenaBattle.status == "streaming")
                    & (ArenaBattle.created_at < now - STALE_STREAMING)
                ),
            )
            .values(status="streaming")
            .returning(ArenaBattle)
        )
    if battle is None:
        raise ArenaError("this battle isn't yours, or it already ran", 409)

    settings = get_settings()
    models = {"a": MODELS_BY_SLUG[battle.model_a], "b": MODELS_BY_SLUG[battle.model_b]}
    sides = {"a": _Side(), "b": _Side()}
    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def answer(side: str) -> None:
        try:
            async for piece in stream_answer(
                models[side], battle.prompt, settings.arena_max_output_tokens
            ):
                if isinstance(piece, Usage):
                    sides[side].usage = piece
                else:
                    sides[side].text += piece
                    await queue.put({"side": side, "text": piece})
            note = sides[side].usage.note if sides[side].usage else None
            await queue.put({"side": side, "done": True, **({"note": note} if note else {})})
        except ProviderError as exc:
            sides[side].error = str(exc)
            await queue.put({"side": side, "error": str(exc)})

    tasks = [asyncio.create_task(answer(side)) for side in ("a", "b")]
    finished = 0
    completed = False
    try:
        while finished < 2:
            event = await queue.get()
            if "done" in event or "error" in event:
                finished += 1
            yield event
        completed = True
    finally:
        for task in tasks:
            task.cancel()
        failed = not completed or any(s.error or not s.text.strip() for s in sides.values())
        spent = sum(cost_usd(models[k], s.usage) for k, s in sides.items() if s.usage)
        # Saved even if the reader disconnected (shielded from cancellation), so
        # the spend is counted and the battle doesn't stay "streaming".
        await asyncio.shield(_save(session_factory, battle_id, sides, spent, failed, completed))
    yield {"status": "failed" if failed else "ready"}


async def _save(
    session_factory,
    battle_id: int,
    sides: dict[str, _Side],
    spent: float,
    failed: bool,
    completed: bool,
) -> None:
    error = next((s.error for s in sides.values() if s.error), None)
    if not completed:
        error = "the connection closed before both answers finished"
    async with session_factory() as session, session.begin():
        await session.execute(
            update(ArenaBattle)
            .where(ArenaBattle.id == battle_id)
            .values(
                response_a=sides["a"].text,
                response_b=sides["b"].text,
                cost_usd=spent,
                status="failed" if failed else "ready",
                error=error if failed else None,
                completed_at=datetime.now(UTC),
            )
        )


# --- voting -------------------------------------------------------------------------------


@dataclass(slots=True)
class VoteResult:
    battle: ArenaBattle
    counted: bool  # False when an answer revealed its identity
    rating_a: float
    rating_b: float


async def _stat(session: AsyncSession, slug: str) -> ArenaModelStat:
    await session.execute(insert(ArenaModelStat).values(slug=slug).on_conflict_do_nothing())
    # Row lock: concurrent votes on the same model apply one after another.
    return await session.scalar(
        select(ArenaModelStat).where(ArenaModelStat.slug == slug).with_for_update()
    )


async def vote(
    session: AsyncSession, user: User, battle_id: int, choice: str, now: datetime
) -> VoteResult:
    if choice not in rating.OUTCOME:
        raise ArenaError("vote a, b, tie or bad")
    battle = await session.scalar(
        select(ArenaBattle).where(ArenaBattle.id == battle_id).with_for_update()
    )
    if battle is None or battle.user_id != user.id:
        raise ArenaError("battle not found", 404)
    if battle.status != "ready":
        raise ArenaError(
            "this battle can't take a vote" if battle.status != "voted" else "you already voted",
            409,
        )

    # Lock in a fixed order (by slug) so two votes can never deadlock.
    first, second = sorted([battle.model_a, battle.model_b])
    locked = {first: await _stat(session, first), second: await _stat(session, second)}
    stat_a, stat_b = locked[battle.model_a], locked[battle.model_b]

    battle.identity_leak = leaked_identity(battle.response_a, battle.response_b)
    counted = not battle.identity_leak
    if counted:
        outcome = rating.OUTCOME[choice]
        new_a, new_b = rating.update(
            stat_a.rating, stat_b.rating, outcome, stat_a.battles, stat_b.battles
        )
        battle.rating_change_a, battle.rating_change_b = (
            new_a - stat_a.rating,
            new_b - stat_b.rating,
        )
        stat_a.rating, stat_b.rating = new_a, new_b
        for stat, score in ((stat_a, outcome), (stat_b, 1 - outcome)):
            stat.battles += 1
            stat.wins += score == 1.0
            stat.losses += score == 0.0
            stat.ties += score == 0.5
            stat.updated_at = now
    battle.vote = choice
    battle.status = "voted"
    battle.voted_at = now
    return VoteResult(battle, counted, stat_a.rating, stat_b.rating)


# --- reading -------------------------------------------------------------------------------


@dataclass(slots=True)
class Standing:
    model: ArenaModel
    rating: float
    battles: int
    wins: int
    losses: int
    ties: int

    @property
    def provisional(self) -> bool:
        return self.battles < rating.PROVISIONAL_BATTLES


async def leaderboard(session: AsyncSession) -> list[Standing]:
    """Enabled models plus anything that has battled before (retired models keep their record)."""
    stats = {s.slug: s for s in (await session.execute(select(ArenaModelStat))).scalars()}
    live = {m.slug for m in enabled_models(get_settings())}
    rows = []
    for model in MODELS:
        stat = stats.get(model.slug)
        if model.slug not in live and not (stat and stat.battles):
            continue
        rows.append(
            Standing(
                model,
                stat.rating if stat else rating.START_RATING,
                stat.battles if stat else 0,
                stat.wins if stat else 0,
                stat.losses if stat else 0,
                stat.ties if stat else 0,
            )
        )
    # Unrated models sink below rated ones at the same score.
    return sorted(rows, key=lambda r: (-r.rating, -r.battles, r.model.name))
