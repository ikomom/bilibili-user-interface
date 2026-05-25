import base64
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from bilibili_api.login_v2 import QrCodeLoginChannel
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from sqlmodel import Session, select

from app.api.deps import SessionDep, get_current_user
from app.bilibili import crud
from app.bilibili.client import BilibiliClient
from app.bilibili.models import BilibiliSubscription, SyncLog
from app.bilibili.schemas import (
    AccountCreate,
    AccountPublic,
    AccountUpdate,
    QRCodeCheckRequest,
    QRCodeCheckResponse,
    QRCodeGenerateResponse,
    RetryFailedResponse,
    SubscriptionCreate,
    SubscriptionPublic,
    SubscriptionUpdate,
    SyncResponse,
)
from app.bilibili.sync_service import SyncService
from app.bilibili.websocket import ws_manager
from app.core.permissions import has_permission, require_permission
from app.core.security import decrypt_credentials, encrypt_credentials
from app.models import User

router = APIRouter(prefix="/bilibili", tags=["bilibili"])
_qr_login_sessions: dict[str, Any] = {}
QRCODE_LOGIN_CHANNEL = QrCodeLoginChannel.TV


async def run_subscription_sync_background(
    subscription_id: uuid.UUID, sync_log_id: uuid.UUID
) -> None:
    with Session(engine) as session:
        service = SyncService(session, ws_manager)
        try:
            await service.sync_subscription(subscription_id, sync_log_id=sync_log_id)
        except Exception:
            # SyncService 已将失败写入 SyncLog，后台任务不要再冒泡成请求级 500。
            return


