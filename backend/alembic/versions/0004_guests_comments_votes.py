"""guests comments votes

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-01 10:15:58.153287
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("target_kind", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'visible'"), nullable=False
        ),
        sa.Column("report_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('visible', 'hidden', 'removed')", name="ck_comments_status"),
        sa.CheckConstraint("target_kind IN ('article', 'tool')", name="ck_comments_target_kind"),
        sa.CheckConstraint("char_length(body) BETWEEN 1 AND 2000", name="ck_comments_body_length"),
        sa.ForeignKeyConstraint(["parent_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_moderation", "comments", ["status", "report_count"], unique=False)
    op.create_index(
        "ix_comments_target", "comments", ["target_kind", "target_id", "created_at"], unique=False
    )
    op.create_index(op.f("ix_comments_user_id"), "comments", ["user_id"], unique=False)
    op.create_table(
        "votes",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("target_kind", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "target_kind IN ('article', 'tool', 'comment')", name="ck_votes_target_kind"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "target_kind", "target_id"),
    )
    op.create_index("ix_votes_target", "votes", ["target_kind", "target_id"], unique=False)
    op.create_table(
        "comment_reports",
        sa.Column("comment_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("comment_id", "user_id"),
    )
    # Existing accounts get a handle before the column becomes required.
    op.add_column("users", sa.Column("handle", sa.String(length=24), nullable=True))
    op.execute("UPDATE users SET handle = 'hanging-' || id WHERE handle IS NULL")
    op.alter_column("users", "handle", nullable=False)
    op.add_column("users", sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("users", "email", existing_type=sa.VARCHAR(length=320), nullable=True)
    op.create_unique_constraint("uq_users_handle", "users", ["handle"])
    # Autogenerate doesn't detect CHECK constraints on existing tables; mirrors app/models.py.
    op.create_check_constraint(
        "ck_users_handle_format", "users", "handle ~ '^[a-z0-9][a-z0-9_-]{2,23}$'"
    )


def downgrade() -> None:
    # WARNING: constraint name is None; this directive will fail as
    # rendered.  Add a name, or use a naming convention; see
    # https://alembic.sqlalchemy.org/en/latest/naming.html
    op.drop_constraint("ck_users_handle_format", "users", type_="check")
    op.drop_constraint("uq_users_handle", "users", type_="unique")
    # Guests have no email and can't exist under the old schema.
    op.execute("DELETE FROM users WHERE email IS NULL")
    op.alter_column("users", "email", existing_type=sa.VARCHAR(length=320), nullable=False)
    op.drop_column("users", "banned_at")
    op.drop_column("users", "handle")
    op.drop_table("comment_reports")
    op.drop_index("ix_votes_target", table_name="votes")
    op.drop_table("votes")
    op.drop_index(op.f("ix_comments_user_id"), table_name="comments")
    op.drop_index("ix_comments_target", table_name="comments")
    op.drop_index("ix_comments_moderation", table_name="comments")
    op.drop_table("comments")
