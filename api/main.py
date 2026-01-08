# api/main.py
from fastapi import FastAPI
from api.router.jobs import router as jobs_router
from api.worker import start_worker
from api.db import init_db



app = FastAPI(title="Job Queue API")


@app.on_event("startup")
def on_startup():
    #starts worker thread
    # ensure the table exists and the schema  is up to date
    init_db()

    #starts a background thread 
    # the thread will fetch tasks from the job queue 
    # Update job status (queued->running->done/failed)
    # !( does not depend on the HTTP request)
    start_worker()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def root():
    return {"message": "go to /docs"}


# 把 /api/jobs 这一整组路由挂上去
app.include_router(jobs_router, prefix="/api")
