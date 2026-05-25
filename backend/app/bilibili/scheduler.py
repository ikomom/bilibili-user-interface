import logging
from uuid import UUID

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.bilibili.models import BilibiliSubscription

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def create_scheduler(database_url: str, timezone: str = "Asia/Shanghai") -> AsyncIOScheduler:
    global _scheduler
    _scheduler = AsyncIOScheduler(
        jobstores={
            "default": SQLAlchemyJobStore(url=database_url),
        },
        timezone=timezone,
    )
    return _scheduler


def get_scheduler() -> AsyncIOScheduler:
    if _scheduler is None:
        raise RuntimeError("APScheduler 尚未初始化")
    return _scheduler


def init_scheduler(scheduler: AsyncIOScheduler, session: Session) -> None:
    subscriptions = session.exec(
        select(BilibiliSubscription).where(BilibiliSubscription.is_paused == False)  # noqa: E712
    ).all()
    for sub in subscriptions:
        add_sync_job(scheduler, sub)


def add_sync_job(scheduler: AsyncIOScheduler, subscription: BilibiliSubscription) -> None:
    frequency = subscription.sync_config.get("sync_frequency", "manual")
    if frequency == "manual":
        return

    trigger = frequency_to_trigger(frequency)
    scheduler.add_job(
        _sync_job_wrapper,
        trigger=trigger,
        args=[subscription.id],
        id=f"sync_{subscription.id}",
        replace_existing=True,
    )


def remove_sync_job(scheduler: AsyncIOScheduler, subscription_id: UUID) -> None:
    try:
        scheduler.remove_job(f"sync_{subscription_id}")
    except Exception:
        pass


def frequency_to_trigger(frequency: str) -> CronTrigger:
    if frequency == "1h":
        return CronTrigger(hour="*", minute="0")
    elif frequency == "6h":
        return CronTrigger(hour="*/6", minute="0")
    elif frequency == "1d":
        return CronTrigger(hour="2", minute="0")
    elif frequency == "1w":
        return CronTrigger(day_of_week="mon", hour="2", minute="0")
    raise ValueError(f"不支持的频率: {frequency}")


async def _sync_job_wrapper(subscription_id: UUID) -> None:
    from app.bilibili.sync_service import SyncService
    from app.bilibili.websocket import ws_manager
    from app.core.db import engine

    with Session(engine) as session:
        service = SyncService(session, ws_manager)
        try:
            await service.sync_subscription(subscription_id, sync_type="scheduled")
        except Exception as e:
            logger.error(f"定时同步失败: {subscription_id} - {e}")
