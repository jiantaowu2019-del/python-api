# api/jobs.py
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Literal, List, Optional
from datetime import datetime, timezone
from uuid import uuid4
import time
from collections import Counter

from api.db import get_conn
from api.queue_state import job_queue  # 如果你决定保留事件驱动 worker


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_to_job(row) -> "Job":
    return Job(
        id=row["id"],
        payload=row["payload"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        result=row["result"],
        error=row["error"],
        attempts=row["attempts"],
        max_retries=row["max_retries"],
    )


router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreate(BaseModel):
    payload: str
    max_retries: int = 3


class Job(BaseModel):
    id: str
    payload: str
    status: Literal["queued", "processing", "done", "failed"]
    created_at: datetime
    updated_at: datetime
    result: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    max_retries: int = 3


class JobUpdateStatus(BaseModel):
    status: Literal["queued", "processing", "done", "failed"]


@router.post("", response_model=Job)
def create_job(job_in: JobCreate):
    job_id = str(uuid4())
    now = now_utc_iso()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, payload, status, created_at, updated_at, result, error, attempts, max_retries)
            VALUES (?, ?, 'queued', ?, ?, NULL, NULL, 0, ?)
            """,
            (job_id, job_in.payload, now, now, job_in.max_retries),
        )
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    # 通知 worker：有新任务（如果你 worker 还用 Queue 驱动）
    job_queue.put(job_id)

    return row_to_job(row)


@router.get("", response_model=List[Job])
def list_jobs(
    status: Optional[Literal["queued", "processing", "done", "failed"]] = None,
    limit: int = Query(50, ge=1, le=200, description="Page size (1-200)"),
    offset: int = Query(0, ge=0, description="Number of items to skip")
    ):


    # this part has replaced by Query parameters with validation ^
    #                                                            
    #if limit < 1 or limit > 200:
        #raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    #if offset < 0:
        #raise HTTPException(status_code=400, detail="offset must be >= 0")

    with get_conn() as conn:
        if status is None:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
            
    return [row_to_job(r) for r in rows]


@router.get("/stats")
def job_stats():
    with get_conn() as conn:
        rows = conn.execute("SELECT status FROM jobs").fetchall()

    counts = Counter(r["status"] for r in rows)
    total = len(rows)
    return {
        "total": total,
        "queued": counts.get("queued", 0),
        "processing": counts.get("processing", 0),
        "done": counts.get("done", 0),
        "failed": counts.get("failed", 0),
    }


@router.get("/count")
def jobs_count(status: Optional[Literal["queued", "processing", "done", "failed"]] = None):
    with get_conn() as conn:
        if status is None:
            row = conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS c FROM jobs WHERE status = ?", (status,)).fetchone()
    return {"count": row["c"]}


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return row_to_job(row)


@router.patch("/{job_id}/status", response_model=Job)
def update_job_status(job_id: str, update: JobUpdateStatus):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")

        # 建议的保护规则（可选）：processing 时不允许随便改
        # if row["status"] == "processing" and update.status != "processing":
        #     raise HTTPException(status_code=409, detail="Cannot change status of a processing job")

        conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            (update.status, now_utc_iso(), job_id),
        )
        new_row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    return row_to_job(new_row)


@router.post("/{job_id}/run", response_model=Job)
def run_job(job_id: str):
    """
    同步执行（演示用）：processing -> sleep(1) -> done
    注意：如果你已经有后台 worker，生产中一般不保留这个接口。
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")

        if row["status"] == "processing":
            raise HTTPException(status_code=400, detail="Job is already processing")
        if row["status"] == "done":
            raise HTTPException(status_code=400, detail="Job is already done")

        conn.execute(
            "UPDATE jobs SET status='processing', updated_at=? WHERE id=?",
            (now_utc_iso(), job_id),
        )

    time.sleep(1)

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status='done', result=?, error=NULL, updated_at=?
            WHERE id=?
            """,
            (f"Job finished with payload: {row['payload']}", now_utc_iso(), job_id),
        )
        new_row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    return row_to_job(new_row)


@router.delete("/{job_id}", response_model=Job)
def delete_job(job_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")

        # 推荐保护规则：processing 不能删
        if row["status"] == "processing":
            raise HTTPException(status_code=409, detail="Cannot delete a processing job")

        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    return row_to_job(row)


@router.post("/{job_id}/requeue", response_model=Job)
def requeue_job(job_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")

        if row["status"] == "processing":
            raise HTTPException(status_code=409, detail="Cannot requeue a processing job")

        conn.execute(
            """
            UPDATE jobs
            SET status='queued',
                result=NULL,
                error=NULL,
                updated_at=?
            WHERE id=?
            """,
            (now_utc_iso(), job_id),
        )
        new_row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    job_queue.put(job_id)
    return row_to_job(new_row)


