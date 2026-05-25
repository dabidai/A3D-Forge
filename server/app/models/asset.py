import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class AssetStatus(str, enum.Enum):
    GENERATING = "generating"
    GENERATED = "generated"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class AssetType(str, enum.Enum):
    TEXT_TO_3D = "text_to_3d"
    IMAGE_TO_3D = "image_to_3d"


class DefectLevel(str, enum.Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


class Asset(Base):
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

    defects: Mapped[list["AssetDefect"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="asset", cascade="all, delete-orphan")


class AssetDefect(Base):
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
