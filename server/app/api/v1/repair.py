"""
模型修复 API：自动修复 + 缺陷检测 + LLM 分析。
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.asset import Asset, AssetDefect
from app.models.task import Task, TaskType, TaskStatus
from app.schemas.repair import RepairRequest, RepairResponse, DefectAnalysisResponse, DefectInfo
from app.tasks.repair_tasks import repair_model_task, analyze_defects_task

router = APIRouter()


@router.post("/auto-repair", response_model=RepairResponse)
async def auto_repair(req: RepairRequest, db: AsyncSession = Depends(get_db)):
    """自动检测缺陷并执行轻修复"""
    result = await db.execute(select(Asset).where(Asset.id == req.asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "资产不存在")

    task = Task(
        id=uuid.uuid4(),
        asset_id=asset.id,
        task_type=TaskType.MODEL_REPAIR,
        status=TaskStatus.PENDING,
        input_params={"action": "auto_repair"},
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    repair_model_task.apply_async(
        kwargs={"asset_id": str(asset.id), "task_id": str(task.id)},
        task_id=str(task.id),
    )

    return RepairResponse(
        asset_id=str(asset.id),
        task_id=str(task.id),
        status="pending",
        defects_found=0,
        auto_repaired=0,
        needs_manual=0,
        report={},
    )


@router.post("/analyze-defects", response_model=DefectAnalysisResponse)
async def analyze_defects(req: RepairRequest, db: AsyncSession = Depends(get_db)):
    """使用LLM深度分析缺陷并生成修复方案"""
    result = await db.execute(select(Asset).where(Asset.id == req.asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "资产不存在")

    task = Task(
        id=uuid.uuid4(),
        asset_id=asset.id,
        task_type=TaskType.LLM_ANALYSIS,
        status=TaskStatus.PENDING,
        input_params={"action": "analyze_defects"},
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    analyze_defects_task.apply_async(
        kwargs={"asset_id": str(asset.id), "task_id": str(task.id)},
        task_id=str(task.id),
    )

    return DefectAnalysisResponse(
        asset_id=str(asset.id),
        overall_severity="pending",
        defects=[],
    )


@router.get("/defects/{asset_id}")
async def get_defects(asset_id: str, db: AsyncSession = Depends(get_db)):
    """查询资产的缺陷列表"""
    result = await db.execute(
        select(AssetDefect).where(AssetDefect.asset_id == asset_id)
    )
    defects = result.scalars().all()
    return {
        "asset_id": asset_id,
        "total": len(defects),
        "defects": [
            {
                "id": str(d.id),
                "type": d.defect_type,
                "level": d.level.value,
                "description": d.description,
                "repairable": d.auto_repairable,
                "repaired": d.repaired,
                "tutorial": d.repair_tutorial,
            }
            for d in defects
        ],
    }
