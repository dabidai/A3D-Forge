"""
资产管理 API：CRUD + 列表查询。
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
    """分页查询资产列表"""
    query = select(Asset)

    if status:
        query = query.where(Asset.status == status)
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # 分页
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
    """获取单个资产详情"""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "资产不存在")
    return AssetResponse.model_validate(asset)


@router.delete("/{asset_id}")
async def delete_asset(asset_id: str, db: AsyncSession = Depends(get_db)):
    """删除资产及其关联文件"""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "资产不存在")

    # 删除文件
    asset_dir = settings.ASSETS_DIR / asset_id
    if asset_dir.exists():
        import shutil
        shutil.rmtree(asset_dir)

    await db.delete(asset)
    await db.commit()
    return {"message": "删除成功"}


@router.get("/{asset_id}/download/{format}")
async def download_asset(asset_id: str, format: str, db: AsyncSession = Depends(get_db)):
    """下载指定格式的模型文件"""
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
