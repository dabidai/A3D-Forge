"""
模型修复与缺陷分析 API。

模块功能：
  - 自动修复: 对已有3D模型执行缺陷检测 → 自动轻修复 → 多格式导出
  - LLM深度分析: 调用Qwen3 TECH_ANALYST角色分析缺陷并生成修复教程/Blender脚本
  - 缺陷查询: 获取指定资产的缺陷列表（含等级、可修复性、修复教程）

自动修复路径:
  轻微缺陷(孔洞/法线/孤立顶点) → Trimesh+PyMeshLab自动修复
  复杂缺陷(非流形/拓扑混乱) → 标注后流转LLM分析 → 生成人工修复方案

依赖:
  - Celery任务: repair_model_task / analyze_defects_task
  - 后处理引擎: PostProcessEngine (Trimesh)
  - 缺陷检测器: DefectDetector
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
    """
    对指定资产执行自动缺陷检测 + 轻修复。

    流程:
      1. 校验资产是否存在
      2. 创建MODEL_REPAIR类型的Task记录
      3. 推送Celery异步修复任务
      4. 立即返回（前端通过轮询tasks接口获取进度）

    参数:
        req: RepairRequest { asset_id: str } — 资产UUID

    返回:
        RepairResponse: task_id用于追踪，初始值均为0/空，实际结果由Celery任务完成后写入
    """
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
    """
    使用本地Qwen3 LLM（TECH_ANALYST角色）深度分析缺陷并生成修复方案。

    流程:
      1. 读取资产已有缺陷记录
      2. 检查语义缓存（避免重复分析相同缺陷组合）
      3. 调用Qwen3进行缺陷分类、定级、修复教程生成
      4. 校验LLM输出格式，缓存结果，更新缺陷记录的tutorial字段

    参数:
        req: RepairRequest { asset_id: str }

    返回:
        DefectAnalysisResponse: overall_severity + 缺陷详情列表
    """
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
    """
    查询指定资产的缺陷详情列表。

    参数:
        asset_id: 资产UUID

    返回:
        { asset_id, total, defects: [{id, type, level, description, repairable, repaired, tutorial}] }
        - type: 缺陷类型（non_manifold_edge / degenerate_face / inverted_normal / isolated_component 等）
        - level: 严重等级（mild 轻微 / moderate 中等 / severe 严重）
        - repairable: 是否可自动修复
        - tutorial: LLM生成的修复教程文本（仅analyze_defects后非空）
    """
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
