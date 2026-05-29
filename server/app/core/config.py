"""
全局配置模块，基于 pydantic-settings 管理所有环境变量和运行时参数。

配置来源:
  1. 类属性默认值（本文件定义）
  2. 项目根目录 .env 文件（通过 model_config 自动加载）
  3. 环境变量（最高优先级，Docker Compose 通过 environment 注入）

Redis DB 分配:
  - DB 0: 缓存（语义向量、LLM结果）
  - DB 1: Celery broker（任务队列消息）
  - DB 2: Celery result backend（任务结果存储）

使用方式:
  from app.core.config import settings
  settings.DATABASE_URL  # 直接访问属性
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """应用全局配置，所有字段可通过 .env 文件或环境变量覆盖。"""

    # ---- 基础信息 ----
    PROJECT_NAME: str = "AI 3D Asset Generator"   # 项目显示名称（Swagger标题）
    VERSION: str = "0.1.0"                        # API版本号
    API_V1_PREFIX: str = "/api/v1"                # API路由前缀

    # ---- PostgreSQL 数据库 ----
    POSTGRES_HOST: str = "postgres"               # Docker容器名（非localhost，容器间通过服务名互访）
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "a3d"
    POSTGRES_PASSWORD: str = "a3d_secret"
    POSTGRES_DB: str = "a3d_assets"

    @property
    def DATABASE_URL(self) -> str:
        """返回 asyncpg 异步驱动连接串，供 AsyncSession 使用。"""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """返回 psycopg2 同步驱动连接串，供 Alembic 迁移工具使用。"""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ---- Redis 缓存/队列 ----
    REDIS_HOST: str = "redis"       # Docker容器名
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0               # 默认DB用于缓存

    @property
    def REDIS_URL(self) -> str:
        """Redis 缓存连接串（DB 0）。"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def CELERY_BROKER_URL(self) -> str:
        """Celery 消息队列连接串（DB 1）。"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """Celery 结果存储连接串（DB 2）。"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/2"

    # ---- Ollama 本地LLM ----
    OLLAMA_HOST: str = "http://ollama:11434"          # Ollama API地址
    OLLAMA_MODEL: str = "qwen3:4b"                    # 4B Dense，约2.5GB，推理需4-6GB内存（适配8G机器）
    OLLAMA_TIMEOUT: int = 180                          # 单次推理超时（秒），CPU推理慢需给足时间
    OLLAMA_MAX_RETRIES: int = 3                        # JSON解析失败时最大重试次数

    # ---- 商用3D API（可选配置，不填则对应功能降级） ----
    TRIPO3D_API_KEY: str = ""                           # Tripo3D API Key（文生3D，https://platform.tripo3d.ai）
    TRIPO3D_API_URL: str = "https://api.tripo3d.ai/v1"
    MESHY_API_KEY: str = ""                             # Meshy AI API Key（图生3D+PBR，https://meshy.ai）
    MESHY_API_URL: str = "https://api.meshy.ai/v1"

    # ---- 本地文件存储 ----
    DATA_DIR: Path = Path("./data")             # 数据根目录（Docker由环境变量覆盖为 /app/data）
    ASSETS_DIR: Path = Path("./data/assets")    # 3D模型资产目录（按asset_id分子目录）
    SCRIPTS_DIR: Path = Path("./data/scripts")  # 修复脚本归档目录
    LOGS_DIR: Path = Path("./data/logs")        # 日志输出目录

    # ---- 处理限制 ----
    MAX_MODEL_FACES: int = 500000        # 单模型最大面数（超出警告）
    MAX_UPLOAD_SIZE_MB: int = 200        # 上传图片最大尺寸
    TASK_TIMEOUT_MINUTES: int = 30       # Celery任务软超时（分钟），超时后抛出SoftTimeLimitExceeded

    # ---- 安全 ----
    SECRET_KEY: str = "dev-secret-change-in-production"   # JWT密钥（生产环境必须替换）
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]   # CORS白名单

    # Pydantic配置：自动从 .env 文件加载
    model_config = dict(env_file=".env", env_file_encoding="utf-8")


# 全局单例，所有模块通过 import settings 获取同一实例
settings = Settings()
