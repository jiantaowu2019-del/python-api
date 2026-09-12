# api/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.router.jobs import router as jobs_router
from api.worker import start_worker
from api.db import init_db

# html,css,js
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent




@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application resources before accepting requests."""
    init_db()
    start_worker()
    yield


app = FastAPI(title="Job Queue API", lifespan=lifespan)



app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

@app.get("/dashboard")
def dashboard():
    return FileResponse(BASE_DIR / "static" / "dashboard.html")






@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def root():
    return {"message": "go to /docs"}


# 把 /api/jobs 这一整组路由挂上去
app.include_router(jobs_router, prefix="/api")
