import sqlite3

import pytest

import api.db
from api.db import get_conn, init_db, record_job_event


@pytest.fixture
def database(tmp_path, monkeypatch):
    test_db = tmp_path / "test_jobs.db"
    monkeypatch.setattr(api.db, "DB_PATH", test_db)
    init_db()
    return test_db


def insert_job(conn, job_id="job-1"):
    conn.execute(
        """
        INSERT INTO jobs (id, payload, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            job_id,
            "test payload",
            "queued",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ),
    )


def test_init_db_creates_job_events(database):
    with sqlite3.connect(database) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("job_events",),
        ).fetchone()

    assert table == ("job_events",)


def test_get_conn_enforces_job_event_foreign_key(database):
    with get_conn() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            record_job_event(
                conn,
                job_id="missing-job",
                event_type="created",
            )


def test_record_job_event_stores_all_supplied_fields(database):
    created_at = "2026-01-02T03:04:05+00:00"

    with get_conn() as conn:
        insert_job(conn)
        event_id = record_job_event(
            conn,
            job_id="job-1",
            event_type="status_changed",
            from_status="queued",
            to_status="processing",
            message="Worker claimed the job",
            created_at=created_at,
        )
        event = conn.execute(
            "SELECT * FROM job_events WHERE id = ?", (event_id,)
        ).fetchone()

    assert event_id == event["id"]
    assert dict(event) == {
        "id": event_id,
        "job_id": "job-1",
        "event_type": "status_changed",
        "from_status": "queued",
        "to_status": "processing",
        "message": "Worker claimed the job",
        "created_at": created_at,
    }


def test_record_job_event_accepts_nullable_fields(database):
    with get_conn() as conn:
        insert_job(conn)
        event_id = record_job_event(
            conn,
            job_id="job-1",
            event_type="created",
            created_at="2026-01-02T03:04:05+00:00",
        )
        event = conn.execute(
            "SELECT from_status, to_status, message FROM job_events WHERE id = ?",
            (event_id,),
        ).fetchone()

    assert tuple(event) == (None, None, None)


def test_record_job_event_uses_callers_transaction(database):
    with get_conn() as conn:
        insert_job(conn)

    with get_conn() as conn:
        record_job_event(
            conn,
            job_id="job-1",
            event_type="status_changed",
            from_status="queued",
            to_status="processing",
        )
        conn.rollback()

    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM job_events").fetchone()[0]

    assert count == 0
