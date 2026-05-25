"""
模型修复与缺陷分析异步任务。
"""
import uuid
import asyncio
from pathlib import Path
from celery import shared_task
from loguru import logger

from app.core.config import settings
from app.models.asset import Asset, AssetStatus, AssetDefect, DefectLevel
from app.models.task import TaskStatus
from app.services.postprocess.engine import post_process_engine
from app.services.postprocess.defect_detector import defect_detector
from app.services.scheduler.router import RoleRouter, LLMRole
from app.services.scheduler.prompt_mgr import PromptManager
from app.services.scheduler.ollama_client import ollama_client
from app.services.scheduler.validator import OutputValidator
from app.services.scheduler.cache_mgr import cache_manager
from app.tasks.generate_tasks import _update_asset_status, _update_task_status


@shared_task(bind=True, name="repair_model", max_retries=2, default_retry_delay=60)
def repair_model_task(self, asset_id: str, task_id: str):
    """对已有模型执行修复流程"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    asset_uid = uuid.UUID(asset_id)
    task_uid = uuid.UUID(task_id)

    try:
        loop.run_until_complete(_update_task_status(task_uid, TaskStatus.RUNNING))
        loop.run_until_complete(_update_asset_status(asset_uid, AssetStatus.PROCESSING))

        # 加载模型
        from app.core.database import async_session
        from sqlalchemy import select

        async with async_session() as session:
            result = await session.execute(select(Asset).where(Asset.id == asset_uid))
            asset = result.scalar_one_or_none()

        model_path = asset.original_model_path or asset.glb_path
        if not model_path:
            raise ValueError("No model file found for repair")

        mesh = post_process_engine.load_model(model_path)

        # 缺陷检测
        defects = defect_detector.detect_all(mesh)
        severity = defect_detector.classify_severity(defects)

        # 自动轻修复
        repaired_mesh, repair_report = post_process_engine.auto_light_repair(mesh)

        # 导出
        output_dir = settings.ASSETS_DIR / asset_id
        formats = post_process_engine.export_formats(repaired_mesh, output_dir, asset_id)

        # 保存缺陷数据到数据库
        async with async_session() as session:
            for d in defects:
                defect_record = AssetDefect(
                    asset_id=asset_uid,
                    defect_type=d["type"],
                    level=DefectLevel(d["level"]),
                    description=d["description"],
                    auto_repairable=d.get("repairable", False),
                )
                session.add(defect_record)
            await session.commit()

        # 更新资产
        loop.run_until_complete(_update_asset_status(
            asset_uid, AssetStatus.PROCESSED,
            processed_model_path=formats.get("glb"),
            glb_path=formats.get("glb"),
            fbx_path=formats.get("fbx"),
            obj_path=formats.get("obj"),
            tags={"repair_report": repair_report, "defects": defects, "severity": severity},
        ))

        auto_repaired = sum(1 for d in defects if d.get("repairable") and d["level"] == "mild")
        needs_manual = len(defects) - auto_repaired

        loop.run_until_complete(_update_task_status(
            task_uid, TaskStatus.SUCCESS,
            progress=1.0,
            output_result={
                "defects_found": len(defects),
                "auto_repaired": auto_repaired,
                "needs_manual": needs_manual,
                "severity": severity,
                "repair_report": repair_report,
            },
        ))

        return {"status": "success", "asset_id": asset_id, "repaired": auto_repaired}

    except Exception as exc:
        logger.error(f"Repair task failed: {exc}")
        loop.run_until_complete(_update_asset_status(asset_uid, AssetStatus.FAILED,
                                                      error_message=str(exc)))
        loop.run_until_complete(_update_task_status(task_uid, TaskStatus.FAILED,
                                                      error_message=str(exc)))
        raise
    finally:
        loop.close()


@shared_task(bind=True, name="analyze_defects", max_retries=2, default_retry_delay=30)
def analyze_defects_task(self, asset_id: str, task_id: str):
    """使用LLM分析缺陷并生成修复建议"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    asset_uid = uuid.UUID(asset_id)
    task_uid = uuid.UUID(task_id)

    try:
        loop.run_until_complete(_update_task_status(task_uid, TaskStatus.RUNNING))

        # 获取资产信息
        from app.core.database import async_session
        from sqlalchemy import select

        async with async_session() as session:
            result = await session.execute(select(Asset).where(Asset.id == asset_uid))
            asset = result.scalar_one_or_none()

            result2 = await session.execute(
                select(AssetDefect).where(AssetDefect.asset_id == asset_uid)
            )
            defect_records = result2.scalars().all()

        if not asset:
            raise ValueError(f"Asset not found: {asset_id}")

        # 构建缺陷摘要
        defects_summary = [
            {"type": d.defect_type, "level": d.level.value, "description": d.description}
            for d in defect_records
        ]

        # 检查缓存
        cache_key = f"defect_analysis:{asset_id}"
        cached = cache_manager.get_similar(
            json.dumps(defects_summary), prefix="llm_defect"
        )
        if cached:
            loop.run_until_complete(_update_task_status(
                task_uid, TaskStatus.SUCCESS,
                progress=1.0,
                output_result=cached,
            ))
            loop.close()
            return {"status": "success", "cached": True, "result": cached}

        # LLM分析
        role, confidence = RoleRouter.route("defect_analysis")
        system_prompt = RoleRouter.get_system_prompt(role)
        system_msg, user_msg = PromptManager.build_prompt(
            role, system_prompt,
            {
                "model_path": asset.processed_model_path or asset.glb_path or "",
                "face_count": str(asset.face_count or 0),
                "anomalies": json.dumps(defects_summary, ensure_ascii=False),
            },
        )

        llm_result = ollama_client.chat(system_msg, user_msg, expect_json=True)

        # 校验输出
        is_valid, errors = OutputValidator.validate(role.value, llm_result)
        if not is_valid:
            logger.warning(f"LLM output validation warnings: {errors}")

        # 缓存结果
        cache_manager.set(json.dumps(defects_summary), llm_result, prefix="llm_defect")

        # 更新缺陷记录：补充修复方案
        if "defects" in llm_result:
            async with async_session() as session:
                for i, d_info in enumerate(llm_result["defects"]):
                    if i < len(defect_records):
                        defect_records[i].repair_tutorial = d_info.get("tutorial")
                        defect_records[i].repair_script_path = d_info.get("blender_script")
                await session.commit()

        loop.run_until_complete(_update_task_status(
            task_uid, TaskStatus.SUCCESS,
            progress=1.0,
            output_result=llm_result,
        ))

        return {"status": "success", "asset_id": asset_id, "result": llm_result}

    except Exception as exc:
        logger.error(f"Defect analysis failed: {exc}")
        loop.run_until_complete(_update_task_status(task_uid, TaskStatus.FAILED,
                                                      error_message=str(exc)))
        raise
    finally:
        loop.close()


import json
