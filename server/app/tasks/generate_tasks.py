"""
3D生成异步任务：文生3D / 图生3D。
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
from app.services.postprocess.engine import post_process_engine
from app.services.postprocess.defect_detector import defect_detector


async def _update_asset_status(asset_id: uuid.UUID, status: AssetStatus, **kwargs):
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
    """文生3D：调用Tripo3D API → 下载模型 → 后处理 → 缺陷检测"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    asset_uid = uuid.UUID(asset_id)
    task_uid = uuid.UUID(task_id)

    try:
        loop.run_until_complete(_update_task_status(task_uid, TaskStatus.RUNNING))
        loop.run_until_complete(_update_asset_status(asset_uid, AssetStatus.GENERATING))

        # 1. 调用Tripo3D生成
        output_dir = settings.ASSETS_DIR / asset_id
        result = tripo3d_client.text_to_3d(
            prompt=prompt,
            negative_prompt=negative_prompt,
            style=style,
            output_dir=output_dir,
        )

        # 2. 加载并分析模型
        model_path = result.get("local_path") or output_dir / f"{result['task_id']}.glb"
        mesh = post_process_engine.load_model(str(model_path))
        stats = post_process_engine.get_mesh_stats(mesh)

        # 3. 自动轻修复
        repaired_mesh, repair_report = post_process_engine.auto_light_repair(mesh)

        # 4. 缺陷检测
        defects = defect_detector.detect_all(repaired_mesh)
        severity = defect_detector.classify_severity(defects)

        # 5. 导出多格式
        formats = post_process_engine.export_formats(repaired_mesh, output_dir, asset_id)

        # 6. 生成预览图
        preview_path = output_dir / f"{asset_id}_preview.png"
        post_process_engine.generate_preview_image(repaired_mesh, str(preview_path))

        # 7. 更新资产记录
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

        loop.run_until_complete(_update_task_status(
            task_uid, TaskStatus.SUCCESS,
            progress=1.0,
            output_result={"stats": stats, "defect_count": len(defects), "severity": severity},
        ))

        return {"status": "success", "asset_id": asset_id, "defect_count": len(defects)}

    except SoftTimeLimitExceeded:
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
        raise self.retry(exc=exc)
    finally:
        loop.close()


@shared_task(bind=True, name="image_to_3d", max_retries=3, default_retry_delay=30)
def image_to_3d_task(self, asset_id: str, task_id: str, image_path: str):
    """图生3D：调用Tripo3D API → 下载模型 → 后处理"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    asset_uid = uuid.UUID(asset_id)
    task_uid = uuid.UUID(task_id)

    try:
        loop.run_until_complete(_update_task_status(task_uid, TaskStatus.RUNNING))
        loop.run_until_complete(_update_asset_status(asset_uid, AssetStatus.GENERATING))

        output_dir = settings.ASSETS_DIR / asset_id
        result = tripo3d_client.image_to_3d(image_path=image_path, output_dir=output_dir)

        mesh = post_process_engine.load_model(result["model_path"])
        stats = post_process_engine.get_mesh_stats(mesh)

        repaired_mesh, repair_report = post_process_engine.auto_light_repair(mesh)
        defects = defect_detector.detect_all(repaired_mesh)
        severity = defect_detector.classify_severity(defects)

        formats = post_process_engine.export_formats(repaired_mesh, output_dir, asset_id)

        preview_path = output_dir / f"{asset_id}_preview.png"
        post_process_engine.generate_preview_image(repaired_mesh, str(preview_path))

        loop.run_until_complete(_update_asset_status(
            asset_uid, AssetStatus.PROCESSED,
            original_model_path=result["model_path"],
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

        loop.run_until_complete(_update_task_status(
            task_uid, TaskStatus.SUCCESS,
            progress=1.0,
            output_result={"stats": stats, "defect_count": len(defects), "severity": severity},
        ))

        return {"status": "success", "asset_id": asset_id, "defect_count": len(defects)}

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
