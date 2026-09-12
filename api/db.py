# api/db.py
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "jobs.db"
DB_PATH = Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH)))


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH,timeout=5)
    conn.row_factory = sqlite3.Row  # take result as like dict
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('queued','processing','done','failed')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            result TEXT,
            error TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS job_events (
            id INTEGER PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT,
            message TEXT,
            created_at TEXT NOT NULL
        );
        """)


def record_job_event(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    event_type: str,
    from_status: str | None = None,
    to_status: str | None = None,
    message: str | None = None,
    created_at: str | None = None,
) -> int:
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        """
        INSERT INTO job_events (
            job_id, event_type, from_status, to_status, message, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (job_id, event_type, from_status, to_status, message, created_at),
    )
    return cursor.lastrowid
