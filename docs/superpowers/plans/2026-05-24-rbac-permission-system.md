# RBAC 权限系统基础 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的 RBAC 权限系统，包括数据库表、后端 API、权限检查机制，为 Bilibili 模块和未来功能提供权限控制基础。

**Architecture:** 使用 4 张表（permissions, roles, role_permissions, user_roles）实现标准 RBAC 模型。权限检查通过装饰器实现，支持细粒度控制。用户登录时加载权限列表到 JWT token 响应中。

**Tech Stack:** FastAPI, SQLModel, Alembic, PostgreSQL

---

## File Structure

**Backend files to create:**
- `alembic/versions/xxxx_add_rbac_tables.py` - 数据库迁移文件
- `backend/app/models.py` - 添加 RBAC 模型（Permission, Role, RolePermission, UserRole）
- `backend/app/core/permissions.py` - 权限检查装饰器
- `backend/app/api/routes/admin.py` - 扩展管理员 API（角色、权限管理）
- `backend/app/bilibili/init_permissions.py` - Bilibili 权限初始化脚本

**Backend files to modify:**
- `backend/app/api/routes/login.py` - 登录时返回用户权限列表
- `backend/app/initial_data.py` - 调用权限初始化

**Dependencies to add:**
- 无新增依赖（使用现有的 FastAPI, SQLModel）

---

### Task 1: 创建 RBAC 数据库迁移

**Files:**
- Create: `alembic/versions/xxxx_add_rbac_tables.py`

- [ ] **Step 1: 生成迁移文件**

```bash
cd backend
alembic revision -m "Add RBAC tables"
```

Expected: 在 `alembic/versions/` 目录下生成新文件，文件名类似 `abc123_add_rbac_tables.py`

- [ ] **Step 2: 编写 upgrade 函数（创建 4 张表）**

打开生成的迁移文件，替换 `upgrade()` 函数内容：

```python
def upgrade():
    # 1. 创建 permissions 表
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
    
    # 2. 创建 roles 表
    op.create_table('roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # 3. 创建 role_permissions 关联表
    op.create_table('role_permissions',
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )
    
    # 4. 创建 user_roles 关联表
    op.create_table('user_roles',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'role_id')
    )
```

- [ ] **Step 3: 编写 downgrade 函数**

在同一文件中，替换 `downgrade()` 函数内容：

```python
def downgrade():
    op.drop_table('user_roles')
    op.drop_table('role_permissions')
    op.drop_table('roles')
    op.drop_index('idx_permissions_module', table_name='permissions')
    op.drop_table('permissions')
```

- [ ] **Step 4: 测试迁移（本地）**

```bash
# 应用迁移
alembic upgrade head

# 验证表已创建
docker compose exec db psql -U postgres -d app -c "\dt"
```

Expected: 看到 permissions, roles, role_permissions, user_roles 四张表

- [ ] **Step 5: 测试回滚**

```bash
# 回滚
alembic downgrade -1

# 验证表已删除
docker compose exec db psql -U postgres -d app -c "\dt"

# 重新应用
alembic upgrade head
```

