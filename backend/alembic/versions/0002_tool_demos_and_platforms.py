"""tool demos and platforms

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29 15:55:58.426840
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tools",
        sa.Column(
            "platform", sa.String(length=16), server_default=sa.text("'github'"), nullable=False
        ),
    )
    op.add_column("tools", sa.Column("title", sa.String(length=300), nullable=True))
    op.add_column("tools", sa.Column("preview_image_url", sa.Text(), nullable=True))
    op.add_column("tools", sa.Column("demo_url", sa.Text(), nullable=True))
    op.add_column("tools", sa.Column("demo_kind", sa.String(length=16), nullable=True))
    op.add_column("tools", sa.Column("media_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint(op.f("tools_full_name_key"), "tools", type_="unique")
    op.create_index(
        "ix_tools_media_queue",
        "tools",
        ["media_checked_at"],
        unique=False,
        postgresql_where=sa.text("platform = 'github'"),
    )
    op.create_unique_constraint("uq_tools_platform_full_name", "tools", ["platform", "full_name"])
    # Autogenerate doesn't detect CHECK constraints; these mirror app/models.py.
    op.create_check_constraint(
        "ck_tools_platform", "tools", "platform IN ('github', 'huggingface')"
    )
    op.create_check_constraint(
        "ck_tools_demo_kind", "tools", "demo_kind IN ('video', 'embed', 'gif', 'image', 'app')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_tools_demo_kind", "tools", type_="check")
    op.drop_constraint("ck_tools_platform", "tools", type_="check")
    # full_name alone is only unique per platform; Spaces can't survive the old constraint.
    op.execute("DELETE FROM tools WHERE platform <> 'github'")
    op.drop_constraint("uq_tools_platform_full_name", "tools", type_="unique")
    op.drop_index(
        "ix_tools_media_queue", table_name="tools", postgresql_where=sa.text("platform = 'github'")
    )
    op.create_unique_constraint(op.f("tools_full_name_key"), "tools", ["full_name"])
    op.drop_column("tools", "media_checked_at")
    op.drop_column("tools", "demo_kind")
    op.drop_column("tools", "demo_url")
    op.drop_column("tools", "preview_image_url")
    op.drop_column("tools", "title")
    op.drop_column("tools", "platform")
