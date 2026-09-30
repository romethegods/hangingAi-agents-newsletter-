from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SourceBrief(_Out):
    slug: str
    name: str


class SourceStatus(SourceBrief):
    url: str
    enabled: bool
    crawl_interval_minutes: int
    last_crawled_at: datetime | None
    last_error: str | None
    consecutive_failures: int


class ArticleOut(_Out):
    id: int
    title: str
    url: str
    summary: str | None
    author: str | None
    image_url: str | None
    content_type: str
    published_at: datetime
    engagement: int | None
    source: SourceBrief


class ArticleDetail(ArticleOut):
    duplicate_of_id: int | None
    coverage: list[ArticleOut] = []  # the same story from other outlets


class FeedPage(BaseModel):
    items: list[ArticleOut]
    next_cursor: str | None = None


class ToolOut(_Out):
    id: int
    platform: str
    full_name: str
    title: str | None
    url: str
    description: str | None
    language: str | None
    stars: int
    star_velocity: float
    topics: list[str]
    pushed_at: datetime | None
    preview_image_url: str | None
    demo_url: str | None
    demo_kind: str | None


class ToolPage(BaseModel):
    items: list[ToolOut]
    total: int


class TopicCount(BaseModel):
    topic: str
    count: int
