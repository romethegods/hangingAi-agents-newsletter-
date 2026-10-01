"""Scoring functions for the feed and the tools directory. Pure, so they're easy to test."""

import bisect
import heapq
import math
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timedelta


def hot_score(
    published_at: datetime,
    now: datetime,
    *,
    source_weight: float = 1.0,
    engagement: int | None = None,
    votes: int = 0,
    half_life_hours: float = 24.0,
) -> float:
    """Exponential time decay (score halves every half_life_hours), boosted by
    log-engagement at the source and log-upvotes from HangingAi readers. Logs keep
    one viral item (or one brigade) from drowning everything else."""
    age_hours = max(0.0, (now - published_at).total_seconds() / 3600)
    decay = 0.5 ** (age_hours / half_life_hours)
    community = 1 + math.log1p(max(0, votes))
    return source_weight * (1 + math.log1p(max(0, engagement or 0))) * community * decay


def top_k[T](items: Iterable[T], k: int, key: Callable[[T], float]) -> list[T]:
    """O(n log k) with a bounded heap, instead of sorting all n items."""
    return heapq.nlargest(k, items, key=key)


def diversified_top_k[T](
    items: Iterable[T],
    k: int,
    key: Callable[[T], float],
    group: Callable[[T], str],
    max_per_group: int,
) -> list[T]:
    """Top k by score, but no group (e.g. content type) takes more than max_per_group
    slots while other groups still have items. Pops from a max-heap: O(n + k log n)."""
    heap = [(-key(item), i, item) for i, item in enumerate(items)]
    heapq.heapify(heap)
    picked: list[T] = []
    overflow: list[T] = []  # capped-out items, used only if the feed would come up short
    counts: dict[str, int] = {}
    while heap and len(picked) < k:
        _, _, item = heapq.heappop(heap)
        g = group(item)
        if counts.get(g, 0) < max_per_group:
            counts[g] = counts.get(g, 0) + 1
            picked.append(item)
        else:
            overflow.append(item)
    return picked + overflow[: k - len(picked)]


def star_velocity(
    snapshots: Sequence[tuple[datetime, int]],
    now: datetime,
    *,
    window: timedelta = timedelta(days=7),
    min_span: timedelta = timedelta(hours=12),
    fallback: float | None = None,
) -> float | None:
    """Stars gained per day over the sliding window, from snapshots sorted by time.

    Binary-searches for the oldest snapshot inside the window. With too little
    history (< min_span) we return `fallback`, e.g. GitHub's "stars today", or None.
    """
    if len(snapshots) < 2:
        return fallback
    times = [t for t, _ in snapshots]
    start = bisect.bisect_left(times, now - window)
    if start >= len(snapshots) - 1:
        return fallback
    (t0, s0), (t1, s1) = snapshots[start], snapshots[-1]
    span = t1 - t0
    if span < min_span:
        return fallback
    return max(0.0, (s1 - s0) / (span.total_seconds() / 86400))
