"""Hugging Face pages are SvelteKit apps that embed their data as JSON in
`data-props` attributes. Reading that JSON is far more stable than CSS
selectors over Tailwind class soup.
"""

import json

from selectolax.parser import HTMLParser

from app.scraping.parsers._html import parse_iso
from app.scraping.types import ContentType, Demo, DemoKind, ParseResult, Platform, RawItem, RawTool

_SUMMARY_LIMIT = 600
_THUMBNAILS = "https://cdn-thumbnails.huggingface.co/social-thumbnails"


def _props(html: str, target: str) -> dict:
    node = HTMLParser(html).css_first(f'[data-target="{target}"][data-props]')
    if node is None:
        return {}
    try:
        return json.loads(node.attributes["data-props"] or "{}")
    except json.JSONDecodeError:
        return {}


def _clip(text: str | None) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return (
        text if len(text) <= _SUMMARY_LIMIT else text[: _SUMMARY_LIMIT - 1].rsplit(" ", 1)[0] + "…"
    )


def parse_papers(html: str, base_url: str = "https://huggingface.co/papers") -> ParseResult:
    result = ParseResult()
    for entry in _props(html, "DailyPapers").get("dailyPapers", []):
        paper = entry.get("paper") or {}
        paper_id, title = paper.get("id"), paper.get("title") or entry.get("title")
        if not paper_id or not title:
            continue
        authors = [a["name"] for a in paper.get("authors", []) if a.get("name")]
        result.items.append(
            RawItem(
                url=f"https://huggingface.co/papers/{paper_id}",
                title=title,
                content_type=ContentType.PAPER,
                summary=_clip(paper.get("summary") or entry.get("summary")),
                author=", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "") or None,
                image_url=entry.get("thumbnail"),
                # The day HF featured it is what's "new" to readers; arXiv date can be weeks older.
                published_at=parse_iso(
                    paper.get("submittedOnDailyAt")
                    or entry.get("publishedAt")
                    or paper.get("publishedAt")
                ),
                engagement=paper.get("upvotes"),
                extra={
                    "arxiv_id": paper_id,
                    "github_repo": paper.get("githubRepo"),
                    "comments": entry.get("numComments"),
                },
            )
        )
    return result


def parse_models(html: str, base_url: str = "https://huggingface.co/models") -> ParseResult:
    result = ParseResult()
    for model in _props(html, "ModelList").get("initialValues", {}).get("models", []):
        model_id = model.get("id")
        if not model_id:
            continue
        details = [model.get("pipeline_tag")]
        if params := model.get("numParameters"):
            details.append(
                f"{params / 1e9:.1f}B params" if params >= 1e9 else f"{params / 1e6:.0f}M params"
            )
        result.items.append(
            RawItem(
                url=f"https://huggingface.co/{model_id}",
                title=model_id,
                content_type=ContentType.MODEL,
                summary=" · ".join(d for d in details if d) or None,
                author=model.get("author"),
                image_url=f"{_THUMBNAILS}/models/{model_id}.png",
                published_at=parse_iso(model.get("lastModified")),
                engagement=model.get("likes"),
                extra={
                    "downloads": model.get("downloads"),
                    "pipeline_tag": model.get("pipeline_tag"),
                },
            )
        )
    return result


def space_embed_url(space_id: str, sdk: str | None) -> str:
    """Official embed host for a Space: owner-name.hf.space (static Spaces: .static.hf.space)."""
    subdomain = space_id.replace("/", "-").replace("_", "-").replace(".", "-").lower()
    return (
        f"https://{subdomain}.static.hf.space"
        if sdk == "static"
        else f"https://{subdomain}.hf.space"
    )


def parse_spaces(html: str, base_url: str = "https://huggingface.co/spaces") -> ParseResult:
    """Trending Spaces: live, embeddable demo apps."""
    result = ParseResult()
    for space in _props(html, "SpaceList").get("initialValues", {}).get("spaces", []):
        space_id = space.get("id")
        if not space_id or space.get("private") or space.get("disabled"):
            continue
        if (space.get("runtime") or {}).get("stage") != "RUNNING":
            continue  # sleeping/broken apps make a bad embedded demo
        category = space.get("ai_category")
        result.tools.append(
            RawTool(
                full_name=space_id,
                platform=Platform.HUGGINGFACE,
                title=" ".join(p for p in (space.get("emoji"), space.get("title")) if p) or None,
                description=space.get("shortDescription") or space.get("ai_short_description"),
                language=space.get("sdk"),
                stars=space.get("likes") or 0,
                topics=[category.lower().replace(" ", "-")] if category else [],
                pushed_at=parse_iso(space.get("lastModified")),
                preview_image_url=f"{_THUMBNAILS}/spaces/{space_id}.png",
                demo=Demo(url=space_embed_url(space_id, space.get("sdk")), kind=DemoKind.APP),
                tags=space.get("tags") or [],
            )
        )
    return result
