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


class Platform(StrEnum):
    GITHUB = "github"
    HUGGINGFACE = "huggingface"  # Hugging Face Spaces: hosted, runnable demo apps


class DemoKind(StrEnum):
    VIDEO = "video"  # a video file (mp4/webm)
    EMBED = "embed"  # an official video player iframe (YouTube, via youtube-nocookie.com)
    GIF = "gif"
    IMAGE = "image"
    APP = "app"  # an embeddable live app (HF Space)


@dataclass(slots=True)
class Demo:
    """A tool's demo, always hotlinked or embedded from its source; never re-hosted."""

    url: str
    kind: DemoKind


@dataclass(slots=True)
class RawTool:
    full_name: str  # "owner/name"
    description: str | None = None
    language: str | None = None
    stars: int = 0  # GitHub stars, or likes for HF Spaces
    forks: int | None = None
    stars_today: int | None = None
    topics: list[str] = field(default_factory=list)
    pushed_at: datetime | None = None
    # New fields go last so existing positional construction keeps working.
    platform: Platform = Platform.GITHUB
    title: str | None = None  # display name when it differs from the repo name (HF Spaces)
    preview_image_url: str | None = None
    demo: Demo | None = None
    tags: list[str] = field(default_factory=list)  # source content tags, used for filtering only

    @property
    def url(self) -> str:
        if self.platform is Platform.HUGGINGFACE:
            return f"https://huggingface.co/spaces/{self.full_name}"
        return f"https://github.com/{self.full_name}"


@dataclass(slots=True)
class ParseResult:
    items: list[RawItem] = field(default_factory=list)
    tools: list[RawTool] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items) + len(self.tools)
