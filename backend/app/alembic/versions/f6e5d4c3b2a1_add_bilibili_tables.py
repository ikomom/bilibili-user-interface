"""Add Bilibili tables

Revision ID: f6e5d4c3b2a1
Revises: a1b2c3d4e5f6
Create Date: 2026-05-25 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql


revision = 'f6e5d4c3b2a1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('bilibili_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_name', sa.String(length=100), nullable=False),
        sa.Column('auth_type', sa.String(length=20), nullable=False),
        sa.Column('credentials', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_bilibili_accounts_user_id', 'bilibili_accounts', ['user_id'])

    op.create_table('bilibili_uploader_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('uploader_uid', sa.String(length=50), nullable=False),
        sa.Column('uploader_name', sa.String(length=100), nullable=False),
        sa.Column('uploader_avatar', sa.Text(), nullable=True),
        sa.Column('uploader_info', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column('sync_config', postgresql.JSONB(), nullable=False),
        sa.Column('is_paused', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['bilibili_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'uploader_uid'),
    )
    op.create_index('idx_subscriptions_user_id', 'bilibili_uploader_subscriptions', ['user_id'])
    op.create_index('idx_subscriptions_uploader_uid', 'bilibili_uploader_subscriptions', ['uploader_uid'])

    op.create_table('bilibili_resources',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resource_type', sa.String(length=20), nullable=False),
        sa.Column('resource_id', sa.String(length=50), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('cover_url', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('full_content', sa.Text(), nullable=True),
        sa.Column('attachments', postgresql.JSONB(), nullable=True),
        sa.Column('resource_meta', postgresql.JSONB(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['subscription_id'], ['bilibili_uploader_subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subscription_id', 'resource_id'),
    )
    op.create_index('idx_resources_subscription_id', 'bilibili_resources', ['subscription_id'])
    op.create_index('idx_resources_published_at', 'bilibili_resources', ['published_at'])
    op.create_index('idx_resources_type', 'bilibili_resources', ['resource_type'])

    op.create_table('sync_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sync_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('success_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('failed_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('skipped_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['subscription_id'], ['bilibili_uploader_subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_sync_logs_subscription_id', 'sync_logs', ['subscription_id'])
    op.create_index('idx_sync_logs_start_time', 'sync_logs', ['start_time'])

    op.create_table('failed_resources',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resource_id', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=20), nullable=False),
        sa.Column('failed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('resource_meta', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['subscription_id'], ['bilibili_uploader_subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subscription_id', 'resource_id'),
    )
    op.create_index('idx_failed_resources_subscription_id', 'failed_resources', ['subscription_id'])


def downgrade():
    op.drop_table('failed_resources')
    op.drop_table('sync_logs')
    op.drop_table('bilibili_resources')
    op.drop_table('bilibili_uploader_subscriptions')
    op.drop_table('bilibili_accounts')
