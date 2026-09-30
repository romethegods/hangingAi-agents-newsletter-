from datetime import UTC, datetime, timedelta

import pytest

from app.ranking import diversified_top_k, hot_score, star_velocity, top_k
from app.scraping.canonical import canonicalize_url, url_hash
from app.scraping.minhash import MinHashLSH, minhash, similarity
from app.scraping.relevance import AiFilter, is_ai_related, is_safe_for_work
from app.scraping.scheduler import CrawlScheduler
from app.token_bucket import TokenBucket

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


# --- canonical URLs -------------------------------------------------------


@pytest.mark.parametrize(
    "a, b",
    [
        ("http://www.tmz.com/2026/09/27/story/", "https://tmz.com/2026/09/27/story"),
        ("https://x.com/a?utm_source=tw&id=5&fbclid=abc", "https://x.com/a?id=5"),
        ("https://x.com/a?b=2&a=1", "https://x.com/a?a=1&b=2"),
        ("https://X.com:443/a#comments", "https://x.com/a"),
    ],
)
def test_equivalent_urls_share_a_hash(a: str, b: str) -> None:
    assert canonicalize_url(a) == canonicalize_url(b)
    assert url_hash(canonicalize_url(a)) == url_hash(canonicalize_url(b))


def test_distinct_urls_stay_distinct() -> None:
    assert canonicalize_url("https://x.com/a?id=1") != canonicalize_url("https://x.com/a?id=2")
    assert canonicalize_url("https://x.com:8080/a") == "https://x.com:8080/a"


# --- minhash --------------------------------------------------------------


@pytest.mark.parametrize(
    "a, b",
    [
        (
            "Nvidia unveils new AI chip for data centers at annual developer conference",
            "Nvidia unveils new AI chip for data centers at annual developer conference today",
        ),
        (
            "Meta open-sources Llama 5 with 1M context",
            "Meta open sources Llama 5 with 1M token context",
        ),
    ],
)
def test_minhash_flags_lightly_edited_headlines(a: str, b: str) -> None:
    index = MinHashLSH()
    index.add(1, minhash(a))
    assert index.find_near(minhash(b)) == 1


@pytest.mark.parametrize(
    "a, b",
    [
        ("OpenAI releases GPT-6 model", "OpenAI releases GPT-7 model"),
        ("OpenAI releases new reasoning model", "Taylor Swift debuts music video at the VMAs"),
    ],
)
def test_minhash_keeps_different_stories_apart(a: str, b: str) -> None:
    index = MinHashLSH()
    index.add(1, minhash(a))
    assert index.find_near(minhash(b)) is None


def test_minhash_properties() -> None:
    sig = minhash("Anthropic releases Claude")
    assert (
        similarity(sig, minhash("claude RELEASES anthropic!")) == 1.0
    )  # set-based, case-insensitive
    assert all(0 <= v < 2**61 for v in sig)  # fits Postgres BIGINT
    assert minhash("the and of") is None  # nothing but stopwords


# --- token bucket ---------------------------------------------------------


def test_token_bucket_enforces_rate() -> None:
    clock = FakeClock()
    bucket = TokenBucket(rate=0.5, capacity=1, clock=clock)  # one request every 2s
    assert bucket.try_acquire()
    assert not bucket.try_acquire()
    assert bucket.seconds_until_available() == pytest.approx(2.0)
    clock.t += 2.0
    assert bucket.try_acquire()


# --- scheduler ------------------------------------------------------------


def test_scheduler_returns_due_sources_in_time_order() -> None:
    s = CrawlScheduler()
    s.add("late", 60, first_run_at=30)
    s.add("early", 60, first_run_at=10)
    s.add("future", 60, first_run_at=500)
    assert s.pop_due(now=100) == ["early", "late"]
    assert s.seconds_until_next(now=100) == 400


