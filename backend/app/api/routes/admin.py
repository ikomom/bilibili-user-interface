import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
)
from app.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_active_superuser)])


# --- Permissions ---
@router.get("/permissions")
def read_permissions(
    session: SessionDep, module: str | None = None
) -> Any:
    query = select(Permission).order_by(Permission.module, Permission.code)
    if module:
        query = query.where(Permission.module == module)
    permissions = session.exec(query).all()
    return [
        {
            "id": permission.id,
            "code": permission.code,
            "name": permission.name,
            "module": permission.module,
            "description": permission.description,
            "created_at": permission.created_at,
            "roles": permission.roles,
        }
        for permission in permissions
    ]


# --- Roles ---
@router.get("/roles")
def read_roles(session: SessionDep) -> Any:
    roles = session.exec(select(Role).order_by(Role.created_at)).all()
    result = []
    for role in roles:
        role_data = {"id": str(role.id), "name": role.name, "description": role.description,
                     "is_system": role.is_system, "created_at": role.created_at,
                     "permission_count": len(role.permissions)}
        result.append(role_data)
    return result


@router.post("/roles", status_code=201)
def create_role(session: SessionDep, data: dict) -> Any:
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="角色名不能为空")
    existing = session.exec(select(Role).where(Role.name == name)).first()
    if existing:
        raise HTTPException(status_code=409, detail="角色名已存在")
    role = Role(name=name, description=data.get("description"))
    session.add(role)
    session.commit()
    session.refresh(role)
    return role


@router.get("/roles/{role_id}")
def read_role(session: SessionDep, role_id: uuid.UUID) -> Any:
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return {"id": str(role.id), "name": role.name, "description": role.description,
            "is_system": role.is_system, "created_at": role.created_at,
            "permissions": role.permissions}


@router.put("/roles/{role_id}")
def update_role(session: SessionDep, role_id: uuid.UUID, data: dict) -> Any:
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if "name" in data:
        role.name = data["name"]
    if "description" in data:
        role.description = data.get("description")
    session.add(role)
    session.commit()
    session.refresh(role)
    return role


@router.delete("/roles/{role_id}")
def delete_role(session: SessionDep, role_id: uuid.UUID) -> Any:
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="系统角色不能删除")
    session.delete(role)
    session.commit()
    return {"message": "角色已删除"}


# --- Role-Permission ---
@router.get("/roles/{role_id}/permissions")
def read_role_permissions(session: SessionDep, role_id: uuid.UUID) -> Any:
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return role.permissions


@router.post("/roles/{role_id}/permissions", status_code=201)
def assign_permission_to_role(session: SessionDep, role_id: uuid.UUID, data: dict) -> Any:
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    permission_id = uuid.UUID(data["permission_id"])
    permission = session.get(Permission, permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="权限不存在")
    existing = session.exec(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
    ).first()
    if existing:
        return {"message": "权限已分配"}
    rp = RolePermission(role_id=role_id, permission_id=permission_id)
    session.add(rp)
    session.commit()
    return {"message": "权限分配成功"}


@router.delete("/roles/{role_id}/permissions/{permission_id}")
def remove_permission_from_role(
    session: SessionDep, role_id: uuid.UUID, permission_id: uuid.UUID
) -> Any:
    rp = session.exec(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
    ).first()
    if not rp:
        raise HTTPException(status_code=404, detail="未找到该权限分配")
    session.delete(rp)
    session.commit()
    return {"message": "权限已移除"}


# --- User-Role ---
@router.get("/users/{user_id}/roles")
def read_user_roles(session: SessionDep, user_id: uuid.UUID) -> Any:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return [
        {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
            "created_at": role.created_at,
            "permissions": [
                {
                    "id": permission.id,
                    "code": permission.code,
                    "name": permission.name,
                    "module": permission.module,
                    "description": permission.description,
                    "created_at": permission.created_at,
                }
                for permission in role.permissions
            ],
        }
        for role in user.roles
    ]


@router.post("/users/{user_id}/roles", status_code=201)
def assign_role_to_user(session: SessionDep, user_id: uuid.UUID, data: dict) -> Any:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    role_id = uuid.UUID(data["role_id"])
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    existing = session.exec(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        )
    ).first()
    if existing:
        return {"message": "角色已分配"}
    ur = UserRole(user_id=user_id, role_id=role_id)
    session.add(ur)
    session.commit()
    return {"message": "角色分配成功"}


@router.delete("/users/{user_id}/roles/{role_id}")
def remove_role_from_user(
    session: SessionDep, user_id: uuid.UUID, role_id: uuid.UUID
) -> Any:
    ur = session.exec(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        )
    ).first()
    if not ur:
        raise HTTPException(status_code=404, detail="未找到该角色分配")
    session.delete(ur)
    session.commit()
    return {"message": "角色已移除"}
