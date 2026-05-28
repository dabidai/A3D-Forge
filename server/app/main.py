"""
FastAPI 应用入口模块。

功能:
  1. 创建 FastAPI 应用实例，配置 CORS 中间件
  2. 通过 lifespan 启动事件确保数据目录存在
  3. 注册 7 个 API 路由模块（生成/修复/资产/任务/日志/统计/导出）
  4. 挂载静态文件服务（模型文件、预览图等）
  5. 提供 /health 健康检查端点

启动命令:
  uvicorn app.main:app --reload --port 8000

API 文档地址:
  - Swagger UI: http://localhost:8000/docs
  - ReDoc: http://localhost:8000/redoc
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from core.config import settings
from api.v1 import generate, repair, assets, tasks, logs, stats, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理。

    Startup: 确保数据根目录存在（assets / scripts / logs）
    Shutdown: 当前无清理逻辑，预留扩展点
    """
    settings.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    settings.SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,  # "AI 3D Asset Generator"
    version=settings.VERSION,     # "0.1.0"
    lifespan=lifespan,            # 启动/关闭事件
)

# CORS 跨域中间件 — 允许前端 (localhost:5173) 访问本地开发API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # 当前白名单: localhost:3000, localhost:5173
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- API 路由注册 ----
# 所有路由统一挂载在 /api/v1 下，Swagger按tags分组展示
app.include_router(generate.router, prefix=f"{settings.API_V1_PREFIX}/generate", tags=["3D Generation"])
app.include_router(repair.router,   prefix=f"{settings.API_V1_PREFIX}/repair",   tags=["Model Repair"])
app.include_router(assets.router,   prefix=f"{settings.API_V1_PREFIX}/assets",   tags=["Assets"])
app.include_router(tasks.router,    prefix=f"{settings.API_V1_PREFIX}/tasks",    tags=["Tasks"])
app.include_router(logs.router,     prefix=f"{settings.API_V1_PREFIX}/logs",     tags=["Logs"])
app.include_router(stats.router,    prefix=f"{settings.API_V1_PREFIX}/stats",    tags=["Statistics"])
app.include_router(export.router,   prefix=f"{settings.API_V1_PREFIX}/export",   tags=["Data Export"])

# 静态文件服务 — /static/assets/{id}/ 映射到 /data/assets/{id}/
app.mount("/static", StaticFiles(directory=str(settings.DATA_DIR)), name="static")


@app.get("/health")
async def health_check():
    """
    健康检查端点。

    返回: {"status": "ok", "version": "0.1.0"}
    用途: Docker Compose healthcheck / K8s liveness probe / 负载均衡器探活
    """
    return {"status": "ok", "version": settings.VERSION}
