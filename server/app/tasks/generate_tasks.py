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

from app.core.config import settings
from app.core.database import async_session
from app.models.asset import Asset, AssetStatus, AssetType
from app.models.task import Task as TaskModel, TaskType, TaskStatus
from app.services.generator.tripo3d import tripo3d_client
from app.services.generator.meshy import meshy_client
from app.services.postprocess.engine import post_process_engine
from app.services.postprocess.defect_detector import defect_detector


async def _update_asset_status(asset_id: uuid.UUID, status: AssetStatus, **kwargs):
    """
    异步更新资产表状态。

    参数:
        asset_id: 资产UUID
        status:   新状态枚举值
        **kwargs: 要更新的字段名和值（如 glb_path=..., face_count=...）
    """
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(Asset).where(Asset.id == asset_id))
        asset = result.scalar_one_or_none()
        if asset:
            asset.status = status
            for key, value in kwargs.items():
                setattr(asset, key, value)
            await session.commit()


async def _update_task_status(task_id: uuid.UUID, status: TaskStatus, **kwargs):
    """
    异步更新任务表状态。

    参数:
        task_id: 任务UUID
        status:  新状态枚举值
        **kwargs: 要更新的字段（如 progress=1.0, output_result=...）
    """
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            task.status = status
            for key, value in kwargs.items():
                setattr(task, key, value)
            await session.commit()


@shared_task(bind=True, name="text_to_3d", max_retries=3, default_retry_delay=30)
def text_to_3d_task(self, asset_id: str, task_id: str, prompt: str,
                    negative_prompt: str = "", style: str = "realistic"):
    """
    文生3D异步任务。

    参数:
        asset_id:        资产UUID字符串
        task_id:         任务UUID字符串
        prompt:          优化后的正负向提示词
        negative_prompt: 负向提示词
        style:           风格 (realistic/cartoon/low_poly/sculpture)

    返回:
        { status: "success", asset_id: str, defect_count: int }
    """
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    asset_uid = uuid.UUID(asset_id)
    task_uid = uuid.UUID(task_id)

    try:
        # 1. 更新状态为执行中
        loop.run_until_complete(_update_task_status(task_uid, TaskStatus.RUNNING))
        loop.run_until_complete(_update_asset_status(asset_uid, AssetStatus.GENERATING))

        # 2. 调用Tripo3D生成 + 轮询 + 下载
        output_dir = settings.ASSETS_DIR / asset_id
        result = tripo3d_client.text_to_3d(
            prompt=prompt,
            negative_prompt=negative_prompt,
            style=style,
            output_dir=output_dir,
        )

        # 3. 加载并分析模型
        model_path = result.get("local_path") or output_dir / f"{result['task_id']}.glb"
        mesh = post_process_engine.load_model(str(model_path))
        stats = post_process_engine.get_mesh_stats(mesh)

        # 4. 自动轻修复（5步管线）
        repaired_mesh, repair_report = post_process_engine.auto_light_repair(mesh)

        # 5. 缺陷检测 + 定级
        defects = defect_detector.detect_all(repaired_mesh)
        severity = defect_detector.classify_severity(defects)

        # 6. 多格式导出
        formats = post_process_engine.export_formats(repaired_mesh, output_dir, asset_id)

        # 7. 预览图生成
        preview_path = output_dir / f"{asset_id}_preview.png"
        post_process_engine.generate_preview_image(repaired_mesh, str(preview_path))

        # 8. 更新资产记录（路径 + 统计 + 缺陷数据）
        loop.run_until_complete(_update_asset_status(
            asset_uid, AssetStatus.PROCESSED,
            original_model_path=str(model_path),
            processed_model_path=formats.get("glb"),
            glb_path=formats.get("glb"),
            fbx_path=formats.get("fbx"),
            obj_path=formats.get("obj"),
            preview_image_path=str(preview_path),
            face_count=stats["face_count"],
            vertex_count=stats["vertex_count"],
            api_provider="tripo3d",
            api_task_id=result["task_id"],
            tags={
                "repair_report": repair_report,
                "defects": defects,
                "severity": severity,
            },
        ))

        # 9. 更新任务记录为成功
        loop.run_until_complete(_update_task_status(
            task_uid, TaskStatus.SUCCESS,
            progress=1.0,
            output_result={"stats": stats, "defect_count": len(defects), "severity": severity},
        ))

        return {"status": "success", "asset_id": asset_id, "defect_count": len(defects)}

    except SoftTimeLimitExceeded:
        # 软超时：有时间做清理 → 标记FAILED
        loop.run_until_complete(_update_asset_status(asset_uid, AssetStatus.FAILED,
                                                      error_message="Task timed out"))
        loop.run_until_complete(_update_task_status(task_uid, TaskStatus.FAILED,
                                                      error_message="Task timed out"))
        raise
    except Exception as exc:
        logger.error(f"Text to 3D failed: {exc}")
        loop.run_until_complete(_update_asset_status(asset_uid, AssetStatus.FAILED,
                                                      error_message=str(exc)))
        loop.run_until_complete(_update_task_status(task_uid, TaskStatus.FAILED,
                                                      error_message=str(exc)))
        # Celery自动重试（最多3次，间隔30s）
        raise self.retry(exc=exc)
    finally:
        loop.close()


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
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    asset_uid = uuid.UUID(asset_id)
    task_uid = uuid.UUID(task_id)

    try:
        loop.run_until_complete(_update_task_status(task_uid, TaskStatus.RUNNING))
        loop.run_until_complete(_update_asset_status(asset_uid, AssetStatus.GENERATING))

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

        loop.run_until_complete(_update_asset_status(
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
        ))

        loop.run_until_complete(_update_task_status(
            task_uid, TaskStatus.SUCCESS,
            progress=1.0,
            output_result={
                "stats": stats,
                "defect_count": len(defects),
                "severity": severity,
                "provider": provider,
            },
        ))

        return {"status": "success", "asset_id": asset_id, "defect_count": len(defects), "provider": provider}

    except SoftTimeLimitExceeded:
        loop.run_until_complete(_update_asset_status(asset_uid, AssetStatus.FAILED,
                                                      error_message="Task timed out"))
        loop.run_until_complete(_update_task_status(task_uid, TaskStatus.FAILED,
                                                      error_message="Task timed out"))
        raise
    except Exception as exc:
        logger.error(f"Image to 3D failed: {exc}")
        loop.run_until_complete(_update_asset_status(asset_uid, AssetStatus.FAILED,
                                                      error_message=str(exc)))
        loop.run_until_complete(_update_task_status(task_uid, TaskStatus.FAILED,
                                                      error_message=str(exc)))
        raise self.retry(exc=exc)
    finally:
        loop.close()
