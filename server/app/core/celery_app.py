from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "a3d_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_soft_time_limit=settings.TASK_TIMEOUT_MINUTES * 60,
    task_time_limit=settings.TASK_TIMEOUT_MINUTES * 60 + 60,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)
