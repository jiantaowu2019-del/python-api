# api/worker.py
from threading import Thread, Event
from time import sleep
from datetime import datetime

from api.router.jobs import jobs_db, Job, jobs_lock  # 复用现有的 Job 模型 & jobs_db 列表

stop_event = Event()


def _run_one_job(job: Job):
    """
    真正“执行一个任务”的逻辑。
    目前只是 sleep 一下，然后把 result 写进去。
    以后可以在这里扩展成：
    - 发邮件
    - 调用第三方 API
    - 生成报表等
    """
    # 标记为 processing
    job.status = "processing"
    # 如果Job 模型里没有 updated_at，就先去 Job 里加上这个字段
    job.updated_at = datetime.utcnow()

    # 模拟干一件需要时间的事
    sleep(10)

    # 标记为 done
    with jobs_lock:
        job.status = "done"
        job.result = f"Job finished with payload: {job.payload}"
        job.updated_at = datetime.utcnow()


def worker_loop(poll_interval: float = 0.5):
    """
    后台 worker 主循环：
    - 不停扫描 jobs_db
    - 找到第一个 queued 的任务就执行
    """
    while not stop_event.is_set():
        # 找一个排队中的任务
        job_to_run = None


        with jobs_lock:
            for job in jobs_db:
                if job.status == "queued":
                   job.status = "processing"     #immediately mark as processing     
                   job.updated_at = datetime.utcnow()
                   job_to_run = job
                   break

        if job_to_run:
            _run_one_job(job_to_run)
        else:
            # 如果暂时没有排队任务，就睡一会儿再看
            sleep(poll_interval)




def start_worker():
    """
    在后台启动一个守护线程来跑 worker_loop。
    """
    t = Thread(target=worker_loop, daemon=True)
    t.start()
