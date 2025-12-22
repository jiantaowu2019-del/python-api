from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from enum import Enum
from uuid import uuid4
from datetime import datetime, timezone
from api.router.jobs import router as jobs_router




app = FastAPI(title="Job Queue API")


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class CreateJobRequest(BaseModel):
    # 先做一个最简单的任务：sleep_ms，表示“模拟耗时任务”
    type: str = Field(default="sleep_ms", examples=["sleep_ms"])
    sleep_ms: int = Field(
        default=100,
        ge=0,
        le=60_000,
        description="milliseconds to sleep",
    )


class CreateJobResponse(BaseModel):
    id: str
    status: JobStatus
    created_at: str


class JobInfo(BaseModel):
    id: str
    status: JobStatus
    type: str
    payload: dict
    result: dict | None = None
    error: str | None = None
    created_at: str
    updated_at: str


# ---- In-memory storage ----
JOBS: dict[str, JobInfo] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def root():
    return {"message": "go to /docs"}
app.include_router(jobs_router, prefix="/api", tags=["jobs"])


@app.post("/jobs", response_model=CreateJobResponse)
def create_job(req: CreateJobRequest):
    job_id = str(uuid4())
    ts = now_iso()

    job = JobInfo(
        id=job_id,
        status=JobStatus.queued,
        type=req.type,
        payload=req.model_dump(),
        result=None,
        error=None,
        created_at=ts,
        updated_at=ts,
    )

    JOBS[job_id] = job
    return CreateJobResponse(
        id=job_id,
        status=job.status,
        created_at=job.created_at,
    )


@app.get("/jobs/{job_id}", response_model=JobInfo)
def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/jobs", response_model=list[JobInfo])
def list_jobs(limit: int = 20):
    items = sorted(JOBS.values(), key=lambda j: j.created_at, reverse=True)
    # 限制一下最大数量，避免一次性返回太多
    return items[: max(1, min(limit, 200))]














