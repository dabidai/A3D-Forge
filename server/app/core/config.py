from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI 3D Asset Generator"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "a3d"
    POSTGRES_PASSWORD: str = "a3d_secret"
    POSTGRES_DB: str = "a3d_assets"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def CELERY_BROKER_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/2"

    # Ollama
    OLLAMA_HOST: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "qwen3:7b-instruct-q4_K_M"
    OLLAMA_TIMEOUT: int = 180
    OLLAMA_MAX_RETRIES: int = 3

    # Commercial 3D APIs
    TRIPO3D_API_KEY: str = ""
    TRIPO3D_API_URL: str = "https://api.tripo3d.ai/v1"
    MESHY_API_KEY: str = ""
    MESHY_API_URL: str = "https://api.meshy.ai/v2"

    # Storage
    DATA_DIR: Path = Path("/data")
    ASSETS_DIR: Path = Path("/data/assets")
    SCRIPTS_DIR: Path = Path("/data/scripts")
    LOGS_DIR: Path = Path("/data/logs")

    # Limits
    MAX_MODEL_FACES: int = 500000
    MAX_UPLOAD_SIZE_MB: int = 200
    TASK_TIMEOUT_MINUTES: int = 30

    # Security
    SECRET_KEY: str = "dev-secret-change-in-production"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = dict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