def _with_latest_sync_status(
    session: Session, subscriptions: list[BilibiliSubscription]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for sub in subscriptions:
        latest_log = session.exec(
            select(SyncLog)
            .where(SyncLog.subscription_id == sub.id)
            .order_by(SyncLog.start_time.desc())
        ).first()
        data = sub.model_dump()
        data["latest_sync_status"] = latest_log.status if latest_log else None
        data["latest_sync_log_id"] = latest_log.id if latest_log else None
        results.append(data)
    return results


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def _credential_to_dict(credential: Any) -> dict[str, str | None]:
    return {
        "sessdata": getattr(credential, "sessdata", None),
        "bili_jct": getattr(credential, "bili_jct", None),
        "buvid3": getattr(credential, "buvid3", None),
        "dedeuserid": getattr(credential, "dedeuserid", None),
        "ac_time_value": getattr(credential, "ac_time_value", None),
    }


CurrentActiveUser = Depends(get_current_active_user)


@router.get("/image-proxy")
async def proxy_bilibili_image(url: str = Query(...)) -> Response:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc.endswith("hdslb.com"):
        raise HTTPException(status_code=400, detail="不支持的图片地址")

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        image_response = await client.get(
            url,
            headers={
                "Referer": "https://www.bilibili.com/",
                "User-Agent": "Mozilla/5.0",
            },
        )
    if image_response.status_code >= 400:
        raise HTTPException(status_code=image_response.status_code, detail="图片加载失败")
    return Response(
        content=image_response.content,
        media_type=image_response.headers.get("content-type", "image/jpeg"),
        headers={"Cache-Control": "public, max-age=86400"},
    )


# --- Accounts ---
@router.post("/accounts", response_model=AccountPublic, status_code=201)
async def create_account(
    data: AccountCreate,
    session: SessionDep,
    current_user: User = require_permission("bilibili:account:create"),
) -> Any:
    client = BilibiliClient(data.credentials, data.auth_type)
    valid = await client.verify_credentials()
    if not valid:
        raise HTTPException(status_code=400, detail="账户凭证无效，请检查后重试")

    encrypted = encrypt_credentials(data.credentials)
    account = crud.create_account(session, current_user.id, {
        "account_name": data.account_name,
        "auth_type": data.auth_type,
        "credentials": encrypted,
    })
    return account


@router.get("/accounts", response_model=list[AccountPublic])
def read_accounts(
    session: SessionDep,
    current_user: User = require_permission("bilibili:account:view"),
) -> Any:
    if current_user.is_superuser:
        return crud.get_accounts(session)
    return crud.get_accounts(session, current_user.id)


@router.get("/accounts/{account_id}", response_model=AccountPublic)
def read_account(
    account_id: uuid.UUID,
    session: SessionDep,
    current_user: User = require_permission("bilibili:account:view"),
) -> Any:
    account = crud.get_account(session, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")
    if not current_user.is_superuser and account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此账户")
    return account


@router.put("/accounts/{account_id}", response_model=AccountPublic)
async def update_account(
    account_id: uuid.UUID,
    data: AccountUpdate,
    session: SessionDep,
    current_user: User = require_permission("bilibili:account:update"),
) -> Any:
    account = crud.get_account(session, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")
    if not current_user.is_superuser and account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改此账户")

    update_data = {}
    if data.account_name is not None:
        update_data["account_name"] = data.account_name
    if data.credentials is not None:
        client = BilibiliClient(data.credentials, data.auth_type or account.auth_type)
        valid = await client.verify_credentials()
        if not valid:
            raise HTTPException(status_code=400, detail="账户凭证无效")
        update_data["credentials"] = encrypt_credentials(data.credentials)
        if data.auth_type:
            update_data["auth_type"] = data.auth_type

    updated = crud.update_account(session, account_id, update_data)
    return updated


@router.delete("/accounts/{account_id}")
def delete_account(
    account_id: uuid.UUID,
    session: SessionDep,
    current_user: User = require_permission("bilibili:account:delete"),
) -> Any:
    account = crud.get_account(session, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")
    if not current_user.is_superuser and account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除此账户")
    crud.delete_account(session, account_id)
    return {"message": "账户已删除"}


@router.post("/accounts/qrcode/generate", response_model=QRCodeGenerateResponse)
async def generate_qrcode(
    current_user: User = require_permission("bilibili:account:create"),
) -> Any:
    from bilibili_api.login_v2 import QrCodeLogin

    login = QrCodeLogin(QRCODE_LOGIN_CHANNEL)
    await login.generate_qrcode()
    qrcode_key = str(uuid.uuid4())
    _qr_login_sessions[qrcode_key] = {
        "login": login,
        "user_id": current_user.id,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=3),
    }
    qr_content = login.get_qrcode_picture().content
    return QRCodeGenerateResponse(
        qrcode_key=qrcode_key,
        qrcode_url=f"data:image/png;base64,{base64.b64encode(qr_content).decode()}",
        expires_at=_qr_login_sessions[qrcode_key]["expires_at"],
    )


@router.post("/accounts/qrcode/check", response_model=QRCodeCheckResponse)
async def check_qrcode(
    data: QRCodeCheckRequest,
    session: SessionDep,
    current_user: User = require_permission("bilibili:account:create"),
) -> Any:
    from bilibili_api.login_v2 import QrCodeLoginEvents

    qr_session = _qr_login_sessions.get(data.qrcode_key)
    if not qr_session or qr_session["user_id"] != current_user.id:
        return QRCodeCheckResponse(status="expired")
    if qr_session["expires_at"] <= datetime.now(timezone.utc):
        _qr_login_sessions.pop(data.qrcode_key, None)
        return QRCodeCheckResponse(status="expired")

    login = qr_session["login"]
    event = await login.check_state()
    if event == QrCodeLoginEvents.SCAN:
        return QRCodeCheckResponse(status="pending")
    if event == QrCodeLoginEvents.CONF:
        return QRCodeCheckResponse(status="scanned")
    if event == QrCodeLoginEvents.TIMEOUT:
        _qr_login_sessions.pop(data.qrcode_key, None)
        return QRCodeCheckResponse(status="expired")

    credentials = _credential_to_dict(login.get_credential())
    try:
        encrypted = encrypt_credentials(credentials)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    account = crud.create_account(session, current_user.id, {
        "account_name": f"扫码账户 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        "auth_type": "qrcode",
        "credentials": encrypted,
    })
    _qr_login_sessions.pop(data.qrcode_key, None)
    return QRCodeCheckResponse(status="confirmed", account=AccountPublic.model_validate(account, from_attributes=True))


# --- Subscriptions ---
@router.post("/subscriptions", status_code=201)
async def create_subscription(
    data: SubscriptionCreate,
    session: SessionDep,
    current_user: User = require_permission("bilibili:subscription:create"),
) -> Any:
    account = crud.get_account(session, data.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")
    if not current_user.is_superuser and account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权使用此账户")

    credentials = decrypt_credentials(account.credentials)
    client = BilibiliClient(credentials, account.auth_type)

    if not await client.check_uploader_exists(data.uploader_uid):
        raise HTTPException(status_code=400, detail="该 UP主不存在或 UID 错误")

    existing = session.exec(
        select(BilibiliSubscription).where(
            BilibiliSubscription.user_id == current_user.id,
            BilibiliSubscription.uploader_uid == data.uploader_uid,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "该 UP主已存在订阅",
                "existing_subscription": {
                    "id": str(existing.id),
                    "uploader_name": existing.uploader_name,
                    "sync_config": existing.sync_config,
                },
            },
        )

    uploader_info = await client.get_user_info(data.uploader_uid)
    sub = crud.create_subscription(session, current_user.id, {
        "account_id": data.account_id,
        "uploader_uid": data.uploader_uid,
        "uploader_name": uploader_info["name"],
        "uploader_avatar": uploader_info["avatar"],
        "uploader_info": uploader_info,
        "sync_config": data.sync_config.model_dump(),
    })

    from app.bilibili.scheduler import add_sync_job, get_scheduler

    add_sync_job(get_scheduler(), sub)

    return sub


@router.get("/subscriptions", response_model=list[SubscriptionPublic])
def read_subscriptions(
    session: SessionDep,
    current_user: User = require_permission("bilibili:subscription:view"),
) -> Any:
    if current_user.is_superuser or has_permission(current_user, "bilibili:admin:view_all", session):
        return _with_latest_sync_status(session, crud.get_subscriptions(session))
    return _with_latest_sync_status(session, crud.get_subscriptions(session, current_user.id))


@router.get("/subscriptions/{sub_id}", response_model=SubscriptionPublic)
def read_subscription(
    sub_id: uuid.UUID,
    session: SessionDep,
    current_user: User = require_permission("bilibili:subscription:view"),
) -> Any:
    sub = crud.get_subscription(session, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    can_view_all = has_permission(current_user, "bilibili:admin:view_all", session)
    if not current_user.is_superuser and not can_view_all and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此订阅")
    return _with_latest_sync_status(session, [sub])[0]


@router.put("/subscriptions/{sub_id}")
def update_subscription(
    sub_id: uuid.UUID,
    data: SubscriptionUpdate,
    session: SessionDep,
    current_user: User = require_permission("bilibili:subscription:update"),
) -> Any:
    sub = crud.get_subscription(session, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if not current_user.is_superuser and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改此订阅")

    update_data = {}
    if data.account_id is not None:
        account = crud.get_account(session, data.account_id)
        if not account:
            raise HTTPException(status_code=404, detail="账户不存在")
        if not current_user.is_superuser and account.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权使用此账户")
        update_data["account_id"] = data.account_id
    if data.sync_config is not None:
        update_data["sync_config"] = data.sync_config.model_dump()

    updated = crud.update_subscription(session, sub_id, update_data)
    if updated and data.sync_config is not None:
        from app.bilibili.scheduler import add_sync_job, get_scheduler, remove_sync_job

        scheduler = get_scheduler()
        remove_sync_job(scheduler, sub_id)
        if not updated.is_paused:
            add_sync_job(scheduler, updated)
    return updated


@router.delete("/subscriptions/{sub_id}")
def delete_subscription(
    sub_id: uuid.UUID,
    session: SessionDep,
    current_user: User = require_permission("bilibili:subscription:delete"),
) -> Any:
    sub = crud.get_subscription(session, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if not current_user.is_superuser and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除此订阅")

    from app.bilibili.scheduler import get_scheduler, remove_sync_job

    remove_sync_job(get_scheduler(), sub_id)

    crud.delete_subscription(session, sub_id)
    return {"message": "订阅已删除"}


@router.patch("/subscriptions/{sub_id}/pause")
def pause_subscription(
    sub_id: uuid.UUID,
    session: SessionDep,
    current_user: User = require_permission("bilibili:subscription:update"),
) -> Any:
    sub = crud.get_subscription(session, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if not current_user.is_superuser and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此订阅")

    sub.is_paused = not sub.is_paused
    session.add(sub)
    session.commit()
    session.refresh(sub)

    from app.bilibili.scheduler import add_sync_job, get_scheduler, remove_sync_job

    scheduler = get_scheduler()
    if sub.is_paused:
        remove_sync_job(scheduler, sub_id)
    else:
        add_sync_job(scheduler, sub)
    return {"is_paused": sub.is_paused}


@router.post("/subscriptions/{sub_id}/sync")
async def sync_subscription(
    sub_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    current_user: User = require_permission("bilibili:subscription:sync"),
) -> Any:
    sub = crud.get_subscription(session, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if not current_user.is_superuser and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权同步此订阅")

    sync_log = SyncLog(
        subscription_id=sub_id,
        sync_type="manual",
        status="running",
        start_time=datetime.now(timezone.utc),
        details=[],
    )
    session.add(sync_log)
    session.commit()
    session.refresh(sync_log)
    sync_log_id = sync_log.id
    background_tasks.add_task(run_subscription_sync_background, sub_id, sync_log_id)
    return SyncResponse(sync_log_id=sync_log_id, message="同步已开始")


@router.post("/subscriptions/{sub_id}/retry-failed")
async def retry_failed_resources(
    sub_id: uuid.UUID,
    session: SessionDep,
    current_user: User = require_permission("bilibili:subscription:sync"),
) -> Any:
    sub = crud.get_subscription(session, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if not current_user.is_superuser and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此订阅")

    account = crud.get_account(session, sub.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="关联账户不存在")

    credentials = decrypt_credentials(account.credentials)
    client = BilibiliClient(credentials, account.auth_type)
    service = SyncService(session, ws_manager)
    success, failed = await service._retry_failed_resources(sub_id, client)

    return RetryFailedResponse(total=success + failed, success=success, failed=failed)


# --- Resources ---
@router.get("/resources")
def read_resources(
    session: SessionDep,
    subscription_id: uuid.UUID | None = Query(None),
    resource_type: str | None = Query(None),
    keyword: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = require_permission("bilibili:resource:view"),
) -> Any:
    offset = (page - 1) * page_size
    subscription_ids = None
    if not current_user.is_superuser and not has_permission(current_user, "bilibili:admin:view_all", session):
        if subscription_id:
            sub = crud.get_subscription(session, subscription_id)
            if not sub or sub.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="无权访问此资源")
        else:
            subscriptions = crud.get_subscriptions(session, current_user.id)
            subscription_ids = [sub.id for sub in subscriptions]

    resources = crud.get_resources(
        session,
        subscription_id=subscription_id,
        subscription_ids=subscription_ids,
        resource_type=resource_type,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        offset=offset,
        limit=page_size,
    )

    return resources


@router.get("/resources/{resource_id}")
def read_resource(
    resource_id: uuid.UUID,
    session: SessionDep,
    current_user: User = require_permission("bilibili:resource:view"),
) -> Any:
    resource = crud.get_resource(session, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")

    if not current_user.is_superuser:
        sub = crud.get_subscription(session, resource.subscription_id)
        if sub and sub.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此资源")
    return resource


# --- Sync Logs ---
@router.get("/sync-logs")
def read_sync_logs(
    session: SessionDep,
    subscription_id: uuid.UUID = Query(...),
    current_user: User = require_permission("bilibili:sync-log:view"),
) -> Any:
    sub = crud.get_subscription(session, subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if not current_user.is_superuser and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此日志")

    return crud.get_sync_logs(session, subscription_id)


@router.get("/sync-logs/{log_id}")
def read_sync_log(
    log_id: uuid.UUID,
    session: SessionDep,
    current_user: User = require_permission("bilibili:sync-log:view"),
) -> Any:
    log = crud.get_sync_log(session, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="日志不存在")

    if not current_user.is_superuser:
        sub = crud.get_subscription(session, log.subscription_id)
        if sub and sub.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此日志")
    return log


# --- WebSocket ---
@router.websocket("/ws/sync-logs/{subscription_id}")
async def websocket_sync_logs(
    websocket: WebSocket,
    subscription_id: uuid.UUID,
    token: str = Query(...),
):
    try:
        from jwt import decode as jwt_decode
        from jwt.exceptions import InvalidTokenError

        from app.core.config import settings
        from app.core.security import ALGORITHM

        try:
            payload = jwt_decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if not user_id:
                await websocket.close(code=4001, reason="Invalid token")
                return
        except InvalidTokenError:
            await websocket.close(code=4001, reason="Invalid token")
            return

        with Session(engine) as ws_session:
            user = ws_session.get(User, uuid.UUID(user_id))
            if not user:
                await websocket.close(code=4001, reason="User not found")
                return

            subscription = ws_session.get(BilibiliSubscription, subscription_id)
            if not subscription:
                await websocket.close(code=4004, reason="Subscription not found")
                return
            if not user.is_superuser and subscription.user_id != user.id:
                await websocket.close(code=4003, reason="Permission denied")
                return

        await ws_manager.connect(websocket, subscription_id)

        with Session(engine) as log_session:
            latest_log = log_session.exec(
                select(SyncLog)
                .where(SyncLog.subscription_id == subscription_id)
                .order_by(SyncLog.start_time.desc())
            ).first()
            if latest_log and latest_log.details:
                for log_entry in latest_log.details:
                    await websocket.send_json(log_entry)

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, subscription_id)


from app.core.db import engine  # noqa: E402, F811
