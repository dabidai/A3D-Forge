"""
统计仪表盘 API：为前端Dashboard提供核心运营指标。

模块功能:
  - 查询资产/任务/缺陷总量及分布
  - 计算生成成功率（近7天）
  - 计算自动修复成功率（近7天）
  - 统计Top缺陷类型及平均每模型缺陷数

数据源:
  - assets 表: 总资产数、状态分布
  - tasks 表: 总任务数、类型分布、成功率
  - asset_defects 表: 缺陷总数、类型分布
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.asset import Asset, AssetStatus, AssetDefect
from app.models.task import Task, TaskStatus

router = APIRouter()


@router.get("/overview")
async def get_overview_stats(db: AsyncSession = Depends(get_db)):
    """
    获取仪表盘概览统计数据。

    返回字段说明:
        total_assets:             资产总数
        total_tasks:              任务总数
        total_defects:            缺陷记录总数
        generation_success_rate:  近7天3D生成成功率(%) = 成功数 / 总提交数
        auto_repair_rate:         近7天自动修复成功率(%) = 修复成功数 / 总修复数
        avg_defects_per_model:    平均每个模型发现的缺陷数
        top_defect_types:         Top5缺陷类型及出现次数
        assets_by_status:         资产按状态分布 {generating: N, processed: N, ...}
        tasks_by_type:            任务按类型分布 {text_to_3d: N, image_to_3d: N, ...}
    """
    # 资产统计
    total_assets = (await db.execute(select(func.count(Asset.id)))).scalar() or 0

    # 资产状态分布
    status_counts = {}
    for s in AssetStatus:
        count = (await db.execute(
            select(func.count(Asset.id)).where(Asset.status == s.value)
        )).scalar() or 0
        status_counts[s.value] = count

    # 任务统计
    total_tasks = (await db.execute(select(func.count(Task.id)))).scalar() or 0

    # 任务类型分布
    task_type_counts = {}
    for t in ["text_to_3d", "image_to_3d", "model_repair", "llm_analysis"]:
        count = (await db.execute(
            select(func.count(Task.id)).where(Task.task_type == t)
        )).scalar() or 0
        task_type_counts[t] = count

    # 生成成功率（近7天）: text_to_3d + image_to_3d 中成功的比例
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    gen_success = (await db.execute(
        select(func.count(Task.id)).where(
            Task.task_type.in_(["text_to_3d", "image_to_3d"]),
            Task.status == TaskStatus.SUCCESS.value,
            Task.created_at >= seven_days_ago,
        )
    )).scalar() or 0
    gen_total = (await db.execute(
        select(func.count(Task.id)).where(
            Task.task_type.in_(["text_to_3d", "image_to_3d"]),
            Task.created_at >= seven_days_ago,
        )
    )).scalar() or 1  # 避免除零

    # 自动修复成功率（近7天）
    repair_success = (await db.execute(
        select(func.count(Task.id)).where(
            Task.task_type == "model_repair",
            Task.status == TaskStatus.SUCCESS.value,
            Task.created_at >= seven_days_ago,
        )
    )).scalar() or 0
    repair_total = (await db.execute(
        select(func.count(Task.id)).where(
            Task.task_type == "model_repair",
            Task.created_at >= seven_days_ago,
        )
    )).scalar() or 1

    # 缺陷统计
    total_defects = (await db.execute(select(func.count(AssetDefect.id)))).scalar() or 0

    # Top5缺陷类型（按出现次数降序）
    defect_types_result = await db.execute(
        select(AssetDefect.defect_type, func.count(AssetDefect.id).label("count"))
        .group_by(AssetDefect.defect_type)
        .order_by(func.count(AssetDefect.id).desc())
        .limit(5)
    )
    top_defect_types = [
        {"type": row[0], "count": row[1]}
        for row in defect_types_result.all()
    ]

    # 平均每模型缺陷数
    assets_with_defects = (await db.execute(
        select(func.count(func.distinct(AssetDefect.asset_id)))
    )).scalar() or 1

    return {
        "total_assets": total_assets,
        "total_tasks": total_tasks,
        "total_defects": total_defects,
        "generation_success_rate": round(gen_success / gen_total * 100, 1),
        "auto_repair_rate": round(repair_success / repair_total * 100, 1),
        "avg_defects_per_model": round(total_defects / max(assets_with_defects or total_assets, 1), 1),
        "top_defect_types": top_defect_types,
        "assets_by_status": status_counts,
        "tasks_by_type": task_type_counts,
    }
