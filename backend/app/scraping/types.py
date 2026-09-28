"""Plain data passed between parsers and the persistence pipeline.

Parsers turn HTML into these objects and know nothing about the database;
the pipeline stores them and knows nothing about HTML.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ContentType(StrEnum):
    NEWS = "news"
    PAPER = "paper"
    MODEL = "model"


@dataclass(slots=True)
class RawItem:
    url: str
    title: str
    content_type: ContentType
    summary: str | None = None
    author: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None
    engagement: int | None = None  # likes / upvotes, whatever the source exposes
    extra: dict = field(default_factory=dict)


@dataclass(slots=True)
class RawTool:
    full_name: str  # "owner/repo"
    description: str | None = None
    language: str | None = None
    stars: int = 0
    forks: int | None = None
    stars_today: int | None = None
    topics: list[str] = field(default_factory=list)
    pushed_at: datetime | None = None

    @property
    def url(self) -> str:
        return f"https://github.com/{self.full_name}"


@dataclass(slots=True)
class ParseResult:
    items: list[RawItem] = field(default_factory=list)
    tools: list[RawTool] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items) + len(self.tools)
