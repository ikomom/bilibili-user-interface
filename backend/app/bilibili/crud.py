import uuid
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.bilibili.models import (
    BilibiliAccount,
    BilibiliResource,
    BilibiliSubscription,
    FailedResource,
    SyncLog,
)


def create_account(
    session: Session, user_id: uuid.UUID, data: dict[str, Any]
) -> BilibiliAccount:
    account = BilibiliAccount(
        user_id=user_id,
        account_name=data["account_name"],
        auth_type=data["auth_type"],
        credentials=data["credentials"],
        bilibili_uid=data.get("bilibili_uid"),
        display_name=data.get("display_name"),
        avatar_url=data.get("avatar_url"),
        profile_info=data.get("profile_info", {}),
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def get_accounts(session: Session, user_id: uuid.UUID | None = None) -> list[BilibiliAccount]:
    query = select(BilibiliAccount)
    if user_id:
        query = query.where(BilibiliAccount.user_id == user_id)
    return session.exec(query.order_by(BilibiliAccount.created_at)).all()


def get_account(session: Session, account_id: uuid.UUID) -> BilibiliAccount | None:
    return session.get(BilibiliAccount, account_id)


def update_account(
    session: Session, account_id: uuid.UUID, data: dict[str, Any]
) -> BilibiliAccount | None:
    account = session.get(BilibiliAccount, account_id)
    if not account:
        return None
    for field in (
        "account_name",
        "auth_type",
        "credentials",
        "bilibili_uid",
        "display_name",
        "avatar_url",
        "profile_info",
        "is_active",
    ):
        if field in data:
            setattr(account, field, data[field])
    account.updated_at = datetime.now(timezone.utc)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def delete_account(session: Session, account_id: uuid.UUID) -> bool:
    account = session.get(BilibiliAccount, account_id)
    if not account:
        return False
    session.delete(account)
    session.commit()
    return True


def create_subscription(
    session: Session, user_id: uuid.UUID, data: dict[str, Any]
) -> BilibiliSubscription:
    sub = BilibiliSubscription(
        user_id=user_id,
        **data,
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


def get_subscriptions(
    session: Session, user_id: uuid.UUID | None = None
) -> list[BilibiliSubscription]:
    query = select(BilibiliSubscription)
    if user_id:
        query = query.where(BilibiliSubscription.user_id == user_id)
    return session.exec(query.order_by(BilibiliSubscription.created_at)).all()


def get_subscription(
    session: Session, sub_id: uuid.UUID
) -> BilibiliSubscription | None:
    return session.get(BilibiliSubscription, sub_id)


def update_subscription(
    session: Session, sub_id: uuid.UUID, data: dict[str, Any]
) -> BilibiliSubscription | None:
    sub = session.get(BilibiliSubscription, sub_id)
    if not sub:
        return None
    for field in ("account_id", "sync_config", "is_paused"):
        if field in data:
            setattr(sub, field, data[field])
    sub.updated_at = datetime.now(timezone.utc)
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


def delete_subscription(session: Session, sub_id: uuid.UUID) -> bool:
    sub = session.get(BilibiliSubscription, sub_id)
    if not sub:
        return False
    session.delete(sub)
    session.commit()
    return True


def _build_resource_query(
    subscription_id: uuid.UUID | None = None,
    subscription_ids: list[uuid.UUID] | None = None,
    resource_type: str | None = None,
    keyword: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Any:
    query = select(BilibiliResource)
    if subscription_id:
        query = query.where(BilibiliResource.subscription_id == subscription_id)
    elif subscription_ids is not None:
        if not subscription_ids:
            return None
        query = query.where(BilibiliResource.subscription_id.in_(subscription_ids))
    if resource_type:
        query = query.where(BilibiliResource.resource_type == resource_type)
    if keyword:
        query = query.where(
            BilibiliResource.title.ilike(f"%{keyword}%")
            | BilibiliResource.summary.ilike(f"%{keyword}%")
        )
    if start_date:
        query = query.where(
            BilibiliResource.published_at >= datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        )
    if end_date:
        query = query.where(
            BilibiliResource.published_at <= datetime.combine(end_date, time.max, tzinfo=timezone.utc)
        )
    return query


def get_resources(
    session: Session,
    subscription_id: uuid.UUID | None = None,
    subscription_ids: list[uuid.UUID] | None = None,
    resource_type: str | None = None,
    keyword: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[BilibiliResource]:
    query = _build_resource_query(
        subscription_id=subscription_id,
        subscription_ids=subscription_ids,
        resource_type=resource_type,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
    )
    if query is None:
        return []
    query = query.order_by(BilibiliResource.published_at.desc()).offset(offset).limit(limit)
    return session.exec(query).all()


def count_resources(
    session: Session,
    subscription_id: uuid.UUID | None = None,
    subscription_ids: list[uuid.UUID] | None = None,
    resource_type: str | None = None,
    keyword: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    query = _build_resource_query(
        subscription_id=subscription_id,
        subscription_ids=subscription_ids,
        resource_type=resource_type,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
    )
    if query is None:
        return 0
    count_query = select(func.count()).select_from(query.subquery())
    return session.exec(count_query).one()


def get_resource(session: Session, resource_id: uuid.UUID) -> BilibiliResource | None:
    return session.get(BilibiliResource, resource_id)


def get_resource_counts(
    session: Session,
    subscription_id: uuid.UUID | None = None,
    subscription_ids: list[uuid.UUID] | None = None,
) -> dict[str, int]:
    query = select(BilibiliResource.resource_type, func.count()).group_by(
        BilibiliResource.resource_type
    )
    if subscription_id:
        query = query.where(BilibiliResource.subscription_id == subscription_id)
    elif subscription_ids is not None:
        if not subscription_ids:
            return {"article": 0, "dynamic": 0, "video": 0}
        query = query.where(BilibiliResource.subscription_id.in_(subscription_ids))

    counts = {"article": 0, "dynamic": 0, "video": 0}
    for resource_type, count in session.exec(query).all():
        if resource_type in counts:
            counts[resource_type] = count
    return counts


def get_sync_logs(
    session: Session, subscription_id: uuid.UUID, limit: int = 20, offset: int = 0
) -> list[SyncLog]:
    query = (
        select(SyncLog)
        .where(SyncLog.subscription_id == subscription_id)
        .order_by(SyncLog.start_time.desc())
        .offset(offset)
        .limit(limit)
    )
    return session.exec(query).all()


def count_sync_logs(
    session: Session, subscription_id: uuid.UUID
) -> int:
    query = select(func.count()).select_from(SyncLog).where(SyncLog.subscription_id == subscription_id)
    return session.exec(query).one()


def get_sync_log(session: Session, log_id: uuid.UUID) -> SyncLog | None:
    return session.get(SyncLog, log_id)


def get_failed_resources(
    session: Session, subscription_id: uuid.UUID
) -> list[FailedResource]:
    return session.exec(
        select(FailedResource).where(
            FailedResource.subscription_id == subscription_id,
            FailedResource.retry_count < 5,
        )
    ).all()
