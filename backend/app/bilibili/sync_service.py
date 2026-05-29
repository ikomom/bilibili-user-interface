import asyncio
import random
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from bilibili_api.exceptions import NetworkException, ResponseCodeException
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
        # 风控降级配置
        self.risk_control_levels = [
            {"delay": 30, "batch_size": 20, "name": "轻度降级"},
            {"delay": 60, "batch_size": 10, "name": "中度降级"},
            {"delay": 120, "batch_size": 5, "name": "重度降级"},
        ]

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
            # 重新获取 subscription 以确保有 account 关系
            subscription = self.session.get(BilibiliSubscription, subscription_id)
            if not subscription or not subscription.account:
                raise ValueError("订阅或关联账户不存在")

            account = subscription.account
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
                # 仅在首次同步时应用历史窗口限制
                use_history_window = history_limit is not None and is_first_sync
                
                # 风控状态追踪
                risk_level = 0
                consecutive_risk_errors = 0
                max_risk_retries = 3

                while True:
                    if use_history_window and history_limit is not None and fetched_count >= history_limit:
                        await self._send_log(subscription_id, {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "level": "INFO",
                            "message": f"已达到历史同步限制 ({history_limit} 条)，停止获取{resource_type}",
                        })
                        break

                    try:
                        resources = await self._fetch_resources_batch(
                            client, subscription, resource_type, offset, risk_level
                        )
                        
                        # 成功获取，重置风控计数
                        if consecutive_risk_errors > 0:
                            await self._send_log(subscription_id, {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "level": "INFO",
                                "message": f"风控已恢复，继续正常同步",
                            })
                        consecutive_risk_errors = 0
                        risk_level = 0
                        
                    except Exception as exc:
                        if self._is_bilibili_risk_control_error(exc):
                            consecutive_risk_errors += 1
                            
                            if consecutive_risk_errors > max_risk_retries:
                                await self._send_log(subscription_id, {
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "level": "ERROR",
                                    "message": f"获取{resource_type}列表多次触发风控，已跳过该类型",
                                    "error": str(exc),
                                })
                                break
                            
                            # 升级风控等级
                            risk_level = min(consecutive_risk_errors, len(self.risk_control_levels))
                            level_config = self.risk_control_levels[risk_level - 1]
                            
                            await self._send_log(subscription_id, {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "level": "WARNING",
                                "message": f"触发风控 (第{consecutive_risk_errors}次)，启动{level_config['name']}：延迟{level_config['delay']}秒，批次减至{level_config['batch_size']}条",
                                "error": str(exc),
                            })
                            
                            await asyncio.sleep(level_config["delay"])
                            continue
                        else:
                            raise
                    
                    if not resources:
                        break

                    await self._send_log(subscription_id, {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "INFO",
                        "message": f"获取到 {len(resources)} 条{resource_type}",
                    })

                    stop_incremental = False
                    for resource_data in resources:
                        # 增量同步：跳过已同步的旧资源
                        if not is_first_sync and subscription.last_sync_at:
                            if resource_data["published_at"] <= subscription.last_sync_at:
                                await self._send_log(subscription_id, {
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "level": "DEBUG",
                                    "type": resource_data["resource_type"],
                                    "resource_id": resource_data["resource_id"],
                                    "title": resource_data["title"],
                                    "published_at": resource_data["published_at"].isoformat(),
                                    "status": "skipped",
                                    "message": "⊙ 资源早于上次同步时间，跳过",
                                })
                                total_skipped += 1
                                stop_incremental = True
                                continue  # 跳过此资源，不再调用 _save_resource

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

                    # 增量同步遇到旧资源后停止
                    if stop_incremental and not use_history_window:
                        await self._send_log(subscription_id, {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "level": "INFO",
                            "message": f"已遇到上次同步的资源，停止获取{resource_type}",
                        })
                        break

                    offset += batch_size
                    
                    # 更人性化的延迟：根据风控等级和随机性
                    if risk_level > 0:
                        base_delay = self.risk_control_levels[risk_level - 1]["delay"] / 4
                    else:
                        base_delay = 5
                    
                    # 添加随机性，模拟真实用户
                    delay = random.uniform(base_delay, base_delay * 2)
                    
                    # 偶尔"停顿"更久，模拟用户看内容
                    if random.random() < 0.2:  # 20% 概率
                        delay *= random.uniform(1.5, 3)
                        await self._send_log(subscription_id, {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "level": "DEBUG",
                            "message": f"模拟用户浏览，延迟 {delay:.1f} 秒...",
                        })
                    else:
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
            }, sync_log_id=sync_log.id)

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
        risk_level: int = 0,
    ) -> list[dict[str, Any]]:
        """
        获取资源批次，支持风控降级
        
        Args:
            risk_level: 风控等级 (0=正常, 1-3=降级等级)
        """
        # 获取基础批次大小
        base_batch_size = subscription.sync_config.get("batch_size", 50)
        
        # 应用风控降级
        if risk_level > 0 and risk_level <= len(self.risk_control_levels):
            batch_size = self.risk_control_levels[risk_level - 1]["batch_size"]
        else:
            batch_size = base_batch_size
        
        # 添加随机性，模拟真实用户行为
        batch_size = random.randint(max(5, batch_size - 5), batch_size)
        
        try:
            if resource_type == "video":
                page = offset // base_batch_size + 1
                return await client.get_user_videos(
                    subscription.uploader_uid, page=page, page_size=batch_size
                )
            elif resource_type == "dynamic":
                return await client.get_user_dynamics(
                    subscription.uploader_uid, offset=str(offset) if offset else None
                )
            elif resource_type == "article":
                page = offset // base_batch_size + 1
                return await client.get_user_articles(
                    subscription.uploader_uid, page=page
                )
        except Exception as exc:
            if self._is_bilibili_risk_control_error(exc):
                # 不再直接返回空列表，而是抛出异常让上层处理
                raise
            raise
        return []

    def _is_bilibili_risk_control_error(self, exc: Exception) -> bool:
        if isinstance(exc, NetworkException):
            return exc.status == 412
        if isinstance(exc, ResponseCodeException):
            return exc.code == 412
        return "状态码：412" in str(exc) or "错误号: 412" in str(exc)

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
                if self._update_existing_resource(existing, resource_data):
                    self.session.add(existing)
                    self.session.commit()
                    await self._send_log(subscription_id, {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "INFO",
                        "type": resource_data["resource_type"],
                        "resource_id": resource_data["resource_id"],
                        "title": resource_data["title"],
                        "published_at": resource_data["published_at"].isoformat(),
                        "status": "success",
                        "message": "✓ 已更新已同步资源",
                    })
                    return "success"

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
                    (FailedResource.subscription_id == subscription_id)
                    & (FailedResource.resource_id == resource_data["resource_id"])
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
            # 查找是否已有失败记录
            existing_failed = self.session.exec(
                select(FailedResource).where(
                    FailedResource.subscription_id == subscription_id,
                    FailedResource.resource_id == resource_data["resource_id"],
                )
            ).first()
            
            if existing_failed:
                # 更新现有失败记录
                existing_failed.retry_count += 1
                existing_failed.last_error = str(e)
                existing_failed.failed_at = datetime.now(timezone.utc)
                existing_failed.resource_meta = resource_data
                self.session.add(existing_failed)
            else:
                # 创建新的失败记录
                failed = FailedResource(
                    subscription_id=subscription_id,
                    resource_id=resource_data["resource_id"],
                    resource_type=resource_data["resource_type"],
                    failed_at=datetime.now(timezone.utc),
                    retry_count=1,
                    last_error=str(e),
                    resource_meta=resource_data,
                )
                self.session.add(failed)
            
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

    def _update_existing_resource(
        self, existing: BilibiliResource, resource_data: dict[str, Any]
    ) -> bool:
        changed = False
        incoming_content = (resource_data.get("full_content") or "").strip()
        current_content = (existing.full_content or "").strip()
        current_summary = (existing.summary or "").strip()

        if incoming_content and incoming_content != current_content and (
            not current_content
            or current_content == current_summary
            or len(incoming_content) > len(current_content)
        ):
            existing.full_content = resource_data["full_content"]
            changed = True

        for field in ("title", "cover_url", "summary", "attachments", "resource_meta", "published_at"):
            if field in resource_data and getattr(existing, field) != resource_data[field]:
                setattr(existing, field, resource_data[field])
                changed = True

        return changed

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

            if failed.resource_meta:
                result = await self._save_resource(
                    subscription_id, failed.resource_meta, client
                )
                if result == "success":
                    success_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1

        return (success_count, failed_count)

    async def _send_log(
        self, subscription_id: UUID, log_entry: dict[str, Any], sync_log_id: UUID | None = None
    ) -> None:
        # 先广播到 WebSocket，不阻塞
        await self.ws_manager.broadcast(subscription_id, log_entry)

        # 仅在关键节点或错误时才写入数据库
        # DEBUG 级别的日志不写入数据库，减少 I/O
        if log_entry.get("level") == "DEBUG":
            return

        if sync_log_id:
            sync_log = self.session.get(SyncLog, sync_log_id)
        else:
            sync_log = self.session.exec(
                select(SyncLog)
                .where(
                    SyncLog.subscription_id == subscription_id,
                    SyncLog.status == "running",
                )
                .order_by(SyncLog.start_time.desc())  # type: ignore[attr-defined]
            ).first()
        if sync_log:
            sync_log.details = [*(sync_log.details or []), log_entry]
            self.session.add(sync_log)
            # 注意：这里仍然每次 commit，但已经过滤掉 DEBUG 日志
            # 如果需要进一步优化，可以改为批量提交或使用 session.flush()
            self.session.commit()
