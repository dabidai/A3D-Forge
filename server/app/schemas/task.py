"""
任务管理相关的Pydantic响应模型。
"""
from pydantic import BaseModel
from datetime import datetime
import uuid


class TaskResponse(BaseModel):
    """
    单个任务响应体。

    字段说明:
      id:                任务UUID
      asset_id:          关联资产ID（可空）
      task_type:         任务类型（text_to_3d / image_to_3d / model_repair / llm_analysis）
      status:            执行状态（pending / running / success / failed / retrying）
      progress:          进度 0.0~1.0
      input_params:      任务输入参数（JSONB）
      output_result:     任务输出结果（JSONB）
      error_message:     失败时的错误信息
      created_at:        创建时间
    """
    id: uuid.UUID
    asset_id: uuid.UUID | None = None
    task_type: str
    status: str
    progress: float
    input_params: dict | None = None
    output_result: dict | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """任务列表响应体。"""
    items: list[TaskResponse]
    total: int
