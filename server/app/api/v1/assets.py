"""
资产管理 API：CRUD + 分页列表 + 多格式下载。

模块功能:
  - 分页查询资产列表，支持按状态/类型筛选
  - 单个资产详情查询
  - 资产删除（含关联本地文件清理）
  - 多格式模型文件下载（GLB/FBX/OBJ）
"""
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.config import settings
from app.models.asset import Asset, AssetStatus
from app.schemas.asset import AssetResponse, AssetListResponse

router = APIRouter()


@router.get("/", response_model=AssetListResponse)
async def list_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    asset_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    分页查询资产列表，支持按状态和类型过滤。

    参数:
        page: 页码，从1开始
        page_size: 每页条数 (1-100)
        status: 按状态过滤 (generating/generated/processing/processed/failed)
        asset_type: 按类型过滤 (text_to_3d/image_to_3d)

    返回:
        AssetListResponse: items(资产列表), total(总数), page, page_size
    """
    query = select(Asset)

    if status:
        query = query.where(Asset.status == status)
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)

    # 先算总数（基于过滤条件）
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # 按创建时间倒序分页
    query = query.order_by(Asset.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    assets = result.scalars().all()

    return AssetListResponse(
        items=[AssetResponse.model_validate(a) for a in assets],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: str, db: AsyncSession = Depends(get_db)):
    """
    获取单个资产完整信息。

    参数:
        asset_id: 资产UUID

    返回:
        AssetResponse: 包含名称、类型、状态、面数、顶点数、各格式路径、标签等
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "资产不存在")
    return AssetResponse.model_validate(asset)


@router.delete("/{asset_id}")
async def delete_asset(asset_id: str, db: AsyncSession = Depends(get_db)):
    """
    删除资产及其所有关联文件和数据库记录。

    参数:
        asset_id: 资产UUID

    返回:
        { "message": "删除成功" }
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "资产不存在")

    # 删除本地文件目录（模型、预览图等）
    asset_dir = settings.ASSETS_DIR / asset_id
    if asset_dir.exists():
        import shutil
        shutil.rmtree(asset_dir)

    # 级联删除关联的defects和tasks
    await db.delete(asset)
    await db.commit()
    return {"message": "删除成功"}


@router.get("/{asset_id}/download/{format}")
async def download_asset(asset_id: str, format: str, db: AsyncSession = Depends(get_db)):
    """
    下载指定格式的模型文件。

    参数:
        asset_id: 资产UUID
        format: 文件格式（glb / fbx / obj）

    返回:
        FileResponse: 直接返回文件下载流
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "资产不存在")

    format_map = {
        "glb": asset.glb_path,
        "fbx": asset.fbx_path,
        "obj": asset.obj_path,
    }
    file_path = format_map.get(format)
    if not file_path or not Path(file_path).exists():
        raise HTTPException(404, f"{format} 格式文件不存在")

    return FileResponse(file_path, filename=f"{asset.name}.{format}")
