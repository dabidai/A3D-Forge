"""
Celery 异步任务队列配置模块。

技术选型:
  - Broker: Redis（消息队列，job入队后持久化）
  - Backend: Redis（结果存储，任务完成后写入）
  - 序列化: JSON（跨语言兼容）

关键配置:
  - task_soft_time_limit: 软超时 → 触发 SoftTimeLimitExceeded 异常，任务可捕获执行清理
  - task_time_limit: 硬超时 → SIGKILL 直接杀进程，无清理机会
  - worker_prefetch_multiplier=1: 每次只预取1个任务，避免长耗时任务堆积
  - worker_max_tasks_per_child=50: 每进程处理50个任务后重启，防止内存泄漏

使用方式:
  from app.core.celery_app import celery_app
  @celery_app.task(name="my_task")
  def my_task(): ...
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "a3d_tasks",                        # 应用名
    broker=settings.CELERY_BROKER_URL,  # Redis消息队列地址（DB 1）
    backend=settings.CELERY_RESULT_BACKEND,  # Redis结果存储地址（DB 2）
)

celery_app.conf.update(
    # 序列化
    task_serializer="json",         # 任务参数序列化格式
    accept_content=["json"],        # 只接受JSON格式的任务
    result_serializer="json",       # 任务结果序列化格式

    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,

    # 任务追踪
    task_track_started=True,        # 记录任务开始时间（允许前端看到"Running"状态）

    # 超时控制
    task_soft_time_limit=settings.TASK_TIMEOUT_MINUTES * 60,        # 软超时：抛出异常，可捕获
    task_time_limit=settings.TASK_TIMEOUT_MINUTES * 60 + 60,       # 硬超时：直接杀进程

    # Worker 优化
    worker_prefetch_multiplier=1,           # 每次预取1个任务（避免长任务堆积）
    worker_max_tasks_per_child=50,          # 每子进程处理50个任务后重启（防内存泄漏）
)
