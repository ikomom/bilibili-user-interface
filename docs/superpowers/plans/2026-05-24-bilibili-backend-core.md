# Bilibili 后端核心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Bilibili 模块的完整后端功能，包括账户管理、订阅管理、资源同步服务、WebSocket 实时日志推送。

**Architecture:** 使用 bilibili-api-python 封装客户端，APScheduler 管理定时任务，WebSocket 推送同步日志。凭证使用 Fernet 加密存储。同步服务支持失败重试和增量同步。

**Tech Stack:** FastAPI, bilibili-api-python, APScheduler, WebSocket, cryptography, tenacity

**Prerequisites:** Plan 1 (RBAC 权限系统) 必须先完成

---

## File Structure

**Backend files to create:**
- `backend/app/bilibili/client.py` - bilibili-api 客户端封装
- `backend/app/bilibili/sync_service.py` - 同步服务
- `backend/app/bilibili/scheduler.py` - APScheduler 定时任务
- `backend/app/bilibili/websocket.py` - WebSocket 连接管理
- `backend/app/bilibili/models.py` - Bilibili SQLModel 模型
- `backend/app/bilibili/schemas.py` - Pydantic schemas + 枚举字典
- `backend/app/bilibili/crud.py` - 数据库操作
- `backend/app/bilibili/router.py` - API 路由
- `backend/app/bilibili/exceptions.py` - 自定义异常
- `alembic/versions/xxxx_add_bilibili_tables.py` - Bilibili 表迁移

**Backend files to modify:**
- `backend/app/core/security.py` - 添加凭证加密/解密函数
- `backend/app/api/main.py` - 注册 bilibili router 和 WebSocket
- `backend/app/main.py` - 添加 APScheduler 生命周期管理
- `backend/requirements.txt` - 添加依赖

**Dependencies to add:**
- bilibili-api-python>=16.0.0
- apscheduler>=3.10.0
- tenacity>=8.2.0
- cryptography>=41.0.0

---

### Task 1: 添加依赖和环境变量

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `.env`

- [ ] **Step 1: 添加 Python 依赖**

在 `backend/requirements.txt` 末尾添加：

```txt
# Bilibili module
bilibili-api-python>=16.0.0
apscheduler>=3.10.0
tenacity>=8.2.0
cryptography>=41.0.0
```

- [ ] **Step 2: 安装依赖**

```bash
cd backend
pip install -r requirements.txt
```

Expected: 所有包安装成功

- [ ] **Step 3: 添加环境变量**

在 `.env` 文件中添加：

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

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt .env
git commit -m "feat(bilibili): add dependencies and environment variables

- Add bilibili-api-python for B站 API 封装
- Add apscheduler for scheduled sync tasks
- Add tenacity for retry logic
- Add cryptography for credential encryption
- Add Bilibili and APScheduler config to .env

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 实现凭证加密/解密

**Files:**
- Modify: `backend/app/core/security.py`

- [ ] **Step 1: 添加导入**

在 `backend/app/core/security.py` 顶部添加：

```python
import os
import json
from cryptography.fernet import Fernet
```

- [ ] **Step 2: 实现密钥管理函数**

```python
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
        
        raise ValueError("缺少加密密钥配置，请将上述密钥添加到 .env 文件后重启")
    
    return key
```

- [ ] **Step 3: 实现加密函数**

```python
def encrypt_credentials(credentials: dict) -> str:
    """
    加密凭证
    
    Args:
        credentials: 凭证字典
        
    Returns:
        加密后的字符串
    """
    key = get_or_create_encryption_key()
    f = Fernet(key.encode())
    json_str = json.dumps(credentials)
    encrypted = f.encrypt(json_str.encode())
    return encrypted.decode()
```

- [ ] **Step 4: 实现解密函数**

```python
def decrypt_credentials(encrypted: str) -> dict:
    """
    解密凭证
    
    Args:
        encrypted: 加密后的字符串
        
    Returns:
        凭证字典
    """
    key = get_or_create_encryption_key()
    f = Fernet(key.encode())
    decrypted = f.decrypt(encrypted.encode())
    return json.loads(decrypted.decode())
```

- [ ] **Step 5: 测试加密/解密**

创建 `backend/tests/test_security.py`：

