import asyncio
import random
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlmodel import Session, delete, select
from tenacity import retry, stop_after_attempt, wait_exponential

from app.bilibili.client import BilibiliClient
from app.bilibili.exceptions import AuthenticationError, UploaderNotFoundError
from app.bilibili.models import (
    BilibiliResource,
    BilibiliSubscription,
    FailedResource,
    SyncLog,
)
from app.bilibili.websocket import ConnectionManager
from app.core.security import decrypt_credentials


class SyncService:
    def __init__(self, session: Session, ws_manager: ConnectionManager) -> None:
        self.session = session
        self.ws_manager = ws_manager

    async def sync_subscription(
        self, subscription_id: UUID, sync_type: str = "manual", sync_log_id: UUID | None = None
    ) -> UUID:
        subscription = self.session.get(BilibiliSubscription, subscription_id)
        if not subscription:
            raise ValueError("订阅不存在")

        if sync_log_id:
            sync_log = self.session.get(SyncLog, sync_log_id)
            if not sync_log:
                raise ValueError("同步日志不存在")
        else:
            sync_log = SyncLog(
                subscription_id=subscription_id,
                sync_type=sync_type,
                status="running",
                start_time=datetime.now(timezone.utc),
                details=[],
            )
            self.session.add(sync_log)
            self.session.commit()

        await self._send_log(subscription_id, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "message": f"开始同步 UP主：{subscription.uploader_name} (UID: {subscription.uploader_uid})",
        })

        try:
            account = self.session.get(BilibiliSubscription, subscription_id).account
            credentials = decrypt_credentials(account.credentials)
            client = BilibiliClient(credentials, account.auth_type)

            if not await client.check_uploader_exists(subscription.uploader_uid):
                raise UploaderNotFoundError(f"UP主 {subscription.uploader_uid} 不存在")

            if not await client.verify_credentials():
                account.is_active = False
                self.session.commit()
                raise AuthenticationError("账户凭证已失效")

            success_retry, failed_retry = await self._retry_failed_resources(
                subscription_id, client
            )
            total_success = success_retry
            total_failed = failed_retry
            total_skipped = 0
            is_first_sync = subscription.last_sync_at is None

            for resource_type in subscription.sync_config.get("resource_types", ["video"]):
                await self._send_log(subscription_id, {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "INFO",
                    "message": f"正在获取{resource_type}列表...",
                })

                offset = 0
                fetched_count = 0
                batch_size = subscription.sync_config.get("batch_size", 50)
                history_limit = subscription.sync_config.get("history_limit")

                while True:
                    if is_first_sync and history_limit is not None and fetched_count >= history_limit:
                        break

                    resources = await self._fetch_resources_batch(
                        client, subscription, resource_type, offset
                    )
                    if not resources:
                        break

                    await self._send_log(subscription_id, {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "INFO",
                        "message": f"获取到 {len(resources)} 条{resource_type}",
                    })

                    stop_incremental = False
                    for resource_data in resources:
                        if not is_first_sync and subscription.last_sync_at:
                            if resource_data["published_at"] <= subscription.last_sync_at:
                                total_skipped += 1
                                stop_incremental = True
                                break

                        result = await self._save_resource(
                            subscription_id, resource_data, client
                        )
                        if result == "success":
                            total_success += 1
                        elif result == "skipped":
                            total_skipped += 1
                        else:
                            total_failed += 1

                    fetched_count += len(resources)
                    if stop_incremental:
                        break
                    offset += batch_size
                    delay = random.uniform(3, 5)
                    await self._send_log(subscription_id, {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "INFO",
                        "message": f"延迟 {delay:.1f} 秒后继续获取...",
                    })
                    await asyncio.sleep(delay)

            sync_log.status = "success"
            sync_log.end_time = datetime.now(timezone.utc)
            sync_log.total_count = total_success + total_skipped + total_failed
            sync_log.success_count = total_success
            sync_log.failed_count = total_failed
            sync_log.skipped_count = total_skipped
            subscription.last_sync_at = datetime.now(timezone.utc)
            self.session.commit()

            await self._send_log(subscription_id, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "message": f"同步完成：成功 {total_success} 条，跳过 {total_skipped} 条，失败 {total_failed} 条",
            })

            return sync_log.id

        except Exception as e:
            sync_log.status = "failed"
            sync_log.end_time = datetime.now(timezone.utc)
            sync_log.error_message = str(e)
            self.session.commit()

            await self._send_log(subscription_id, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR",
                "message": f"同步失败：{str(e)}",
                "stack_trace": traceback.format_exc(),
            }, sync_log_id=sync_log.id)
            raise

    async def _fetch_resources_batch(
        self,
        client: BilibiliClient,
        subscription: BilibiliSubscription,
        resource_type: str,
        offset: int,
    ) -> list[dict[str, Any]]:
        batch_size = subscription.sync_config.get("batch_size", 50)
        if resource_type == "video":
            page = offset // batch_size + 1
            return await client.get_user_videos(
                subscription.uploader_uid, page=page, page_size=batch_size
            )
        elif resource_type == "dynamic":
            return await client.get_user_dynamics(
                subscription.uploader_uid, offset=str(offset) if offset else None
            )
        elif resource_type == "article":
            page = offset // batch_size + 1
            return await client.get_user_articles(
                subscription.uploader_uid, page=page
            )
        return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
    )
    async def _save_resource(
        self,
        subscription_id: UUID,
        resource_data: dict[str, Any],
        client: BilibiliClient,  # noqa: ARG002
    ) -> str:
        try:
            existing = self.session.exec(
                select(BilibiliResource).where(
                    BilibiliResource.subscription_id == subscription_id,
                    BilibiliResource.resource_id == resource_data["resource_id"],
                )
            ).first()

            if existing:
                await self._send_log(subscription_id, {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "INFO",
                    "type": resource_data["resource_type"],
                    "resource_id": resource_data["resource_id"],
                    "title": resource_data["title"],
                    "published_at": resource_data["published_at"].isoformat(),
                    "status": "skipped",
                    "message": "⊙ 已存在，跳过",
                })
                return "skipped"

            resource = BilibiliResource(
                subscription_id=subscription_id,
                **{k: v for k, v in resource_data.items() if k in (
                    "resource_type", "resource_id", "title", "cover_url",
                    "summary", "full_content", "attachments", "resource_meta", "published_at",
                )},
            )
            self.session.add(resource)
            self.session.commit()

            self.session.exec(
                delete(FailedResource).where(
                    FailedResource.subscription_id == subscription_id,
                    FailedResource.resource_id == resource_data["resource_id"],
                )
            )
            self.session.commit()

            await self._send_log(subscription_id, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "type": resource_data["resource_type"],
                "resource_id": resource_data["resource_id"],
                "title": resource_data["title"],
                "published_at": resource_data["published_at"].isoformat(),
                "status": "success",
                "message": "✓ 保存成功",
            })
            return "success"

        except Exception as e:
            failed = FailedResource(
                subscription_id=subscription_id,
                resource_id=resource_data["resource_id"],
                resource_type=resource_data["resource_type"],
                failed_at=datetime.now(timezone.utc),
                retry_count=0,
                last_error=str(e),
                resource_meta=resource_data,
            )
            self.session.merge(failed)
            self.session.commit()

            await self._send_log(subscription_id, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR",
                "type": resource_data["resource_type"],
                "resource_id": resource_data["resource_id"],
                "title": resource_data["title"],
                "status": "failed",
                "error": str(e),
                "stack_trace": traceback.format_exc(),
            })
            return "failed"

    async def _retry_failed_resources(
        self, subscription_id: UUID, client: BilibiliClient
    ) -> tuple[int, int]:
        failed_resources = self.session.exec(
            select(FailedResource).where(
                FailedResource.subscription_id == subscription_id,
                FailedResource.retry_count < 5,
            )
        ).all()

        if not failed_resources:
            return (0, 0)

        await self._send_log(subscription_id, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "message": f"正在重试 {len(failed_resources)} 个失败资源...",
        })

        success_count = 0
        failed_count = 0

        for failed in failed_resources:
            failed.retry_count += 1
            self.session.commit()

            result = await self._save_resource(
                subscription_id, failed.resource_meta, client
            )
            if result == "success":
                success_count += 1
            else:
                failed_count += 1

        return (success_count, failed_count)

    async def _send_log(
        self, subscription_id: UUID, log_entry: dict[str, Any], sync_log_id: UUID | None = None
    ) -> None:
        if sync_log_id:
            sync_log = self.session.get(SyncLog, sync_log_id)
        else:
            sync_log = self.session.exec(
                select(SyncLog)
                .where(
                    SyncLog.subscription_id == subscription_id,
                    SyncLog.status == "running",
                )
                .order_by(SyncLog.start_time.desc())
            ).first()
        if sync_log:
            sync_log.details = [*(sync_log.details or []), log_entry]
            self.session.add(sync_log)
            self.session.commit()
        await self.ws_manager.broadcast(subscription_id, log_entry)
