"""
Celery异步任务追踪数据模型。

任务状态流转:
  PENDING → RUNNING → SUCCESS
      ↓         ↓
  (重试)    FAILED → RETRYING → PENDING

枚举值:
  TaskType:   text_to_3d(文生3D) | image_to_3d(图生3D) | model_repair(模型修复) | script_execution(脚本执行) | llm_analysis(LLM分析)
  TaskStatus: pending(等待执行) | running(执行中) | success(成功) | failed(失败) | retrying(重试中)
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class TaskType(str, enum.Enum):
    """异步任务类型枚举。"""
    TEXT_TO_3D = "text_to_3d"           # 文生3D：调用Tripo3D → 后处理
    IMAGE_TO_3D = "image_to_3d"         # 图生3D：Meshy/Tripo3D → 后处理
    MODEL_REPAIR = "model_repair"       # 模型修复：缺陷检测 → 轻修复 → 导出
    SCRIPT_EXECUTION = "script_execution" # 脚本执行：Blender Python脚本运行
    LLM_ANALYSIS = "llm_analysis"       # LLM分析：Qwen3 TECH_ANALYST → 缺陷报告


class TaskStatus(str, enum.Enum):
    """任务执行状态枚举。"""
    PENDING = "pending"     # 已入队，等待Worker取走
    RUNNING = "running"     # Worker正在执行
    SUCCESS = "success"     # 执行完成
    FAILED = "failed"       # 执行失败（含重试次数耗尽）
    RETRYING = "retrying"   # 执行失败，正在重试


class Task(Base):
    """
    任务追踪表，记录每次异步操作的输入/输出/状态/耗时。

    关键字段:
      id:              任务UUID（同时作为Celery task_id，便于追踪）
      asset_id:        关联资产ID（外键 assets.id）
      celery_task_id:  Celery内部任务ID
      input_params (JSONB):  任务输入参数（prompt / image_path / style 等）
      output_result (JSONB): 任务输出结果（stats / defect_count / severity 等）
      progress:        执行进度 0.0~1.0
      retry_count:     重试次数（Celery自动重试+人工重试）
      started_at:      任务开始执行时间
      completed_at:    任务完成时间
    """
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True)
    task_type: Mapped[TaskType] = mapped_column(SAEnum(TaskType))
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.PENDING)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    retry_count: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    asset: Mapped["Asset | None"] = relationship(back_populates="tasks")
