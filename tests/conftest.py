# tests/conftest.py

import pytest
from fastapi.testclient import TestClient

import api.db
from api.db import init_db
from api.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = tmp_path / "test_jobs.db"
    monkeypatch.setattr(api.db, "DB_PATH", test_db)

    # 1. avoid API test enqueue to real redis
    monkeypatch.setattr(
        "api.router.jobs.enqueue",
        lambda job_id: None
    )

    # 2. avoid TestClient startup a real worker
    monkeypatch.setattr(
        "api.main.start_worker",
        lambda: None
    )

    init_db()

    with TestClient(app) as test_client:
        yield test_client