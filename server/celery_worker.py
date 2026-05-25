"""
Celery Worker 入口：处理3D生成、模型修复、LLM分析等异步任务。
启动: celery -A celery_worker worker --loglevel=info --concurrency=2
"""
from app.core.celery_app import celery_app
from app.tasks.generate_tasks import text_to_3d_task, image_to_3d_task
from app.tasks.repair_tasks import repair_model_task, analyze_defects_task

# 注册所有任务（通过装饰器自动注册，此导入确保任务被发现）
__all__ = [
    "text_to_3d_task",
    "image_to_3d_task",
    "repair_model_task",
    "analyze_defects_task",
]
