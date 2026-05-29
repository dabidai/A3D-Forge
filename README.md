# A3D-Forge

AI 3D 资产生成平台 · 阶段一（草稿验证版）

## 架构

```
Windows 本机                        WSL Ubuntu (Docker)
┌──────────────────┐              ┌────────────────────────┐
│ uvicorn :8000    │──localhost──│  postgres :5432        │
│ (FastAPI)        │              │  redis    :6379        │
│                  │              │  ollama   :11434       │
│ npm run dev :5173│              │  celery worker         │
│ (Vite 前端)      │              └────────────────────────┘
└──────────────────┘
```

## 前置条件

- Windows 本机：Python 3.11+、Node.js 20+
- WSL Ubuntu：Docker Desktop
- Tripo3D API Key（[platform.tripo3d.ai](https://platform.tripo3d.ai) 注册获取）

## 配置

编辑 `server/.env`：

```ini
TRIPO3D_API_KEY=tsk_你的key
```

当前完整配置项见 `server/.env` 文件。

## 启动

### 1. WSL — 启动基础设施

```bash
cd /mnt/f/company/A3D-Forge
docker compose up -d
```

### 2. WSL — 初始化（仅首次）

```bash
# 拉取 Qwen3 模型
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
npm install                        # 仅首次
npm run dev
```

### 5. 访问

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| API 文档 | http://localhost:8000/docs |

## 日常使用

```bash
# WSL:
docker compose up -d

# Windows 终端1:
cd F:\company\A3D-Forge\server && uvicorn app.main:app --reload

# Windows 终端2:
cd F:\company\A3D-Forge\web && npm run dev
```

## 常用操作

| 操作 | 命令 |
|------|------|
| 查看 Worker 日志 | `docker logs a3d-worker --tail 50` |
| 实时跟踪日志 | `docker logs a3d-worker -f` |
| 查看 Redis 任务队列 | `docker exec a3d-redis redis-cli -n 1 LLEN celery` |
| 重建 Worker | `docker compose up -d --build worker` |
| 查看生成文件 | `ls server/data/assets/` |
| 检查 Tripo3D 余额 | `curl -H "Authorization: Bearer YOUR_KEY" https://api.tripo3d.ai/v2/openapi/user/balance` |

## 任务流程

```
前端提交 → FastAPI 创建 DB 记录 → push 到 Redis 队列
                                      ↓
                               Celery Worker 捡取
                                      ↓
                         [可选] Qwen3 优化提示词 (3~5min)
                                      ↓
                         [可选] Qwen3 内容审核 (1~2min)
                                      ↓
                               Tripo3D API 生成 (1~3min)
                                      ↓
                               模型下载 → 修复 → 缺陷检测 → 导出
                                      ↓
                              状态更新 → 前端轮询感知完成
```

生成结果保存在 `server/data/assets/{asset_id}/`，包含 GLB、OBJ 格式和材质贴图。

## 停止

```bash
# Windows: Ctrl+C 停掉 uvicorn 和 npm run dev
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
│   ├── alembic/             # 数据库迁移
│   ├── alembic.ini
│   └── requirements.txt
├── web/                     # React 前端
│   └── src/
│       ├── components/      # ModelViewer (Three.js) 等
│       ├── pages/           # 仪表盘、生成、修复、资产、日志
│       ├── stores/          # Zustand 状态管理
│       └── api/             # API 客户端
├── docs/                    # 文档
│   ├── operations-manual.md     # 操作手册
│   ├── troubleshooting.md       # 问题排查
│   ├── knowledge-summary.md     # 技术知识点
│   └── sparse-matrix-optimization.md  # 稀疏矩阵优化记录
├── docker-compose.yml
└── README.md
```

## 更多文档

- [操作手册](docs/operations-manual.md)
- [常见问题](docs/troubleshooting.md)
- [知识总结](docs/knowledge-summary.md)
