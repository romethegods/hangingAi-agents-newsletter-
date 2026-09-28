"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-28 11:13:23.112175
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float(), server_default=sa.text("1.0"), nullable=False),
        sa.Column(
            "crawl_interval_minutes", sa.Integer(), server_default=sa.text("60"), nullable=False
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "consecutive_failures", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "tools",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("stars", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("forks", sa.Integer(), nullable=True),
        sa.Column(
            "topics",
            postgresql.ARRAY(sa.String(length=64)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("star_velocity", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("full_name"),
    )
    op.create_index("ix_tools_stars", "tools", [sa.literal_column("stars DESC")], unique=False)
    op.create_index("ix_tools_topics", "tools", ["topics"], unique=False, postgresql_using="gin")
    op.create_index(
        "ix_tools_velocity", "tools", [sa.literal_column("star_velocity DESC")], unique=False
    )
    op.create_table(
        "articles",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("url_canonical", sa.Text(), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=300), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(length=16), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("engagement", sa.Integer(), nullable=True),
        sa.Column("minhash", postgresql.ARRAY(sa.BigInteger()), nullable=True),
        sa.Column("duplicate_of_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(title, '')), 'A') || setweight(to_tsvector('english', coalesce(summary, '')), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_type IN ('news', 'paper', 'model')", name="ck_articles_content_type"
        ),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["articles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url_hash"),
    )
    op.create_index(
        op.f("ix_articles_duplicate_of_id"), "articles", ["duplicate_of_id"], unique=False
    )
    op.create_index(
        "ix_articles_feed",
        "articles",
        [sa.literal_column("published_at DESC"), sa.literal_column("id DESC")],
        unique=False,
        postgresql_where=sa.text("duplicate_of_id IS NULL"),
    )
    op.create_index(
        "ix_articles_search", "articles", ["search_tsv"], unique=False, postgresql_using="gin"
    )
    op.create_index(op.f("ix_articles_source_id"), "articles", ["source_id"], unique=False)
    op.create_table(
        "tool_star_snapshots",
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tool_id", "captured_at"),
    )


def downgrade() -> None:
    op.drop_table("tool_star_snapshots")
    op.drop_index(op.f("ix_articles_source_id"), table_name="articles")
    op.drop_index("ix_articles_search", table_name="articles", postgresql_using="gin")
    op.drop_index(
        "ix_articles_feed",
        table_name="articles",
        postgresql_where=sa.text("duplicate_of_id IS NULL"),
    )
    op.drop_index(op.f("ix_articles_duplicate_of_id"), table_name="articles")
    op.drop_table("articles")
    op.drop_index("ix_tools_velocity", table_name="tools")
    op.drop_index("ix_tools_topics", table_name="tools", postgresql_using="gin")
    op.drop_index("ix_tools_stars", table_name="tools")
    op.drop_table("tools")
    op.drop_table("sources")
