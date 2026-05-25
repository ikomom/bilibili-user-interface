import uuid
from datetime import datetime, timezone

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# RBAC link models (must be defined before User, Permission, Role)
class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permissions"

    role_id: uuid.UUID = Field(foreign_key="roles.id", primary_key=True, ondelete="CASCADE")
    permission_id: uuid.UUID = Field(foreign_key="permissions.id", primary_key=True, ondelete="CASCADE")


class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"

    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True, ondelete="CASCADE")
    role_id: uuid.UUID = Field(foreign_key="roles.id", primary_key=True, ondelete="CASCADE")
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore[assignment]
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    roles: list["Role"] = Relationship(back_populates="users", link_model=UserRole)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None
    permissions: list[str] = []


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# RBAC models
class Permission(SQLModel, table=True):
    __tablename__ = "permissions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=100, unique=True, index=True)
    name: str = Field(max_length=100)
    module: str = Field(max_length=50, index=True)
    description: str | None = None
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    roles: list["Role"] = Relationship(back_populates="permissions", link_model=RolePermission)


class Role(SQLModel, table=True):
    __tablename__ = "roles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=50, unique=True, index=True)
    description: str | None = None
    is_system: bool = Field(default=False)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    permissions: list[Permission] = Relationship(back_populates="roles", link_model=RolePermission)
    users: list["User"] = Relationship(back_populates="roles", link_model=UserRole)


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore[assignment]


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
