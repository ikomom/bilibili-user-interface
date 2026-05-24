# Bilibili 模块设计文档

## 概述

为项目添加 Bilibili 功能模块，支持管理 B站账户、订阅 UP主、自动同步资源（视频、动态、专栏）。

**核心功能：**
1. **账户管理** - 支持多种认证方式（Cookie/SESSDATA/扫码登录）
2. **订阅管理** - 订阅 UP主并配置同步规则
3. **资源同步** - 自动/手动同步 UP主发布的内容
4. **实时日志** - WebSocket 推送同步进度和详细日志
5. **权限控制** - 基于 RBAC 的细粒度权限管理

**技术栈：**
- 后端：FastAPI + bilibili-api + APScheduler + WebSocket
- 前端：React + TanStack Query + react-use-websocket + shadcn/ui
- 数据库：PostgreSQL（新增 8 张表）

---

## 数据库设计

### 1. Bilibili 功能表（4 张）

#### bilibili_accounts（B站账户表）
```sql
CREATE TABLE bilibili_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_name VARCHAR(100) NOT NULL,  -- 账户备注名
    auth_type VARCHAR(20) NOT NULL,      -- 'cookie' | 'sessdata' | 'qrcode'
    credentials JSONB NOT NULL,          -- 加密存储的凭证
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_bilibili_accounts_user_id ON bilibili_accounts(user_id);
```

#### bilibili_uploader_subscriptions（UP主订阅表）
```sql
CREATE TABLE bilibili_uploader_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES bilibili_accounts(id) ON DELETE CASCADE,
    uploader_uid VARCHAR(50) NOT NULL,   -- UP主 B站 UID
    uploader_name VARCHAR(100) NOT NULL,
    uploader_avatar TEXT,
    uploader_info JSONB,                 -- 粉丝数、简介等
    sync_config JSONB NOT NULL,          -- 同步配置
    is_paused BOOLEAN DEFAULT false,
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, uploader_uid)        -- 同一用户不能重复订阅
);

CREATE INDEX idx_subscriptions_user_id ON bilibili_uploader_subscriptions(user_id);
CREATE INDEX idx_subscriptions_uploader_uid ON bilibili_uploader_subscriptions(uploader_uid);
```

**sync_config 结构：**
```json
{
  "resource_types": ["video", "dynamic", "article"],
  "sync_frequency": "6h",  // "1h" | "6h" | "1d" | "1w" | "manual"
  "history_limit": 50,     // 首次同步历史数量，null 表示全量
  "batch_size": 50         // 每次获取数量
}
```

#### bilibili_resources（资源表）
```sql
CREATE TABLE bilibili_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES bilibili_uploader_subscriptions(id) ON DELETE CASCADE,
    resource_type VARCHAR(20) NOT NULL,  -- 'video' | 'dynamic' | 'article'
    resource_id VARCHAR(50) NOT NULL,    -- BV号/动态ID/专栏ID
    title TEXT NOT NULL,
    cover_url TEXT,
    summary TEXT,                        -- 预览文本（列表展示）
    full_content TEXT,                   -- 完整内容（详情页）
    attachments JSONB,                   -- 附件信息
    metadata JSONB NOT NULL,             -- 原始数据 + 转换后的字段
    published_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(subscription_id, resource_id)
);

CREATE INDEX idx_resources_subscription_id ON bilibili_resources(subscription_id);
CREATE INDEX idx_resources_published_at ON bilibili_resources(published_at DESC);
CREATE INDEX idx_resources_type ON bilibili_resources(resource_type);
```

**metadata 结构示例：**
```json
{
  "video_type": 1,
  "video_type_display": "自制",
  "play_count": 10000,
  "like_count": 500,
  "coin_count": 200,
  "duration": 600,
  "bvid": "BV1xx...",
  "url": "https://www.bilibili.com/video/BV1xx..."
}
```

#### sync_logs（同步日志表）
```sql
CREATE TABLE sync_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES bilibili_uploader_subscriptions(id) ON DELETE CASCADE,
    sync_type VARCHAR(20) NOT NULL,      -- 'manual' | 'scheduled'
    status VARCHAR(20) NOT NULL,         -- 'running' | 'success' | 'failed'
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    total_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    error_message TEXT,
    details JSONB                        -- 详细日志条目
);

CREATE INDEX idx_sync_logs_subscription_id ON sync_logs(subscription_id);
CREATE INDEX idx_sync_logs_start_time ON sync_logs(start_time DESC);
```

#### failed_resources（失败资源表）
```sql
CREATE TABLE failed_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES bilibili_uploader_subscriptions(id) ON DELETE CASCADE,
    resource_id VARCHAR(50) NOT NULL,
    resource_type VARCHAR(20) NOT NULL,
    failed_at TIMESTAMP DEFAULT NOW(),
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    metadata JSONB,                      -- 保存资源基本信息
    UNIQUE(subscription_id, resource_id)
);

CREATE INDEX idx_failed_resources_subscription_id ON failed_resources(subscription_id);
```

### 2. RBAC 权限表（4 张）

#### permissions（权限表）
```sql
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) NOT NULL UNIQUE,   -- 'bilibili:account:create'
    name VARCHAR(100) NOT NULL,
    module VARCHAR(50) NOT NULL,         -- 'bilibili'
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_permissions_module ON permissions(module);
```

#### roles（角色表）
```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    is_system BOOLEAN DEFAULT false,     -- 系统预设角色不可删除
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### role_permissions（角色-权限关联表）
```sql
CREATE TABLE role_permissions (
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);
```

#### user_roles（用户-角色关联表）
```sql
CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);
```

---

## 后端架构设计

### 目录结构

```
backend/app/
├── bilibili/
│   ├── __init__.py
│   ├── client.py              # bilibili-api 封装
│   ├── sync_service.py        # 同步服务
│   ├── scheduler.py           # APScheduler 定时任务
│   ├── websocket.py           # WebSocket 连接管理
│   ├── init_permissions.py    # 权限初始化
│   ├── models.py              # SQLModel 模型
│   ├── schemas.py             # Pydantic schemas + 枚举字典
│   ├── crud.py                # 数据库操作
│   └── router.py              # API 路由
├── api/
│   └── main.py                # 注册 bilibili router
├── core/
│   ├── security.py            # 添加凭证加密/解密
│   └── permissions.py         # 权限检查装饰器
└── initial_data.py            # 调用权限初始化
```

### 核心模块设计

#### 0. 枚举字典和转换（schemas.py）

**枚举映射字典：**
```python
# app/bilibili/schemas.py

# 视频类型
VIDEO_TYPE_DISPLAY = {
    1: "自制",
    2: "转载"
}

# 动态类型
DYNAMIC_TYPE_DISPLAY = {
    1: "转发动态",
    2: "图文动态",
    4: "文字动态",
    8: "视频动态",
    16: "小视频",
    64: "专栏动态",
    256: "音频动态",
    2048: "普通动态"
}

# 资源类型
RESOURCE_TYPE_DISPLAY = {
    "video": "视频",
    "dynamic": "动态",
    "article": "专栏"
}

# 同步频率
SYNC_FREQUENCY_DISPLAY = {
    "1h": "每小时",
    "6h": "每6小时",
    "1d": "每天",
    "1w": "每周",
    "manual": "手动"
}

# 同步状态
SYNC_STATUS_DISPLAY = {
    "running": "同步中",
    "success": "成功",
    "failed": "失败"
}
```

#### 1. bilibili-api 客户端封装（client.py）

**BilibiliClient 类：**
```python
from bilibili_api import user, video, Credential
from bilibili_api.exceptions import ResponseCodeException

