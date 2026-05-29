import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import anyio
import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from app.bilibili import router as bilibili_router
from app.bilibili.models import (
    BilibiliAccount,
    BilibiliResource,
    BilibiliSubscription,
    SyncLog,
)
from app.bilibili.schemas import AccountPublic, SyncConfig
from app.bilibili.sync_service import SyncService
from app.models import Permission, Role, RolePermission, User, UserRole


def _route(path: str, method: str) -> APIRoute:
    for route in bilibili_router.router.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route {method} {path} not found")


def test_account_routes_do_not_expose_credentials() -> None:
    assert _route("/bilibili/accounts", "POST").response_model is AccountPublic
    assert _route("/bilibili/accounts", "GET").response_model == list[AccountPublic]
    assert _route("/bilibili/accounts/{account_id}", "GET").response_model is AccountPublic
    assert _route("/bilibili/accounts/{account_id}", "PUT").response_model is AccountPublic


def test_account_credentials_are_stored_as_encrypted_string() -> None:
    assert BilibiliAccount.model_fields["credentials"].annotation is str


def test_bilibili_account_model_has_profile_fields() -> None:
    assert "bilibili_uid" in BilibiliAccount.model_fields
    assert "display_name" in BilibiliAccount.model_fields
    assert "avatar_url" in BilibiliAccount.model_fields
    assert "profile_info" in BilibiliAccount.model_fields


def test_create_account_stores_bilibili_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password="hash",
        is_superuser=True,
    )
    created = {}

    class FakeClient:
        def __init__(self, _credentials, _auth_type):
            pass

        async def verify_credentials(self):
            return True

        async def get_current_account_profile(self):
            return {
                "uid": "11473291",
                "name": "笨笨的韭菜",
                "avatar": "https://example.com/avatar.jpg",
                "follower_count": 123,
                "description": "简介",
            }

    def fake_create_account(_session, user_id, data):
        created.update({"user_id": user_id, "data": data})
        return BilibiliAccount(user_id=user_id, **data)

    monkeypatch.setattr(bilibili_router, "BilibiliClient", FakeClient)
    monkeypatch.setattr(bilibili_router, "encrypt_credentials", lambda _credentials: "encrypted")
    monkeypatch.setattr(bilibili_router.crud, "create_account", fake_create_account)

    response = anyio.run(
        bilibili_router.create_account,
        bilibili_router.AccountCreate(
            account_name="手动账户",
            auth_type="sessdata",
            credentials={"sessdata": "sess", "bili_jct": "csrf", "dedeuserid": "11473291"},
        ),
        object(),
        user,
    )

    assert response.display_name == "笨笨的韭菜"
    assert created["data"]["bilibili_uid"] == "11473291"
    assert created["data"]["display_name"] == "笨笨的韭菜"
    assert created["data"]["avatar_url"] == "https://example.com/avatar.jpg"
    assert created["data"]["profile_info"]["follower_count"] == 123


def test_bilibili_models_are_registered_for_alembic_autogenerate() -> None:
    expected_tables = {
        "bilibili_accounts",
        "bilibili_uploader_subscriptions",
        "bilibili_resources",
        "sync_logs",
        "failed_resources",
    }
    assert expected_tables.issubset(BilibiliAccount.metadata.tables.keys())


def test_bilibili_resource_published_at_is_timezone_aware_column() -> None:
    assert BilibiliResource.__table__.c.published_at.type.timezone is True


def test_subscription_relationships_cascade_delete_dependents() -> None:
    relationships = BilibiliSubscription.__mapper__.relationships

    assert "delete-orphan" in relationships["resources"].cascade
    assert "delete-orphan" in relationships["sync_logs"].cascade


def test_read_resources_limits_normal_user_to_owned_subscriptions(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        hashed_password="hash",
        is_superuser=False,
    )
    owned_subscription_id = uuid.uuid4()
    calls = {}

    def fake_get_subscriptions(_session, user_id=None):
        assert user_id == user.id
        return [SimpleNamespace(id=owned_subscription_id, user_id=user.id)]

    def fake_get_resources(_session, **kwargs):
        calls.update(kwargs)
        return []

    monkeypatch.setattr(bilibili_router.crud, "get_subscriptions", fake_get_subscriptions)
    monkeypatch.setattr(bilibili_router.crud, "get_resources", fake_get_resources)
    monkeypatch.setattr(bilibili_router, "has_permission", lambda *_args: False)

    assert bilibili_router.read_resources(
        session=object(),
        subscription_id=None,
        resource_type=None,
        keyword=None,
        page=1,
        page_size=20,
        current_user=user,
    ) == []
    assert calls["subscription_ids"] == [owned_subscription_id]


def test_read_resources_rejects_unowned_subscription_before_query(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        hashed_password="hash",
        is_superuser=False,
    )
    subscription_id = uuid.uuid4()
    queried_resources = False

    def fake_get_subscription(_session, sub_id):
        assert sub_id == subscription_id
        return SimpleNamespace(id=sub_id, user_id=uuid.uuid4())

    def fake_get_resources(_session, **_kwargs):
        nonlocal queried_resources
        queried_resources = True
        return []

    monkeypatch.setattr(bilibili_router.crud, "get_subscription", fake_get_subscription)
    monkeypatch.setattr(bilibili_router.crud, "get_resources", fake_get_resources)
    monkeypatch.setattr(bilibili_router, "has_permission", lambda *_args: False)

    with pytest.raises(HTTPException) as exc_info:
        bilibili_router.read_resources(
            session=object(),
            subscription_id=subscription_id,
            resource_type=None,
            keyword=None,
            page=1,
            page_size=20,
            current_user=user,
        )

    assert exc_info.value.status_code == 403
    assert queried_resources is False


