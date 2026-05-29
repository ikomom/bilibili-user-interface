import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class BilibiliAccount(SQLModel, table=True):
    __tablename__ = "bilibili_accounts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    account_name: str = Field(max_length=100)
    auth_type: str = Field(max_length=20)
    credentials: str
    bilibili_uid: str | None = Field(default=None, max_length=50)
    display_name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = None
    profile_info: dict = Field(default={}, sa_column=Column(JSONB))
    is_active: bool = Field(default=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    subscriptions: list["BilibiliSubscription"] = Relationship(
        back_populates="account",
        cascade_delete=True,
    )


class BilibiliSubscription(SQLModel, table=True):
    __tablename__ = "bilibili_uploader_subscriptions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    account_id: uuid.UUID = Field(foreign_key="bilibili_accounts.id", ondelete="CASCADE")
    uploader_uid: str = Field(max_length=50)
    uploader_name: str = Field(max_length=100)
    uploader_avatar: str | None = None
    uploader_info: dict = Field(default={}, sa_column=Column(JSONB))
    sync_config: dict = Field(sa_column=Column(JSONB))
    is_paused: bool = Field(default=False)
    last_sync_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    account: BilibiliAccount = Relationship(back_populates="subscriptions")
    resources: list["BilibiliResource"] = Relationship(
        back_populates="subscription",
        cascade_delete=True,
    )
    sync_logs: list["SyncLog"] = Relationship(
        back_populates="subscription",
        cascade_delete=True,
    )


class BilibiliResource(SQLModel, table=True):
    __tablename__ = "bilibili_resources"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    subscription_id: uuid.UUID = Field(foreign_key="bilibili_uploader_subscriptions.id", ondelete="CASCADE")
    resource_type: str = Field(max_length=20)
    resource_id: str = Field(max_length=50)
    title: str
    cover_url: str | None = None
    summary: str | None = None
    full_content: str | None = None
    attachments: dict | None = Field(default=None, sa_column=Column(JSONB))
    resource_meta: dict = Field(sa_column=Column(JSONB))
    published_at: datetime = Field(sa_type=DateTime(timezone=True))
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    subscription: BilibiliSubscription = Relationship(back_populates="resources")


class SyncLog(SQLModel, table=True):
    __tablename__ = "sync_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    subscription_id: uuid.UUID = Field(foreign_key="bilibili_uploader_subscriptions.id", ondelete="CASCADE")
    sync_type: str = Field(max_length=20)
    status: str = Field(max_length=20)
    start_time: datetime = Field(sa_type=DateTime(timezone=True))
    end_time: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    total_count: int = Field(default=0)
    success_count: int = Field(default=0)
    failed_count: int = Field(default=0)
    skipped_count: int = Field(default=0)
    error_message: str | None = None
    details: list | None = Field(default=None, sa_column=Column(JSONB))

    subscription: BilibiliSubscription = Relationship(back_populates="sync_logs")


class FailedResource(SQLModel, table=True):
    __tablename__ = "failed_resources"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    subscription_id: uuid.UUID = Field(foreign_key="bilibili_uploader_subscriptions.id", ondelete="CASCADE")
    resource_id: str = Field(max_length=50)
    resource_type: str = Field(max_length=20)
    failed_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    retry_count: int = Field(default=0)
    last_error: str | None = None
    resource_meta: dict | None = Field(default=None, sa_column=Column(JSONB))
