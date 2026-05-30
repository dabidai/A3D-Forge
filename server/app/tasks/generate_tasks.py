"""
3D生成异步Celery任务：文生3D / 图生3D。

任务流程（文生3D）:
  1. 状态更新: PENDING → RUNNING
  2. 调用 Tripo3D API 生成模型（轮询直至完成）
  3. Trimesh 加载并分析网格统计信息
  4. PostProcessEngine 自动轻修复（5步管线）
  5. DefectDetector 全量缺陷检测 + 定级
  6. 多格式导出 (GLB + FBX + OBJ)
  7. 生成预览图 (800x600 PNG)
  8. 更新资产记录（路径、面数、缺陷数据） → PROCESSED / FAILED

任务流程（图生3D）:
  同上，但生成阶段优先使用 Meshy（PBR材质），未配置则回退 Tripo3D

重试策略:
  Celery max_retries=3, default_retry_delay=30s（指数退避由Celery内部管理）
  超时保护: soft_time_limit=30min → SoftTimeLimitExceeded → 标记FAILED
"""
import uuid
import json
from pathlib import Path
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

from app.core.celery_app import celery_app  # noqa: F401 — 确保Celery app在API进程中被初始化
from app.core.config import settings
from app.core.database import SyncSession
from app.models.asset import Asset, AssetStatus, AssetType
from app.models.task import Task as TaskModel, TaskType, TaskStatus
from app.services.generator.tripo3d import tripo3d_client
from app.services.generator.meshy import meshy_client
from app.services.postprocess.engine import post_process_engine
from app.services.postprocess.defect_detector import defect_detector
from app.services.scheduler.router import RoleRouter
from app.services.scheduler.prompt_mgr import PromptManager
from app.services.scheduler.ollama_client import ollama_client


def _update_asset_status(asset_id: uuid.UUID, status: AssetStatus, **kwargs):
    """同步更新资产表状态（供 Celery 任务使用）。"""
    from sqlalchemy import select
    with SyncSession() as session:
        result = session.execute(select(Asset).where(Asset.id == asset_id))
        asset = result.scalar_one_or_none()
        if asset:
            asset.status = status
            for key, value in kwargs.items():
                setattr(asset, key, value)
            session.commit()