class BilibiliClient:
    def __init__(self, credentials: dict, auth_type: str):
        """初始化客户端，根据 auth_type 设置凭证"""
        self.auth_type = auth_type
        self.credential = self._create_credential(credentials)
        
    def _create_credential(self, credentials: dict) -> Credential:
        """根据凭证类型创建 Credential 对象"""
        if self.auth_type == "cookie":
            # 解析 Cookie 字符串
            cookie_dict = self._parse_cookie(credentials["cookie"])
            return Credential(
                sessdata=cookie_dict.get("SESSDATA"),
                bili_jct=cookie_dict.get("bili_jct"),
                buvid3=cookie_dict.get("buvid3")
            )
        elif self.auth_type in ["sessdata", "qrcode"]:
            return Credential(
                sessdata=credentials["sessdata"],
                bili_jct=credentials["bili_jct"],
                buvid3=credentials.get("buvid3")
            )
        
    async def verify_credentials(self) -> bool:
        """验证凭证是否有效"""
        try:
            # 尝试获取当前用户信息
            u = user.User(credential=self.credential)
            await u.get_self_info()
            return True
        except ResponseCodeException:
            return False
        
    async def get_user_info(self, uid: str) -> dict:
        """获取 UP主信息（昵称、头像、粉丝数等）"""
        u = user.User(uid=int(uid), credential=self.credential)
        info = await u.get_user_info()
        return {
            "uid": uid,
            "name": info["name"],
            "avatar": info["face"],
            "follower_count": info["follower"],
            "description": info.get("sign", "")
        }
        
    async def check_uploader_exists(self, uid: str) -> bool:
        """检查 UP主是否存在"""
        try:
            u = user.User(uid=int(uid), credential=self.credential)
            await u.get_user_info()
            return True
        except ResponseCodeException as e:
            if e.code == -404:  # 用户不存在
                return False
            raise
        
    async def get_user_videos(
        self, uid: str, page: int = 1, page_size: int = 50
    ) -> List[dict]:
        """获取 UP主视频列表"""
        u = user.User(uid=int(uid), credential=self.credential)
        videos = await u.get_videos(pn=page, ps=page_size)
        
        return [
            self._transform_video_data(v) 
            for v in videos["list"]["vlist"]
        ]
        
    async def get_user_dynamics(
        self, uid: str, offset: str = None
    ) -> List[dict]:
        """获取 UP主动态"""
        u = user.User(uid=int(uid), credential=self.credential)
        dynamics = await u.get_dynamics(offset=offset)
        
        return [
            self._transform_dynamic_data(d)
            for d in dynamics["cards"]
        ]
        
    async def get_user_articles(
        self, uid: str, page: int = 1
    ) -> List[dict]:
        """获取 UP主专栏"""
        u = user.User(uid=int(uid), credential=self.credential)
        articles = await u.get_articles(pn=page)
        
        return [
            self._transform_article_data(a)
            for a in articles["articles"]
        ]
        
    def _transform_video_data(self, raw: dict) -> dict:
        """转换视频数据，添加 *_display 字段"""
        from app.bilibili.schemas import VIDEO_TYPE_DISPLAY
        
        return {
            "resource_type": "video",
            "resource_id": raw["bvid"],
            "title": raw["title"],
            "cover_url": raw["pic"],
            "summary": raw["description"][:100],
            "full_content": raw["description"],
            "published_at": datetime.fromtimestamp(raw["created"]),
            "metadata": {
                "bvid": raw["bvid"],
                "aid": raw["aid"],
                "video_type": raw.get("copyright", 1),
                "video_type_display": VIDEO_TYPE_DISPLAY.get(raw.get("copyright", 1), "未知"),
                "play_count": raw["play"],
                "like_count": raw.get("like", 0),
                "coin_count": raw.get("coin", 0),
                "duration": raw["length"],
                "url": f"https://www.bilibili.com/video/{raw['bvid']}"
            }
        }
        
    def _transform_dynamic_data(self, raw: dict) -> dict:
        """转换动态数据"""
        from app.bilibili.schemas import DYNAMIC_TYPE_DISPLAY
        
        card = json.loads(raw["card"])
        dynamic_type = raw["desc"]["type"]
        
        return {
            "resource_type": "dynamic",
            "resource_id": str(raw["desc"]["dynamic_id"]),
            "title": card.get("title", "动态"),
            "cover_url": card.get("pic", ""),
            "summary": card.get("content", card.get("dynamic", ""))[:100],
            "full_content": card.get("content", card.get("dynamic", "")),
            "published_at": datetime.fromtimestamp(raw["desc"]["timestamp"]),
            "attachments": self._extract_dynamic_attachments(card),
            "metadata": {
                "dynamic_id": raw["desc"]["dynamic_id"],
                "dynamic_type": dynamic_type,
                "dynamic_type_display": DYNAMIC_TYPE_DISPLAY.get(dynamic_type, "未知"),
                "like_count": raw["desc"].get("like", 0),
                "url": f"https://t.bilibili.com/{raw['desc']['dynamic_id']}"
            }
        }
        
    def _transform_article_data(self, raw: dict) -> dict:
        """转换专栏数据"""
        return {
            "resource_type": "article",
            "resource_id": str(raw["id"]),
            "title": raw["title"],
            "cover_url": raw["image_urls"][0] if raw["image_urls"] else "",
            "summary": raw["summary"],
            "full_content": raw["summary"],  # 完整内容需要单独获取
            "published_at": datetime.fromtimestamp(raw["publish_time"]),
            "metadata": {
                "article_id": raw["id"],
                "view_count": raw["view"],
                "like_count": raw["like"],
                "url": f"https://www.bilibili.com/read/cv{raw['id']}"
            }
        }
        
    def _extract_dynamic_attachments(self, card: dict) -> dict:
        """提取动态附件信息"""
        attachments = {"images": [], "documents": []}
        
        # 提取图片
        if "pictures" in card:
            attachments["images"] = [p["img_src"] for p in card["pictures"]]
        
        return attachments
        
    def _parse_cookie(self, cookie_str: str) -> dict:
        """解析 Cookie 字符串"""
        cookie_dict = {}
        for item in cookie_str.split(";"):
            if "=" in item:
                key, value = item.strip().split("=", 1)
                cookie_dict[key] = value
        return cookie_dict
```

**错误处理：**
- 网络错误：重试 3 次（指数退避：1s, 2s, 4s）
- 认证失败：抛出 `AuthenticationError`
- 限流错误：延迟 5 秒后重试
- UP主不存在：抛出 `UploaderNotFoundError`

**自定义异常（app/bilibili/exceptions.py）：**
```python
class BilibiliAPIError(Exception):
    """Bilibili API 基础异常"""
    pass

class AuthenticationError(BilibiliAPIError):
    """认证失败"""
    pass

class RateLimitError(BilibiliAPIError):
    """被限流"""
    pass

class UploaderNotFoundError(BilibiliAPIError):
    """UP主不存在"""
    pass

class NetworkError(BilibiliAPIError):
    """网络错误"""
    pass
```

#### 2. 同步服务（sync_service.py）

**SyncService 类：**
```python
import random
from tenacity import retry, stop_after_attempt, wait_exponential

class SyncService:
    def __init__(self, session: Session, ws_manager: ConnectionManager):
        self.session = session
        self.ws_manager = ws_manager
        
    async def sync_subscription(
        self, subscription_id: UUID, sync_type: str = "manual"
    ) -> UUID:
        """
        同步单个订阅
        返回 sync_log_id
        """
        subscription = self.session.get(Subscription, subscription_id)
        if not subscription:
            raise ValueError("订阅不存在")
            
        # 1. 创建同步日志记录（status=running）
        sync_log = SyncLog(
            subscription_id=subscription_id,
            sync_type=sync_type,
            status="running",
            start_time=datetime.now(),
            details=[]
        )
        self.session.add(sync_log)
        self.session.commit()
        
        await self._send_log(subscription_id, {
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "message": f"开始同步 UP主：{subscription.uploader_name} (UID: {subscription.uploader_uid})"
        })
        
        try:
            # 2. 检查 UP主是否存在
            account = self.session.get(Account, subscription.account_id)
            credentials = decrypt_credentials(account.credentials)
            client = BilibiliClient(credentials, account.auth_type)
            
            if not await client.check_uploader_exists(subscription.uploader_uid):
                raise UploaderNotFoundError(f"UP主 {subscription.uploader_uid} 不存在")
            
            # 3. 检查账户凭证是否有效
            if not await client.verify_credentials():
                account.is_active = False
                self.session.commit()
                raise AuthenticationError("账户凭证已失效")
            
            # 4. 获取失败资源列表，优先重试
            success_retry, failed_retry = await self._retry_failed_resources(subscription_id, client)
            
            # 5. 根据 sync_config 获取资源
            total_success = success_retry
            total_failed = failed_retry
            total_skipped = 0
            
            is_first_sync = subscription.last_sync_at is None
            
            for resource_type in subscription.sync_config["resource_types"]:
                await self._send_log(subscription_id, {
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO",
                    "message": f"正在获取{resource_type}列表..."
                })
                
                # 6. 分批获取
                offset = 0
                fetched_count = 0
                batch_size = subscription.sync_config.get("batch_size", 50)
                history_limit = subscription.sync_config.get("history_limit")
                
                while True:
                    # 检查是否达到历史限制
                    if is_first_sync and history_limit and fetched_count >= history_limit:
                        break
                    
                    resources = await self._fetch_resources_batch(
                        client, subscription, resource_type, offset
                    )
                    
                    if not resources:
                        break
                    
                    await self._send_log(subscription_id, {
                        "timestamp": datetime.now().isoformat(),
                        "level": "INFO",
                        "message": f"获取到 {len(resources)} 条{resource_type}"
                    })
                    
                    # 7. 处理每条资源
                    for resource_data in resources:
                        # 检查发布时间（增量同步）
                        if not is_first_sync and subscription.last_sync_at:
                            if resource_data["published_at"] <= subscription.last_sync_at:
                                # 已经同步过了，停止
                                break
                        
                        # 保存资源
                        success = await self._save_resource(
                            subscription_id, resource_data, client
                        )
                        
                        if success:
                            total_success += 1
                        else:
                            total_failed += 1
                    
                    fetched_count += len(resources)
                    offset += batch_size
                    
                    # 延迟 3-5 秒（随机）
                    delay = random.uniform(3, 5)
                    await self._send_log(subscription_id, {
                        "timestamp": datetime.now().isoformat(),
                        "level": "INFO",
                        "message": f"延迟 {delay:.1f} 秒后继续获取..."
                    })
                    await asyncio.sleep(delay)
            
            # 8. 更新同步日志（status=success）
            sync_log.status = "success"
            sync_log.end_time = datetime.now()
            sync_log.success_count = total_success
            sync_log.failed_count = total_failed
            sync_log.skipped_count = total_skipped
            
            # 9. 更新 subscription.last_sync_at
            subscription.last_sync_at = datetime.now()
            
            self.session.commit()
            
            await self._send_log(subscription_id, {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"同步完成：成功 {total_success} 条，跳过 {total_skipped} 条，失败 {total_failed} 条"
            })
            
            return sync_log.id
            
        except Exception as e:
            # 更新同步日志（status=failed）
            sync_log.status = "failed"
            sync_log.end_time = datetime.now()
            sync_log.error_message = str(e)
            self.session.commit()
            
            await self._send_log(subscription_id, {
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "message": f"同步失败：{str(e)}",
                "stack_trace": traceback.format_exc()
            })
            
            raise
        
    async def _fetch_resources_batch(
        self, client: BilibiliClient, subscription: Subscription, 
        resource_type: str, offset: int
    ) -> List[dict]:
        """分批获取资源"""
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
        wait=wait_exponential(multiplier=1, min=1, max=4)
    )
    async def _save_resource(
        self, subscription_id: UUID, resource_data: dict, client: BilibiliClient
    ) -> bool:
        """保存单个资源，返回是否成功"""
        try:
            # 检查是否已存在
            existing = self.session.exec(
                select(Resource).where(
                    Resource.subscription_id == subscription_id,
                    Resource.resource_id == resource_data["resource_id"]
                )
            ).first()
            
            if existing:
                await self._send_log(subscription_id, {
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO",
                    "type": resource_data["resource_type"],
                    "resource_id": resource_data["resource_id"],
                    "title": resource_data["title"],
                    "published_at": resource_data["published_at"].isoformat(),
                    "status": "skipped",
                    "message": "⊙ 已存在，跳过"
                })
                return True
            
            # 创建新资源
            resource = Resource(
                subscription_id=subscription_id,
                **resource_data
            )
            self.session.add(resource)
            self.session.commit()
            
            # 从失败表中移除（如果存在）
            self.session.exec(
                delete(FailedResource).where(
                    FailedResource.subscription_id == subscription_id,
                    FailedResource.resource_id == resource_data["resource_id"]
                )
            )
            self.session.commit()
            
            await self._send_log(subscription_id, {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "type": resource_data["resource_type"],
                "resource_id": resource_data["resource_id"],
                "title": resource_data["title"],
                "published_at": resource_data["published_at"].isoformat(),
                "status": "success",
                "message": "✓ 保存成功"
            })
            
            return True
            
        except Exception as e:
            # 记录到失败表
            failed = FailedResource(
                subscription_id=subscription_id,
                resource_id=resource_data["resource_id"],
                resource_type=resource_data["resource_type"],
                failed_at=datetime.now(),
                retry_count=0,
                last_error=str(e),
                metadata=resource_data
            )
            self.session.merge(failed)  # 使用 merge 处理重复
            self.session.commit()
            
            await self._send_log(subscription_id, {
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "type": resource_data["resource_type"],
                "resource_id": resource_data["resource_id"],
                "title": resource_data["title"],
                "status": "failed",
                "error": str(e),
                "stack_trace": traceback.format_exc()
            })
            
            return False
        
    async def _retry_failed_resources(
        self, subscription_id: UUID, client: BilibiliClient
    ) -> Tuple[int, int]:
        """重试失败的资源，返回 (成功数, 失败数)"""
        MAX_RETRY_COUNT = 5
        
        failed_resources = self.session.exec(
            select(FailedResource).where(
                FailedResource.subscription_id == subscription_id,
                FailedResource.retry_count < MAX_RETRY_COUNT
            )
        ).all()
        
        if not failed_resources:
            return (0, 0)
        
        await self._send_log(subscription_id, {
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "message": f"正在重试 {len(failed_resources)} 个失败资源..."
        })
        
        success_count = 0
        failed_count = 0
        
        for failed in failed_resources:
            # 更新重试次数
            failed.retry_count += 1
            self.session.commit()
            
            # 尝试保存
            success = await self._save_resource(
                subscription_id, failed.metadata, client
            )
            
            if success:
                success_count += 1
            else:
                failed_count += 1
        
        return (success_count, failed_count)
        
    async def _send_log(
        self, subscription_id: UUID, log_entry: dict
    ):
        """发送日志到 WebSocket"""
        await self.ws_manager.broadcast(subscription_id, log_entry)
