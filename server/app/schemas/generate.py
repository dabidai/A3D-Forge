"""
3D生成相关的请求/响应 Pydantic 数据模型。

作用:
  - 定义API输入输出的字段、类型、验证规则
  - 自动生成 OpenAPI (Swagger) 文档
  - FastAPI 自动校验请求体/查询参数

包含:
  请求: TextTo3DRequest, BatchTextTo3DRequest
  响应: TextTo3DResponse, ImageTo3DResponse, GenerationStatusResponse, BatchTextTo3DResponse
"""
from pydantic import BaseModel, Field


class TextTo3DRequest(BaseModel):
    """文生3D请求体。

    字段:
      prompt:            自然语言3D描述（必填，1-2000字符）
      negative_prompt:   负向提示词（不希望出现的内容）
      style:             目标风格，realistic/cartoon/low_poly/sculpture
      complexity:        复杂度 low/medium/high
      skip_optimization: 跳过LLM优化（调试或不想等LLM时使用）
      skip_audit:        跳过内容审核
    """
    prompt: str = Field(..., description="自然语言3D描述", min_length=1, max_length=2000)
    negative_prompt: str = Field(default="", max_length=2000)
    style: str = Field(default="realistic", description="风格: realistic/cartoon/low_poly/sculpture")
    complexity: str = Field(default="medium", description="复杂度: low/medium/high")
    skip_optimization: bool = Field(default=False, description="跳过LLM提示词优化")
    skip_audit: bool = Field(default=False, description="跳过内容安全审核")


class TextTo3DResponse(BaseModel):
    """文生3D响应体。

    original_prompt / optimized_prompt: 展示LLM前后对比
    audit_result: 审核结果，含 compliant / risk_level 等字段
    """
    task_id: str
    asset_id: str
    status: str
    message: str                         # "3D生成任务已提交"
    original_prompt: str | None = None   # 用户原始输入
    optimized_prompt: str | None = None  # LLM优化后的正负向提示词
    optimized_negative_prompt: str | None = None
    audit_result: dict | None = None     # LLM审核结果


class ImageTo3DResponse(BaseModel):
    """图生3D响应体。"""
    task_id: str
    asset_id: str
    status: str
    message: str
    audit_result: dict | None = None


class GenerationStatusResponse(BaseModel):
    """生成状态查询响应体。

    前端每3秒轮询此接口，直到 status 不在 (generating/processing/pending) 中。

    字段:
      progress:     0.0~1.0 进度
      model_url:    生成的GLB模型访问URL（相对路径）
      preview_url:  预览图URL（800x600 PNG）
      face_count:   模型三角面数
    """
    asset_id: str
    status: str
    progress: float
    model_url: str | None = None
    preview_url: str | None = None
    face_count: int | None = None
    error_message: str | None = None


class BatchTextTo3DRequest(BaseModel):
    """批量文生3D请求体。

    prompts: 每行一个提示词（1-20条），共享同一 style 和 negative_prompt
    """
    prompts: list[str] = Field(..., min_length=1, max_length=20)
    negative_prompt: str = Field(default="")
    style: str = Field(default="realistic")
    skip_optimization: bool = Field(default=False)


class BatchTextTo3DResponse(BaseModel):
    """批量文生3D响应体。

    batch_id: 批次标识
    tasks:    每个prompt对应的 TextTo3DResponse 列表
    """
    batch_id: str
    total: int
    tasks: list[TextTo3DResponse]