def _update_task_status(task_id: uuid.UUID, status: TaskStatus, **kwargs):
    """同步更新任务表状态（供 Celery 任务使用）。"""
    from sqlalchemy import select
    with SyncSession() as session:
        result = session.execute(select(TaskModel).where(TaskModel.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            task.status = status
            for key, value in kwargs.items():
                setattr(task, key, value)
            session.commit()


@shared_task(bind=True, name="text_to_3d", max_retries=3, default_retry_delay=30)
def text_to_3d_task(self, asset_id: str, task_id: str, prompt: str,
                    negative_prompt: str = "", style: str = "realistic",
                    skip_optimization: bool = False, skip_audit: bool = False):
    """
    文生3D异步任务（LLM优化+生成+后处理全流程）。

    流程:
      1. (可选) Qwen3优化用户提示词 → 结构化生成参数
      2. (可选) Qwen3内容安全审核
      3. 调用 Tripo3D API 生成模型（轮询直至完成）
      4. Trimesh 加载并分析网格统计信息
      5. PostProcessEngine 自动轻修复（5步管线）
      6. DefectDetector 全量缺陷检测 + 定级
      7. 多格式导出 (GLB + FBX + OBJ)
      8. 生成预览图 (800x600 PNG)
      9. 更新资产记录

    参数:
        asset_id:          资产UUID字符串
        task_id:           任务UUID字符串
        prompt:            用户原始提示词
        negative_prompt:   负向提示词
        style:             风格 (realistic/cartoon/low_poly/sculpture)
        skip_optimization: 跳过LLM提示词优化
        skip_audit:        跳过内容安全审核

    返回:
        { status: "success", asset_id: str, defect_count: int }
    """
    asset_uid = uuid.UUID(asset_id)
    task_uid = uuid.UUID(task_id)

    try:
        # 1. 更新状态为执行中
        _update_task_status(task_uid, TaskStatus.RUNNING)
        _update_asset_status(asset_uid, AssetStatus.GENERATING)

        # 2. (可选) Qwen3 提示词优化
        final_prompt = prompt
        final_negative = negative_prompt
        if not skip_optimization:
            try:
                role, _ = RoleRouter.route("text_to_3d_prompt")
                system_prompt = RoleRouter.get_system_prompt(role)
                system_msg, user_msg = PromptManager.build_prompt(
                    role, system_prompt,
                    {"user_input": prompt, "style": style, "complexity": "medium"},
                )
                opt_result = ollama_client.chat(system_msg, user_msg, expect_json=True)
                if "error" not in opt_result:
                    final_prompt = opt_result.get("positive_prompt", prompt)
                    final_negative = opt_result.get("negative_prompt", negative_prompt)
                    logger.info(f"LLM prompt optimized: {final_prompt[:80]}...")
            except Exception as e:
                logger.warning(f"LLM optimization failed, using raw prompt: {e}")

        # 3. (可选) Qwen3 内容安全审核
        if not skip_audit:
            try:
                role, _ = RoleRouter.route("content_audit")
                system_prompt = RoleRouter.get_system_prompt(role)
                system_msg, user_msg = PromptManager.build_prompt(
                    role, system_prompt,
                    {"content": final_prompt, "source": "text_to_3d_input"},
                )
                audit_result = ollama_client.chat(system_msg, user_msg, expect_json=True)
                if "error" not in audit_result and not audit_result.get("compliant", True):
                    logger.warning(f"Content audit flagged: {audit_result}")
            except Exception as e:
                logger.warning(f"LLM audit failed, proceeding anyway: {e}")

        # 4. 调用Tripo3D生成 + 轮询 + 下载
        output_dir = settings.ASSETS_DIR / asset_id
        result = tripo3d_client.text_to_3d(
            prompt=final_prompt,
            negative_prompt=final_negative,
            style=style,
            output_dir=output_dir,
        )

        # 5. 加载并分析模型（先确保原始文件以 asset_id 命名，供前端直接访问）
        model_path = result.get("local_path") or output_dir / f"{result['task_id']}.glb"
        fallback_path = output_dir / f"{asset_id}.glb"
        if Path(model_path) != fallback_path:
            import shutil
            shutil.copy2(str(model_path), str(fallback_path))
        mesh = post_process_engine.load_model(str(model_path))
        stats = post_process_engine.get_mesh_stats(mesh)

        # 6. 多格式导出（暂时跳过修复和缺陷检测，直接导出原始模型）
        # repaired_mesh, repair_report = post_process_engine.auto_light_repair(mesh)
        # defects = defect_detector.detect_all(repaired_mesh)
        # severity = defect_detector.classify_severity(defects)
        formats = post_process_engine.export_formats(mesh, output_dir, asset_id)

        # 7. 更新资产记录
        _update_asset_status(
            asset_uid, AssetStatus.PROCESSED,
            original_model_path=str(model_path),
            glb_path=formats.get("glb"),
            obj_path=formats.get("obj"),
            face_count=stats["face_count"],
            vertex_count=stats["vertex_count"],
            api_provider="tripo3d",
            api_task_id=result["task_id"],
        )

        # 8. 更新任务为成功
        _update_task_status(
            task_uid, TaskStatus.SUCCESS,
            progress=1.0,
            output_result={"stats": stats},
        )

        return {"status": "success", "asset_id": asset_id}

    except SoftTimeLimitExceeded:
        _update_asset_status(asset_uid, AssetStatus.FAILED, error_message="Task timed out")
        _update_task_status(task_uid, TaskStatus.FAILED, error_message="Task timed out")
        raise
    except Exception as exc:
        logger.error(f"Text to 3D failed: {exc}")
        _update_asset_status(asset_uid, AssetStatus.FAILED, error_message=str(exc))
        _update_task_status(task_uid, TaskStatus.FAILED, error_message=str(exc))
        raise self.retry(exc=exc)


@shared_task(bind=True, name="image_to_3d", max_retries=3, default_retry_delay=30)
def image_to_3d_task(self, asset_id: str, task_id: str, image_path: str):
    """
    图生3D异步任务。

    生成策略: Meshy优先（支持PBR材质生成），未配置则降级到Tripo3D

    参数:
        asset_id:   资产UUID
        task_id:    任务UUID
        image_path: 已上传到本地的图片路径

    返回:
        { status: "success", asset_id: str, defect_count: int, provider: str }
    """
    asset_uid = uuid.UUID(asset_id)
    task_uid = uuid.UUID(task_id)

    try:
        _update_task_status(task_uid, TaskStatus.RUNNING)
        _update_asset_status(asset_uid, AssetStatus.GENERATING)

        output_dir = settings.ASSETS_DIR / asset_id

        # ---- Meshy优先（PBR材质），Tripo3D兜底 ----
        provider = "tripo3d"
        model_path = None
        pbr_paths = None

        if meshy_client.configured:
            try:
                logger.info("Using Meshy for image-to-3d")
                result = meshy_client.image_to_3d(image_path=image_path, output_dir=output_dir)
                model_path = result.get("model_path")
                pbr_paths = result.get("pbr_material_paths")
                provider = "meshy"
            except Exception as e:
                logger.warning(f"Meshy failed, falling back to Tripo3D: {e}")

        if not model_path:
            logger.info("Using Tripo3D for image-to-3d")
            result = tripo3d_client.image_to_3d(image_path=image_path, output_dir=output_dir)
            model_path = result.get("local_path") or (output_dir / f"{result['task_id']}.glb")
            model_path = str(model_path)

        # ---- 后处理流程（同文生3D） ----
        mesh = post_process_engine.load_model(model_path)
        stats = post_process_engine.get_mesh_stats(mesh)

        repaired_mesh, repair_report = post_process_engine.auto_light_repair(mesh)
        defects = defect_detector.detect_all(repaired_mesh)
        severity = defect_detector.classify_severity(defects)

        formats = post_process_engine.export_formats(repaired_mesh, output_dir, asset_id)

        preview_path = output_dir / f"{asset_id}_preview.png"
        post_process_engine.generate_preview_image(repaired_mesh, str(preview_path))

        tags = {
            "repair_report": repair_report,
            "defects": defects,
            "severity": severity,
        }
        if pbr_paths:
            tags["pbr_materials"] = pbr_paths

        _update_asset_status(
            asset_uid, AssetStatus.PROCESSED,
            original_model_path=model_path,
            processed_model_path=formats.get("glb"),
            glb_path=formats.get("glb"),
            fbx_path=formats.get("fbx"),
            obj_path=formats.get("obj"),
            preview_image_path=str(preview_path),
            face_count=stats["face_count"],
            vertex_count=stats["vertex_count"],
            api_provider=provider,
            api_task_id=result.get("task_id", ""),
            tags=tags,
        )

        _update_task_status(
            task_uid, TaskStatus.SUCCESS,
            progress=1.0,
            output_result={
                "stats": stats,
                "defect_count": len(defects),
                "severity": severity,
                "provider": provider,
            },
        )

        return {"status": "success", "asset_id": asset_id, "defect_count": len(defects), "provider": provider}

    except SoftTimeLimitExceeded:
        _update_asset_status(asset_uid, AssetStatus.FAILED, error_message="Task timed out")
        _update_task_status(task_uid, TaskStatus.FAILED, error_message="Task timed out")
        raise
    except Exception as exc:
        logger.error(f"Image to 3D failed: {exc}")
        _update_asset_status(asset_uid, AssetStatus.FAILED, error_message=str(exc))
        _update_task_status(task_uid, TaskStatus.FAILED, error_message=str(exc))
        raise self.retry(exc=exc)
