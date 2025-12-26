#api/jobs.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal, List, Optional
from datetime import datetime
from uuid import uuid4
import time
from collections import Counter  

# add a global locker
from threading import Lock
jobs_lock = Lock()


# 给这个 router 设定统一前缀 /jobs
router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)

# 创建任务时用户需要提供的字段
class JobCreate(BaseModel):
    payload: str  # 比如要干什么事情：发邮件、生成报表之类

# 返回给客户端的任务结构
class Job(BaseModel):
    id: str
    payload: str
    status: Literal["queued", "processing", "done", "failed"]
    created_at: datetime
    updated_at: datetime
    result: Optional[str] = None
    error: Optional[str] = None

# 用一个简单的 list 模拟数据库
jobs_db: List[Job] = []

@router.post("", response_model=Job)
def create_job(job_in: JobCreate):
    now = datetime.utcnow()
    job = Job(
        id=str(uuid4()),
        payload=job_in.payload,
        status="queued",
        created_at=now,
        updated_at=now,
    )
    
    with jobs_lock:
        jobs_db.append(job)
    return job



@router.get("", response_model=List[Job])
def list_jobs(status: Optional[Literal["queued", "processing", "done", "failed"]] = None):
    """
    列出所有 Job，或者按状态过滤：
    - /api/jobs                 -> 返回全部
    - /api/jobs?status=queued  -> 只返回排队中的
    """
    with jobs_lock:
        if status is None: 
            # 返回一个浅拷贝，避免迭代时被别的线程 append/pop
            return list(jobs_db)
        return [job for job in jobs_db if job.status == status]
# ...（上面是 list_jobs）

@router.get("/stats")
def job_stats():
    """
    返回 Job 的整体统计信息：
    - total: 总数
    - queued / processing / done / failed: 各状态数量
    """
    with jobs_lock:
        counts = Counter(job.status for job in jobs_db)
        return {
            "total": len(jobs_db),
            "queued": counts.get("queued", 0),
            "processing": counts.get("processing", 0),
            "done": counts.get("done", 0),
            "failed": counts.get("failed", 0),
        }



@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str):
    with jobs_lock:
        for job in jobs_db:
            if job.id == job_id:
                return job
    raise HTTPException(status_code=404, detail="Job not found")


class JobUpdateStatus(BaseModel):
    status: Literal["queued", "processing", "done", "failed"]

@router.patch("/{job_id}/status", response_model=Job)
def update_job_status(job_id: str, update: JobUpdateStatus):
    with jobs_lock:
        for job in jobs_db:
            if job.id == job_id:
                job.status = update.status
                job.updated_at = datetime.utcnow()
                return job
    raise HTTPException(status_code=404, detail="Job not found")


# ⭐ “执行任务”的接口（同步假装干点活）
@router.post("/{job_id}/run", response_model=Job)
def run_job(job_id: str):
    """
    简单模拟执行一个 Job：
    - 把状态改成 processing
    - 假装工作 1 秒
    - 把状态改成 done，并写入 result
    """
    with jobs_lock:
        for job in jobs_db:
            if job.id == job_id:
                target = job
                break

        if target is None:
            raise HTTPException(status_code=404, detail="Job not found")
            
        if target.status == "processing":
            raise HTTPException(status_code=400, detail="Job is already processing")
        if target.status == "done":
             raise HTTPException(status_code=400, detail="Job is already done")

        # 标记为处理中
        target.status = "processing"
        target.updated_at = datetime.utcnow()

        # 假装做了一些工作，耗费时间
        time.sleep(1)

         # 完成
        target.status = "done"
        target.result = f"Job finished with payload: {target.payload}"
        target.updated_at = datetime.utcnow()
        return target
    raise HTTPException(status_code=404, detail="Job not found")









# ... 现在已有的代码保持不动 ...

@router.delete("/{job_id}", response_model=Job)
def delete_job(job_id: str):
    """
    删除一个 Job，并把被删除的 Job 返回给客户端。
    """
    with jobs_lock:
        for idx, job in enumerate(jobs_db):
            if job.id == job_id:
                # 从 "数据库" 列表中移除
                deleted = jobs_db.pop(idx)
                return deleted
    raise HTTPException(status_code=404, detail="Job not found")