def test_read_resources_allows_view_all_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password="hash",
        is_superuser=False,
    )
    calls = {}

    def fake_get_resources(_session, **kwargs):
        calls.update(kwargs)
        return []

    monkeypatch.setattr(bilibili_router, "has_permission", lambda *_args: True)
    monkeypatch.setattr(bilibili_router.crud, "get_resources", fake_get_resources)

    assert bilibili_router.read_resources(
        session=object(),
        subscription_id=None,
        resource_type=None,
        keyword=None,
        start_date=None,
        end_date=None,
        page=1,
        page_size=20,
        current_user=user,
    ) == []

    assert calls["subscription_ids"] is None


def test_read_resource_counts_returns_all_types(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        hashed_password="hash",
        is_superuser=False,
    )
    subscription_id = uuid.uuid4()

    monkeypatch.setattr(
        bilibili_router.crud,
        "get_subscription",
        lambda _session, sub_id: SimpleNamespace(id=sub_id, user_id=user.id),
    )
    monkeypatch.setattr(
        bilibili_router.crud,
        "get_resource_counts",
        lambda _session, **_kwargs: {"video": 1, "dynamic": 2, "article": 3},
    )
    monkeypatch.setattr(bilibili_router, "has_permission", lambda *_args: False)

    assert bilibili_router.read_resource_counts(
        session=object(),
        subscription_id=subscription_id,
        current_user=user,
    ).model_dump() == {"article": 3, "dynamic": 2, "video": 1}


def test_delete_subscription_uses_configured_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.bilibili import scheduler as scheduler_module

    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password="hash",
        is_superuser=True,
    )
    subscription_id = uuid.uuid4()
    scheduler = object()
    calls = {}

    monkeypatch.setattr(
        bilibili_router.crud,
        "get_subscription",
        lambda session, sub_id: SimpleNamespace(id=sub_id, user_id=user.id),
    )
    monkeypatch.setattr(bilibili_router.crud, "delete_subscription", lambda session, sub_id: True)
    monkeypatch.setattr(scheduler_module, "get_scheduler", lambda: scheduler, raising=False)

    def fake_remove_sync_job(configured_scheduler, sub_id):
        calls["scheduler"] = configured_scheduler
        calls["subscription_id"] = sub_id

    monkeypatch.setattr(scheduler_module, "remove_sync_job", fake_remove_sync_job)

    assert bilibili_router.delete_subscription(
        sub_id=subscription_id,
        session=object(),
        current_user=user,
    ) == {"message": "订阅已删除"}
    assert calls == {"scheduler": scheduler, "subscription_id": subscription_id}


def test_update_subscription_rejects_account_owned_by_another_user(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        hashed_password="hash",
        is_superuser=False,
    )
    subscription_id = uuid.uuid4()
    account_id = uuid.uuid4()
    updated = False

    monkeypatch.setattr(
        bilibili_router.crud,
        "get_subscription",
        lambda _session, sub_id: SimpleNamespace(id=sub_id, user_id=user.id),
    )
    monkeypatch.setattr(
        bilibili_router.crud,
        "get_account",
        lambda _session, acct_id: SimpleNamespace(id=acct_id, user_id=uuid.uuid4()),
    )

    def fake_update_subscription(_session, _sub_id, _data):
        nonlocal updated
        updated = True

    monkeypatch.setattr(bilibili_router.crud, "update_subscription", fake_update_subscription)

    with pytest.raises(HTTPException) as exc_info:
        bilibili_router.update_subscription(
            sub_id=subscription_id,
            data=bilibili_router.SubscriptionUpdate(account_id=account_id),
            session=object(),
            current_user=user,
        )

    assert exc_info.value.status_code == 403
    assert updated is False


def test_init_permissions_backfills_missing_permissions_and_role_links() -> None:
    from app.bilibili.init_permissions import BILIBILI_PERMISSIONS, init_permissions

    class FakeResult:
        def __init__(self, values):
            self.values = values

        def first(self):
            return self.values[0] if self.values else None

        def all(self):
            return self.values

    class FakeSession:
        def __init__(self):
            self.permissions = [Permission(**BILIBILI_PERMISSIONS[0])]
            self.roles = [Role(name="user", is_system=True)]
            self.role_permissions = []
            self.user_roles = []
            self.superuser = User(
                id=uuid.uuid4(),
                email="admin@example.com",
                hashed_password="hash",
                is_superuser=True,
            )
            self.committed = False

        def exec(self, statement):
            statement_text = str(statement)
            if "role_permissions" in statement_text:
                params = statement.compile().params
                return FakeResult([
                    rp
                    for rp in self.role_permissions
                    if rp.role_id == params["role_id_1"]
                    and rp.permission_id == params["permission_id_1"]
                ])
            if "user_roles" in statement_text:
                params = statement.compile().params
                return FakeResult([
                    ur
                    for ur in self.user_roles
                    if ur.user_id == params["user_id_1"]
                    and ur.role_id == params["role_id_1"]
                ])
            if "permissions" in statement_text:
                if "WHERE permissions.code" in statement_text:
                    code = statement.compile().params["code_1"]
                    return FakeResult([p for p in self.permissions if p.code == code])
                if "WHERE permissions.module" in statement_text:
                    module = statement.compile().params["module_1"]
                    return FakeResult([p for p in self.permissions if p.module == module])
                return FakeResult(self.permissions)
            if "roles" in statement_text:
                if "WHERE roles.name" in statement_text:
                    name = statement.compile().params["name_1"]
                    return FakeResult([r for r in self.roles if r.name == name])
                return FakeResult(self.roles)
            if "user" in statement_text:
                return FakeResult([self.superuser])
            return FakeResult([])

        def add(self, obj):
            if isinstance(obj, Permission):
                self.permissions.append(obj)
            elif isinstance(obj, Role):
                self.roles.append(obj)
            elif isinstance(obj, RolePermission):
                self.role_permissions.append(obj)
            elif isinstance(obj, UserRole):
                self.user_roles.append(obj)

        def flush(self):
            return None

        def commit(self):
            self.committed = True

    session = FakeSession()

    init_permissions(session)

    permission_codes = {permission.code for permission in session.permissions}
    role_names = {role.name for role in session.roles}
    assert {permission["code"] for permission in BILIBILI_PERMISSIONS}.issubset(permission_codes)
    assert {"admin", "user"}.issubset(role_names)
    assert session.role_permissions
    assert session.user_roles
    assert session.committed is True


