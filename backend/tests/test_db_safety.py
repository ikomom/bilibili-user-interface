import pytest

from tests.conftest import assert_test_database


def test_assert_test_database_rejects_non_test_database() -> None:
    with pytest.raises(RuntimeError, match="Refusing to run destructive test cleanup"):
        assert_test_database("app")


def test_assert_test_database_allows_test_database() -> None:
    assert_test_database("app_test")
