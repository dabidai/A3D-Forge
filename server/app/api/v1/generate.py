"""
3D生成 API：文生3D / 图生3D。
"""
import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import settings
from app.models.asset import Asset, AssetStatus, AssetType
from app.models.task import Task, TaskType, TaskStatus
from app.schemas.generate import TextTo3DRequest, TextTo3DResponse, ImageTo3DResponse, GenerationStatusResponse
from app.tasks.generate_tasks import text_to_3d_task, image_to_3d_task

router = APIRouter()


@router.post("/text-to-3d", response_model=TextTo3DResponse)
async def create_text_to_3d(req: TextTo3DRequest, db: AsyncSession = Depends(get_db)):
    """提交文生3D任务"""
    asset = Asset(
        id=uuid.uuid4(),
        name=req.prompt[:50],
        asset_type=AssetType.TEXT_TO_3D,
        status=AssetStatus.GENERATING,
        source_prompt=req.prompt,
    )
    db.add(asset)

    task = Task(
        id=uuid.uuid4(),
        asset_id=asset.id,
        task_type=TaskType.TEXT_TO_3D,
        status=TaskStatus.PENDING,
        input_params=req.model_dump(),
    )
    db.add(task)
    await db.commit()
    await db.refresh(asset)
    await db.refresh(task)

    # 推送Celery任务
    celery_result = text_to_3d_task.apply_async(
        kwargs={
            "asset_id": str(asset.id),
            "task_id": str(task.id),
            "prompt": req.prompt,
            "negative_prompt": req.negative_prompt,
            "style": req.style,
        },
        task_id=str(task.id),
    )
    task.celery_task_id = celery_result.id
    await db.commit()

    return TextTo3DResponse(
        task_id=str(task.id),
        asset_id=str(asset.id),
        status="pending",
        message="3D生成任务已提交",
    )


@router.post("/image-to-3d", response_model=ImageTo3DResponse)
async def create_image_to_3d(
    file: UploadFile = File(...),
    style: str = Form(default="realistic"),
    db: AsyncSession = Depends(get_db),
):
    """提交图生3D任务"""
    # 校验文件
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "只支持图片文件")

    # 保存上传图片
    upload_dir = settings.ASSETS_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_ext = Path(file.filename).suffix or ".png"
    saved_path = upload_dir / f"{uuid.uuid4()}{file_ext}"
    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    asset = Asset(
        id=uuid.uuid4(),
        name=file.filename or "image_to_3d",
        asset_type=AssetType.IMAGE_TO_3D,
        status=AssetStatus.GENERATING,
        source_image_path=str(saved_path),
    )
    db.add(asset)

    task = Task(
        id=uuid.uuid4(),
        asset_id=asset.id,
        task_type=TaskType.IMAGE_TO_3D,
        status=TaskStatus.PENDING,
        input_params={"style": str(style), "image_path": str(saved_path)},
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    celery_result = image_to_3d_task.apply_async(
        kwargs={
            "asset_id": str(asset.id),
            "task_id": str(task.id),
            "image_path": str(saved_path),
        },
        task_id=str(task.id),
    )
    task.celery_task_id = celery_result.id
    await db.commit()

    return ImageTo3DResponse(
        task_id=str(task.id),
        asset_id=str(asset.id),
        status="pending",
        message="图生3D任务已提交",
    )


@router.get("/status/{asset_id}", response_model=GenerationStatusResponse)
async def get_generation_status(asset_id: str, db: AsyncSession = Depends(get_db)):
    """查询生成任务状态"""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "资产不存在")

    # 获取关联任务进度
    task_result = await db.execute(
        select(Task).where(Task.asset_id == asset.id).order_by(Task.created_at.desc()).limit(1)
    )
    task = task_result.scalar_one_or_none()
    progress = task.progress if task else 0.0

    return GenerationStatusResponse(
        asset_id=str(asset.id),
        status=asset.status.value,
        progress=progress,
        model_url=f"/static/assets/{asset_id}/{asset_id}.glb" if asset.glb_path else None,
        preview_url=f"/static/assets/{asset_id}/{asset_id}_preview.png" if asset.preview_image_path else None,
        face_count=asset.face_count,
        error_message=asset.error_message,
    )
