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
import asyncio
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
from app.services.scheduler.router import RoleRouter
from app.services.scheduler.prompt_mgr import PromptManager
from app.services.scheduler.ollama_client import ollama_client

router = APIRouter()


async def _run_llm_in_thread(system_msg: str, user_msg: str, expect_json: bool = True) -> dict:
    """
    在线程池中运行同步Ollama推理，避免阻塞FastAPI事件循环。

    参数:
        system_msg: 系统提示词（定义LLM角色行为）
        user_msg: 用户消息（具体待处理内容）
        expect_json: 是否期望返回JSON格式，为True时temperature=0.1以保证输出稳定

    返回:
        dict: LLM输出的解析结果，出错时包含 "error" 键
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: ollama_client.chat(system_msg, user_msg, expect_json)
    )


async def _optimize_prompt(prompt: str, style: str, complexity: str) -> dict | None:
    """
    调用Qwen3 PROMPT_OPTIMIZER角色优化用户自然语言提示词。

    参数:
        prompt: 用户原始中文/英文描述
        style: 目标风格（realistic/cartoon/low_poly/sculpture）
        complexity: 目标复杂度（low/medium/high）

    返回:
        dict | None: 优化结果，包含 positive_prompt / negative_prompt / style / complexity 字段；
                     调用失败或Ollama不可用时返回None，不影响主流程
    """
    try:
        role, _ = RoleRouter.route("text_to_3d_prompt")
        system_prompt = RoleRouter.get_system_prompt(role)
        system_msg, user_msg = PromptManager.build_prompt(
            role, system_prompt,
            {"user_input": prompt, "style": style, "complexity": complexity},
        )
        result = await _run_llm_in_thread(system_msg, user_msg)
        if "error" in result:
            return None
        return result
    except Exception:
        return None


async def _audit_content(content: str, source: str) -> dict | None:
    """
    调用Qwen3 CONTENT_AUDITOR角色审核输入内容安全性。

    参数:
        content: 待审核的文本内容（用户输入或优化后的提示词）
        source: 内容来源标识（如 "text_to_3d_input"）

    返回:
        dict | None: 审核结果，包含 compliant(合规判定) / risk_level(风险等级) 等字段；
                     调用失败时返回None，不阻塞主流程
    """
    try:
        role, _ = RoleRouter.route("content_audit")
        system_prompt = RoleRouter.get_system_prompt(role)
        system_msg, user_msg = PromptManager.build_prompt(
            role, system_prompt,
            {"content": content, "source": source},
        )
        result = await _run_llm_in_thread(system_msg, user_msg)
        if "error" in result:
            return None
        return result
    except Exception:
        return None


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
    optimized_prompt = None
    optimized_negative = None
    audit_result = None

    # 1. Qwen3 提示词优化：将自然语言转为结构化3D生成参数
    if not req.skip_optimization:
        opt_result = await _optimize_prompt(req.prompt, req.style, req.complexity)
        if opt_result:
            optimized_prompt = opt_result.get("positive_prompt", req.prompt)
            optimized_negative = opt_result.get("negative_prompt", req.negative_prompt)

    final_prompt = optimized_prompt or req.prompt
    final_negative = optimized_negative or req.negative_prompt

    # 2. Qwen3 内容安全审核：检查输入是否符合合规要求
    if not req.skip_audit:
        audit_result = await _audit_content(final_prompt, "text_to_3d_input")

    # 3. 创建资产记录（Asset）和任务记录（Task），关联celery任务
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
            "prompt": final_prompt,
            "original_prompt": req.prompt,
            "negative_prompt": final_negative,
            "style": req.style,
            "complexity": req.complexity,
            "optimized": optimized_prompt is not None,
            "audit_passed": audit_result.get("compliant", True) if audit_result else True,
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
            "prompt": final_prompt,
            "negative_prompt": final_negative,
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
        original_prompt=req.prompt,
        optimized_prompt=optimized_prompt,
        optimized_negative_prompt=optimized_negative,
        audit_result=audit_result,
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

    # 内容安全审核 (基于文件名)
    audit_result = await _audit_content(file.filename or "image", "image_to_3d_input")

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
            "audit_passed": audit_result.get("compliant", True) if audit_result else True,
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
        audit_result=audit_result,
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