```python
import pytest
from app.core.security import encrypt_credentials, decrypt_credentials

def test_encrypt_decrypt_credentials():
    """测试凭证加密和解密"""
    original = {
        "sessdata": "test_sessdata_123",
        "bili_jct": "test_bili_jct_456",
        "buvid3": "test_buvid3_789"
    }
    
    # 加密
    encrypted = encrypt_credentials(original)
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0
    
    # 解密
    decrypted = decrypt_credentials(encrypted)
    assert decrypted == original

def test_encrypt_different_each_time():
    """测试每次加密结果不同（包含随机 IV）"""
    credentials = {"sessdata": "test"}
    
    encrypted1 = encrypt_credentials(credentials)
    encrypted2 = encrypt_credentials(credentials)
    
    # 加密结果不同
    assert encrypted1 != encrypted2
    
    # 但解密结果相同
    assert decrypt_credentials(encrypted1) == decrypt_credentials(encrypted2)
```

Run: `pytest backend/tests/test_security.py -v`

Expected: 所有测试通过

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat(bilibili): add credential encryption/decryption

- Use Fernet symmetric encryption for credentials
- Auto-generate encryption key if not present
- Add unit tests for encryption/decryption
- Ensure encrypted data is different each time (random IV)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 创建 Bilibili 数据库模型

**Files:**
- Create: `backend/app/bilibili/models.py`

- [ ] **Step 1: 创建文件并添加导入**

```python
from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import Field, Relationship, SQLModel, JSON, Column
from sqlalchemy.dialects.postgresql import JSONB
```

- [ ] **Step 2: 创建 BilibiliAccount 模型**

```python
class BilibiliAccount(SQLModel, table=True):
    __tablename__ = "bilibili_accounts"
    
    id: UUID = Field(default=None, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    account_name: str = Field(max_length=100)
    auth_type: str = Field(max_length=20)  # 'cookie' | 'sessdata' | 'qrcode'
    credentials: str = Field(sa_column=Column(JSONB))  # 加密存储
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)
    
    # Relationships
    subscriptions: list["BilibiliSubscription"] = Relationship(back_populates="account")
```

- [ ] **Step 3: 创建 BilibiliSubscription 模型**

```python
class BilibiliSubscription(SQLModel, table=True):
    __tablename__ = "bilibili_uploader_subscriptions"
    
    id: UUID = Field(default=None, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    account_id: UUID = Field(foreign_key="bilibili_accounts.id", ondelete="CASCADE")
    uploader_uid: str = Field(max_length=50)
    uploader_name: str = Field(max_length=100)
    uploader_avatar: Optional[str] = None
    uploader_info: dict = Field(default={}, sa_column=Column(JSONB))
    sync_config: dict = Field(sa_column=Column(JSONB))
    is_paused: bool = Field(default=False)
    last_sync_at: Optional[datetime] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)
    
    # Relationships
    account: BilibiliAccount = Relationship(back_populates="subscriptions")
    resources: list["BilibiliResource"] = Relationship(back_populates="subscription")
    sync_logs: list["SyncLog"] = Relationship(back_populates="subscription")
```

- [ ] **Step 4: 创建 BilibiliResource 模型**

```python
class BilibiliResource(SQLModel, table=True):
    __tablename__ = "bilibili_resources"
    
    id: UUID = Field(default=None, primary_key=True)
    subscription_id: UUID = Field(foreign_key="bilibili_uploader_subscriptions.id", ondelete="CASCADE")
    resource_type: str = Field(max_length=20)  # 'video' | 'dynamic' | 'article'
    resource_id: str = Field(max_length=50)
    title: str
    cover_url: Optional[str] = None
    summary: Optional[str] = None
    full_content: Optional[str] = None
    attachments: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    metadata: dict = Field(sa_column=Column(JSONB))
    published_at: datetime
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    
    # Relationships
    subscription: BilibiliSubscription = Relationship(back_populates="resources")
```

- [ ] **Step 5: 创建 SyncLog 模型**

