"""
数据库连接与会话管理模块。

技术选型:
  - 驱动: asyncpg（异步） — 用于 FastAPI 接口层
  - 连接池: SQLAlchemy 2.0 内置 (pool_size=10, max_overflow=20)
  - 会话: async_sessionmaker 按请求创建/释放，expire_on_commit=False 避免惰性加载

使用方式:
  from app.core.database import get_db, Base
  # 路由中: db: AsyncSession = Depends(get_db)
  # 模型中: class MyModel(Base)
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.core.config import settings

# 异步引擎 — 通过 asyncpg 连接 PostgreSQL（FastAPI 接口层使用）
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

# 异步会话工厂 — FastAPI 路由通过 get_db() 使用
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 同步引擎+会话 — Celery Worker 使用（避免 event loop 冲突）
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    echo=False,
    pool_size=5,
    max_overflow=10,
)

SyncSession = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """
    SQLAlchemy ORM 声明式基类。

    所有数据模型继承此类，自动拥有:
      - 表名自动推导（__tablename__）
      - Mapped 类型映射支持
      - 元数据注册（供 Alembic 迁移使用）
    """
    pass


async def get_db() -> AsyncSession:
    """
    FastAPI 依赖注入：为每个请求创建数据库会话。

    用法: db: AsyncSession = Depends(get_db)

    生命周期:
      1. 创建会话 → yield 给路由处理函数
      2. 正常完成 → 自动 commit
      3. 异常退出 → 自动 rollback
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
