"""
用户行为日志数据模型。

阶段一核心数据沉淀目标:
  通过记录全链路用户操作行为，分析:
    - 用户偏好: 提示词风格/复杂度选择/生成类型比例
    - 转化漏斗: 生成 → 后处理 → 修复 → 下载 各环节转化率
    - 效率指标: 平均操作频率、热门功能使用比例
  为阶段二模型微调和产品优化提供数据支撑。

数据保留策略:
  阶段一不做清理，全量保留。阶段二根据数据量决定归档策略。
"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserLog(Base):
    """
    用户行为日志表。

    字段说明:
      id:          日志UUID
      session_id:  前端生成的浏览器会话ID（Zustand store中 crypto.randomUUID()） — 关联同一用户连续操作
      action:      操作类型标识（page_view / generate_text_to_3d / auto_repair / llm_analysis 等）
      page:        操作所在页面（仪表盘 / 3D生成 / 模型修复 / 资产管理 / 操作日志）
      asset_id:    关联资产ID（可选，如生成/查看/修复具体资产时填入）
      details:     扩展信息JSON（可选，如生成参数、下载格式等）
      ip_address:  客户端IP（自动从Request获取）
      user_agent:  浏览器User-Agent（用于区分设备/浏览器）
      created_at:  记录时间（UTC）
    """
    __tablename__ = "user_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(100), index=True)  # 建立索引以加速会话查询
    action: Mapped[str] = mapped_column(String(100))
    page: Mapped[str | None] = mapped_column(String(200), nullable=True)
    asset_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
