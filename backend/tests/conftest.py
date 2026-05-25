import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, delete

os.environ.setdefault("POSTGRES_DB", "app_test")
os.environ["POSTGRES_DB"] = os.environ.get("POSTGRES_TEST_DB", os.environ["POSTGRES_DB"])

import app.bilibili.models  # noqa: E402, F401
from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import Item, SQLModel, User
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


def assert_test_database(database_name: str) -> None:
    if not database_name.endswith("_test"):
        raise RuntimeError(
            "Refusing to run destructive test cleanup against non-test database: "
            f"{database_name!r}. Set POSTGRES_DB to a database ending with '_test'."
        )


def ensure_test_database() -> None:
    assert_test_database(settings.POSTGRES_DB)
    maintenance_url = str(settings.SQLALCHEMY_DATABASE_URI).rsplit("/", 1)[0] + "/postgres"
    maintenance_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    try:
        with maintenance_engine.connect() as connection:
            database_exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": settings.POSTGRES_DB},
            ).scalar()
            if not database_exists:
                connection.execute(text(f'CREATE DATABASE "{settings.POSTGRES_DB}"'))
    except Exception:
        from sqlalchemy import create_engine

        fallback_engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
        with fallback_engine.connect() as connection:
            database_exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": settings.POSTGRES_DB},
            ).scalar()
            if not database_exists:
                connection.execute(text(f'CREATE DATABASE "{settings.POSTGRES_DB}"'))
        fallback_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    ensure_test_database()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        init_db(session)
        yield session
        statement = delete(Item)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        session.commit()
        init_db(session)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
