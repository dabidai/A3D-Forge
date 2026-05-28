"""
Celery Worker 启动入口。

功能:
  加载 Celery 应用实例，自动发现并注册所有异步任务。

已注册任务:
  - text_to_3d_task:     文本 → 3D模型（Tripo3D）
  - image_to_3d_task:    图片 → 3D模型（Meshy优先，Tripo3D兜底）
  - repair_model_task:   模型自动修复（缺陷检测 + 轻修复 + 导出）
  - analyze_defects_task: LLM深度分析缺陷（Qwen3 → 修复教程 + Blender脚本）

启动命令:
  celery -A celery_worker worker --loglevel=info --concurrency=2

  --concurrency=2: 限制2个并发worker，因为Ollama CPU推理耗资源，并发过高会OOM
"""
from app.core.celery_app import celery_app
from app.tasks.generate_tasks import text_to_3d_task, image_to_3d_task
from app.tasks.repair_tasks import repair_model_task, analyze_defects_task

# 显式导出任务列表（装饰器 @shared_task 已自动注册到 celery_app，此处导入确保Python解释器加载）
__all__ = [
    "text_to_3d_task",
    "image_to_3d_task",
    "repair_model_task",
    "analyze_defects_task",
]
