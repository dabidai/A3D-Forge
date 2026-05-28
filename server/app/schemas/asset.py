"""
资产管理相关的Pydantic响应模型。

model_config = {"from_attributes": True}:
  允许从SQLAlchemy ORM对象直接转换为Pydantic模型（model_validate() 接受ORM实例）。

字段命名:
  使用Python风格（snake_case），FastAPI序列化时保持与ORM字段一致。
"""
from pydantic import BaseModel
from datetime import datetime
import uuid


class AssetResponse(BaseModel):
    """
    单个资产响应体。

    字段说明:
      id:                   资产UUID
      name:                 资产名称（截取prompt前50字符）
      asset_type:           生成类型（text_to_3d / image_to_3d）
      status:               处理状态（generating/generated/processing/processed/failed）
      source_prompt:        原始用户提示词
      face_count:           三角面数
      vertex_count:         顶点数
      api_provider:         调用的API服务商（tripo3d / meshy）
      glb_path/fbx_path/obj_path: 各格式模型文件路径
      preview_image_path:   预览图路径
      tags:                 动态标签（含repair_report/defects/severity等）
      error_message:        失败原因
    """
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
    """资产分页列表响应体。"""
    items: list[AssetResponse]   # 当前页资产列表
    total: int                   # 符合过滤条件的总资产数
    page: int                    # 当前页码
    page_size: int               # 每页条数