```python
class SyncLog(SQLModel, table=True):
    __tablename__ = "sync_logs"
    
    id: UUID = Field(default=None, primary_key=True)
    subscription_id: UUID = Field(foreign_key="bilibili_uploader_subscriptions.id", ondelete="CASCADE")
    sync_type: str = Field(max_length=20)  # 'manual' | 'scheduled'
    status: str = Field(max_length=20)  # 'running' | 'success' | 'failed'
    start_time: datetime
    end_time: Optional[datetime] = None
    total_count: int = Field(default=0)
    success_count: int = Field(default=0)
    failed_count: int = Field(default=0)
    skipped_count: int = Field(default=0)
    error_message: Optional[str] = None
    details: Optional[list] = Field(default=None, sa_column=Column(JSONB))
    
    # Relationships
    subscription: BilibiliSubscription = Relationship(back_populates="sync_logs")
```

- [ ] **Step 6: 创建 FailedResource 模型**

```python
class FailedResource(SQLModel, table=True):
    __tablename__ = "failed_resources"
    
    id: UUID = Field(default=None, primary_key=True)
    subscription_id: UUID = Field(foreign_key="bilibili_uploader_subscriptions.id", ondelete="CASCADE")
    resource_id: str = Field(max_length=50)
    resource_type: str = Field(max_length=20)
    failed_at: Optional[datetime] = Field(default_factory=datetime.now)
    retry_count: int = Field(default=0)
    last_error: Optional[str] = None
    metadata: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
```

- [ ] **Step 7: 验证模型导入**

```bash
cd backend
python -c "from app.bilibili.models import BilibiliAccount, BilibiliSubscription, BilibiliResource, SyncLog, FailedResource; print('Models imported successfully')"
```

Expected: 输出 "Models imported successfully"

- [ ] **Step 8: Commit**

```bash
git add backend/app/bilibili/models.py
git commit -m "feat(bilibili): add Bilibili SQLModel models

- Add BilibiliAccount model with encrypted credentials
- Add BilibiliSubscription model with sync_config
- Add BilibiliResource model with metadata
- Add SyncLog model for tracking sync history
- Add FailedResource model for retry logic
- Use JSONB columns for flexible data storage

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 创建 Bilibili 数据库迁移

**Files:**
- Create: `alembic/versions/xxxx_add_bilibili_tables.py`

- [ ] **Step 1: 生成迁移文件**

```bash
cd backend
alembic revision -m "Add Bilibili tables"
```

Expected: 生成新的迁移文件

- [ ] **Step 2: 编写 upgrade 函数（创建 5 张表）**

由于代码较长，这里只展示结构，完整代码参考设计文档：

```python
def upgrade():
    # 1. bilibili_accounts
    op.create_table('bilibili_accounts', ...)
    op.create_index('idx_bilibili_accounts_user_id', ...)
    
    # 2. bilibili_uploader_subscriptions
    op.create_table('bilibili_uploader_subscriptions', ...)
    op.create_index('idx_subscriptions_user_id', ...)
    op.create_index('idx_subscriptions_uploader_uid', ...)
    
    # 3. bilibili_resources
    op.create_table('bilibili_resources', ...)
    op.create_index('idx_resources_subscription_id', ...)
    op.create_index('idx_resources_published_at', ...)
    op.create_index('idx_resources_type', ...)
    
    # 4. sync_logs
    op.create_table('sync_logs', ...)
    op.create_index('idx_sync_logs_subscription_id', ...)
    op.create_index('idx_sync_logs_start_time', ...)
    
    # 5. failed_resources
    op.create_table('failed_resources', ...)
    op.create_index('idx_failed_resources_subscription_id', ...)
```

- [ ] **Step 3: 编写 downgrade 函数**

```python
def downgrade():
    op.drop_table('failed_resources')
    op.drop_table('sync_logs')
    op.drop_table('bilibili_resources')
    op.drop_table('bilibili_uploader_subscriptions')
    op.drop_table('bilibili_accounts')
```

- [ ] **Step 4: 应用迁移**

```bash
alembic upgrade head
```

Expected: 5 张表创建成功

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/*_add_bilibili_tables.py
git commit -m "feat(bilibili): add Bilibili database tables migration

- Add 5 Bilibili tables with proper indexes
- Add foreign key constraints with CASCADE delete
- Add UNIQUE constraint on (user_id, uploader_uid)
- Support upgrade and downgrade

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

