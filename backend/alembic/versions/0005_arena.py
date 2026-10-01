"""arena

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-01 13:52:16.298559
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "arena_model_stats",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("rating", sa.Float(), server_default=sa.text("1000"), nullable=False),
        sa.Column("battles", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("wins", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("losses", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("ties", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("slug"),
    )
    op.create_table(
        "arena_battles",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("model_a", sa.String(length=64), nullable=False),
        sa.Column("model_b", sa.String(length=64), nullable=False),
        sa.Column("response_a", sa.Text(), nullable=True),
        sa.Column("response_b", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("vote", sa.String(length=8), nullable=True),
        sa.Column("identity_leak", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("public", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=10, scale=6),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("rating_change_a", sa.Float(), nullable=True),
        sa.Column("rating_change_b", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'streaming', 'ready', 'voted', 'failed')",
            name="ck_arena_battles_status",
        ),
        sa.CheckConstraint("vote IN ('a', 'b', 'tie', 'bad')", name="ck_arena_battles_vote"),
        sa.CheckConstraint("model_a <> model_b", name="ck_arena_battles_distinct_models"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_arena_battles_created", "arena_battles", ["created_at"], unique=False)
    op.create_index(
        "ix_arena_battles_public",
        "arena_battles",
        [sa.literal_column("voted_at DESC")],
        unique=False,
        postgresql_where=sa.text("public AND status = 'voted'"),
    )
    op.create_index(
        "ix_arena_battles_user_created", "arena_battles", ["user_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_arena_battles_user_created", table_name="arena_battles")
    op.drop_index(
        "ix_arena_battles_public",
        table_name="arena_battles",
        postgresql_where=sa.text("public AND status = 'voted'"),
    )
    op.drop_index("ix_arena_battles_created", table_name="arena_battles")
    op.drop_table("arena_battles")
    op.drop_table("arena_model_stats")
