from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    votes: int = 0  # HangingAi upvotes
    comments: int = 0


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
    votes: int = 0
    comments: int = 0


class ToolPage(BaseModel):
    items: list[ToolOut]
    total: int


class TopicCount(BaseModel):
    topic: str
    count: int


class UserOut(_Out):
    id: int
    handle: str
    email: str | None
    is_guest: bool
    brief_enabled: bool
    brief_hour: int
    timezone: str


class LoginRequest(BaseModel):
    email: str
    next: str | None = None


class VerifyRequest(BaseModel):
    token: str


class SessionOut(BaseModel):
    session_token: str
    expires_at: datetime
    user: UserOut


class SettingsIn(BaseModel):
    handle: str | None = Field(default=None, max_length=40)
    brief_enabled: bool | None = None
    brief_hour: int | None = Field(default=None, ge=0, le=23)
    timezone: str | None = Field(default=None, max_length=64)


class FollowsOut(BaseModel):
    tools: list[ToolOut]
    topics: list[str]


class ReleaseOut(_Out):
    id: int
    tag: str
    name: str | None
    url: str
    published_at: datetime | None
    notes: str | None
    tool: ToolOut


class BriefArticle(ArticleOut):
    matched: bool = False  # matched one of the reader's topics


class BriefOut(BaseModel):
    personalized: bool
    followed_topics: list[str]
    releases: list[ReleaseOut]
    rising: list[ToolOut]
    reads: list[BriefArticle]
    demo: ToolOut | None


class UnsubscribeRequest(BaseModel):
    u: int
    t: str


class CommentIn(BaseModel):
    target_kind: str
    target_id: int
    body: str = Field(max_length=4000)  # trimmed and re-checked against the real limit
    parent_id: int | None = None


class CommentOut(BaseModel):
    id: int
    parent_id: int | None
    author: str  # handle
    body: str | None  # None when hidden or removed
    status: str
    created_at: datetime
    votes: int
    voted: bool
    mine: bool
    replies: list["CommentOut"] = []


class CommentsOut(BaseModel):
    count: int
    comments: list[CommentOut]
    here: int = 0  # viewers with this chat open right now


class ReportIn(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


class VoteOut(BaseModel):
    voted: bool
    votes: int


class ModerationItem(BaseModel):
    id: int
    target_kind: str
    target_id: int
    author: str
    author_id: int
    body: str
    status: str
    report_count: int
    created_at: datetime


class BattleIn(BaseModel):
    prompt: str = Field(max_length=8000)  # trimmed and re-checked against the real limit


class VoteIn(BaseModel):
    choice: str


class ArenaModelOut(BaseModel):
    slug: str
    name: str
    maker: str
    open_weights: bool


class BattleOut(BaseModel):
    id: int
    prompt: str
    status: str
    response_a: str | None
    response_b: str | None
    error: str | None
    vote: str | None
    created_at: datetime
    mine: bool
    public: bool
    # Revealed only after the vote, so the comparison stays blind.
    model_a: ArenaModelOut | None = None
    model_b: ArenaModelOut | None = None
    rating_change_a: float | None = None
    rating_change_b: float | None = None
    identity_leak: bool = False


class StandingOut(ArenaModelOut):
    rating: float
    battles: int
    wins: int
    losses: int
    ties: int
    win_rate: float | None
    provisional: bool


class ArenaStatusOut(BaseModel):
    open: bool
    models: int
    battles_left: int | None  # None until the visitor has an identity
    battles_per_day: int


class GalleryBattleOut(BaseModel):
    id: int
    prompt: str
    vote: str
    model_a: ArenaModelOut
    model_b: ArenaModelOut
    voted_at: datetime
