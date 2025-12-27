# api/worker.py
from threading import Thread, Event
from time import sleep
from datetime import datetime
from queue import Empty

from api.queue_state import job_queue
from api.router.jobs import jobs_db, Job, jobs_lock  # ✅ import lock

stop_event = Event()


def _execute_job_logic(job: Job):
    """
    这里放“真正干活”的逻辑（锁外）。
    现在还是用 sleep 模拟。
    你可以用一个小开关方便演示失败：
    - payload 包含 "fail" -> 故意抛异常
    """
    if "fail" in job.payload.lower():
        raise RuntimeError("Simulated failure (payload contains 'fail')")

    sleep(10)  # 模拟耗时任务


def _finalize_success(job: Job):
    with jobs_lock:
        job.status = "done"
        job.result = f"Job finished with payload: {job.payload}"
        job.error = None
        job.updated_at = datetime.utcnow()


def _finalize_failure(job: Job, err: Exception):
    with jobs_lock:
        job.error = str(err)
        job.updated_at = datetime.utcnow()

        # attempts 已在 worker_loop 抢占时 +1，这里只负责决定下一状态
        if job.attempts <= job.max_retries:
            # 还可以重试：回到 queued
            job.status = "queued"
        else:
            # 超过最大重试：标记 failed
            job.status = "failed"


def worker_loop(poll_interval: float = 0.5):
    while not stop_event.is_set():
        try:
            # 阻塞等待新任务；加 timeout 是为了能响应 stop_event
            job_id = job_queue.get(timeout=0.5)
        except Empty:
            continue


        job_to_run = None

        # ✅ 原子抢占：queued -> processing，同时增加 attempts
        with jobs_lock:
            for job in jobs_db:
                if job.status != "queued":
                    job_to_run = None

                else:
                    job.status = "processing"
                    job.attempts += 1
                    job.updated_at = datetime.utcnow()
                    job_to_run = job
                    break

        if not job_to_run:
            sleep(poll_interval)
            continue

        # ✅ 锁外执行 + 错误处理
        try:
            _execute_job_logic(job_to_run)
        except Exception as e:

            # 以下可以封装成 _finalize_failure(job_to_run, e)   
            with jobs_lock:
                job_to_run.error = str(e)
                job_to_run.updated_at = datetime.utcnow()
                if job_to_run.attempts <= job_to_run.max_retries:    #约定：max_retries 表示失败后可额外重试次数（总尝试=1+max_retries）
                    job_to_run.status = "queued"
                    # ✅ 失败后要重试：重新 put 回队列
                    job_queue.put(job_to_run.id)
                else:
                    job_to_run.status = "failed"
        else:

            #以下可以封装成 _finalize_success(job_to_run)
            with jobs_lock:
                job_to_run.status = "done"
                job_to_run.result = f"Job finished with payload: {job_to_run.payload}"
                job_to_run.error = None
                job_to_run.updated_at = datetime.utcnow()
        finally:
            job_queue.task_done()


def start_worker():
    t = Thread(target=worker_loop, daemon=True)
    t.start()

