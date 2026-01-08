# Job Queue API

一个用 **FastAPI** 写的简易 Job Queue 服务，用来演示：

- 如何设计 RESTful API
- 如何用 `APIRouter` 管理子路由
- 如何用后台线程模拟「任务异步执行」
- 如何在没有数据库的情况下，用内存结构先把系统跑起来

## 技术栈

- Python 3.12
- FastAPI
- Uvicorn
- Pydantic
- 标准库：`threading`, `time`, `uuid`, `datetime`

## 项目结构（简化版）

```text
job-queue/
  ├─ api/
  │   ├─ __init__.py
  │   ├─ jobs.py        # /api/jobs* 的路由 + in-memory "数据库"
  │   └─ worker.py      # 后台 worker 线程，轮询 jobs_db 执行任务
  ├─ api/
  │   └─ router/        # （如果有的话，用于更清晰拆分路由）
  ├─ main.py            # FastAPI 入口，挂载 router，启动 worker
  └─ README.md

说明：
目前项目里同时有：

顶层的 /jobs 系列接口（main.py 里的 JOBS 字典）

/api/jobs 系列接口（api/jobs.py 里的 jobs_db 列表 + worker）
实际的「队列 + worker」功能主要是通过 /api/jobs 这套实现的。

快速启动

创建并激活虚拟环境（已完成可以跳过）

python -m venv .venv
# Windows PowerShell:
.venv\Scripts\activate


安装依赖

pip install fastapi uvicorn


启动服务

uvicorn api.main:app --reload


打开浏览器访问：

健康检查: http://127.0.0.1:8000/health

API 文档（Swagger UI）：http://127.0.0.1:8000/docs

主要 API 设计（/api/jobs 系列）

这一组接口是配合后台 worker 一起工作的，是整个 Job Queue 的核心。

1. 创建 Job

Endpoint: POST /api/jobs

Body 示例：

{
  "payload": "send welcome email to user-123"
}


返回示例：

{
  "id": "92659416-f594-4141-bb7c-14f8bd7c2d73",
  "payload": "send welcome email to user-123",
  "status": "queued",
  "created_at": "2025-12-24T04:04:11.876273",
  "updated_at": "2025-12-24T04:04:11.876273",
  "result": null,
  "error": null
}

2. 查询 Job 列表

Endpoint: GET /api/jobs

说明：返回当前内存中的所有 Job。

3. 查询单个 Job

Endpoint: GET /api/jobs/{job_id}

4. 手动修改 Job 状态（调试用）

Endpoint: PATCH /api/jobs/{job_id}/status

Body 示例：

{
  "status": "processing"
}

5. 手动执行 Job（同步版）

Endpoint: POST /api/jobs/{job_id}/run

说明：模拟执行一次 Job，内部会：

把状态改为 processing

sleep(1) 假装在干活

把状态改为 done，并写入 result

6. 删除 Job

Endpoint: DELETE /api/jobs/{job_id}

说明：从内存“数据库”中删除一个 Job，并返回被删除的 Job。

后台 Worker 架构

项目里有一个后台线程，会在应用启动时自动拉起来：

main.py 中：

@app.on_event("startup")
def on_startup():
    start_worker()


api/worker.py 中：

worker_loop：死循环扫 jobs_db

找到第一个 status == "queued" 的 Job，就调用 _run_one_job

_run_one_job 会：

把 Job 状态改为 processing

sleep(1)

把 Job 状态改为 done，写入 result 和 updated_at

简易架构图
          HTTP 请求（/api/jobs*）
                 |
                 v
           FastAPI (main.py)
                 |
         include_router(jobs_router, prefix="/api")
                 |
                 v
          Jobs Router (api/jobs.py)
                 |
         in-memory jobs_db: List[Job]
                 |
          -----------------------------
          |                           |
     前台接口（创建/查询/删除）      后台 worker 线程
                                      |
                               定期扫描 jobs_db，
                             执行 queued -> done

学到了什么 / 可以写在简历上的点

设计并实现了一个简易 Job Queue API，支持创建、查询、删除任务

使用 FastAPI + APIRouter 拆分路由模块

使用后台线程实现了类似“队列 worker”的异步执行模型

熟悉了 Swagger UI（FastAPI /docs）的用法和接口自描述能力

未来可以扩展的方向

把内存存储换成真正的数据库（例如 PostgreSQL）

Job 类型支持多种任务（发送邮件、调用第三方 API 等）

加入重试机制、失败队列

接入 Redis / 消息队列（Celery / RQ 等）


---
