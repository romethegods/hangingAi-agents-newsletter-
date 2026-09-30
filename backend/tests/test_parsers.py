"""Parsers run against real pages captured with scripts/capture_fixture.py.

If a site redesign breaks one of these, re-capture the fixture and fix the parser.
"""

from pathlib import Path

import pytest

from app.scraping.parsers.github import parse_repo_media, youtube_embed_url
from app.scraping.registry import SOURCES_BY_SLUG
from app.scraping.relevance import is_ai_related
from app.scraping.types import ContentType, Demo, DemoKind, Platform

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


# --- demos & images --------------------------------------------------------


@pytest.mark.parametrize(
    "repo, kind, url",
    [
        # Demo video beats every image in the README.
        (
            "vectorize-io/hindsight",
            DemoKind.VIDEO,
            "https://github.com/user-attachments/assets/923b798d-3581-4897-bb62-9cfa5a931682",
        ),
        # Animated GIF tour; /owner/repo/raw/... rewritten to the raw CDN (robots disallows /raw/).
        (
            "debpalash/VoiceStudio",
            DemoKind.GIF,
            "https://raw.githubusercontent.com/debpalash/VoiceStudio/main/docs/media/electron/voicestudio.gif",
        ),
        # No video or GIF: first content image, skipping the logo and every badge.
        (
            "browser-use/browser-use",
            DemoKind.IMAGE,
            "https://github.com/user-attachments/assets/9955dda9-ede3-4971-8ee0-91cbc3850125",
        ),
    ],
)
def test_readme_demo_picker(repo: str, kind: DemoKind, url: str) -> None:
    html = load(f"github_repo_{repo.replace('/', '_', 1)}.html")
    media = parse_repo_media(html, f"https://github.com/{repo}")
    assert media.demo == Demo(url=url, kind=kind)
    # Only owner-uploaded previews are kept; GitHub's generated text card is dropped.
    if repo == "vectorize-io/hindsight":
        assert media.preview_image_url is None
    else:
        assert media.preview_image_url.startswith(
            "https://repository-images.githubusercontent.com/"
        )


def test_readme_demo_picker_rejects_badges_logos_and_expiring_links() -> None:
    html = """<article class="markdown-body">
      <img src="https://camo.githubusercontent.com/x" data-canonical-src="https://img.shields.io/badge/x">
      <img src="/o/r/raw/main/logo.png" alt="Project logo">
      <img src="https://private-user-images.githubusercontent.com/1/a.png?jwt=abc">
      <img src="/o/r/raw/main/icon.svg">
    </article>"""
    assert parse_repo_media(html, "https://github.com/o/r").demo is None


def test_huggingface_spaces() -> None:
    tools = parse("hf-spaces-trending", "huggingface_spaces.html").tools
    assert len(tools) == 24  # every trending Space in the fixture is RUNNING
    space = tools[0]
    assert space.platform is Platform.HUGGINGFACE
    assert space.full_name == "multimodalart/jev-decision-index"
    assert space.title == "🔬 Jev Decision Index"
    assert space.url == "https://huggingface.co/spaces/multimodalart/jev-decision-index"
    assert space.demo == Demo(
        url="https://multimodalart-jev-decision-index.static.hf.space", kind=DemoKind.APP
    )
    gradio = next(t for t in tools if t.full_name == "Qwen/Qwen-Image-2.1")
    assert gradio.demo.url == "https://qwen-qwen-image-2-1.hf.space"
    assert space.preview_image_url.endswith(
        "/social-thumbnails/spaces/multimodalart/jev-decision-index.png"
    )


def test_article_images() -> None:
    model = parse("hf-models-trending", "huggingface_models.html").items[0]
    assert model.image_url.endswith("/social-thumbnails/models/convaiinnovations/laya.png")
    tmz = parse("tmz", "tmz_home.html").items[0]
    assert tmz.image_url.endswith("_md.jpg")  # upgraded from the card's tiny _xs size


def test_readme_youtube_demo_beats_gif_and_sponsor_images_are_skipped() -> None:
    # Camo-proxied images are judged by their original URL (data-canonical-src).
    html = """<article class="markdown-body">
      <a href="https://github.com/sponsors/x"><img src="https://camo.githubusercontent.com/a"
         data-canonical-src="https://cdn.example.com/growth/sponsor/kimi-en.png"></a>
      <a href="https://www.youtube.com/watch?v=1p-SMEiK6Kg"><img src="https://camo.githubusercontent.com/b"
         data-canonical-src="https://i.ytimg.com/vi/1p-SMEiK6Kg/maxresdefault.jpg"></a>
      <img src="/o/r/raw/main/demo.gif">
    </article>"""
    assert parse_repo_media(html, "https://github.com/o/r").demo == Demo(
        url="https://www.youtube-nocookie.com/embed/1p-SMEiK6Kg", kind=DemoKind.EMBED
    )


@pytest.mark.parametrize(
    "href, embed",
    [
        ("https://www.youtube.com/watch?v=1p-SMEiK6Kg", "1p-SMEiK6Kg"),
        ("https://www.youtube.com/watch?feature=share&v=1p-SMEiK6Kg", "1p-SMEiK6Kg"),
        ("https://youtu.be/1p-SMEiK6Kg?t=30", "1p-SMEiK6Kg"),
        ("https://www.youtube.com/shorts/1p-SMEiK6Kg", "1p-SMEiK6Kg"),
        ("https://vimeo.com/123", None),
        (None, None),
    ],
)
def test_youtube_embed_url(href, embed) -> None:
    expected = f"https://www.youtube-nocookie.com/embed/{embed}" if embed else None
    assert youtube_embed_url(href) == expected
