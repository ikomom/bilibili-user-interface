"""Add Bilibili account profile fields

Revision ID: c2d3e4f5a6b7
Revises: b7c8d9e0f1a2
Create Date: 2026-05-26 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c2d3e4f5a6b7"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("bilibili_accounts", sa.Column("bilibili_uid", sa.String(length=50), nullable=True))
    op.add_column("bilibili_accounts", sa.Column("display_name", sa.String(length=100), nullable=True))
    op.add_column("bilibili_accounts", sa.Column("avatar_url", sa.Text(), nullable=True))
    op.add_column(
        "bilibili_accounts",
        sa.Column(
            "profile_info",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("bilibili_accounts", "profile_info")
    op.drop_column("bilibili_accounts", "avatar_url")
    op.drop_column("bilibili_accounts", "display_name")
    op.drop_column("bilibili_accounts", "bilibili_uid")
