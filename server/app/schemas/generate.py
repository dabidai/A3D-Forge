from pydantic import BaseModel, Field


class TextTo3DRequest(BaseModel):
    prompt: str = Field(..., description="自然语言3D描述", min_length=1, max_length=2000)
    negative_prompt: str = Field(default="", max_length=2000)
    style: str = Field(default="realistic", description="风格: realistic/cartoon/low_poly/sculpture")
    complexity: str = Field(default="medium", description="复杂度: low/medium/high")


class TextTo3DResponse(BaseModel):
    task_id: str
    asset_id: str
    status: str
    message: str


class ImageTo3DResponse(BaseModel):
    task_id: str
    asset_id: str
    status: str
    message: str


class GenerationStatusResponse(BaseModel):
    asset_id: str
    status: str
    progress: float
    model_url: str | None = None
    preview_url: str | None = None
    face_count: int | None = None
    error_message: str | None = None
