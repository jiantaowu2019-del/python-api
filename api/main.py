# api/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from enum import Enum
from uuid import uuid4
from datetime import datetime, timezone
from api.router.jobs import router as jobs_router
from uuid import uuid4
from api.worker import start_worker



app = FastAPI(title="Job Queue API")


@app.on_event("startup")
def on_startup():
    # 启动后台 worker 线程
    start_worker()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def root():
    return {"message": "go to /docs"}


# 把 /api/jobs 这一整组路由挂上去
app.include_router(jobs_router, prefix="/api")
