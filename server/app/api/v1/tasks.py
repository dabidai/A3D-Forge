"""
任务管理 API：查询、重试、撤销。
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
    """查询任务列表"""
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
    """获取任务详情"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "任务不存在")
    return TaskResponse.model_validate(task)


@router.post("/{task_id}/retry")
async def retry_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """重试失败的任务"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.status not in (TaskStatus.FAILED,):
        raise HTTPException(400, "只能重试失败的任务")

    task.status = TaskStatus.PENDING
    task.retry_count += 1
    task.error_message = None
    await db.commit()

    # 重新推送Celery任务（简化：仅支持生成类重试）
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