```

**同步逻辑细节：**

1. **首次同步**：
   - 根据 `sync_config.history_limit` 决定获取数量
   - `null` 表示全量同步
   - 数字表示最近 N 条

2. **增量同步**：
   - 双重检查：`published_at > last_sync_at` AND `resource_id` 不存在
   - 获取到发布时间 ≤ `last_sync_at` 的资源时停止

3. **分批获取**：
   - 每次最多 50 条
   - 延迟 3-5 秒（随机，避免被限流）
   - 日志显示进度："已获取 50/150"

4. **失败处理**：
   - 单个资源失败立即重试 3 次
   - 仍失败则记录到 `failed_resources`
   - 不影响其他资源的同步

#### 3. 定时任务（scheduler.py）

**使用 APScheduler：**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

scheduler = AsyncIOScheduler(
    jobstores={
        'default': SQLAlchemyJobStore(url=settings.DATABASE_URL)
    },
    timezone=settings.APSCHEDULER_TIMEZONE  # 从环境变量读取
)

def init_scheduler(session: Session):
    """启动时加载所有启用的订阅"""
    subscriptions = session.exec(
        select(Subscription).where(
            Subscription.is_paused == False
        )
    ).all()
    
    for sub in subscriptions:
        add_sync_job(sub)
        
def add_sync_job(subscription: Subscription):
    """为订阅添加定时任务"""
    frequency = subscription.sync_config['sync_frequency']
    
    if frequency == 'manual':
        return
        
    # 转换为 cron 表达式
    trigger = frequency_to_trigger(frequency)
    
    scheduler.add_job(
        sync_subscription,
        trigger=trigger,
        args=[subscription.id],
        id=f"sync_{subscription.id}",
        replace_existing=True
    )
    
def remove_sync_job(subscription_id: UUID):
    """移除定时任务"""
    try:
        scheduler.remove_job(f"sync_{subscription_id}")
    except JobLookupError:
        pass  # 任务不存在，忽略

def frequency_to_trigger(frequency: str):
    """将频率转换为 APScheduler trigger"""
    from apscheduler.triggers.cron import CronTrigger
    
    if frequency == "1h":
        return CronTrigger(hour='*', minute='0')
    elif frequency == "6h":
        return CronTrigger(hour='*/6', minute='0')
    elif frequency == "1d":
        return CronTrigger(hour='2', minute='0')  # 凌晨 2 点
    elif frequency == "1w":
        return CronTrigger(day_of_week='mon', hour='2', minute='0')
    else:
        raise ValueError(f"不支持的频率: {frequency}")

# 在 main.py 中添加生命周期管理
@app.on_event("startup")
async def startup_event():
    """应用启动时启动调度器"""
    scheduler.start()
    with Session(engine) as session:
        init_scheduler(session)
    logger.info("APScheduler 已启动")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时停止调度器"""
    scheduler.shutdown()
    logger.info("APScheduler 已停止")
```

#### 4. WebSocket 管理（websocket.py）

**ConnectionManager 类：**
```python
class ConnectionManager:
    def __init__(self):
        # 按 subscription_id 分组管理连接
        self.active_connections: Dict[UUID, List[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, subscription_id: UUID):
        """接受连接"""
        await websocket.accept()
        if subscription_id not in self.active_connections:
            self.active_connections[subscription_id] = []
        self.active_connections[subscription_id].append(websocket)
        
    def disconnect(self, websocket: WebSocket, subscription_id: UUID):
        """断开连接"""
        if subscription_id in self.active_connections:
            self.active_connections[subscription_id].remove(websocket)
            
    async def broadcast(self, subscription_id: UUID, message: dict):
        """广播消息到指定订阅的所有连接"""
        if subscription_id not in self.active_connections:
            return
            
        dead_connections = []
        for connection in self.active_connections[subscription_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
                
        # 清理断开的连接
        for conn in dead_connections:
            self.disconnect(conn, subscription_id)
```

**WebSocket 路由：**
```python
from fastapi import WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError

async def get_current_user_ws(
    websocket: WebSocket,
    token: str = Query(...)
) -> User:
    """WebSocket 认证依赖"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            raise WebSocketDisconnect()
        
        with Session(engine) as session:
            user = session.get(User, UUID(user_id))
            if not user:
                await websocket.close(code=4001, reason="User not found")
                raise WebSocketDisconnect()
            return user
    except JWTError:
        await websocket.close(code=4001, reason="Invalid token")
        raise WebSocketDisconnect()

@router.websocket("/ws/sync-logs/{subscription_id}")
async def websocket_sync_logs(
    websocket: WebSocket,
    subscription_id: UUID,
    token: str = Query(...),  # 从查询参数获取 token
):
    # 认证
    try:
        current_user = await get_current_user_ws(websocket, token)
    except WebSocketDisconnect:
        return
    
    # 权限检查
    with Session(engine) as session:
        subscription = session.get(Subscription, subscription_id)
        if not subscription:
            await websocket.close(code=4004, reason="Subscription not found")
            return
            
        if not current_user.is_superuser and subscription.user_id != current_user.id:
            await websocket.close(code=4003, reason="Permission denied")
            return
    
    await ws_manager.connect(websocket, subscription_id)
    
    try:
        # 发送历史日志（最近一次同步的日志）
        with Session(engine) as session:
            latest_log = session.exec(
                select(SyncLog)
                .where(SyncLog.subscription_id == subscription_id)
                .order_by(SyncLog.start_time.desc())
            ).first()
            
            if latest_log and latest_log.details:
                for log_entry in latest_log.details:
                    await websocket.send_json(log_entry)
            
        # 保持连接，等待新日志
        while True:
            # 接收心跳消息
            data = await websocket.receive_text()
            # 可以验证心跳内容，这里简单忽略
            
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, subscription_id)
```

**日志消息格式：**
```json
{
  "timestamp": "2026-05-24T10:30:15",
  "level": "INFO",
  "type": "video",
  "resource_id": "BV1xx...",
  "title": "视频标题",
  "published_at": "2026-05-24",
  "status": "success",
  "error": null,
  "stack_trace": null
}
```