def test_admin_user_roles_include_permissions_for_preview() -> None:
    from app.api.routes.admin import read_user_roles

    permission = Permission(
        id=uuid.uuid4(),
        code="bilibili:subscription:view",
        name="查看订阅",
        module="bilibili",
        description="查看订阅列表",
    )
    role = Role(
        id=uuid.uuid4(),
        name="bilibili_user",
        description="B站用户",
        permissions=[permission],
    )
    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        hashed_password="hash",
        roles=[role],
    )

    class FakeSession:
        def get(self, model, model_id):
            assert model is User
            assert model_id == user.id
            return user

    [result] = read_user_roles(FakeSession(), user.id)

    assert result["name"] == "bilibili_user"
    assert result["permissions"][0]["code"] == "bilibili:subscription:view"


def test_sync_service_persists_broadcast_logs_to_running_sync_log() -> None:
    subscription_id = uuid.uuid4()
    sync_log = SyncLog(
        subscription_id=subscription_id,
        sync_type="manual",
        status="running",
        start_time=datetime.now(timezone.utc),
        details=[],
    )
    sent_logs = []

    class FakeSession:
        def exec(self, statement):
            statement_text = str(statement)
            if "sync_logs" in statement_text:
                return SimpleNamespace(first=lambda: sync_log)
            return SimpleNamespace(first=lambda: None)

        def add(self, obj):
            assert obj is sync_log

        def commit(self):
            return None

    class FakeWsManager:
        async def broadcast(self, sub_id, log_entry):
            sent_logs.append((sub_id, log_entry))

    log_entry = {"timestamp": "2026-05-25T00:00:00+00:00", "message": "hello"}
    service = SyncService(FakeSession(), FakeWsManager())

    anyio.run(service._send_log, subscription_id, log_entry)

    assert sync_log.details == [log_entry]
    assert sent_logs == [(subscription_id, log_entry)]


def test_fetch_resources_batch_skips_resource_type_on_bilibili_412() -> None:
    from bilibili_api.exceptions import NetworkException

    subscription_id = uuid.uuid4()
    sent_logs = []

    class FakeClient:
        async def get_user_videos(self, _uid, page=1, page_size=50):
            raise NetworkException(412, "风控页面")

    service = SyncService(session=object(), ws_manager=object())

    async def fake_send_log(_subscription_id, log_entry, _sync_log_id=None):
        sent_logs.append(log_entry)

    service._send_log = fake_send_log

    result = anyio.run(
        service._fetch_resources_batch,
        FakeClient(),
        SimpleNamespace(
            id=subscription_id,
            uploader_uid="11473291",
            sync_config={"batch_size": 50},
        ),
        "video",
        0,
    )

    assert result == []
    assert sent_logs[-1]["level"] == "WARNING"
    assert "B站风控" in sent_logs[-1]["message"]


def test_incremental_sync_processes_current_old_batch_for_backfill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.bilibili import sync_service as sync_service_module

    subscription_id = uuid.uuid4()
    last_sync_at = datetime.now(timezone.utc)
    account = SimpleNamespace(credentials="encrypted", auth_type="qrcode")
    subscription = SimpleNamespace(
        id=subscription_id,
        account=account,
        uploader_name="UP主",
        uploader_uid="11473291",
        sync_config={"resource_types": ["dynamic"], "batch_size": 50},
        last_sync_at=last_sync_at,
    )
    saved_resource_ids = []

    class FakeSession:
        def get(self, model, obj_id):
            if model is BilibiliSubscription and obj_id == subscription_id:
                return subscription
            return None

        def add(self, _obj):
            pass

        def commit(self):
            pass

    class FakeClient:
        def __init__(self, _credentials, _auth_type):
            pass

        async def check_uploader_exists(self, _uid):
            return True

        async def verify_credentials(self):
            return True

    service = SyncService(FakeSession(), object())

    async def fake_retry_failed_resources(_subscription_id, _client):
        return (0, 0)

    async def fake_fetch_resources_batch(_client, _subscription, _resource_type, _offset):
        return [
            {
                "resource_type": "dynamic",
                "resource_id": "old-1",
                "title": "旧动态1",
                "published_at": last_sync_at - timedelta(minutes=1),
            },
            {
                "resource_type": "dynamic",
                "resource_id": "old-2",
                "title": "旧动态2",
                "published_at": last_sync_at - timedelta(minutes=2),
            },
        ]

    async def fake_save_resource(_subscription_id, resource_data, _client):
        saved_resource_ids.append(resource_data["resource_id"])
        return "skipped"

    async def fake_send_log(_subscription_id, _log_entry, sync_log_id=None):
        pass

    async def fake_sleep(_seconds):
        pass

    monkeypatch.setattr(sync_service_module, "decrypt_credentials", lambda _credentials: {})
    monkeypatch.setattr(sync_service_module, "BilibiliClient", FakeClient)
    monkeypatch.setattr(sync_service_module.asyncio, "sleep", fake_sleep)
    service._retry_failed_resources = fake_retry_failed_resources
    service._fetch_resources_batch = fake_fetch_resources_batch
    service._save_resource = fake_save_resource
    service._send_log = fake_send_log

    anyio.run(service.sync_subscription, subscription_id)

    assert saved_resource_ids == ["old-1", "old-2"]


