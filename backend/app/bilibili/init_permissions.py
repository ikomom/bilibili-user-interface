from sqlmodel import Session, select

from app.models import Permission, Role, RolePermission, User, UserRole

BILIBILI_PERMISSIONS = [
    {"code": "bilibili:account:create", "name": "创建 B站账户", "module": "bilibili"},
    {"code": "bilibili:account:view", "name": "查看 B站账户", "module": "bilibili"},
    {"code": "bilibili:account:update", "name": "更新 B站账户", "module": "bilibili"},
    {"code": "bilibili:account:delete", "name": "删除 B站账户", "module": "bilibili"},
    {"code": "bilibili:subscription:create", "name": "创建订阅", "module": "bilibili"},
    {"code": "bilibili:subscription:view", "name": "查看订阅", "module": "bilibili"},
    {"code": "bilibili:subscription:update", "name": "更新订阅", "module": "bilibili"},
    {"code": "bilibili:subscription:delete", "name": "删除订阅", "module": "bilibili"},
    {"code": "bilibili:subscription:sync", "name": "手动同步", "module": "bilibili"},
    {"code": "bilibili:resource:view", "name": "查看资源", "module": "bilibili"},
    {"code": "bilibili:sync-log:view", "name": "查看同步日志", "module": "bilibili"},
]

ADMIN_PERMISSIONS = [
    {"code": "admin:role:create", "name": "创建角色", "module": "admin"},
    {"code": "admin:role:view", "name": "查看角色", "module": "admin"},
    {"code": "admin:role:update", "name": "更新角色", "module": "admin"},
    {"code": "admin:role:delete", "name": "删除角色", "module": "admin"},
    {"code": "admin:user:assign-role", "name": "分配用户角色", "module": "admin"},
]

DEFAULT_PERMISSIONS = BILIBILI_PERMISSIONS + ADMIN_PERMISSIONS


def init_permissions(session: Session) -> None:
    for perm_data in DEFAULT_PERMISSIONS:
        existing = session.exec(
            select(Permission).where(Permission.code == perm_data["code"])
        ).first()
        if not existing:
            session.add(Permission(**perm_data))
    session.flush()

    admin_role = _get_or_create_role(
        session,
        name="admin",
        description="管理员角色，拥有所有权限",
    )
    user_role = _get_or_create_role(
        session,
        name="user",
        description="普通用户角色，拥有 Bilibili 功能权限",
    )
    session.flush()

    all_permissions = session.exec(select(Permission)).all()
    for perm in all_permissions:
        _add_role_permission(session, admin_role.id, perm.id)

    bilibili_perms = session.exec(
        select(Permission).where(Permission.module == "bilibili")
    ).all()
    for perm in bilibili_perms:
        _add_role_permission(session, user_role.id, perm.id)

    superuser = session.exec(
        select(User).where(User.is_superuser == True)  # noqa: E712
    ).first()
    if superuser:
        existing = session.exec(
            select(UserRole).where(
                UserRole.user_id == superuser.id,
                UserRole.role_id == admin_role.id,
            )
        ).first()
        if not existing:
            session.add(UserRole(user_id=superuser.id, role_id=admin_role.id))

    session.commit()


def _get_or_create_role(session: Session, name: str, description: str) -> Role:
    role = session.exec(select(Role).where(Role.name == name)).first()
    if role:
        return role
    role = Role(name=name, description=description, is_system=True)
    session.add(role)
    return role


def _add_role_permission(
    session: Session, role_id, permission_id
) -> None:
    existing = session.exec(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
    ).first()
    if not existing:
        session.add(RolePermission(role_id=role_id, permission_id=permission_id))
