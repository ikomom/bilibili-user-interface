from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

VIDEO_TYPE_DISPLAY = {
    1: "自制",
    2: "转载",
}

DYNAMIC_TYPE_DISPLAY = {
    1: "转发动态",
    2: "图文动态",
    4: "文字动态",
    8: "视频动态",
    16: "小视频",
    64: "专栏动态",
    256: "音频动态",
    2048: "普通动态",
}

RESOURCE_TYPE_DISPLAY = {
    "video": "视频",
    "dynamic": "动态",
    "article": "专栏",
}

SYNC_FREQUENCY_DISPLAY = {
    "1h": "每小时",
    "6h": "每6小时",
    "1d": "每天",
    "1w": "每周",
    "manual": "手动",
}

SYNC_STATUS_DISPLAY = {
    "running": "同步中",
    "success": "成功",
    "failed": "失败",
}


class SyncConfig(BaseModel):
    resource_types: list[Literal["video", "dynamic", "article"]] = ["video", "dynamic", "article"]
    sync_frequency: Literal["1h", "6h", "1d", "1w", "manual"] = "6h"
    history_limit: int | None = 50
    batch_size: int = 50


class AccountCreate(BaseModel):
    account_name: str
    auth_type: Literal["cookie", "sessdata", "qrcode"]
    credentials: dict


class AccountUpdate(BaseModel):
    account_name: str | None = None
    auth_type: Literal["cookie", "sessdata", "qrcode"] | None = None
    credentials: dict | None = None


class AccountPublic(BaseModel):
    id: UUID
    user_id: UUID
    account_name: str
    auth_type: str
    bilibili_uid: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    profile_info: dict = {}
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None


class SubscriptionCreate(BaseModel):
    account_id: UUID
    uploader_uid: str
    sync_config: SyncConfig


class SubscriptionUpdate(BaseModel):
    account_id: UUID | None = None
    sync_config: SyncConfig | None = None


class SubscriptionPublic(BaseModel):
    id: UUID
    user_id: UUID
    account_id: UUID
    uploader_uid: str
    uploader_name: str
    uploader_avatar: str | None
    uploader_info: dict
    sync_config: dict
    is_paused: bool
    last_sync_at: datetime | None
    latest_sync_status: str | None = None
    latest_sync_log_id: UUID | None = None
    created_at: datetime | None
    updated_at: datetime | None


class ResourcePublic(BaseModel):
    id: UUID
    subscription_id: UUID
    resource_type: str
    resource_id: str
    title: str
    cover_url: str | None
    summary: str | None
    full_content: str | None
    attachments: dict | None
    resource_meta: dict
    published_at: datetime
    created_at: datetime | None


class ResourceFilter(BaseModel):
    subscription_id: UUID | None = None
    resource_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    keyword: str | None = None
    page: int = 1
    page_size: int = 20


class PaginatedResources(BaseModel):
    resources: list[ResourcePublic]
    total: int
    page: int
    page_size: int


class ResourceCounts(BaseModel):
    video: int = 0
    dynamic: int = 0
    article: int = 0


class SyncLogPublic(BaseModel):
    id: UUID
    subscription_id: UUID
    sync_type: str
    status: str
    start_time: datetime
    end_time: datetime | None
    total_count: int
    success_count: int
    failed_count: int
    skipped_count: int
    error_message: str | None
    details: list[Any] | None


class QRCodeGenerateResponse(BaseModel):
    qrcode_key: str
    qrcode_url: str
    expires_at: datetime


class QRCodeCheckRequest(BaseModel):
    qrcode_key: str


class QRCodeCheckResponse(BaseModel):
    status: Literal["pending", "scanned", "confirmed", "expired"]
    account: AccountPublic | None = None
    credentials: dict | None = None


class SyncResponse(BaseModel):
    sync_log_id: UUID
    message: str


class RetryFailedResponse(BaseModel):
    total: int
    success: int
    failed: int


class FailedResourcePublic(BaseModel):
    id: UUID
    subscription_id: UUID
    resource_id: str
    resource_type: str
    failed_at: datetime
    retry_count: int
    last_error: str | None
    resource_meta: dict[str, Any] | None