def test_manual_sync_uses_history_limit_after_first_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.bilibili import sync_service as sync_service_module

    subscription_id = uuid.uuid4()
    last_sync_at = datetime.now(timezone.utc)
    account = SimpleNamespace(credentials="encrypted", auth_type="qrcode")
    subscription = SimpleNamespace(
        id=subscription_id,
        account=account,
        uploader_name="UP主",
        uploader_uid="11473291",
        sync_config={
            "resource_types": ["dynamic"],
            "batch_size": 50,
            "history_limit": 100,
        },
        last_sync_at=last_sync_at,
    )
    offsets = []

    class FakeSession:
        def get(self, model, obj_id):
            if model is BilibiliSubscription and obj_id == subscription_id:
                return subscription
            return None

        def add(self, _obj):
            pass

        def commit(self):
            pass

    class FakeClient:
        def __init__(self, _credentials, _auth_type):
            pass

        async def check_uploader_exists(self, _uid):
            return True

        async def verify_credentials(self):
            return True

    service = SyncService(FakeSession(), object())

    async def fake_retry_failed_resources(_subscription_id, _client):
        return (0, 0)

    async def fake_fetch_resources_batch(_client, _subscription, _resource_type, offset):
        offsets.append(offset)
        return [
            {
                "resource_type": "dynamic",
                "resource_id": f"old-{offset}-{index}",
                "title": "旧动态",
                "published_at": last_sync_at - timedelta(minutes=offset + index + 1),
            }
            for index in range(50)
        ]

    async def fake_save_resource(_subscription_id, _resource_data, _client):
        return "skipped"

    async def fake_send_log(_subscription_id, _log_entry, sync_log_id=None):
        pass

    monkeypatch.setattr(sync_service_module, "decrypt_credentials", lambda _credentials: {})
    monkeypatch.setattr(sync_service_module, "BilibiliClient", FakeClient)
    service._retry_failed_resources = fake_retry_failed_resources
    service._fetch_resources_batch = fake_fetch_resources_batch
    service._save_resource = fake_save_resource
    service._send_log = fake_send_log

    anyio.run(service.sync_subscription, subscription_id, "manual")

    assert offsets == [0, 50]


def test_sync_completion_log_is_persisted_after_status_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.bilibili import sync_service as sync_service_module

    subscription_id = uuid.uuid4()
    account = SimpleNamespace(credentials="encrypted", auth_type="qrcode")
    subscription = SimpleNamespace(
        id=subscription_id,
        account=account,
        uploader_name="UP主",
        uploader_uid="11473291",
        sync_config={"resource_types": ["dynamic"], "batch_size": 50},
        last_sync_at=None,
    )
    sent_logs = []

    class FakeSession:
        def get(self, model, obj_id):
            if model is BilibiliSubscription and obj_id == subscription_id:
                return subscription
            return None

        def add(self, _obj):
            pass

        def commit(self):
            pass

    class FakeClient:
        def __init__(self, _credentials, _auth_type):
            pass

        async def check_uploader_exists(self, _uid):
            return True

        async def verify_credentials(self):
            return True

    service = SyncService(FakeSession(), object())

    async def fake_retry_failed_resources(_subscription_id, _client):
        return (0, 0)

    async def fake_fetch_resources_batch(_client, _subscription, _resource_type, _offset):
        return []

    async def fake_send_log(_subscription_id, log_entry, sync_log_id=None):
        sent_logs.append((log_entry, sync_log_id))

    monkeypatch.setattr(sync_service_module, "decrypt_credentials", lambda _credentials: {})
    monkeypatch.setattr(sync_service_module, "BilibiliClient", FakeClient)
    service._retry_failed_resources = fake_retry_failed_resources
    service._fetch_resources_batch = fake_fetch_resources_batch
    service._send_log = fake_send_log

    sync_log_id = anyio.run(service.sync_subscription, subscription_id)

    completion_logs = [
        (entry, persisted_log_id)
        for entry, persisted_log_id in sent_logs
        if entry["message"].startswith("同步完成")
    ]
    assert completion_logs == [(
        {
            "timestamp": completion_logs[0][0]["timestamp"],
            "level": "INFO",
            "message": "同步完成：成功 0 条，跳过 0 条，失败 0 条",
        },
        sync_log_id,
    )]


