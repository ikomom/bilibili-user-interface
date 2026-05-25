"""Fix Bilibili credentials column type

Revision ID: b7c8d9e0f1a2
Revises: f6e5d4c3b2a1
Create Date: 2026-05-26 00:02:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b7c8d9e0f1a2"
down_revision = "f6e5d4c3b2a1"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "bilibili_accounts",
        "credentials",
        existing_type=postgresql.JSONB(),
        type_=sa.Text(),
        postgresql_using="credentials::text",
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "bilibili_accounts",
        "credentials",
        existing_type=sa.Text(),
        type_=postgresql.JSONB(),
        postgresql_using="credentials::jsonb",
        existing_nullable=False,
    )
