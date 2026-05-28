# A3D-Forge

AI 3D 资产生成平台 · 阶段一（草稿验证版）

## 架构

```
Windows 本机                        WSL Ubuntu (Docker)
┌──────────────────┐              ┌────────────────────────┐
│ uvicorn :8000    │──localhost──│  postgres :5432        │
│ (FastAPI)        │              │  redis    :6379        │
│                  │              │  ollama   :11434       │
│ pnpm dev :5173   │              │  celery worker         │
│ (Vite 前端)      │              └────────────────────────┘
└──────────────────┘
```

## 前置条件

- Windows 本机：Python 3.11+、Node.js 20+、pnpm
- WSL Ubuntu：Docker Desktop（或 Docker Engine）
- Tripo3D API Key（[platform.tripo3d.ai](https://platform.tripo3d.ai) 注册获取）

## 配置

编辑 `server/.env`，填入 Tripo3D API Key：

```ini
TRIPO3D_API_KEY=tsk_你的key
```

## 启动

### 1. WSL — 启动基础设施

```bash
cd /mnt/f/company/A3D-Forge
docker compose up -d
```

### 2. WSL — 初始化（仅首次）

```bash
# 拉取 Qwen3 4B 模型（约 2.5GB，需 4-6GB 内存，适配 8G 机器）
# 若内存充足可换 qwen3:8b
docker exec a3d-ollama ollama pull qwen3:4b

# 创建数据库表
docker exec a3d-worker alembic revision --autogenerate -m "init"
docker exec a3d-worker alembic upgrade head
```

### 3. Windows — 启动后端

```bash
cd F:\company\A3D-Forge\server
pip install -r requirements.txt    # 仅首次
uvicorn app.main:app --reload --port 8000
```

### 4. Windows — 启动前端

```bash
cd F:\company\A3D-Forge\web
pnpm install                       # 仅首次
pnpm dev
```

### 5. 访问

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| API 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |

## 日常使用

```bash
# WSL:
docker compose up -d

# Windows 终端1:
cd F:\company\A3D-Forge\server && uvicorn app.main:app --reload

# Windows 终端2:
cd F:\company\A3D-Forge\web && pnpm dev
```

## 停止

```bash
# Windows: Ctrl+C 停掉 uvicorn 和 pnpm dev
# WSL:
docker compose down
```

## 项目结构

```
A3D-Forge/
├── server/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/          # REST API 路由
│   │   ├── core/            # 配置、数据库、Celery
│   │   ├── models/          # SQLAlchemy 数据模型
│   │   ├── schemas/         # Pydantic 请求/响应模型
│   │   ├── services/
│   │   │   ├── scheduler/   # Qwen3 调度服务（5 模块）
│   │   │   ├── generator/   # Tripo3D API 客户端
│   │   │   ├── postprocess/ # 模型后处理引擎
│   │   │   └── scripts/     # Blender 修复脚本库
│   │   └── tasks/           # Celery 异步任务
│   └── requirements.txt
├── web/                     # React 前端
│   └── src/
│       ├── components/      # ModelViewer (Three.js) 等组件
│       ├── pages/           # 仪表盘、生成、修复、资产、日志
│       ├── stores/          # Zustand 状态管理
│       └── api/             # API 客户端
├── nginx/                   # nginx 配置（生产用）
├── docker-compose.yml       # WSL 基础设施编排
└── README.md
```
