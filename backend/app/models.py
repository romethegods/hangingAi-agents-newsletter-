"""Database schema. Any change here needs an Alembic migration in alembic/versions."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.scraping.types import ContentType, DemoKind, Platform


def _sql_in(values) -> str:
    return ", ".join(f"'{v.value}'" for v in values)


CONTENT_TYPES = _sql_in(ContentType)


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, server_default=text("1.0"))
    crawl_interval_minutes: Mapped[int] = mapped_column(Integer, server_default=text("60"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Article(Base):
    """News stories, papers and models: anything shown in the feed."""

    __tablename__ = "articles"
    __table_args__ = (
        CheckConstraint(f"content_type IN ({CONTENT_TYPES})", name="ck_articles_content_type"),
        # Feed query: newest canonical (non-duplicate) items, keyset-paginated.
        Index(
            "ix_articles_feed",
            text("published_at DESC"),
            text("id DESC"),
            postgresql_where=text("duplicate_of_id IS NULL"),
        ),
        Index("ix_articles_search", "search_tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text)
    url_canonical: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(300))
    image_url: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(16))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    engagement: Mapped[int | None] = mapped_column(Integer)
    minhash: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))  # near-dup signature
    duplicate_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), index=True
    )
    extra: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('english', coalesce(summary, '')), 'B')",
            persisted=True,
        ),
    )

    source: Mapped[Source] = relationship(lazy="joined")


class Tool(Base):
    """Open-source AI tools: GitHub repos and Hugging Face Spaces (live demo apps)."""

    __tablename__ = "tools"
    __table_args__ = (
        UniqueConstraint("platform", "full_name", name="uq_tools_platform_full_name"),
        CheckConstraint(f"platform IN ({_sql_in(Platform)})", name="ck_tools_platform"),
        CheckConstraint(f"demo_kind IN ({_sql_in(DemoKind)})", name="ck_tools_demo_kind"),
        Index("ix_tools_velocity", text("star_velocity DESC")),
        Index("ix_tools_stars", text("stars DESC")),
        Index("ix_tools_topics", "topics", postgresql_using="gin"),
        # README scan queue: GitHub tools never scanned, or scanned longest ago.
        Index(
            "ix_tools_media_queue",
            "media_checked_at",
            postgresql_where=text("platform = 'github'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(16), server_default=text("'github'"))
    full_name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(64))
    stars: Mapped[int] = mapped_column(Integer, server_default=text("0"))  # likes for HF Spaces
    forks: Mapped[int | None] = mapped_column(Integer)
    topics: Mapped[list[str]] = mapped_column(ARRAY(String(64)), server_default=text("'{}'"))
    star_velocity: Mapped[float] = mapped_column(Float, server_default=text("0"))  # per day
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Demos are hotlinked/embedded from the source, never re-hosted.
    preview_image_url: Mapped[str | None] = mapped_column(Text)
    demo_url: Mapped[str | None] = mapped_column(Text)
    demo_kind: Mapped[str | None] = mapped_column(String(16))
    media_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    releases_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ToolStarSnapshot(Base):
    """Star count over time; star_velocity is computed from a sliding window of these."""

    __tablename__ = "tool_star_snapshots"

    tool_id: Mapped[int] = mapped_column(
        ForeignKey("tools.id", ondelete="CASCADE"), primary_key=True
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    stars: Mapped[int] = mapped_column(Integer)


class ToolRelease(Base):
    """A GitHub release of a tracked tool; the "your stack shipped" part of the brief."""

    __tablename__ = "tool_releases"
    __table_args__ = (
        UniqueConstraint("tool_id", "tag", name="uq_tool_releases_tool_tag"),
        Index("ix_tool_releases_recent", "tool_id", text("published_at DESC")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey("tools.id", ondelete="CASCADE"))
    tag: Mapped[str] = mapped_column(String(200))
    name: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    is_prerelease: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tool: Mapped[Tool] = relationship(lazy="joined")


class User(Base):
    """Anyone who follows, votes or comments. Guests have no email; adding one is
    optional and only needed to get the brief by email or use another device."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("brief_hour BETWEEN 0 AND 23", name="ck_users_brief_hour"),
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        CheckConstraint("handle ~ '^[a-z0-9][a-z0-9_-]{2,23}$'", name="ck_users_handle_format"),
        UniqueConstraint("handle", name="uq_users_handle"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    handle: Mapped[str] = mapped_column(String(24))  # public name, e.g. hanging-1234
    email: Mapped[str | None] = mapped_column(String(320), unique=True)  # None for guests
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    brief_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    brief_hour: Mapped[int] = mapped_column(Integer, server_default=text("7"))  # local time
    timezone: Mapped[str] = mapped_column(String(64), server_default=text("'America/New_York'"))
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_guest(self) -> bool:
        return self.email is None


class LoginToken(Base):
    """One-time sign-in link. Only a SHA-256 of the token is stored."""

    __tablename__ = "login_tokens"
    __table_args__ = (Index("ix_login_tokens_email_created", "email", "created_at"),)

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    """Signed-in browser session. Only a SHA-256 of the cookie value is stored."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")


class Follow(Base):
    """A user following a tool (target = tool id) or a topic (target = topic slug)."""

    __tablename__ = "follows"
    __table_args__ = (
        CheckConstraint("kind IN ('tool', 'topic')", name="ck_follows_kind"),
        # "Who follows X": drives the release-scan queue.
        Index("ix_follows_target", "kind", "target"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    target: Mapped[str] = mapped_column(String(200), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Brief(Base):
    """One daily brief per user per local date; the unique key makes sending idempotent."""

    __tablename__ = "briefs"
    __table_args__ = (
        UniqueConstraint("user_id", "brief_date", name="uq_briefs_user_date"),
        CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_briefs_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    brief_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), server_default=text("'pending'"))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BriefItem(Base):
    """What a brief contained, so nothing repeats within a week."""

    __tablename__ = "brief_items"
    __table_args__ = (
        CheckConstraint("kind IN ('release', 'tool', 'article')", name="ck_brief_items_kind"),
    )

    brief_id: Mapped[int] = mapped_column(
        ForeignKey("briefs.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    ref_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class Comment(Base):
    """A comment on an article or tool. Replies point at their parent (one level deep)."""

    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint("target_kind IN ('article', 'tool')", name="ck_comments_target_kind"),
        CheckConstraint("status IN ('visible', 'hidden', 'removed')", name="ck_comments_status"),
        CheckConstraint("char_length(body) BETWEEN 1 AND 2000", name="ck_comments_body_length"),
        Index("ix_comments_target", "target_kind", "target_id", "created_at"),
        # Moderation queue: anything hidden or reported, newest first.
        Index("ix_comments_moderation", "status", "report_count"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    target_kind: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[int] = mapped_column(BigInteger)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), server_default=text("'visible'"))
    report_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(lazy="joined")


class CommentReport(Base):
    __tablename__ = "comment_reports"

    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Vote(Base):
    """One upvote per user per thing; voting again removes it."""

    __tablename__ = "votes"
    __table_args__ = (
        CheckConstraint(
            "target_kind IN ('article', 'tool', 'comment')", name="ck_votes_target_kind"
        ),
        Index("ix_votes_target", "target_kind", "target_id"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    target_kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    target_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
