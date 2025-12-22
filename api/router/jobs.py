# api/jobs.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal, List
from datetime import datetime
from uuid import uuid4

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


# 用一个简单的 list 模拟数据库
jobs_db: List[Job] = []


@router.post("", response_model=Job)
def create_job(job_in: JobCreate):
    job = Job(
        id=str(uuid4()),
        payload=job_in.payload,
        status="queued",
        created_at=datetime.utcnow(),
    )
    jobs_db.append(job)
    return job


@router.get("", response_model=List[Job])
def list_jobs():
    return jobs_db


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
            return job
    raise HTTPException(status_code=404, detail="Job not found")










