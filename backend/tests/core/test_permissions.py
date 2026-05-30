import uuid

from sqlmodel import Session

from app.core.permissions import has_permission, require_permission
from app.models import User


def test_has_permission_superuser(db: Session) -> None:
    """Superuser should have all permissions"""
    superuser = User(
        id=uuid.uuid4(),
        email="super@example.com",
        hashed_password="hash",
        is_superuser=True,
    )
    
    assert has_permission(superuser, "any:permission:code", db) is True


def test_has_permission_without_role(db: Session) -> None:
    """User without role should not have permission"""
    user = User(
        id=uuid.uuid4(),
        email="norole@example.com",
        hashed_password="hash",
        is_superuser=False,
    )
    
    # Don't add to db, just test the logic
    assert has_permission(user, "nonexistent:permission", db) is False


def test_require_permission_returns_depends(db: Session) -> None:
    """require_permission should return a Depends object"""
    checker = require_permission("any:permission")
    # The checker is a Depends object, we test that it's callable
    assert callable(checker.dependency)
