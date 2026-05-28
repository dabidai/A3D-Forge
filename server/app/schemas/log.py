"""
用户行为日志相关的请求模型。
"""
from pydantic import BaseModel


class UserLogRequest(BaseModel):
    """
    用户行为日志上报请求体。

    字段:
      session_id: 浏览器会话ID（前端 Zustand store 中 crypto.randomUUID() 生成）
      action:     操作类型标识（page_view / generate_text_to_3d / auto_repair / llm_analysis 等）
      page:       操作所在页面名称（仪表盘 / 3D生成 / 模型修复 / 资产管理 / 操作日志）
      asset_id:   关联的资产ID（可选，如查看/修复/下载特定资产时传入）
      details:    扩展JSON信息（可选，如生成参数、下载格式等补充数据）
    """
    session_id: str
    action: str
    page: str | None = None
    asset_id: str | None = None
    details: dict | None = None
