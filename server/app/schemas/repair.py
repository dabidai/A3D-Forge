"""
模型修复相关的请求/响应 Pydantic 数据模型。
"""
from pydantic import BaseModel


class RepairRequest(BaseModel):
    """修复请求体。

    asset_id: 待修复的资产UUID（资产必须已存在且有模型文件）
    """
    asset_id: str


class RepairResponse(BaseModel):
    """自动修复响应体。

    初始响应各计数为0，实际数值由Celery任务完成后通过tasks接口查询。

    字段:
      defects_found: 检测到的缺陷总数
      auto_repaired: 自动修复成功的缺陷数
      needs_manual:  需要人工介入的缺陷数
      report:        修复报告详情
    """
    asset_id: str
    task_id: str
    status: str
    defects_found: int
    auto_repaired: int
    needs_manual: int
    report: dict


class DefectInfo(BaseModel):
    """单个缺陷信息。

    字段:
      type:        缺陷类型标识
      level:       严重等级 mild/moderate/severe
      description: 缺陷描述文本
      repairable:  是否可自动修复
      count:       同类缺陷数量
    """
    type: str
    level: str
    description: str
    repairable: bool
    count: int


class DefectAnalysisResponse(BaseModel):
    """LLM缺陷分析响应体。

    字段:
      overall_severity: 整体严重等级 mild/moderate/severe/pending
      defects:          缺陷列表
      repair_script:    LLM生成的Blender修复脚本（可选）
      tutorial:         LLM生成的修复教程文本（可选）
    """
    asset_id: str
    overall_severity: str
    defects: list[DefectInfo]
    repair_script: str | None = None
    tutorial: str | None = None
