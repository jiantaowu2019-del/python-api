# api/worker.py
from threading import Thread, Event
from time import sleep
from datetime import datetime, timezone

from api.db import get_conn
from api.redis_client import dequeue_blocking, enqueue

stop_event = Event()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _claim_job_by_id(job_id: str):
    """
    原子 claim：
    - 只有当 status='queued' 才能抢占为 processing
    - attempts += 1
    """
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE jobs
            SET status='processing',
                attempts = attempts + 1,
                updated_at = ?
            WHERE id = ? AND status='queued'
            """,
            (now_utc_iso(), job_id),
        )
        if cur.rowcount == 0:
            return None
        return conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()



def _execute_job_logic(payload: str):
    # 演示失败：payload 含 fail -> 抛异常
    if "fail" in payload.lower():
        sleep(2) 
        raise RuntimeError("Simulated failure (payload contains 'fail')")
    

def worker_loop():
    while not stop_event.is_set():
        job_id = dequeue_blocking(timeout=1)
        if job_id is None:
            continue

        job = _claim_job_by_id(job_id)
        if job is None:
            # 可能是：已被处理/被删/状态不是 queued（重复入队等）
            continue

        payload = job["payload"]
        attempts = int(job["attempts"])
        max_retries = int(job["max_retries"])

        try:
            _execute_job_logic(payload)
        except Exception as e:
            # max_retries = 允许“重试次数”
            # 总尝试上限 = 1 + max_retries
            can_retry = attempts <= (1 + max_retries)
            next_status = "queued" if can_retry else "failed"

            with get_conn() as conn:
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

            # 还能重试：重新入 Redis 队列
            if can_retry:
                enqueue(job_id)
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