def test_manual_sync_endpoint_schedules_background_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password="hash",
        is_superuser=True,
    )
    subscription_id = uuid.uuid4()
    scheduled = []

    monkeypatch.setattr(
        bilibili_router.crud,
        "get_subscription",
        lambda _session, sub_id: SimpleNamespace(id=sub_id, user_id=user.id),
    )

    class FakeBackgroundTasks:
        def add_task(self, func, *args):
            scheduled.append((func, args))

    class FakeSession:
        def add(self, obj):
            assert isinstance(obj, SyncLog)

        def commit(self):
            return None

        def refresh(self, obj):
            assert isinstance(obj, SyncLog)

    async def call_sync_endpoint():
        return await bilibili_router.sync_subscription(
            sub_id=subscription_id,
            session=FakeSession(),
            current_user=user,
            background_tasks=FakeBackgroundTasks(),
        )

    response = anyio.run(call_sync_endpoint)

    assert response.message == "同步已开始"
    assert len(scheduled) == 1
    assert scheduled[0][1] == (subscription_id, response.sync_log_id)


def test_qrcode_check_creates_account_when_scan_confirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password="hash",
        is_superuser=True,
    )
    qrcode_key = str(uuid.uuid4())
    created = {}

    class FakeCredential:
        sessdata = "sess"
        bili_jct = "jct"
        buvid3 = "buvid"
        dedeuserid = "11473291"
        ac_time_value = "refresh"

    class FakeClient:
        def __init__(self, _credentials, _auth_type):
            pass

        async def get_current_account_profile(self):
            return {
                "uid": "11473291",
                "name": "笨笨的韭菜",
                "avatar": "https://example.com/avatar.jpg",
                "follower_count": 123,
                "description": "简介",
            }

    class FakeLogin:
        async def check_state(self):
            from bilibili_api.login_v2 import QrCodeLoginEvents

            return QrCodeLoginEvents.DONE

        def get_credential(self):
            return FakeCredential()

    bilibili_router._qr_login_sessions[qrcode_key] = {
        "login": FakeLogin(),
        "user_id": user.id,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=3),
    }
    monkeypatch.setattr(bilibili_router, "encrypt_credentials", lambda data: f"encrypted:{data['sessdata']}")
    monkeypatch.setattr(bilibili_router, "BilibiliClient", FakeClient)

    def fake_create_account(_session, user_id, data):
        created.update({"user_id": user_id, "data": data})
        return BilibiliAccount(
            id=uuid.uuid4(),
            user_id=user_id,
            **data,
            is_active=True,
            created_at=None,
            updated_at=None,
        )

    monkeypatch.setattr(bilibili_router.crud, "create_account", fake_create_account)

    async def call_check_qrcode():
        return await bilibili_router.check_qrcode(
            data=bilibili_router.QRCodeCheckRequest(qrcode_key=qrcode_key),
            session=object(),
            current_user=user,
        )

    response = anyio.run(call_check_qrcode)

    assert response.status == "confirmed"
    assert response.account is not None
    assert created["user_id"] == user.id
    assert created["data"]["auth_type"] == "qrcode"
    assert created["data"]["credentials"] == "encrypted:sess"
    assert created["data"]["account_name"] == "笨笨的韭菜"
    assert created["data"]["display_name"] == "笨笨的韭菜"
    assert created["data"]["avatar_url"] == "https://example.com/avatar.jpg"
    assert qrcode_key not in bilibili_router._qr_login_sessions


def test_qrcode_check_keeps_unscanned_qrcode_pending() -> None:
    from bilibili_api.login_v2 import QrCodeLoginEvents

    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password="hash",
        is_superuser=True,
    )
    qrcode_key = str(uuid.uuid4())

    class FakeLogin:
        async def check_state(self):
            return QrCodeLoginEvents.SCAN

    bilibili_router._qr_login_sessions[qrcode_key] = {
        "login": FakeLogin(),
        "user_id": user.id,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=3),
    }

    async def call_check_qrcode():
        return await bilibili_router.check_qrcode(
            data=bilibili_router.QRCodeCheckRequest(qrcode_key=qrcode_key),
            session=object(),
            current_user=user,
        )

    response = anyio.run(call_check_qrcode)

    assert response.status == "pending"


def test_qrcode_login_uses_tv_channel() -> None:
    from bilibili_api.login_v2 import QrCodeLoginChannel

    assert bilibili_router.QRCODE_LOGIN_CHANNEL is QrCodeLoginChannel.TV


def test_qrcode_check_returns_configuration_error_when_encryption_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bilibili_api.login_v2 import QrCodeLoginEvents

    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password="hash",
        is_superuser=True,
    )
    qrcode_key = str(uuid.uuid4())

    class FakeLogin:
        async def check_state(self):
            return QrCodeLoginEvents.DONE

        def get_credential(self):
            return SimpleNamespace(
                sessdata="sess",
                bili_jct="csrf",
                buvid3="buvid",
                dedeuserid="1",
                ac_time_value="refresh",
            )

    def fake_encrypt_credentials(_credentials):
        raise ValueError("缺少 BILIBILI_CREDENTIALS_ENCRYPTION_KEY 配置")

    monkeypatch.setattr(bilibili_router, "encrypt_credentials", fake_encrypt_credentials)
    bilibili_router._qr_login_sessions[qrcode_key] = {
        "login": FakeLogin(),
        "user_id": user.id,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=3),
    }

    async def call_check_qrcode():
        return await bilibili_router.check_qrcode(
            data=bilibili_router.QRCodeCheckRequest(qrcode_key=qrcode_key),
            session=object(),
            current_user=user,
        )

    with pytest.raises(HTTPException) as exc_info:
        anyio.run(call_check_qrcode)

    assert exc_info.value.status_code == 500
    assert "BILIBILI_CREDENTIALS_ENCRYPTION_KEY" in exc_info.value.detail
    assert qrcode_key in bilibili_router._qr_login_sessions


