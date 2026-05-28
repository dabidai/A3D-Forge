"""
任务管理 API：查询列表、获取详情、重试失败任务。

模块功能:
  - 按状态/类型查询Celery异步任务列表
  - 获取单个任务详细信息（进度、输入参数、输出结果）
  - 重试失败的任务（仅支持生成类任务：text_to_3d / image_to_3d）

任务状态流转:
  PENDING → RUNNING → SUCCESS / FAILED → (重试) → PENDING
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.task import Task, TaskStatus
from app.schemas.task import TaskResponse, TaskListResponse

router = APIRouter()


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    status: str | None = None,
    task_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    查询任务列表，支持按状态和类型过滤。

    参数:
        status: 过滤状态 (pending/running/success/failed/retrying)
        task_type: 过滤类型 (text_to_3d/image_to_3d/model_repair/llm_analysis)
        limit: 返回条数上限 (1-200, 默认50)

    返回:
        TaskListResponse: items(任务列表), total(总数)
    """
    query = select(Task)
    if status:
        query = query.where(Task.status == status)
    if task_type:
        query = query.where(Task.task_type == task_type)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Task.created_at.desc()).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()

    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    获取单个任务详情。

    参数:
        task_id: 任务UUID

    返回:
        TaskResponse: 包含类型、状态、进度(0.0~1.0)、输入参数、输出结果、错误信息
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "任务不存在")
    return TaskResponse.model_validate(task)


@router.post("/{task_id}/retry")
async def retry_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    重试失败的任务。

    仅支持 text_to_3d / image_to_3d 类型任务的重试，
    将状态重置为PENDING，保留重试计数，重新推送Celery任务。

    参数:
        task_id: 任务UUID

    返回:
        { "message": "任务已重新入队", "task_id": str }
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.status not in (TaskStatus.FAILED,):
        raise HTTPException(400, "只能重试失败的任务")

    # 重置状态
    task.status = TaskStatus.PENDING
    task.retry_count += 1
    task.error_message = None
    await db.commit()

    # 根据原任务类型重新推送Celery任务
    from app.tasks.generate_tasks import text_to_3d_task, image_to_3d_task
    if task.task_type.value == "text_to_3d" and task.input_params:
        text_to_3d_task.apply_async(
            kwargs={
                "asset_id": str(task.asset_id),
                "task_id": str(task.id),
                "prompt": task.input_params.get("prompt", ""),
                "negative_prompt": task.input_params.get("negative_prompt", ""),
                "style": task.input_params.get("style", "realistic"),
            },
            task_id=str(task.id),
        )
    elif task.task_type.value == "image_to_3d" and task.input_params:
        image_to_3d_task.apply_async(
            kwargs={
                "asset_id": str(task.asset_id),
                "task_id": str(task.id),
                "image_path": task.input_params.get("image_path", ""),
            },
            task_id=str(task.id),
        )

    return {"message": "任务已重新入队", "task_id": str(task.id)}
