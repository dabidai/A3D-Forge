"""
3D资产与缺陷数据模型。

数据库表:
  assets          — 3D资产主表（生成参数、文件路径、面数/顶点数、状态）
  asset_defects   — 资产缺陷明细表（缺陷类型、等级、可修复性、修复教程）

资产状态流转:
  GENERATING → GENERATED → PROCESSING → PROCESSED
                   ↓                      ↓
                FAILED                 FAILED

枚举值:
  AssetStatus: generating(生成中) | generated(已生成) | processing(后处理中) | processed(已处理) | failed(失败)
  AssetType:   text_to_3d(文生3D) | image_to_3d(图生3D)
  DefectLevel: mild(轻微可自动修复) | moderate(中等需人工确认) | severe(严重需手动修复)
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class AssetStatus(str, enum.Enum):
    """资产处理状态枚举。"""
    GENERATING = "generating"   # Celery任务已入队，等待API返回
    GENERATED = "generated"     # 商用API已返回模型，等待后处理
    PROCESSING = "processing"   # 后处理引擎运行中（修复/检测/导出）
    PROCESSED = "processed"     # 全部处理完成（已修复+多格式导出+预览图）
    FAILED = "failed"           # 任一环节失败（含错误信息）


class AssetType(str, enum.Enum):
    """3D生成方式枚举。"""
    TEXT_TO_3D = "text_to_3d"       # 文本提示词生成3D
    IMAGE_TO_3D = "image_to_3d"     # 图片生成3D（含PBR材质）


class DefectLevel(str, enum.Enum):
    """缺陷严重等级枚举。"""
    MILD = "mild"               # 轻微：可自动修复（孔洞填充/法线修正）
    MODERATE = "moderate"       # 中等：需要确认后修复（孤立面/UV问题）
    SEVERE = "severe"           # 严重：必须人工修复（非流形结构/拓扑混乱）


class Asset(Base):
    """
    3D资产主表，记录生成的完整生命周期。

    关键字段:
      id:                   资产UUID（也是文件目录名 /data/assets/{id}/）
      name:                 资产名称（截取prompt前50字符）
      source_prompt:        原始用户输入（文生3D）
      source_image_path:    上传图片路径（图生3D）
      original_model_path:  商用API返回的原始模型路径
      processed_model_path: 后处理修复后的模型路径
      glb_path/fbx_path/obj_path: 多格式导出路径
      preview_image_path:   预览图PNG路径（800x600）
      face_count:           模型三角面数
      vertex_count:         模型顶点数
      tags (JSONB):         动态标签 { repair_report, defects, severity, pbr_materials }
      api_provider:         调用的商用API（tripo3d / meshy）
      error_message:        失败原因文本
    """
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    asset_type: Mapped[AssetType] = mapped_column(SAEnum(AssetType))
    status: Mapped[AssetStatus] = mapped_column(SAEnum(AssetStatus), default=AssetStatus.GENERATING)
    source_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_model_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    processed_model_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    glb_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fbx_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    obj_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preview_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    face_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vertex_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dimensions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    api_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    api_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联：一个资产有多个缺陷记录和多个任务（级联删除）
    defects: Mapped[list["AssetDefect"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="asset", cascade="all, delete-orphan")


class AssetDefect(Base):
    """
    资产缺陷明细表，由 DefectDetector 自动检测 + LLM 深度分析产生。

    缺陷检测来源:
      - 自动检测: DefectDetector.detect_all() → 4类检测（非流形/退化面/法线异常/孤立组件）
      - LLM分析: analyze_defects_task → Qwen3 TECH_ANALYST → 补充修复教程

    关键字段:
      defect_type:         缺陷分类（non_manifold_edge / degenerate_face / inverted_normal / isolated_component 等）
      level:               严重等级（mild / moderate / severe）
      region_data (JSONB): 缺陷在3D空间中的区域坐标（用于前端高亮标注，阶段一预留）
      repair_script_path:  LLM生成的Blender修复脚本文件路径
      repair_tutorial:     LLM生成的文本修复教程（Markdown格式）
      auto_repairable:     是否可通过自动修复管线处理
      repaired:            是否已修复
    """
    __tablename__ = "asset_defects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"))
    defect_type: Mapped[str] = mapped_column(String(100))
    level: Mapped[DefectLevel] = mapped_column(SAEnum(DefectLevel))
    description: Mapped[str] = mapped_column(Text)
    region_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    repair_script_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    repair_tutorial: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_repairable: Mapped[bool] = mapped_column(default=False)
    repaired: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    asset: Mapped["Asset"] = relationship(back_populates="defects")
