"""Crawl scheduling with a min-heap keyed by next run time.

pop_due() is O(k log n) for k due sources; failing sources back off
exponentially so a broken site isn't hammered every interval.
"""

import heapq
import itertools
from dataclasses import dataclass


@dataclass(slots=True)
class _Entry:
    interval: float
    failures: int = 0


class CrawlScheduler:
    def __init__(self, max_backoff_seconds: float = 24 * 3600) -> None:
        self.max_backoff = max_backoff_seconds
        self._heap: list[tuple[float, int, str]] = []
        self._entries: dict[str, _Entry] = {}
        self._tiebreak = itertools.count()

    def __len__(self) -> int:
        return len(self._entries)

    def add(self, slug: str, interval_seconds: float, first_run_at: float) -> None:
        self._entries[slug] = _Entry(interval=interval_seconds)
        self._push(slug, first_run_at)

    def _push(self, slug: str, run_at: float) -> None:
        heapq.heappush(self._heap, (run_at, next(self._tiebreak), slug))

    def pop_due(self, now: float) -> list[str]:
        due = []
        while self._heap and self._heap[0][0] <= now:
            _, _, slug = heapq.heappop(self._heap)
            if slug in self._entries:
                due.append(slug)
        return due

    def reschedule(self, slug: str, now: float, *, succeeded: bool) -> float:
        entry = self._entries[slug]
        entry.failures = 0 if succeeded else entry.failures + 1
        delay = min(entry.interval * (2**entry.failures), max(self.max_backoff, entry.interval))
        self._push(slug, now + delay)
        return now + delay

    def seconds_until_next(self, now: float) -> float | None:
        return max(0.0, self._heap[0][0] - now) if self._heap else None