def test_bilibili_user_info_allows_missing_follower(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.bilibili.client import BilibiliClient

    class FakeUser:
        def __init__(self, uid=None, credential=None):
            self.uid = uid

        async def get_user_info(self):
            return {"name": "UP主", "face": "avatar.png", "sign": "简介"}

        async def get_relation_info(self):
            return {"follower": 123}

    monkeypatch.setattr("app.bilibili.client.user.User", FakeUser)

    client = BilibiliClient({"sessdata": "sess", "bili_jct": "csrf"}, "qrcode")

    info = anyio.run(client.get_user_info, "11473291")

    assert info["follower_count"] == 123


def test_bilibili_user_info_defaults_missing_follower_to_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.bilibili.client import BilibiliClient

    class FakeUser:
        def __init__(self, uid=None, credential=None):
            self.uid = uid

        async def get_user_info(self):
            return {"name": "UP主", "face": "avatar.png", "sign": "简介"}

        async def get_relation_info(self):
            return {}

    monkeypatch.setattr("app.bilibili.client.user.User", FakeUser)

    client = BilibiliClient({"sessdata": "sess", "bili_jct": "csrf"}, "qrcode")

    info = anyio.run(client.get_user_info, "11473291")

    assert info["follower_count"] == 0


def test_verify_credentials_uses_logged_in_mid(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.bilibili.client import BilibiliClient

    created_uids = []

    class FakeUser:
        def __init__(self, uid=None, credential=None):
            created_uids.append(uid)

        async def get_user_info(self):
            return {"name": "UP主", "face": "avatar.png"}

    monkeypatch.setattr("app.bilibili.client.user.User", FakeUser)

    client = BilibiliClient({"sessdata": "sess", "bili_jct": "csrf", "dedeuserid": "123"}, "qrcode")

    assert anyio.run(client.verify_credentials) is True
    assert created_uids == [123]


def test_transform_dynamic_data_accepts_card_dict() -> None:
    from app.bilibili.client import BilibiliClient

    client = BilibiliClient({"sessdata": "sess", "bili_jct": "csrf"}, "qrcode")

    transformed = client._transform_dynamic_data({
        "card": {"title": "动态标题", "dynamic": "动态正文"},
        "desc": {
            "type": 1,
            "dynamic_id": 123456,
            "timestamp": 1_700_000_000,
            "like": 7,
        },
    })

    assert transformed["title"] == "动态标题"
    assert transformed["full_content"] == "动态正文"


def test_transform_dynamic_data_reads_picture_dynamic_description() -> None:
    from app.bilibili.client import BilibiliClient

    client = BilibiliClient({"sessdata": "sess", "bili_jct": "csrf"}, "qrcode")

    transformed = client._transform_dynamic_data({
        "card": {
            "item": {
                "description": "图文动态正文",
                "pictures": [{"img_src": "https://example.com/a.jpg"}],
            }
        },
        "desc": {
            "type": 2,
            "dynamic_id": 1205068631041376260,
            "timestamp": 1_700_000_000,
            "like": 7,
        },
    })

    assert transformed["summary"] == "图文动态正文"
    assert transformed["full_content"] == "图文动态正文"
    assert transformed["attachments"]["images"] == ["https://example.com/a.jpg"]


def test_transform_dynamic_data_reads_repost_content() -> None:
    from app.bilibili.client import BilibiliClient

    client = BilibiliClient({"sessdata": "sess", "bili_jct": "csrf"}, "qrcode")

    transformed = client._transform_dynamic_data({
        "card": {
            "item": {"content": "转发动态正文"},
            "origin": '{"item":{"content":"原动态正文"}}',
        },
        "desc": {
            "type": 1,
            "dynamic_id": 1206257967593160728,
            "timestamp": 1_700_000_000,
            "like": 7,
        },
    })

    assert transformed["summary"] == "转发动态正文"
    assert transformed["full_content"] == "转发动态正文"


def test_transform_dynamic_data_treats_null_pictures_as_empty() -> None:
    from app.bilibili.client import BilibiliClient

    client = BilibiliClient({"sessdata": "sess", "bili_jct": "csrf"}, "qrcode")

    transformed = client._transform_dynamic_data({
        "card": {"item": {"description": "正文", "pictures": None}},
        "desc": {
            "type": 2,
            "dynamic_id": 1205068631041376260,
            "timestamp": 1_700_000_000,
            "like": 7,
        },
    })

    assert transformed["attachments"]["images"] == []


def test_get_user_dynamics_treats_null_cards_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.bilibili.client import BilibiliClient

    class FakeUser:
        def __init__(self, uid=None, credential=None):
            self.uid = uid

        async def get_dynamics(self, offset=None):
            return {"cards": None}

    monkeypatch.setattr("app.bilibili.client.user.User", FakeUser)

    client = BilibiliClient({"sessdata": "sess", "bili_jct": "csrf"}, "qrcode")

    assert anyio.run(client.get_user_dynamics, "11473291") == []


def test_transform_article_data_defaults_missing_stats() -> None:
    from app.bilibili.client import BilibiliClient

    client = BilibiliClient({"sessdata": "sess", "bili_jct": "csrf"}, "qrcode")

    transformed = client._transform_article_data({
        "id": 123,
        "title": "专栏标题",
        "image_urls": [],
        "summary": "摘要",
        "publish_time": 1_700_000_000,
    })

    assert transformed["resource_meta"]["view_count"] == 0
    assert transformed["resource_meta"]["like_count"] == 0


def test_get_user_articles_fetches_authenticated_note_content(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.bilibili.client import BilibiliClient

    class FakeUser:
        def __init__(self, uid=None, credential=None):
            self.uid = uid

        async def get_articles(self, pn=1):
            return {
                "articles": [
                    {
                        "id": 123,
                        "title": "充电笔记",
                        "image_urls": [],
                        "summary": "摘要",
                        "publish_time": 1_700_000_000,
                        "category": {"id": 42},
                    }
                ]
            }

    class FakeNote:
        def __init__(self, cvid=None, note_type=None, credential=None):
            self.credential = credential

        async def fetch_content(self):
            pass

        def markdown(self):
            return "充电笔记正文"

    monkeypatch.setattr("app.bilibili.client.user.User", FakeUser)
    monkeypatch.setattr("app.bilibili.client.article.Note", FakeNote)

    client = BilibiliClient({"sessdata": "sess", "bili_jct": "csrf"}, "qrcode")

    [result] = anyio.run(client.get_user_articles, "11473291")

    assert result["full_content"] == "充电笔记正文"


def test_article_full_content_does_not_fetch_web_page_for_non_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.bilibili.client import BilibiliClient

    article_called = False

    class FakeArticle:
        def __init__(self, *args, **kwargs):
            nonlocal article_called
            article_called = True

    monkeypatch.setattr("app.bilibili.client.article.Article", FakeArticle)

    client = BilibiliClient({"sessdata": "sess", "bili_jct": "csrf"}, "qrcode")

    content = anyio.run(
        client._fetch_article_full_content,
        {"id": 123, "summary": "摘要", "category": {"id": 1}},
    )

    assert content == "摘要"
    assert article_called is False


def test_get_user_articles_treats_missing_articles_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.bilibili.client import BilibiliClient

    class FakeUser:
        def __init__(self, uid=None, credential=None):
            self.uid = uid

        async def get_articles(self, pn=1):
            return {}

    monkeypatch.setattr("app.bilibili.client.user.User", FakeUser)

    client = BilibiliClient({"sessdata": "sess", "bili_jct": "csrf"}, "qrcode")

    assert anyio.run(client.get_user_articles, "11473291") == []


def test_failed_sync_log_entry_is_persisted_after_status_changes() -> None:
    subscription_id = uuid.uuid4()
    sync_log_id = uuid.uuid4()
    sync_log = SyncLog(
        id=sync_log_id,
        subscription_id=subscription_id,
        sync_type="manual",
        status="failed",
        start_time=datetime.now(timezone.utc),
        details=[{"message": "开始同步"}],
    )

    class FakeSession:
        def get(self, _model, _id):
            return sync_log

        def add(self, _obj):
            pass

        def commit(self):
            pass

    class FakeWsManager:
        async def broadcast(self, _subscription_id, _log_entry):
            pass

    service = SyncService(FakeSession(), FakeWsManager())

    anyio.run(
        service._send_log,
        subscription_id,
        {"level": "ERROR", "message": "同步失败"},
        sync_log_id,
    )

    assert sync_log.details[-1]["message"] == "同步失败"


def test_subscriptions_include_latest_sync_status() -> None:
    subscription_id = uuid.uuid4()
    sub = BilibiliSubscription(
        id=subscription_id,
        user_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        uploader_uid="11473291",
        uploader_name="UP主",
        uploader_info={},
        sync_config={"resource_types": ["video"], "sync_frequency": "manual"},
    )
    sync_log = SyncLog(
        subscription_id=subscription_id,
        sync_type="manual",
        status="failed",
        start_time=datetime.now(timezone.utc),
        details=[],
    )

    class FakeSession:
        def exec(self, _statement):
            return self

        def first(self):
            return sync_log

    [result] = bilibili_router._with_latest_sync_status(FakeSession(), [sub])

    assert result["latest_sync_status"] == "failed"
    assert result["latest_sync_log_id"] == sync_log.id


def test_create_subscription_registers_sync_job(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        hashed_password="hash",
        is_superuser=False,
    )
    account_id = uuid.uuid4()
    account = SimpleNamespace(id=account_id, user_id=user.id, credentials="encrypted", auth_type="qrcode")
    scheduler = object()
    calls = {}

    class FakeClient:
        def __init__(self, _credentials, _auth_type):
            pass

        async def check_uploader_exists(self, _uid):
            return True

        async def get_user_info(self, uid):
            return {
                "uid": uid,
                "name": "UP主",
                "avatar": "avatar.png",
                "follower_count": 1,
                "description": "简介",
            }

    sub = BilibiliSubscription(
        id=uuid.uuid4(),
        user_id=user.id,
        account_id=account_id,
        uploader_uid="11473291",
        uploader_name="UP主",
        uploader_info={},
        sync_config={"resource_types": ["video"], "sync_frequency": "6h"},
    )

    monkeypatch.setattr(bilibili_router.crud, "get_account", lambda _session, _id: account)
    monkeypatch.setattr(bilibili_router.crud, "get_subscriptions", lambda _session, _user_id: [])
    monkeypatch.setattr(bilibili_router.crud, "create_subscription", lambda *_args: sub)
    monkeypatch.setattr(bilibili_router, "decrypt_credentials", lambda _credentials: {})
    monkeypatch.setattr(bilibili_router, "BilibiliClient", FakeClient)

    from app.bilibili import scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "get_scheduler", lambda: scheduler, raising=False)

    def fake_add_sync_job(configured_scheduler, subscription):
        calls["scheduler"] = configured_scheduler
        calls["subscription"] = subscription

    monkeypatch.setattr(scheduler_module, "add_sync_job", fake_add_sync_job)

    class FakeResult:
        def first(self):
            return None

    class FakeSession:
        def exec(self, _statement):
            return FakeResult()

    result = anyio.run(
        bilibili_router.create_subscription,
        bilibili_router.SubscriptionCreate(
            account_id=account_id,
            uploader_uid="11473291",
            sync_config=SyncConfig(sync_frequency="6h"),
        ),
        FakeSession(),
        user,
    )

    assert result is sub
    assert calls == {"scheduler": scheduler, "subscription": sub}


def test_update_subscription_reschedules_sync_job(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        hashed_password="hash",
        is_superuser=False,
    )
    subscription_id = uuid.uuid4()
    scheduler = object()
    calls = []
    sub = BilibiliSubscription(
        id=subscription_id,
        user_id=user.id,
        account_id=uuid.uuid4(),
        uploader_uid="11473291",
        uploader_name="UP主",
        uploader_info={},
        sync_config={"resource_types": ["video"], "sync_frequency": "1h"},
    )

    monkeypatch.setattr(bilibili_router.crud, "get_subscription", lambda _session, _id: sub)
    monkeypatch.setattr(bilibili_router.crud, "update_subscription", lambda *_args: sub)

    from app.bilibili import scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "get_scheduler", lambda: scheduler, raising=False)
    monkeypatch.setattr(
        scheduler_module,
        "remove_sync_job",
        lambda configured_scheduler, sub_id: calls.append(("remove", configured_scheduler, sub_id)),
    )
    monkeypatch.setattr(
        scheduler_module,
        "add_sync_job",
        lambda configured_scheduler, subscription: calls.append(("add", configured_scheduler, subscription)),
    )

    result = bilibili_router.update_subscription(
        sub_id=subscription_id,
        data=bilibili_router.SubscriptionUpdate(
            sync_config=SyncConfig(sync_frequency="1h"),
        ),
        session=object(),
        current_user=user,
    )

    assert result is sub
    assert calls == [
        ("remove", scheduler, subscription_id),
        ("add", scheduler, sub),
    ]


def test_read_resources_passes_date_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password="hash",
        is_superuser=True,
    )
    calls = {}
    start_date = datetime(2026, 5, 1, tzinfo=timezone.utc).date()
    end_date = datetime(2026, 5, 24, tzinfo=timezone.utc).date()

    def fake_get_resources(_session, **kwargs):
        calls.update(kwargs)
        return []

    monkeypatch.setattr(bilibili_router.crud, "get_resources", fake_get_resources)

    assert bilibili_router.read_resources(
        session=object(),
        subscription_id=None,
        resource_type=None,
        keyword=None,
        start_date=start_date,
        end_date=end_date,
        page=1,
        page_size=20,
        current_user=user,
    ) == []

    assert calls["start_date"] == start_date
    assert calls["end_date"] == end_date


