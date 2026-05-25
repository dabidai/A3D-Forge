from pydantic import BaseModel
from datetime import datetime
import uuid


class TaskResponse(BaseModel):
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
    items: list[TaskResponse]
    total: int
