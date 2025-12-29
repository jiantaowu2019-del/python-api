# api/worker.py
from threading import Thread, Event
from time import sleep
from datetime import datetime, timezone

from api.db import get_conn

stop_event = Event()

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _claim_one_job():
    """
    抢占一个 queued job（原子）：
    1) 选最早 created 的 queued
    2) UPDATE ... WHERE status='queued' 确保只抢一次
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM jobs WHERE status='queued' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if row is None:
            return None

        job_id = row["id"]
        updated = now_utc_iso()

        cur = conn.execute(
            """
            UPDATE jobs
            SET status='processing',
                attempts = attempts + 1,
                updated_at = ?
            WHERE id = ? AND status='queued'
            """,
            (updated, job_id),
        )

        if cur.rowcount == 0:
            return None  # 被别的 worker 抢走了

        return conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

def _execute_job_logic(payload: str):
    # 演示失败：payload 含 fail -> 抛异常
    if "fail" in payload.lower():
        sleep(2) 
        raise RuntimeError("Simulated failure (payload contains 'fail')")
    

def worker_loop(poll_interval: float = 0.5):
    while not stop_event.is_set():
        job = _claim_one_job()
        if job is None:
            sleep(poll_interval)
            continue

        job_id = job["id"]
        payload = job["payload"]
        attempts = job["attempts"]
        max_retries = job["max_retries"]

        try:
            _execute_job_logic(payload)
        except Exception as e:
            with get_conn() as conn:
                # 这里的语义：max_retries = 允许重试次数
                # 总尝试上限 = 1 + max_retries
                # attempts 是已经做过的尝试次数（claim 时 +1）
                if attempts < 1 + max_retries:
                    next_status = "queued"
                else:
                    next_status = "failed"

                conn.execute(
                    """
                    UPDATE jobs
                    SET status=?,
                        error=?,
                        updated_at=?
                    WHERE id=?
                    """,
                    (next_status, str(e), now_utc_iso(), job_id),
                )
        else:
            with get_conn() as conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status='done',
                        result=?,
                        error=NULL,
                        updated_at=?
                    WHERE id=?
                    """,
                    (f"Job finished with payload: {payload}", now_utc_iso(), job_id),
                )

def start_worker():
    t = Thread(target=worker_loop, daemon=True)
    t.start()