def test_scheduler_backs_off_exponentially_and_resets_on_success() -> None:
    s = CrawlScheduler(max_backoff_seconds=1000)
    s.add("src", 100, first_run_at=0)
    s.pop_due(0)
    assert s.reschedule("src", 0, succeeded=False) == 200
    s.pop_due(200)
    assert s.reschedule("src", 200, succeeded=False) == 600
    s.pop_due(600)
    assert s.reschedule("src", 600, succeeded=False) == 1400  # 100 * 2**3
    s.pop_due(1400)
    assert s.reschedule("src", 1400, succeeded=False) == 2400  # 100 * 2**4 = 1600, capped at 1000
    s.pop_due(2400)
    assert s.reschedule("src", 2400, succeeded=True) == 2500


# --- relevance ------------------------------------------------------------


@pytest.mark.parametrize(
    "text, strict, broad",
    [
        ("Bill Gates Says A.I. Could Kill At Least A Billion People", True, True),
        ("OpenAI and Anthropic sign new deal", True, True),
        ("人生进阶 AI学习 指南", True, True),
        ("Supermodel lands new talent agent", False, True),  # why news uses STRICT
        ("Multi-agent harness that runs Claude Code and Codex together", False, True),
        ("Taylor Swift debuts music video at VMAs", False, False),
        ("Open-source 10.5 GHz phased array RADAR system", False, False),
        ("PAID influencer drama", False, False),
    ],
)
def test_relevance_filter(text: str, strict: bool, broad: bool) -> None:
    assert is_ai_related(text, mode=AiFilter.STRICT) is strict
    assert is_ai_related(text, mode=AiFilter.BROAD) is broad
    assert is_ai_related(text, mode=AiFilter.NONE)


@pytest.mark.parametrize(
    "text, safe",
    [
        ("abenzerps/Qwen-Image-2.1-Uncensored-GGUF", False),
        ("Pepe104/MiniMax-H3-Turbo-Lora-UNCENSORED", False),
        ("NSFW image generator", False),
        ("Qwen/Qwen-Image-2.1", True),
        ("Strip whitespace from LLM output", True),
        ("Stripe payments agent", True),
    ],
)
def test_safe_for_work_filter(text: str, safe: bool) -> None:
    assert is_safe_for_work(text) is safe


def test_safe_for_work_honors_hub_content_tags() -> None:
    assert not is_safe_for_work("Harmless title", tags=["gradio", "not-for-all-audiences"])


# --- ranking --------------------------------------------------------------


def test_hot_score_decays_with_age_and_grows_with_engagement() -> None:
    fresh = hot_score(NOW, NOW)
    day_old = hot_score(NOW - timedelta(hours=24), NOW)
    assert day_old == pytest.approx(fresh / 2)
    assert hot_score(NOW, NOW, engagement=100) > fresh
    assert hot_score(NOW, NOW, source_weight=2.0) == pytest.approx(2 * fresh)


def test_top_k() -> None:
    assert top_k([3, 9, 1, 7], 2, key=float) == [9, 7]


def test_diversified_top_k_caps_each_group() -> None:
    items = [("model", 10), ("model", 9), ("model", 8), ("paper", 2), ("paper", 1)]
    picked = diversified_top_k(items, 4, key=lambda x: x[1], group=lambda x: x[0], max_per_group=2)
    assert picked == [("model", 10), ("model", 9), ("paper", 2), ("paper", 1)]


def test_diversified_top_k_backfills_when_one_group_runs_out() -> None:
    items = [("model", 10), ("model", 9), ("model", 8), ("paper", 1)]
    picked = diversified_top_k(items, 4, key=lambda x: x[1], group=lambda x: x[0], max_per_group=2)
    assert picked == [("model", 10), ("model", 9), ("paper", 1), ("model", 8)]


def test_star_velocity_uses_sliding_window() -> None:
    snapshots = [
        (NOW - timedelta(days=30), 0),  # outside the 7-day window, ignored
        (NOW - timedelta(days=4), 1000),
        (NOW - timedelta(days=2), 1500),
        (NOW, 2000),
    ]
    assert star_velocity(snapshots, NOW) == pytest.approx(250.0)


def test_star_velocity_falls_back_without_enough_history() -> None:
    assert star_velocity([(NOW, 10)], NOW, fallback=42.0) == 42.0
    assert star_velocity([(NOW - timedelta(hours=1), 10), (NOW, 20)], NOW) is None
