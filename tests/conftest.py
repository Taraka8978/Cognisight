import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """
    Use a temporary SQLite file for each test run.

    We patch focus_sentry.database.DB_PATH before importing the app,
    then call init_db so schema is created on the test db.
    """
    from focus_sentry import database

    test_db_path = tmp_path / "focus_sentry_test.db"
    monkeypatch.setattr(database, "DB_PATH", test_db_path)

    database.init_db()

    from focus_sentry.app import app

    return TestClient(app)