#### 5. 权限控制（core/permissions.py）

**权限检查装饰器：**
```python
def require_permission(permission_code: str):
    """检查用户是否有指定权限"""
    async def dependency(
        current_user: User = Depends(get_current_user),
        session: Session = Depends(get_session)
    ) -> User:
        # 超级管理员跳过检查
        if current_user.is_superuser:
            return current_user
            
        # 查询用户权限
        has_perm = session.exec(
            select(Permission)
            .join(RolePermission)
            .join(UserRole)
            .where(
                UserRole.user_id == current_user.id,
                Permission.code == permission_code
            )
        ).first()
        
        if not has_perm:
            raise HTTPException(403, "无权限")
            
        return current_user
    return Depends(dependency)
```

**数据过滤：**
```python
def filter_by_permission(
    query: Select,
    user: User,
    model: Type[SQLModel],
    permission_code: str
) -> Select:
    """根据权限过滤查询结果"""
    # 管理员或有 view_all 权限：查看所有
    if user.is_superuser or has_permission(user, f"{permission_code}:view_all"):
        return query
        
    # 普通用户：只看自己的
    return query.where(model.user_id == user.id)
```

---

## API 设计

### API 端点列表

#### 账户管理

```
POST   /bilibili/accounts
GET    /bilibili/accounts
GET    /bilibili/accounts/{id}
PUT    /bilibili/accounts/{id}
DELETE /bilibili/accounts/{id}
POST   /bilibili/accounts/qrcode/generate
POST   /bilibili/accounts/qrcode/check
```

**权限要求：**
- `bilibili:account:create` - 创建账户
- `bilibili:account:view` - 查看账户
- `bilibili:account:update` - 更新账户
- `bilibili:account:delete` - 删除账户

**关键端点详情：**

**POST /bilibili/accounts** - 创建账户
```python
class AccountCreate(BaseModel):
    account_name: str
    auth_type: Literal["cookie", "sessdata", "qrcode"]
    credentials: dict  # 根据 auth_type 不同结构不同

# Cookie 方式
credentials = {"cookie": "SESSDATA=xxx; bili_jct=xxx; ..."}

# SESSDATA 方式
credentials = {
    "sessdata": "xxx",
    "bili_jct": "xxx",
    "buvid3": "xxx"
}

# 扫码方式（先调用 generate，再调用 check）
credentials = {"qrcode_key": "xxx"}
```

**POST /bilibili/accounts/qrcode/generate** - 生成扫码登录二维码
```python
# 返回
{
    "qrcode_key": "xxx",
    "qrcode_url": "https://...",  # 二维码图片 URL
    "expires_at": "2026-05-24T10:35:00"
}
```

**POST /bilibili/accounts/qrcode/check** - 检查扫码状态
```python
# 请求
{"qrcode_key": "xxx"}

# 返回
{
    "status": "scanned" | "confirmed" | "expired",
    "credentials": {...}  # status=confirmed 时返回
}
```

#### UP主订阅管理

```
POST   /bilibili/subscriptions
GET    /bilibili/subscriptions
GET    /bilibili/subscriptions/{id}
PUT    /bilibili/subscriptions/{id}
DELETE /bilibili/subscriptions/{id}
PATCH  /bilibili/subscriptions/{id}/pause
POST   /bilibili/subscriptions/{id}/sync
POST   /bilibili/subscriptions/{id}/retry-failed
```

**权限要求：**
- `bilibili:subscription:create`
- `bilibili:subscription:view`
- `bilibili:subscription:update`
- `bilibili:subscription:delete`
- `bilibili:subscription:sync`

**关键端点详情：**

**POST /bilibili/subscriptions** - 创建订阅
```python
class SubscriptionCreate(BaseModel):
    account_id: UUID
    uploader_uid: str
    sync_config: SyncConfig

class SyncConfig(BaseModel):
    resource_types: List[Literal["video", "dynamic", "article"]] = ["video", "dynamic", "article"]
    sync_frequency: Literal["1h", "6h", "1d", "1w", "manual"] = "6h"
    history_limit: Optional[int] = 50  # null 表示全量
    batch_size: int = 50  # 每次获取数量

# 实现示例（router.py）
@router.post("/subscriptions")
async def create_subscription(
    data: SubscriptionCreate,
    current_user: User = Depends(require_permission("bilibili:subscription:create")),
    session: Session = Depends(get_session)
):
    # 1. 检查 UP主是否存在
    account = session.get(Account, data.account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(404, "账户不存在")
    
    credentials = decrypt_credentials(account.credentials)
    client = BilibiliClient(credentials, account.auth_type)
    
    if not await client.check_uploader_exists(data.uploader_uid):
        raise HTTPException(400, "该 UP主不存在或 UID 错误")
    
    # 2. 检查是否已订阅
    existing = session.exec(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.uploader_uid == data.uploader_uid
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
                    "created_at": existing.created_at.isoformat()
                }
            }
        )
    
    # 3. 获取 UP主信息并保存
    uploader_info = await client.get_user_info(data.uploader_uid)
    
    subscription = Subscription(
        user_id=current_user.id,
        account_id=data.account_id,
        uploader_uid=data.uploader_uid,
        uploader_name=uploader_info["name"],
        uploader_avatar=uploader_info["avatar"],
        uploader_info=uploader_info,
        sync_config=data.sync_config.dict()
    )
    
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    
    # 4. 添加定时任务
    from app.bilibili.scheduler import add_sync_job
    add_sync_job(subscription)
    
    return subscription
```

**POST /bilibili/subscriptions/{id}/sync** - 手动触发同步
```python
# 返回
{
    "sync_log_id": "xxx",
    "message": "同步已开始"
}
```

**POST /bilibili/subscriptions/{id}/retry-failed** - 重试失败的资源
```python
# 返回
{
    "total": 10,
    "success": 8,
    "failed": 2
}
```

#### 资源查询

```
GET    /bilibili/resources
GET    /bilibili/resources/{id}
```

**查询参数：**
```python
subscription_id: Optional[UUID]
resource_type: Optional[str]
start_date: Optional[date]
end_date: Optional[date]
keyword: Optional[str]  # 搜索标题和内容
page: int = 1
page_size: int = 20
```

#### 同步日志

```
GET    /bilibili/sync-logs
GET    /bilibili/sync-logs/{id}
```

#### WebSocket

```
WS     /bilibili/ws/sync-logs/{subscription_id}
```

---

## 前端设计

### 页面组件设计

#### 1. 账户管理页（/bilibili/accounts）

**组件结构：**
```
AccountsPage
├── AccountsTable (复用 shadcn/ui Table)
│   ├── 列：账户名（可点击跳转B站）、认证方式、状态、操作
│   └── 操作：编辑、删除
└── AddAccountDialog (复用 shadcn/ui Dialog)
    ├── Tabs 切换认证方式
    │   ├── Cookie 输入框
    │   ├── SESSDATA 字段表单
    │   └── 扫码登录（直接显示二维码，无需再弹窗）
    │       ├── QRCodeDisplay 组件
    │       └── 轮询检查扫码状态
    └── 提交按钮
```

**关键交互：**
- 点击账户名 → 跳转到 `https://space.bilibili.com/{uid}`
- 扫码登录：生成二维码后，每 2 秒轮询检查状态
- 扫码成功后自动关闭对话框并刷新列表

#### 2. 同步资源页（/bilibili/subscriptions）

**组件结构：**
```
SubscriptionsPage
├── SubscriptionsTable
│   ├── 列：UP主（可点击）、状态标签、最后同步时间、操作
│   ├── 状态标签（SyncStatusBadge）
│   │   ├── 同步中（蓝色，带动画）
│   │   ├── 已暂停（灰色）
│   │   ├── 正常（绿色）
│   │   └── 失败（红色）
│   └── 操作列
│       ├── 立即同步按钮
│       ├── 暂停/恢复按钮
│       ├── 编辑按钮
│       ├── 删除按钮
│       └── 查看日志按钮（图标 + Tooltip）
├── AddSubscriptionDialog
│   ├── 选择账户（下拉框）
│   ├── 输入 UP主 UID
│   ├── 同步配置
│   │   ├── 资源类型（多选框，默认全选）
│   │   ├── 同步频率（下拉框，默认 6h）
│   │   └── 首次同步历史数量
│   │       ├── 不同步历史
│   │       ├── 最近 N 条（输入框，默认 50）
│   │       └── 全量同步（警告提示）
│   └── 提交按钮
└── SyncLogDialog（日志弹窗）
    ├── 标题：UP主名称 - 同步日志
    ├── 日志列表（LogEntry 组件）
    │   ├── 时间戳（灰色小字）
    │   ├── 日志类型标签（Badge）
    │   │   ├── INFO（蓝色）
    │   │   ├── WARN（黄色）
    │   │   └── ERROR（红色）
    │   ├── 资源类型标识（[视频]/[动态]/[专栏]）
    │   ├── 状态图标（✓ 成功 / ⊙ 跳过 / ✗ 失败）
    │   ├── 资源 ID + 标题预览（前 30 字）
    │   └── 错误堆栈（红色可折叠区域）
    │       └── Collapsible 组件
    └── 自动滚动到底部 + WebSocket 实时更新
```

**日志格式示例：**
```
[10:30:15] [INFO] 开始同步 UP主：XXX (UID: 123456)
[10:30:18] [INFO] ✓ [视频] BV1xx... - 如何使用Claude Code（2026-05-24）
[10:30:18] [INFO] ⊙ [视频] BV1yy... - 旧视频标题（已存在，跳过）
[10:30:19] [ERROR] ✗ [视频] BV1zz... - 某个视频（保存失败）
  └─ 堆栈信息...（可折叠）
[10:30:30] [INFO] 同步完成：成功 78 条，跳过 2 条，失败 1 条
```

