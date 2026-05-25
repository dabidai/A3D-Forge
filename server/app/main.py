from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from core.config import settings
from api.v1 import generate, repair, assets, tasks, logs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure data directories exist
    settings.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    settings.SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(generate.router, prefix=f"{settings.API_V1_PREFIX}/generate", tags=["3D Generation"])
app.include_router(repair.router, prefix=f"{settings.API_V1_PREFIX}/repair", tags=["Model Repair"])
app.include_router(assets.router, prefix=f"{settings.API_V1_PREFIX}/assets", tags=["Assets"])
app.include_router(tasks.router, prefix=f"{settings.API_V1_PREFIX}/tasks", tags=["Tasks"])
app.include_router(logs.router, prefix=f"{settings.API_V1_PREFIX}/logs", tags=["Logs"])

# Static file serving for exported assets
app.mount("/static", StaticFiles(directory=str(settings.DATA_DIR)), name="static")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}
