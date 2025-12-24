#api/jobs.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal, List, Optional
from datetime import datetime
from uuid import uuid4
import time

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
    jobs_db.append(job)
    return job



@router.get("", response_model=List[Job])
def list_jobs(status: Optional[Literal["queued", "processing", "done", "failed"]] = None):
    """
    列出所有 Job，或者按状态过滤：
    - /api/jobs                 -> 返回全部
    - /api/jobs?status=queued  -> 只返回排队中的
    """
    if status is None:
        return jobs_db
    return [job for job in jobs_db if job.status == status]

from collections import Counter  # 如果顶部还没有这行，就加上

# ...（上面是 list_jobs）

@router.get("/stats")
def job_stats():
    """
    返回 Job 的整体统计信息：
    - total: 总数
    - queued / processing / done / failed: 各状态数量
    """
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
    for job in jobs_db:
        if job.id == job_id:
            return job
    raise HTTPException(status_code=404, detail="Job not found")

class JobUpdateStatus(BaseModel):
    status: Literal["queued", "processing", "done", "failed"]

@router.patch("/{job_id}/status", response_model=Job)
def update_job_status(job_id: str, update: JobUpdateStatus):
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
    for job in jobs_db:
        if job.id == job_id:
            if job.status == "processing":
                raise HTTPException(status_code=400, detail="Job is already processing")
            if job.status == "done":
                raise HTTPException(status_code=400, detail="Job is already done")

            # 标记为处理中
            job.status = "processing"
            job.updated_at = datetime.utcnow()

            # 假装做了一些工作
            time.sleep(1)

            # 完成
            job.status = "done"
            job.result = f"Job finished with payload: {job.payload}"
            job.updated_at = datetime.utcnow()
            return job

    raise HTTPException(status_code=404, detail="Job not found")









# ... 现在已有的代码保持不动 ...

@router.delete("/{job_id}", response_model=Job)
def delete_job(job_id: str):
    """
    删除一个 Job，并把被删除的 Job 返回给客户端。
    """
    for idx, job in enumerate(jobs_db):
        if job.id == job_id:
            # 从 "数据库" 列表中移除
            deleted = jobs_db.pop(idx)
            return deleted
    raise HTTPException(status_code=404, detail="Job not found")