**关键交互：**
- 点击 UP主名称 → 跳转到详情页 `/bilibili/subscriptions/{id}`
- 点击"立即同步" → 调用 API，显示 Toast 提示
- 同步中的订阅：状态标签显示"同步中"，日志按钮高亮
- 点击日志按钮 → 打开 SyncLogDialog，建立 WebSocket 连接
- 关闭日志弹窗 → 断开 WebSocket 连接

**去重处理：**
- 输入 UID 后失焦时，检查 UP主是否存在
- 如果已订阅，弹出确认对话框：
  ```
  该 UP主已存在订阅
  UP主：XXX
  当前配置：视频、动态 | 每 6 小时
  
  [取消] [重新配置]
  ```
- 点击"重新配置" → 进入编辑模式

#### 3. UP主详情页（/bilibili/subscriptions/:id）

**布局：**
```
SubscriptionDetailPage
├── Layout (左右布局，3:7 比例)
│   ├── Left: UploaderInfo（封装组件）
│   │   ├── 头像（可点击跳转B站）
│   │   ├── 昵称（可点击跳转B站）
│   │   ├── 粉丝数、简介
│   │   ├── 订阅配置卡片
│   │   │   ├── 资源类型开关（Switch）
│   │   │   ├── 同步频率选择
│   │   │   └── 保存按钮
│   │   └── 统计信息
│   │       ├── 已同步资源数
│   │       ├── 最后同步时间
│   │       └── 失败资源数（红色，可点击重试）
│   └── Right: ResourceList（封装组件）
│       ├── 筛选器
│       │   ├── 资源类型（Tabs）
│       │   ├── 时间范围（DateRangePicker）
│       │   └── 关键词搜索（Input，搜索标题+内容）
│       └── 资源卡片列表（ResourceCard）
│           ├── 封面/缩略图
│           ├── 标题（可点击跳转B站）
│           ├── 预览文本（summary，灰色小字）
│           ├── 附件标识（图标 + 数量）
│           │   ├── 📄 文档 x3
│           │   └── 🖼️ 图片 x5
│           ├── 元数据（播放量、点赞、发布时间）
│           └── 无限滚动加载
```

**关键交互：**
- 点击头像/昵称 → 跳转到 `https://space.bilibili.com/{uid}`
- 点击资源标题 → 跳转到 B站对应页面
  - 视频：`https://www.bilibili.com/video/{bvid}`
  - 动态：`https://t.bilibili.com/{dynamic_id}`
  - 专栏：`https://www.bilibili.com/read/cv{article_id}`
- 修改配置后点击保存 → 更新订阅，重新调度定时任务
- 筛选器变化 → 重新请求资源列表

### 核心封装组件

#### 1. BilibiliAccountForm
- 账户表单，支持三种认证方式（Tabs 切换）
- Cookie/SESSDATA 输入验证
- 扫码登录二维码显示和状态轮询

#### 2. QRCodeDisplay
- 显示二维码图片
- 轮询检查扫码状态（每 2 秒）
- 显示状态提示："请使用 B站 APP 扫码" / "扫码成功" / "已过期"

#### 3. UploaderInfo
- UP主信息卡片
- 头像、昵称可点击跳转 B站
- 订阅配置编辑
- 统计信息展示

#### 4. ResourceList
- 资源列表容器
- 筛选器集成
- 无限滚动加载
- 空状态提示

#### 5. ResourceCard
- 单个资源卡片
- 区分 summary（列表）和 full_content（详情）
- 附件标识显示
- 元数据展示（带 *_display 字段）

#### 6. SyncLogDialog
- 同步日志弹窗
- WebSocket 实时更新
- 自动滚动到底部
- LogEntry 列表

#### 7. LogEntry
- 单条日志组件
- 时间戳 + 类型标签 + 内容
- 错误堆栈可折叠（Collapsible）
- 根据日志类型显示不同颜色

#### 8. SyncStatusBadge
- 同步状态标签
- 同步中：蓝色 + 旋转动画
- 已暂停：灰色
- 正常：绿色
- 失败：红色

### WebSocket 配置

#### 开发环境（vite.config.ts）

```typescript
export default defineConfig({
  server: {
    proxy: {
      "/backend": {
        target: "http://localhost:8888",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/backend/, ""),
        ws: true,  // 支持 WebSocket 代理
      },
    },
  },
})
```

#### 前端连接（使用 react-use-websocket）

```typescript
import { useWebSocket } from 'react-use-websocket';
import { useAuth } from '@/hooks/use-auth';

function SyncLogDialog({ subscriptionId }: { subscriptionId: string }) {
  const { token } = useAuth();  // 获取认证 token
  
  // 根据环境构建 WebSocket URL
  const wsUrl = import.meta.env.DEV
    ? `ws://localhost:5173/backend/api/v1/bilibili/ws/sync-logs/${subscriptionId}?token=${token}`
    : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}://${window.location.host}/api/v1/bilibili/ws/sync-logs/${subscriptionId}?token=${token}`;
  
  const [logs, setLogs] = useState<LogEntry[]>([]);
  
  const { lastMessage, readyState } = useWebSocket(wsUrl, {
    shouldReconnect: () => true,
    reconnectAttempts: 10,
    reconnectInterval: 3000,
    heartbeat: {
      message: 'ping',
      interval: 30000,
    },
    onMessage: (event) => {
      const log = JSON.parse(event.data);
      setLogs(prev => [...prev, log]);
      // 自动滚动到底部
      scrollToBottom();
    },
  });
  
  return (
    <Dialog>
      {/* 日志列表 */}
    </Dialog>
  );
}
```

#### 生产环境配置

**Nginx/Traefik WebSocket 代理：**
```nginx
location /api/v1/bilibili/ws/ {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400;  # 24 小时
}
```

### 菜单集成

**动态显示 Bilibili 菜单（AppSidebar.tsx）：**

```typescript
import { Home, Briefcase, Users, Video } from "lucide-react"

const baseItems: Item[] = [
  { icon: Home, title: "Dashboard", path: "/" },
  { icon: Briefcase, title: "Items", path: "/items" },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  
  // 检查用户是否有 Bilibili 权限
  // 假设 User 类型包含 permissions: string[] 字段
  const hasBilibiliAccess = currentUser?.permissions?.some(
    (p: string) => p.startsWith("bilibili:")
  )
  
  const items = [
    ...baseItems,
    // 动态添加 Bilibili 菜单组
    ...(hasBilibiliAccess ? [{
      icon: Video,
      title: "Bilibili",
      children: [
        { title: "账户管理", path: "/bilibili/accounts" },
        { title: "同步资源", path: "/bilibili/subscriptions" }
      ]
    }] : []),
    // 管理员菜单
    ...(currentUser?.is_superuser ? [
      { icon: Users, title: "Admin", path: "/admin" }
    ] : [])
  ]
  
  return (
    <Sidebar collapsible="icon">
      {/* ... */}
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
    </Sidebar>
  )
}
```

**User 类型定义（frontend/src/types/user.ts）：**
```typescript
export interface User {
  id: string
  email: string
  full_name: string
  is_superuser: boolean
  permissions: string[]  // 权限代码列表，如 ["bilibili:account:view", ...]
}
```

---

## 部署和初始化

### 1. 数据库迁移

**创建 Alembic 迁移文件：**

```bash
# 生成迁移文件
alembic revision --autogenerate -m "Add Bilibili and RBAC tables"

# 审查生成的迁移文件
# 确保：
# - 索引正确创建
# - 外键约束正确
# - 默认值正确
# - 使用 CREATE INDEX CONCURRENTLY（如果表已有数据）

