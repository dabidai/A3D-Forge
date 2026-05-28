"""
数据导出 API：缺陷数据集导出 + 修复脚本库导出。

模块功能:
  - 导出全量缺陷样本（JSON / CSV），用于阶段二模型训练
  - 导出标准化修复脚本合集（Python文件下载）
  - 查询修复脚本库内容

阶段一核心价值:
  将自动检测+LLM分析的缺陷数据沉淀为结构化数据集，
  将积累的Blender修复脚本归档为可复用的脚本资产。
"""
import json
import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.asset import AssetDefect
from app.services.scripts.blender_scripts import REPAIR_SCRIPT_TEMPLATES

router = APIRouter()


@router.get("/defects-dataset")
async def export_defects_dataset(
    format: str = Query("json", description="导出格式: json 或 csv"),
    db: AsyncSession = Depends(get_db),
):
    """
    导出全量缺陷样本数据集。

    包含字段: id, asset_id, defect_type, level, description, auto_repairable, repaired, has_tutorial, created_at

    参数:
        format: "json" 返回JSON响应 / "csv" 返回CSV文件下载

    返回:
        JSON: { total, exported_at, defects: [...] }
        CSV: 附件 StreamingResponse
    """
    result = await db.execute(
        select(AssetDefect).order_by(AssetDefect.created_at.desc())
    )
    defects = result.scalars().all()

    records = [
        {
            "id": str(d.id),
            "asset_id": str(d.asset_id),
            "defect_type": d.defect_type,
            "level": d.level.value,
            "description": d.description,
            "auto_repairable": d.auto_repairable,
            "repaired": d.repaired,
            "has_tutorial": bool(d.repair_tutorial),
            "created_at": d.created_at.isoformat(),
        }
        for d in defects
    ]

    if format == "csv":
        output = io.StringIO()
        if records:
            writer = csv.DictWriter(output, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)
        else:
            output.write("No defect records found.\n")
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=defects_dataset.csv"},
        )

    return {
        "total": len(records),
        "exported_at": __import__("datetime").datetime.utcnow().isoformat(),
        "defects": records,
    }


@router.get("/repair-scripts")
async def export_repair_scripts():
    """
    查询标准化修复脚本库内容（JSON格式）。

    返回:
        { total_scripts, scripts: [{name, script}] }
        包含5个基础修复脚本: fill_small_holes, fix_normals, merge_by_distance, decimate, export_glb
    """
    return {
        "total_scripts": len(REPAIR_SCRIPT_TEMPLATES),
        "exported_at": __import__("datetime").datetime.utcnow().isoformat(),
        "scripts": [
            {
                "name": name,
                "script": script.strip(),
            }
            for name, script in REPAIR_SCRIPT_TEMPLATES.items()
        ],
    }


@router.get("/repair-scripts/download")
async def download_repair_scripts_bundle():
    """
    下载修复脚本合集（单个Python文件）。

    将所有模板脚本合并为一个 .py 文件供下载，
    可直接导入Blender Python环境执行。

    返回:
        StreamingResponse: attachment; filename=repair_scripts.py
    """
    output = io.StringIO()
    output.write('"""\nA3D-Forge 标准化修复脚本库\n"""\n\n')
    for name, script in REPAIR_SCRIPT_TEMPLATES.items():
        output.write(f"# === {name} ===\n")
        output.write(script.strip())
        output.write("\n\n")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/x-python",
        headers={"Content-Disposition": "attachment; filename=repair_scripts.py"},
    )
