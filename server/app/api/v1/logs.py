"""
日志管理 API：用户行为日志上报与查询。

模块功能:
  - 接收前端上报的用户操作行为（页面浏览、生成提交、修复操作等）
  - 提供行为日志查询，支持按session/action过滤

数据用途（阶段一核心数据沉淀）:
  - 分析用户生成偏好（风格、复杂度）
  - 统计各环节耗时与转化率
  - 为阶段二模型微调提供行为数据支撑
"""
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.user_log import UserLog
from app.schemas.log import UserLogRequest

router = APIRouter()


@router.post("/report")
async def report_log(req: UserLogRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    前端上报用户行为日志。

    前端每次操作（页面导航、生成提交、修复触发等）调用此接口，
    自动记录IP和User-Agent用于会话分析。

    参数:
        req: UserLogRequest
            - session_id: 前端生成的浏览器会话ID
            - action: 操作类型（page_view / generate_text_to_3d / auto_repair 等）
            - page: 所在页面名称
            - asset_id: 关联的资产ID（可选）
            - details: 附加JSON详情（可选）
    """
    log = UserLog(
        session_id=req.session_id,
        action=req.action,
        page=req.page,
        asset_id=req.asset_id,
        details=req.details,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(log)
    await db.commit()
    return {"message": "ok"}


@router.get("/list")
async def list_logs(
    session_id: str | None = None,
    action: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """
    查询用户行为日志列表，支持按会话和操作类型过滤。

    参数:
        session_id: 按浏览器会话过滤（可选）
        action: 按操作类型过滤（可选）
        limit: 返回条数上限 (1-1000, 默认100)

    返回:
        { total, items: [{id, session_id, action, page, asset_id, created_at}] }
    """
    query = select(UserLog)
    if session_id:
        query = query.where(UserLog.session_id == session_id)
    if action:
        query = query.where(UserLog.action == action)

    query = query.order_by(UserLog.created_at.desc()).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "total": len(logs),
        "items": [
            {
                "id": str(log.id),
                "session_id": log.session_id,
                "action": log.action,
                "page": log.page,
                "asset_id": log.asset_id,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }
