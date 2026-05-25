"""
日志管理 API：用户行为日志上报与查询。
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
    """上报用户行为日志"""
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
    """查询用户行为日志"""
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