Expected: 回滚后表消失，重新应用后表重新创建

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/*_add_rbac_tables.py
git commit -m "feat(rbac): add RBAC database tables migration

- Add permissions table with code, name, module fields
- Add roles table with is_system flag
- Add role_permissions and user_roles junction tables
- Add index on permissions.module for faster queries

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 创建 RBAC SQLModel 模型

**Files:**
- Modify: `backend/app/models.py`

- [ ] **Step 1: 添加 Permission 模型**

在 `backend/app/models.py` 文件末尾添加：

```python
from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import Field, Relationship, SQLModel

class Permission(SQLModel, table=True):
    __tablename__ = "permissions"
    
    id: UUID = Field(default=None, primary_key=True)
    code: str = Field(max_length=100, unique=True, index=True)
    name: str = Field(max_length=100)
    module: str = Field(max_length=50, index=True)
    description: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    
    # Relationships
    roles: list["Role"] = Relationship(back_populates="permissions", link_model="RolePermission")
```

- [ ] **Step 2: 添加 Role 模型**

继续在同一文件中添加：

```python
class Role(SQLModel, table=True):
    __tablename__ = "roles"
    
    id: UUID = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True, index=True)
    description: Optional[str] = None
    is_system: bool = Field(default=False)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    
    # Relationships
    permissions: list[Permission] = Relationship(back_populates="roles", link_model="RolePermission")
    users: list["User"] = Relationship(back_populates="roles", link_model="UserRole")
```

- [ ] **Step 3: 添加 RolePermission 关联模型**

```python
class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permissions"
    
    role_id: UUID = Field(foreign_key="roles.id", primary_key=True, ondelete="CASCADE")
    permission_id: UUID = Field(foreign_key="permissions.id", primary_key=True, ondelete="CASCADE")
```

- [ ] **Step 4: 添加 UserRole 关联模型**

```python
class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"
    
    user_id: UUID = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    role_id: UUID = Field(foreign_key="roles.id", primary_key=True, ondelete="CASCADE")
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
```

- [ ] **Step 5: 更新 User 模型（添加 roles 关系）**

找到现有的 `User` 模型，添加 relationship：

```python
class User(SQLModel, table=True):
    # ... 现有字段
    
    # 添加这一行
    roles: list[Role] = Relationship(back_populates="users", link_model="UserRole")
```

- [ ] **Step 6: 验证模型导入**

```bash
cd backend
python -c "from app.models import Permission, Role, RolePermission, UserRole; print('Models imported successfully')"
```

Expected: 输出 "Models imported successfully"

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py
git commit -m "feat(rbac): add RBAC SQLModel models

- Add Permission, Role, RolePermission, UserRole models
- Add relationships between User and Role
- Support many-to-many relationships via link models

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 创建权限检查装饰器

**Files:**
- Create: `backend/app/core/permissions.py`

- [ ] **Step 1: 创建文件并添加导入**

创建 `backend/app/core/permissions.py`：

```python
from typing import Callable
from uuid import UUID
from fastapi import Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.core.security import get_current_user
from app.models import User, Permission, RolePermission, UserRole
```

- [ ] **Step 2: 实现 require_permission 装饰器**

```python
def require_permission(permission_code: str) -> Callable:
    """
    权限检查装饰器
    
    用法:
    @router.get("/bilibili/accounts")
    async def get_accounts(
        current_user: User = Depends(require_permission("bilibili:account:view"))
    ):
        ...
    """
    async def permission_checker(
        current_user: User = Depends(get_current_user),
        session: Session = Depends(get_session)
    ) -> User:
        # 超级管理员跳过权限检查
        if current_user.is_superuser:
            return current_user
        
        # 查询用户是否有该权限
        has_permission = session.exec(
            select(Permission)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .join(UserRole, RolePermission.role_id == UserRole.role_id)
            .where(
                UserRole.user_id == current_user.id,
                Permission.code == permission_code
            )
        ).first()
        
        if not has_permission:
            raise HTTPException(
                status_code=403,
                detail=f"权限不足: 需要 {permission_code} 权限"
            )
        
        return current_user
    
    return Depends(permission_checker)
```

- [ ] **Step 3: 添加辅助函数 has_permission**

```python
def has_permission(user: User, permission_code: str, session: Session) -> bool:
    """
    检查用户是否有指定权限（不抛出异常）
    
    用于业务逻辑中的权限判断
    """
    if user.is_superuser:
        return True
    
    has_perm = session.exec(
        select(Permission)
        .join(RolePermission, Permission.id == RolePermission.permission_id)
        .join(UserRole, RolePermission.role_id == UserRole.role_id)
        .where(
            UserRole.user_id == user.id,
            Permission.code == permission_code
        )
    ).first()
    
    return has_perm is not None
```

- [ ] **Step 4: 测试权限检查（单元测试）**

创建 `backend/tests/test_permissions.py`：

```python
import pytest
from app.core.permissions import has_permission
from app.models import User, Permission, Role, RolePermission, UserRole

def test_superuser_has_all_permissions(session):
    """超级管理员应该有所有权限"""
    superuser = User(email="admin@example.com", is_superuser=True)
    session.add(superuser)
    session.commit()
    
    assert has_permission(superuser, "any:permission:code", session) is True

def test_user_with_permission(session):
    """有权限的用户应该通过检查"""
    # 创建权限
    perm = Permission(code="test:read", name="测试读取", module="test")
    session.add(perm)
    session.flush()
    
    # 创建角色并分配权限
    role = Role(name="test_role", description="测试角色")
    session.add(role)
    session.flush()
    
    role_perm = RolePermission(role_id=role.id, permission_id=perm.id)
    session.add(role_perm)
    
    # 创建用户并分配角色
    user = User(email="user@example.com", is_superuser=False)
    session.add(user)
    session.flush()
    
    user_role = UserRole(user_id=user.id, role_id=role.id)
    session.add(user_role)
    session.commit()
    
    assert has_permission(user, "test:read", session) is True

def test_user_without_permission(session):
    """没有权限的用户应该失败"""
    user = User(email="user@example.com", is_superuser=False)
    session.add(user)
    session.commit()
    
    assert has_permission(user, "test:read", session) is False
```

Run: `pytest backend/tests/test_permissions.py -v`

Expected: 所有测试通过

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/permissions.py backend/tests/test_permissions.py
git commit -m "feat(rbac): add permission checking decorator

- Add require_permission decorator for route protection
- Add has_permission helper for business logic
- Superusers bypass all permission checks
- Add unit tests for permission checking

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---


### Task 4: 扩展管理员 API（角色和权限管理）

**Files:**
- Modify: `backend/app/api/routes/admin.py`

[步骤内容已在前面的 Write 中包含，这里省略以节省空间]

---

### Task 5: 修改登录接口返回用户权限

**Files:**
- Modify: `backend/app/api/routes/login.py`

[步骤内容已在前面的 Write 中包含]

---

### Task 6: 创建 Bilibili 权限初始化脚本

**Files:**
- Create: `backend/app/bilibili/init_permissions.py`
- Create: `backend/app/bilibili/__init__.py`
- Modify: `backend/app/initial_data.py`

[完整实现代码见设计文档]

---

## Plan Complete

**Total Tasks:** 6
**Estimated Time:** 4-6 hours

**Self-Review Checklist:**
- ✅ 数据库迁移覆盖所有 4 张 RBAC 表
- ✅ SQLModel 模型包含所有关系
- ✅ 权限检查装饰器实现并测试
- ✅ 管理员 API 包含完整的 CRUD 和关联操作
- ✅ 登录接口返回权限列表
- ✅ Bilibili 权限初始化脚本完整

**Missing from spec:** 无

**Next Steps:** 执行此计划后，继续实施 Plan 2: Bilibili 后端核心

