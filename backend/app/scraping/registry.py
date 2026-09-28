"""Every source HangingAi crawls. Adding a news site is one SourceDef entry."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from app.scraping.parsers import github, huggingface
from app.scraping.parsers.news_cards import CardSelectors, parse_cards
from app.scraping.relevance import AiFilter
from app.scraping.types import ParseResult

Parser = Callable[[str, str], ParseResult]


@dataclass(frozen=True, slots=True)
class SourceDef:
    slug: str
    name: str
    url: str
    parser: Parser
    interval_minutes: int = 60
    weight: float = 1.0  # editorial trust/importance, used by ranking
    ai_filter: AiFilter = AiFilter.NONE
    enabled: bool = True
    notes: str = ""


def _cards(**selectors) -> Parser:
    return partial(parse_cards, selectors=CardSelectors(**selectors))


SOURCES: tuple[SourceDef, ...] = (
    SourceDef(
        slug="hf-papers",
        name="Hugging Face Daily Papers",
        url="https://huggingface.co/papers",
        parser=huggingface.parse_papers,
        interval_minutes=180,
        weight=1.2,
    ),
    SourceDef(
        slug="hf-models-trending",
        name="Hugging Face Trending Models",
        url="https://huggingface.co/models?sort=trending",
        parser=huggingface.parse_models,
        interval_minutes=240,
    ),
    SourceDef(
        slug="github-trending",
        name="GitHub Trending",
        url="https://github.com/trending?since=daily",
        parser=github.parse_trending,
        interval_minutes=180,
        ai_filter=AiFilter.BROAD,
    ),
    *(
        SourceDef(
            slug=f"github-topic-{topic}",
            name=f"GitHub topic: {topic}",
            url=f"https://github.com/topics/{topic}",
            parser=github.parse_topic,
            interval_minutes=720,
        )
        for topic in ("ai-agents", "llm", "mcp", "rag")
    ),
    SourceDef(
        slug="tmz",
        name="TMZ",
        url="https://www.tmz.com/",
        parser=_cards(link_must_contain="tmz.com/20"),
        interval_minutes=60,
        weight=0.6,
        ai_filter=AiFilter.STRICT,
    ),
    SourceDef(
        slug="cnn-tech",
        name="CNN Tech",
        url="https://www.cnn.com/business/tech",
        parser=_cards(card="[data-component-name=card]", title=".container__headline-text"),
        ai_filter=AiFilter.STRICT,
        enabled=False,
        notes="Returns 'Unknown Error' to headless browsers and its RSS is stale since 2016. "
        "Do not bypass bot protection; re-enable only with a permitted access method.",
    ),
)

SOURCES_BY_SLUG = {s.slug: s for s in SOURCES}
