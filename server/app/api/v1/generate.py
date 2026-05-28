"""
3D生成 API：文生3D / 图生3D / 批量生成。

模块功能：
  - 接收用户文本/图片输入，创建资产记录，推送Celery异步生成任务
  - 集成本地Qwen3 LLM进行提示词优化（PROMPT_OPTIMIZER角色）和内容安全审核（CONTENT_AUDITOR角色）
  - 支持批量文生3D请求，循环创建单个任务
  - 提供生成状态查询接口，供前端轮询展示进度

依赖：
  - Celery任务: text_to_3d_task / image_to_3d_task
  - LLM调度: RoleRouter (角色路由) + PromptManager (提示词构建) + OllamaClient (推理)
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
from app.schemas.generate import (
    TextTo3DRequest, TextTo3DResponse, ImageTo3DResponse, GenerationStatusResponse,
    BatchTextTo3DRequest, BatchTextTo3DResponse,
)
from app.tasks.generate_tasks import text_to_3d_task, image_to_3d_task

router = APIRouter()


@router.post("/text-to-3d", response_model=TextTo3DResponse)
async def create_text_to_3d(req: TextTo3DRequest, db: AsyncSession = Depends(get_db)):
    """
    提交文生3D异步任务。

    流程:
      1. (可选) Qwen3优化用户提示词 → 生成更结构化的正/负向提示词
      2. (可选) Qwen3内容安全审核 → 检测违规/敏感内容
      3. 创建Asset资产记录 + Task任务记录
      4. 推送Celery异步任务执行实际的3D生成

    参数:
        req: TextTo3DRequest
            - prompt: 自然语言3D描述 (1-2000字符)
            - negative_prompt: 负向提示词
            - style: 风格 (realistic/cartoon/low_poly/sculpture)
            - skip_optimization: 跳过LLM提示词优化
            - skip_audit: 跳过内容安全审核

    返回:
        TextTo3DResponse: task_id, asset_id, status, 原始/优化后提示词, 审核结果
    """
    # 1. 创建资产记录（Asset）和任务记录（Task），直接推送Celery异步任务
    #    LLM优化和审核由Celery Worker在后台执行，避免阻塞API响应
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
        input_params={
            "prompt": req.prompt,
            "negative_prompt": req.negative_prompt,
            "style": req.style,
            "complexity": req.complexity,
            "skip_optimization": req.skip_optimization,
            "skip_audit": req.skip_audit,
        },
    )
    db.add(task)
    await db.commit()
    await db.refresh(asset)
    await db.refresh(task)

    # 推送Celery异步任务，task_id与数据库记录一致，便于追踪
    celery_result = text_to_3d_task.apply_async(
        kwargs={
            "asset_id": str(asset.id),
            "task_id": str(task.id),
            "prompt": req.prompt,
            "negative_prompt": req.negative_prompt,
            "style": req.style,
            "skip_optimization": req.skip_optimization,
            "skip_audit": req.skip_audit,
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
        original_prompt=req.prompt,
    )


@router.post("/image-to-3d", response_model=ImageTo3DResponse)
async def create_image_to_3d(
    file: UploadFile = File(...),
    style: str = Form(default="realistic"),
    db: AsyncSession = Depends(get_db),
):
    """
    提交图生3D异步任务。

    流程:
      1. 校验上传文件类型（仅允许 image/*）
      2. 保存图片至本地 {DATA_DIR}/assets/uploads/
      3. (可选) Qwen3内容安全审核
      4. 创建Asset + Task记录，推送Celery任务

    参数:
        file: 上传的图片文件（JPG/PNG）
        style: 目标风格，默认 realistic

    返回:
        ImageTo3DResponse: task_id, asset_id, status, 审核结果
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "只支持图片文件")

    # 保存上传图片到本地
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
        input_params={
            "style": str(style),
            "image_path": str(saved_path),
            "original_filename": file.filename,
        },
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


@router.post("/batch-text-to-3d", response_model=BatchTextTo3DResponse)
async def create_batch_text_to_3d(req: BatchTextTo3DRequest, db: AsyncSession = Depends(get_db)):
    """
    批量提交文生3D任务。

    对 prompts 列表中的每一项依次调用 create_text_to_3d，
    每个prompt创建独立的Asset和Task，共享同一style和negative_prompt。

    参数:
        req: BatchTextTo3DRequest
            - prompts: 提示词列表（1-20条）
            - negative_prompt: 负向提示词（所有任务共用）
            - style: 风格（所有任务共用）
            - skip_optimization: 是否跳过LLM优化
    """
    tasks_responses = []
    for prompt in req.prompts:
        single_req = TextTo3DRequest(
            prompt=prompt,
            negative_prompt=req.negative_prompt,
            style=req.style,
            skip_optimization=req.skip_optimization,
        )
        resp = await create_text_to_3d(single_req, db)
        tasks_responses.append(resp)

    batch_id = str(uuid.uuid4())
    return BatchTextTo3DResponse(
        batch_id=batch_id,
        total=len(tasks_responses),
        tasks=tasks_responses,
    )


@router.get("/status/{asset_id}", response_model=GenerationStatusResponse)
async def get_generation_status(asset_id: str, db: AsyncSession = Depends(get_db)):
    """
    查询指定资产的生成任务状态。

    前端使用此接口轮询（每3秒），直到status变为 processed/failed。

    参数:
        asset_id: 资产UUID字符串

    返回:
        GenerationStatusResponse: 包含当前状态、进度(0.0~1.0)、模型URL、预览图URL、面数、错误信息
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "资产不存在")

    # 获取最近的任务进度
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
