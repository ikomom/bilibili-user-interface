from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import SessionDep, get_current_user
from app.models import Permission, RolePermission, User, UserRole


def require_permission(permission_code: str) -> Callable:
    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_user)],
        session: SessionDep,
    ) -> User:
        if current_user.is_superuser:
            return current_user

        has_permission = session.exec(
            select(Permission)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .join(UserRole, RolePermission.role_id == UserRole.role_id)
            .where(
                UserRole.user_id == current_user.id,
                Permission.code == permission_code,
            )
        ).first()

        if not has_permission:
            raise HTTPException(
                status_code=403,
                detail=f"权限不足: 需要 {permission_code} 权限",
            )

        return current_user

    return Depends(permission_checker)


def has_permission(user: User, permission_code: str, session: Session) -> bool:
    if user.is_superuser:
        return True

    has_perm = session.exec(
        select(Permission)
        .join(RolePermission, Permission.id == RolePermission.permission_id)
        .join(UserRole, RolePermission.role_id == UserRole.role_id)
        .where(
            UserRole.user_id == user.id,
            Permission.code == permission_code,
        )
    ).first()

    return has_perm is not None