# 应用迁移
alembic upgrade head
```

**迁移文件示例（alembic/versions/xxxx_add_bilibili_and_rbac_tables.py）：**

```python
"""Add Bilibili and RBAC tables

Revision ID: xxxx
Revises: yyyy
Create Date: 2026-05-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'xxxx'
down_revision = 'yyyy'
branch_labels = None
depends_on = None


def upgrade():
    # 1. 创建 RBAC 权限表
    op.create_table('permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('module', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index('idx_permissions_module', 'permissions', ['module'])
    
    # 2. 创建角色表
    op.create_table('roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # 3. 创建角色-权限关联表
    op.create_table('role_permissions',
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )
    
    # 4. 创建用户-角色关联表
    op.create_table('user_roles',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'role_id')
    )
    
    # 5. 创建 Bilibili 账户表
    op.create_table('bilibili_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_name', sa.String(length=100), nullable=False),
        sa.Column('auth_type', sa.String(length=20), nullable=False),
        sa.Column('credentials', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_bilibili_accounts_user_id', 'bilibili_accounts', ['user_id'])
    
    # 6. 创建 UP主订阅表
    op.create_table('bilibili_uploader_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('uploader_uid', sa.String(length=50), nullable=False),
        sa.Column('uploader_name', sa.String(length=100), nullable=False),
        sa.Column('uploader_avatar', sa.Text(), nullable=True),
        sa.Column('uploader_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('sync_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_paused', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['bilibili_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'uploader_uid')
    )
    op.create_index('idx_subscriptions_user_id', 'bilibili_uploader_subscriptions', ['user_id'])
    op.create_index('idx_subscriptions_uploader_uid', 'bilibili_uploader_subscriptions', ['uploader_uid'])
    
    # 7. 创建资源表
    op.create_table('bilibili_resources',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resource_type', sa.String(length=20), nullable=False),
        sa.Column('resource_id', sa.String(length=50), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('cover_url', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('full_content', sa.Text(), nullable=True),
        sa.Column('attachments', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['subscription_id'], ['bilibili_uploader_subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subscription_id', 'resource_id')
    )
    op.create_index('idx_resources_subscription_id', 'bilibili_resources', ['subscription_id'])
    op.create_index('idx_resources_published_at', 'bilibili_resources', ['published_at'], postgresql_ops={'published_at': 'DESC'})
    op.create_index('idx_resources_type', 'bilibili_resources', ['resource_type'])
    
    # 8. 创建同步日志表
    op.create_table('sync_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sync_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('total_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('success_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('failed_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('skipped_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['subscription_id'], ['bilibili_uploader_subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sync_logs_subscription_id', 'sync_logs', ['subscription_id'])
    op.create_index('idx_sync_logs_start_time', 'sync_logs', ['start_time'], postgresql_ops={'start_time': 'DESC'})
    
    # 9. 创建失败资源表
    op.create_table('failed_resources',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resource_id', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=20), nullable=False),
        sa.Column('failed_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['subscription_id'], ['bilibili_uploader_subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subscription_id', 'resource_id')
    )
    op.create_index('idx_failed_resources_subscription_id', 'failed_resources', ['subscription_id'])
    op.create_index('idx_failed_resources_failed_at', 'failed_resources', ['failed_at'], postgresql_ops={'failed_at': 'DESC'})


def downgrade():
    # 按相反顺序删除表
    op.drop_index('idx_failed_resources_failed_at', table_name='failed_resources')
    op.drop_index('idx_failed_resources_subscription_id', table_name='failed_resources')
    op.drop_table('failed_resources')
    
    op.drop_index('idx_sync_logs_start_time', table_name='sync_logs')
    op.drop_index('idx_sync_logs_subscription_id', table_name='sync_logs')
    op.drop_table('sync_logs')
    
    op.drop_index('idx_resources_type', table_name='bilibili_resources')
    op.drop_index('idx_resources_published_at', table_name='bilibili_resources')
    op.drop_index('idx_resources_subscription_id', table_name='bilibili_resources')
    op.drop_table('bilibili_resources')
    
    op.drop_index('idx_subscriptions_uploader_uid', table_name='bilibili_uploader_subscriptions')
    op.drop_index('idx_subscriptions_user_id', table_name='bilibili_uploader_subscriptions')
    op.drop_table('bilibili_uploader_subscriptions')
    
    op.drop_index('idx_bilibili_accounts_user_id', table_name='bilibili_accounts')
    op.drop_table('bilibili_accounts')
    
    op.drop_table('user_roles')
    op.drop_table('role_permissions')
    op.drop_table('roles')
    
    op.drop_index('idx_permissions_module', table_name='permissions')
    op.drop_table('permissions')
```

**迁移最佳实践：**
1. 本地先测试 `upgrade` 和 `downgrade`
2. 使用 `alembic upgrade head --sql` 预览 SQL
3. 生产部署前备份数据库
4. 迁移文件立即提交到 git
5. 注意：UNIQUE 约束 `(user_id, uploader_uid)` 可能过于严格，如果用户需要用不同账户订阅同一 UP主，考虑改为 `(account_id, uploader_uid)`

**依赖包更新（requirements.txt）：**
```txt
# 现有依赖...

# Bilibili 模块新增
bilibili-api-python>=16.0.0
apscheduler>=3.10.0
tenacity>=8.2.0
cryptography>=41.0.0
```

### 2. 权限初始化

**创建初始化脚本（app/bilibili/init_permissions.py）：**

```python
from sqlmodel import Session
from app.models import Permission, Role, RolePermission

def init_bilibili_permissions(session: Session):
    """初始化 Bilibili 模块的权限和角色"""
    
    # 1. 创建权限
    permissions = [
        # 账户权限
        Permission(code="bilibili:account:view", name="查看B站账户", module="bilibili"),
        Permission(code="bilibili:account:create", name="创建B站账户", module="bilibili"),
        Permission(code="bilibili:account:update", name="编辑B站账户", module="bilibili"),
        Permission(code="bilibili:account:delete", name="删除B站账户", module="bilibili"),
        
        # 订阅权限
        Permission(code="bilibili:subscription:view", name="查看订阅", module="bilibili"),
        Permission(code="bilibili:subscription:create", name="创建订阅", module="bilibili"),
        Permission(code="bilibili:subscription:update", name="编辑订阅", module="bilibili"),
        Permission(code="bilibili:subscription:delete", name="删除订阅", module="bilibili"),
        Permission(code="bilibili:subscription:sync", name="触发同步", module="bilibili"),
        
        # 资源权限
        Permission(code="bilibili:resource:view", name="查看资源", module="bilibili"),
        
        # 日志权限
        Permission(code="bilibili:log:view", name="查看同步日志", module="bilibili"),
        
        # 管理员权限
        Permission(code="bilibili:admin:view_all", name="查看所有用户数据", module="bilibili"),
    ]
    
    session.add_all(permissions)
    session.flush()
    
    # 2. 创建角色
    bilibili_user_role = Role(
        name="bilibili_user",
        description="B站功能普通用户",
        is_system=True
    )
    
    bilibili_admin_role = Role(
        name="bilibili_admin",
        description="B站功能管理员",
        is_system=True
    )
    
    session.add_all([bilibili_user_role, bilibili_admin_role])
    session.flush()
    
    # 3. 为角色分配权限
    # bilibili_user: 基础权限（管理自己的数据）
    user_permissions = [p for p in permissions if "admin" not in p.code]
    for perm in user_permissions:
        session.add(RolePermission(
            role_id=bilibili_user_role.id,
            permission_id=perm.id
        ))
    
    # bilibili_admin: 所有权限
    for perm in permissions:
        session.add(RolePermission(
            role_id=bilibili_admin_role.id,
            permission_id=perm.id
        ))
    
    session.commit()
    print("✓ Bilibili 权限和角色初始化完成")
```

**在 app/initial_data.py 中调用：**

```python
def init():
    # ... 现有的初始化代码
    
    # 初始化 Bilibili 权限
    from app.bilibili.init_permissions import init_bilibili_permissions
    init_bilibili_permissions(session)
```

### 3. 环境变量配置

**更新 .env 文件：**

```bash
# Bilibili 配置
BILIBILI_REQUEST_TIMEOUT=30
BILIBILI_RETRY_TIMES=3
BILIBILI_RATE_LIMIT_DELAY=5
BILIBILI_SYNC_BATCH_SIZE=50
BILIBILI_CREDENTIALS_ENCRYPTION_KEY=  # 首次启动自动生成

# APScheduler 配置
APSCHEDULER_TIMEZONE=Asia/Shanghai
```

**自动生成加密密钥（app/core/security.py）：**

```python
from cryptography.fernet import Fernet
import os

def get_or_create_encryption_key() -> str:
    """获取或创建加密密钥"""
    key = os.getenv("BILIBILI_CREDENTIALS_ENCRYPTION_KEY")
    
    if not key:
        # 生成新密钥
        key = Fernet.generate_key().decode()
        
        # 提示用户添加到 .env
        print("=" * 60)
        print("请将以下配置添加到 .env 文件：")
        print(f"BILIBILI_CREDENTIALS_ENCRYPTION_KEY={key}")
        print("=" * 60)
        
        raise ValueError("缺少加密密钥配置")
    
    return key

def encrypt_credentials(credentials: dict) -> str:
    """加密凭证"""
    key = get_or_create_encryption_key()
    f = Fernet(key.encode())
    return f.encrypt(json.dumps(credentials).encode()).decode()

def decrypt_credentials(encrypted: str) -> dict:
    """解密凭证"""
    key = get_or_create_encryption_key()
    f = Fernet(key.encode())
    return json.loads(f.decrypt(encrypted.encode()).decode())
```

### 4. Docker Compose 更新

**更新 compose.override.yml：**

```yaml
services:
  backend:
    environment:
      - BILIBILI_REQUEST_TIMEOUT=${BILIBILI_REQUEST_TIMEOUT:-30}
      - BILIBILI_RETRY_TIMES=${BILIBILI_RETRY_TIMES:-3}
      - BILIBILI_RATE_LIMIT_DELAY=${BILIBILI_RATE_LIMIT_DELAY:-5}
      - BILIBILI_SYNC_BATCH_SIZE=${BILIBILI_SYNC_BATCH_SIZE:-50}
      - BILIBILI_CREDENTIALS_ENCRYPTION_KEY=${BILIBILI_CREDENTIALS_ENCRYPTION_KEY}
      - APSCHEDULER_TIMEZONE=${APSCHEDULER_TIMEZONE:-Asia/Shanghai}
```

### 5. 首次部署流程

**自动化部署脚本（scripts/deploy_bilibili.sh）：**

```bash
#!/bin/bash
set -e

echo "开始部署 Bilibili 模块..."

# 1. 备份数据库
echo "备份数据库..."
docker compose exec db pg_dump -U postgres app > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. 停止服务
echo "停止服务..."
docker compose down

# 3. 拉取最新代码
echo "拉取代码..."
git pull

# 4. 构建镜像
echo "构建镜像..."
docker compose build backend frontend

# 5. 启动服务
echo "启动服务..."
docker compose up -d

# 6. 等待数据库就绪
echo "等待数据库就绪..."
sleep 5

# 7. 运行迁移
echo "运行数据库迁移..."
docker compose exec backend alembic upgrade head

# 8. 初始化权限（如果是首次部署）
echo "初始化权限..."
docker compose exec backend python -c "from app.initial_data import init; init()"

echo "✓ 部署完成！"
echo ""
echo "下一步："
echo "1. 登录管理后台"
echo "2. 为需要的用户分配 'bilibili_user' 角色"
echo "3. 用户即可在菜单中看到 Bilibili 功能"
```

### 6. 升级现有部署

**迁移步骤：**

1. **备份数据库**
   ```bash
   docker compose exec db pg_dump -U postgres app > backup.sql
   ```

2. **拉取代码并重启**
   ```bash
   git pull
   docker compose down
   docker compose up -d --build
   ```

3. **容器启动时自动执行**
   - 数据库迁移（prestart 容器）
   - 权限初始化（initial_data.py）

4. **管理员分配权限**
   - 登录 `/admin`
   - 为用户分配 `bilibili_user` 角色

---

## 错误处理和安全

### 错误处理策略

#### 1. bilibili-api 层

**网络错误：**
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(NetworkError)
)
async def fetch_data(...):
    pass
```

**认证失败：**
- 标记账户为 `is_active=False`
- 记录错误日志
- 前端显示"凭证已失效，请重新登录"

**限流错误：**
- 延迟 5 秒后重试
- 记录到同步日志
- 如果持续限流，暂停同步并通知用户

**UP主不存在：**
- 返回明确错误信息
- 前端显示"该 UP主不存在或 UID 错误"

#### 2. 同步服务层

**异常捕获：**
```python
try:
    # 同步逻辑
except AuthenticationError:
    log_error("认证失败", error_type="AUTH_ERROR")
    mark_account_inactive()
except RateLimitError:
    log_error("被限流", error_type="RATE_LIMIT")
    delay_next_sync()
except UploaderNotFoundError:
    log_error("UP主不存在", error_type="UPLOADER_NOT_FOUND")
except Exception as e:
    log_error(str(e), error_type="UNKNOWN_ERROR", stack_trace=traceback.format_exc())
```

#### 3. WebSocket 错误处理

**连接管理：**
- 客户端断线：自动清理连接
- 服务端异常：发送错误消息后关闭连接
- 心跳超时：主动关闭连接

**前端重连策略（react-use-websocket）：**
- 最多重试 10 次
- 指数退避：3s, 6s, 12s... 最大 30s
- 用户手动关闭日志弹窗时停止重连

### 数据安全

#### 1. 凭证加密存储

**加密方式：**
- 使用 `cryptography.fernet` 对称加密
- 加密密钥存储在环境变量 `BILIBILI_CREDENTIALS_ENCRYPTION_KEY`
- 只在使用时解密

**存储流程：**
```python
# 保存时加密
encrypted = encrypt_credentials({
    "sessdata": "xxx",
    "bili_jct": "xxx"
})
account.credentials = encrypted

# 使用时解密
credentials = decrypt_credentials(account.credentials)
client = BilibiliClient(credentials)
```

#### 2. 敏感信息脱敏

**API 响应脱敏：**
```python
class AccountPublic(BaseModel):
    id: UUID
    account_name: str
    auth_type: str
    is_active: bool
    credentials_preview: str  # "SESSDATA=abc***xyz"
    
def mask_credentials(credentials: dict) -> str:
    """脱敏显示凭证"""
    if "sessdata" in credentials:
        sessdata = credentials["sessdata"]
        return f"SESSDATA={sessdata[:3]}***{sessdata[-3:]}"
    return "***"
```

**日志脱敏：**
- 同步日志中不记录完整凭证
- 错误堆栈中过滤敏感信息

**管理员查看限制：**
- 管理员可以看到其他用户的订阅和资源
- 但账户凭证字段仍然脱敏显示

#### 3. 权限检查

**API 层权限检查：**
```python
@router.get("/bilibili/accounts")
async def get_accounts(
    current_user: User = Depends(require_permission("bilibili:account:view")),
    session: Session = Depends(get_session)
):
    # 普通用户只能看自己的
    query = select(Account)
    if not current_user.is_superuser:
        query = query.where(Account.user_id == current_user.id)
    
    accounts = session.exec(query).all()
    return accounts
```

**WebSocket 权限检查：**
```python
@router.websocket("/ws/sync-logs/{subscription_id}")
async def websocket_sync_logs(
    websocket: WebSocket,
    subscription_id: UUID,
    current_user: User = Depends(get_current_user_ws)
):
    subscription = session.get(Subscription, subscription_id)
    
    # 检查权限
    if not current_user.is_superuser and subscription.user_id != current_user.id:
        await websocket.close(code=4003)
        return
```

---

## 测试策略

### 1. 单元测试

**测试覆盖：**
- `BilibiliClient` 各方法（使用 mock）
- `SyncService` 同步逻辑
- 权限检查装饰器
- 凭证加密/解密

**示例：**
```python
def test_encrypt_decrypt_credentials():
    original = {"sessdata": "test123"}
    encrypted = encrypt_credentials(original)
    decrypted = decrypt_credentials(encrypted)
    assert decrypted == original

@pytest.mark.asyncio
async def test_sync_subscription_success(mock_bilibili_client):
    # 测试同步成功流程
    pass

@pytest.mark.asyncio
async def test_sync_subscription_uploader_not_found(mock_bilibili_client):
    # 测试 UP主不存在的情况
    pass
```

### 2. 集成测试

**测试场景：**
- 创建账户 → 创建订阅 → 触发同步 → 验证资源入库
- 扫码登录流程
- WebSocket 连接和消息推送
- 定时任务触发

### 3. E2E 测试（Playwright）

**测试流程：**
```typescript
test('创建订阅并同步', async ({ page }) => {
  // 1. 登录
  await page.goto('/login')
  await page.fill('[name="email"]', 'test@example.com')
  await page.fill('[name="password"]', 'password')
  await page.click('button[type="submit"]')
  
  // 2. 进入 Bilibili 页面
  await page.click('text=Bilibili')
  await page.click('text=同步资源')
  
  // 3. 创建订阅
  await page.click('text=添加订阅')
  await page.fill('[name="uploader_uid"]', '123456')
  await page.click('button:has-text("提交")')
  
  // 4. 触发同步
  await page.click('button:has-text("立即同步")')
  
  // 5. 验证同步日志
  await page.click('button[aria-label="查看日志"]')
  await expect(page.locator('text=开始同步')).toBeVisible()
})
```

---

## 性能优化

### 1. 数据库优化

**索引策略：**
- `bilibili_resources.subscription_id` - 查询某个订阅的资源
- `bilibili_resources.published_at DESC` - 按时间排序
- `bilibili_resources.resource_type` - 按类型筛选
- `bilibili_uploader_subscriptions.user_id` - 查询用户订阅
- `bilibili_uploader_subscriptions.uploader_uid` - 检查重复订阅

**查询优化：**
- 资源列表使用分页（默认 20 条/页）
- 使用 `select_related` 减少 N+1 查询
- 同步日志 `details` 字段使用 JSONB，支持索引

### 2. 缓存策略

**Redis 缓存（可选）：**
- UP主信息缓存（1 小时）
- 资源列表缓存（5 分钟）
- 减少对 bilibili-api 的调用

### 3. 并发控制

**同步任务限制：**
- 同一订阅不能同时触发多次同步
- 使用数据库锁或 Redis 分布式锁

**API 限流：**
- 使用 `slowapi` 限制 API 调用频率
- 防止恶意触发大量同步任务

---

## 监控和日志

### 1. 应用日志

**日志级别：**
- INFO：正常同步流程
- WARN：限流、重试
- ERROR：同步失败、认证失败

**日志格式：**
```python
logger.info(
    "同步完成",
    extra={
        "subscription_id": str(subscription_id),
        "success_count": 78,
        "failed_count": 1,
        "duration": 45.2
    }
)
```

### 2. 监控指标

**关键指标：**
- 同步成功率
- 平均同步时长
- 失败资源数量
- WebSocket 连接数
- API 调用频率

**告警规则：**
- 同步失败率 > 10%
- 单次同步时长 > 5 分钟
- 失败资源累计 > 100 条

---

## 未来扩展

### 1. 评论功能

**数据库表：**
```sql
CREATE TABLE bilibili_comments (
    id UUID PRIMARY KEY,
    resource_id UUID REFERENCES bilibili_resources(id),
    comment_id VARCHAR(50) NOT NULL,
    user_name VARCHAR(100),
    content TEXT,
    like_count INTEGER,
    reply_count INTEGER,
    published_at TIMESTAMP,
    UNIQUE(resource_id, comment_id)
);
```

**同步逻辑：**
- 在资源同步时，可选同步评论
- 只同步热门评论（点赞数 > 阈值）

### 2. 通知功能

**通知场景：**
- UP主发布新视频 → 推送通知
- 同步失败 → 邮件通知
- 凭证失效 → 前端提示

### 3. 数据分析

**统计功能：**
- UP主发布频率分析
- 视频播放量趋势
- 热门内容推荐

### 4. 导出功能

**导出格式：**
- CSV：资源列表导出
- JSON：完整数据导出
- Markdown：生成阅读笔记

---

## 总结

本设计文档详细描述了 Bilibili 模块的完整实现方案，包括：

**核心功能：**
- ✅ 多种认证方式的账户管理
- ✅ 灵活的订阅配置和管理
- ✅ 自动/手动同步资源
- ✅ 实时日志推送（WebSocket）
- ✅ 失败重试机制
- ✅ 基于 RBAC 的权限控制

**技术亮点：**
- 使用 APScheduler 实现轻量级定时任务
- WebSocket 实时推送同步日志
- 凭证加密存储保证安全
- 完整的 RBAC 权限系统
- 遵循 Alembic 最佳实践

**可扩展性：**
- 预留评论功能扩展
- 支持未来添加通知、分析等功能
- 权限系统可复用到其他模块

**下一步：**
1. 审查本设计文档
2. 创建实施计划
3. 开始开发

---

## RBAC 权限管理前端设计

### 1. 管理员界面扩展

在现有的 `/admin` 页面中添加权限管理功能。

#### 用户管理页面扩展（/admin/users）

**现有功能：**
- 用户列表
- 创建/编辑/删除用户

**新增功能：**
- 为用户分配角色

**组件结构：**
```
UsersPage (扩展现有)
├── UsersTable
│   ├── 列：邮箱、姓名、超级管理员、角色、操作
│   └── 操作：编辑、删除、管理角色
└── UserRolesDialog（新增）
    ├── 用户信息展示
    ├── 角色列表（多选框）
    │   ├── bilibili_user
    │   ├── bilibili_admin
    │   └── 其他角色...
    ├── 当前权限预览（只读）
    └── 保存按钮
```

**API 端点：**
```
GET    /api/v1/admin/users/{user_id}/roles
POST   /api/v1/admin/users/{user_id}/roles
DELETE /api/v1/admin/users/{user_id}/roles/{role_id}
```

**实现示例：**
```typescript
function UserRolesDialog({ userId }: { userId: string }) {
  const { data: userRoles } = useQuery({
    queryKey: ['user-roles', userId],
    queryFn: () => api.get(`/admin/users/${userId}/roles`)
  })
  
  const { data: allRoles } = useQuery({
    queryKey: ['roles'],
    queryFn: () => api.get('/admin/roles')
  })
  
  const assignRole = useMutation({
    mutationFn: (roleId: string) => 
      api.post(`/admin/users/${userId}/roles`, { role_id: roleId })
  })
  
  return (
    <Dialog>
      <DialogHeader>
        <DialogTitle>管理用户角色</DialogTitle>
      </DialogHeader>
      <DialogContent>
        {/* 角色多选框 */}
        <div className="space-y-2">
          {allRoles?.map(role => (
            <div key={role.id} className="flex items-center space-x-2">
              <Checkbox
                checked={userRoles?.some(r => r.id === role.id)}
                onCheckedChange={(checked) => {
                  if (checked) {
                    assignRole.mutate(role.id)
                  } else {
                    removeRole.mutate(role.id)
                  }
                }}
              />
              <Label>{role.name}</Label>
              <span className="text-sm text-muted-foreground">
                {role.description}
              </span>
            </div>
          ))}
        </div>
        
        {/* 权限预览 */}
        <div className="mt-4">
          <h4 className="text-sm font-medium mb-2">当前权限：</h4>
          <div className="flex flex-wrap gap-1">
            {userRoles?.flatMap(r => r.permissions).map(p => (
              <Badge key={p.code} variant="secondary">
                {p.name}
              </Badge>
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

#### 角色管理页面（/admin/roles）（新增）

**功能：**
- 查看所有角色
- 创建/编辑/删除角色（非系统角色）
- 为角色分配权限

**组件结构：**
```
RolesPage（新增）
├── RolesTable
│   ├── 列：角色名、描述、权限数量、系统角色、操作
│   └── 操作：编辑、删除（系统角色不可删除）、管理权限
├── CreateRoleDialog
│   ├── 角色名称
│   ├── 描述
│   └── 提交按钮
└── RolePermissionsDialog
    ├── 角色信息展示
    ├── 权限列表（按模块分组）
    │   ├── Bilibili 模块
    │   │   ├── bilibili:account:view
    │   │   ├── bilibili:account:create
    │   │   └── ...
    │   └── 其他模块...
    └── 保存按钮
```

**API 端点：**
```
GET    /api/v1/admin/roles
POST   /api/v1/admin/roles
GET    /api/v1/admin/roles/{role_id}
PUT    /api/v1/admin/roles/{role_id}
DELETE /api/v1/admin/roles/{role_id}
GET    /api/v1/admin/roles/{role_id}/permissions
POST   /api/v1/admin/roles/{role_id}/permissions
DELETE /api/v1/admin/roles/{role_id}/permissions/{permission_id}
```

**实现示例：**
```typescript
function RolePermissionsDialog({ roleId }: { roleId: string }) {
  const { data: role } = useQuery({
    queryKey: ['role', roleId],
    queryFn: () => api.get(`/admin/roles/${roleId}`)
  })
  
  const { data: allPermissions } = useQuery({
    queryKey: ['permissions'],
    queryFn: () => api.get('/admin/permissions')
  })
  
  // 按模块分组
  const permissionsByModule = groupBy(allPermissions, 'module')
  
  return (
    <Dialog>
      <DialogHeader>
        <DialogTitle>管理角色权限 - {role?.name}</DialogTitle>
      </DialogHeader>
      <DialogContent className="max-h-[600px] overflow-y-auto">
        {Object.entries(permissionsByModule).map(([module, permissions]) => (
          <div key={module} className="mb-4">
            <h4 className="font-medium mb-2">{module} 模块</h4>
            <div className="space-y-2 pl-4">
              {permissions.map(permission => (
                <div key={permission.id} className="flex items-center space-x-2">
                  <Checkbox
                    checked={role?.permissions?.some(p => p.id === permission.id)}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        assignPermission.mutate(permission.id)
                      } else {
                        removePermission.mutate(permission.id)
                      }
                    }}
                  />
                  <Label className="text-sm">
                    {permission.name}
                    <span className="text-xs text-muted-foreground ml-2">
                      ({permission.code})
                    </span>
                  </Label>
                </div>
              ))}
            </div>
          </div>
        ))}
      </DialogContent>
    </Dialog>
  )
}
```

#### 权限列表页面（/admin/permissions）（新增，只读）

**功能：**
- 查看所有权限
- 按模块筛选
- 查看哪些角色拥有该权限

**组件结构：**
```
PermissionsPage（新增）
├── 模块筛选器（Tabs）
│   ├── 全部
│   ├── bilibili
│   └── 其他模块...
└── PermissionsTable
    ├── 列：权限代码、名称、描述、拥有该权限的角色
    └── 只读展示
```

### 2. 后端 API 实现

**角色管理 API（app/api/routes/admin.py）：**

```python
@router.get("/roles")
async def get_roles(
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session)
):
    """获取所有角色"""
    roles = session.exec(select(Role)).all()
    return roles

@router.post("/roles")
async def create_role(
    data: RoleCreate,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session)
):
    """创建角色"""
    role = Role(**data.dict())
    session.add(role)
    session.commit()
    session.refresh(role)
    return role

@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: UUID,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session)
):
    """删除角色（系统角色不可删除）"""
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(404, "角色不存在")
    
    if role.is_system:
        raise HTTPException(400, "系统角色不可删除")
    
    session.delete(role)
    session.commit()
    return {"message": "删除成功"}

@router.get("/roles/{role_id}/permissions")
async def get_role_permissions(
    role_id: UUID,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session)
):
    """获取角色的权限"""
    permissions = session.exec(
        select(Permission)
        .join(RolePermission)
        .where(RolePermission.role_id == role_id)
    ).all()
    return permissions

@router.post("/roles/{role_id}/permissions")
async def assign_permission_to_role(
    role_id: UUID,
    data: PermissionAssign,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session)
):
    """为角色分配权限"""
    role_permission = RolePermission(
        role_id=role_id,
        permission_id=data.permission_id
    )
    session.add(role_permission)
    session.commit()
    return {"message": "分配成功"}

@router.get("/users/{user_id}/roles")
async def get_user_roles(
    user_id: UUID,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session)
):
    """获取用户的角色"""
    roles = session.exec(
        select(Role)
        .join(UserRole)
        .where(UserRole.user_id == user_id)
    ).all()
    return roles

@router.post("/users/{user_id}/roles")
async def assign_role_to_user(
    user_id: UUID,
    data: RoleAssign,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session)
):
    """为用户分配角色"""
    user_role = UserRole(
        user_id=user_id,
        role_id=data.role_id
    )
    session.add(user_role)
    session.commit()
    return {"message": "分配成功"}

@router.get("/permissions")
async def get_permissions(
    module: Optional[str] = None,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session)
):
    """获取所有权限"""
    query = select(Permission)
    if module:
        query = query.where(Permission.module == module)
    
    permissions = session.exec(query).all()
    return permissions
```

### 3. 用户登录时加载权限

**后端修改（app/api/routes/login.py）：**

```python
@router.post("/login/access-token")
async def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
):
    # ... 现有的认证逻辑
    
    # 加载用户权限
    permissions = session.exec(
        select(Permission)
        .join(RolePermission)
        .join(UserRole)
        .where(UserRole.user_id == user.id)
    ).all()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_superuser": user.is_superuser,
            "permissions": [p.code for p in permissions]  # 返回权限代码列表
        }
    }
```

### 4. 菜单路由更新

**在 AppSidebar 中添加管理员菜单：**

```typescript
const items = [
  ...baseItems,
  ...(hasBilibiliAccess ? [bilibiliMenu] : []),
  ...(currentUser?.is_superuser ? [{
    icon: Users,
    title: "Admin",
    children: [
      { title: "用户管理", path: "/admin/users" },
      { title: "角色管理", path: "/admin/roles" },      // 新增
      { title: "权限列表", path: "/admin/permissions" }  // 新增
    ]
  }] : [])
]
```


