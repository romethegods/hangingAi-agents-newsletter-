"""Database schema. Any change here needs an Alembic migration in alembic/versions."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
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
