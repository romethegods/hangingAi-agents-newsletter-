"""Parsers run against real pages captured with scripts/capture_fixture.py.

If a site redesign breaks one of these, re-capture the fixture and fix the parser.
"""

from pathlib import Path

import pytest

from app.scraping.registry import SOURCES_BY_SLUG
from app.scraping.relevance import is_ai_related
from app.scraping.types import ContentType

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def parse(slug: str, fixture: str):
    source = SOURCES_BY_SLUG[slug]
    return source.parser(load(fixture), source.url)


def test_github_trending() -> None:
    tools = parse("github-trending", "github_trending.html").tools
    assert len(tools) == 8
    first = tools[0]
    assert first.full_name == "debpalash/VoiceStudio"
    assert first.url == "https://github.com/debpalash/VoiceStudio"
    assert first.language == "Python"
    assert first.stars == 42_444 and first.forks == 4_987 and first.stars_today == 3_274
    assert "voice cloning" in first.description


def test_github_trending_ai_filter_drops_non_ai_repos() -> None:
    source = SOURCES_BY_SLUG["github-trending"]
    kept = {
        t.full_name
        for t in parse("github-trending", "github_trending.html").tools
        if is_ai_related(t.full_name, t.description, mode=source.ai_filter)
    }
    assert "NawfalMotii79/PLFM_RADAR" not in kept
    assert "cs341-illinois/coursebook" not in kept
    assert {"paperclipai/paperclip", "mvschwarz/openrig", "vectorize-io/hindsight"} <= kept


def test_github_topic() -> None:
    tools = parse("github-topic-ai-agents", "github_topic_ai_agents.html").tools
    assert len(tools) == 20
    first = tools[0]
    assert first.full_name == "affaan-m/ECC"
    assert first.stars == 268_742
    assert "ai-agents" in first.topics
    assert first.pushed_at is not None and first.pushed_at.tzinfo is not None


def test_huggingface_papers() -> None:
    items = parse("hf-papers", "huggingface_papers.html").items
    assert len(items) == 28
    paper = items[0]
    assert paper.content_type is ContentType.PAPER
    assert paper.url == "https://huggingface.co/papers/2609.31620"
    assert paper.title.startswith("FuseReg")
    assert paper.author.endswith("et al.")
    assert paper.engagement == 110
    assert paper.published_at.date().isoformat() == "2026-09-28"  # day featured, not arXiv date
    assert len(paper.summary) <= 600


def test_huggingface_models() -> None:
    items = parse("hf-models-trending", "huggingface_models.html").items
    assert len(items) == 30
    model = items[0]
    assert model.content_type is ContentType.MODEL
    assert model.url == "https://huggingface.co/convaiinnovations/laya"
    assert model.summary == "text-classification · 421M params"
    assert model.engagement == 4227


def test_tmz_cards_are_deduplicated_and_dated_from_url() -> None:
    items = parse("tmz", "tmz_home.html").items
    urls = [i.url for i in items]
    assert len(urls) == len(set(urls)) and len(items) >= 15
    assert all("/photos/" not in u for u in urls)
    assert all(i.published_at is not None for i in items)
    assert all(" " in i.title for i in items)  # nested headings joined with spaces


def test_tmz_strict_filter_keeps_only_ai_stories() -> None:
    kept = [
        i.title for i in parse("tmz", "tmz_home.html").items if is_ai_related(i.title, i.summary)
    ]
    assert kept == ["Bill Gates Says A.I. Could Kill At Least A Billion People"]


@pytest.mark.parametrize("slug", ["hf-papers", "hf-models-trending", "github-topic-llm", "tmz"])
def test_parsers_tolerate_unrelated_html(slug: str) -> None:
    assert (
        len(
            SOURCES_BY_SLUG[slug].parser(
                "<html><body><p>nothing here</p></body></html>", "https://x.com"
            )
        )
        == 0
    )