def test_save_resource_reports_existing_as_skipped() -> None:
    subscription_id = uuid.uuid4()
    published_at = datetime.now(timezone.utc)
    resource_data = {
        "resource_type": "video",
        "resource_id": "BV1xx",
        "title": "已存在视频",
        "summary": "简介",
        "full_content": "简介",
        "published_at": published_at,
    }
    existing = BilibiliResource(
        subscription_id=subscription_id,
        resource_type="video",
        resource_id="BV1xx",
        title="已存在视频",
        summary="简介",
        full_content="简介",
        published_at=published_at,
    )
    sent_logs = []

    class FakeResult:
        def first(self):
            return existing

    class FakeSession:
        def exec(self, _statement):
            return FakeResult()

    class FakeWsManager:
        async def broadcast(self, _subscription_id, log_entry):
            sent_logs.append(log_entry)

    service = SyncService(FakeSession(), FakeWsManager())

    async def fake_send_log(_subscription_id, log_entry, _sync_log_id=None):
        sent_logs.append(log_entry)

    service._send_log = fake_send_log

    result = anyio.run(service._save_resource, subscription_id, resource_data, object())

    assert result == "skipped"
    assert sent_logs[-1]["status"] == "skipped"


def test_save_resource_updates_existing_when_full_content_is_better() -> None:
    subscription_id = uuid.uuid4()
    existing = BilibiliResource(
        subscription_id=subscription_id,
        resource_type="article",
        resource_id="123",
        title="旧标题",
        summary="摘要",
        full_content="摘要",
        resource_meta={},
        published_at=datetime.now(timezone.utc),
    )
    resource_data = {
        "resource_type": "article",
        "resource_id": "123",
        "title": "新标题",
        "summary": "摘要",
        "full_content": "完整正文内容",
        "published_at": existing.published_at,
        "resource_meta": {"url": "https://www.bilibili.com/read/cv123"},
    }
    sent_logs = []
    added = []

    class FakeResult:
        def first(self):
            return existing

    class FakeSession:
        def exec(self, _statement):
            return FakeResult()

        def add(self, obj):
            added.append(obj)

        def commit(self):
            pass

    class FakeWsManager:
        async def broadcast(self, _subscription_id, log_entry):
            sent_logs.append(log_entry)

    service = SyncService(FakeSession(), FakeWsManager())

    async def fake_send_log(_subscription_id, log_entry, _sync_log_id=None):
        sent_logs.append(log_entry)

    service._send_log = fake_send_log

    result = anyio.run(service._save_resource, subscription_id, resource_data, object())

    assert result == "success"
    assert existing.title == "新标题"
    assert existing.full_content == "完整正文内容"
    assert existing.resource_meta == resource_data["resource_meta"]
    assert added == [existing]
    assert sent_logs[-1]["status"] == "success"
