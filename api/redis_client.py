# api/redis_client.py
import os
import redis
from typing import Optional

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_KEY = os.getenv("JOB_QUEUE_KEY", "job_queue")

_r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def enqueue(job_id: str) -> None:
    _r.lpush(QUEUE_KEY, job_id)

def dequeue_blocking(timeout: int = 1) -> Optional[str]:
    """
    阻塞式取任务（BRPOP）：
    - timeout 秒超时返回 None（便于检查 stop_event）
    """
    res = _r.brpop(QUEUE_KEY, timeout=timeout)
    if res is None:
        return None
    _, job_id = res
    return job_id
