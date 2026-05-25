from pydantic import BaseModel
from datetime import datetime
import uuid


class AssetResponse(BaseModel):
    id: uuid.UUID
    name: str
    asset_type: str
    status: str
    source_prompt: str | None = None
    face_count: int | None = None
    vertex_count: int | None = None
    api_provider: str | None = None
    glb_path: str | None = None
    fbx_path: str | None = None
    obj_path: str | None = None
    preview_image_path: str | None = None
    tags: dict | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssetListResponse(BaseModel):
    items: list[AssetResponse]
    total: int
    page: int
    page_size: int
