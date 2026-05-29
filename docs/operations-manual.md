# A3D-Forge 操作手册

## 启动流程

### 1. WSL — 启动基础设施（每次开机后）

```bash
cd /mnt/f/company/A3D-Forge
docker compose up -d
```

启动 PostgreSQL、Redis、Ollama、Celery Worker 四个容器。

### 2. WSL — 拉取 Ollama 模型（仅首次）

```bash
docker exec a3d-ollama ollama pull qwen3:4b
```

### 3. WSL — 初始化数据库（仅首次）

```bash
docker exec a3d-worker alembic revision --autogenerate -m "init"
docker exec a3d-worker alembic upgrade head
```

### 4. Windows — 启动后端

```bash
cd F:\company\A3D-Forge\server
pip install -r requirements.txt    # 仅首次
uvicorn app.main:app --reload --port 8000
```

### 5. Windows — 启动前端

```bash
cd F:\company\A3D-Forge\web
npm install                        # 仅首次
npm run dev
```

### 6. 访问

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| API 文档 | http://localhost:8000/docs |

---

## 常用操作

### 查看 Worker 日志

```bash
docker logs a3d-worker --tail 50
docker logs a3d-worker -f           # 实时跟踪
```

### 查看 Redis 队列积压

```bash
docker exec a3d-redis redis-cli -n 1 LLEN celery
```

### 重启 Worker

```bash
docker compose restart worker
```

### 重建 Worker（依赖变更后）

```bash
docker compose up -d --build worker
```

### 查看资产文件

```bash
ls -lh f:/company/A3D-Forge/server/data/assets/
```

### 手动测试 Tripo3D API

```bash
# 查余额
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.tripo3d.ai/v2/openapi/user/balance

# 查任务状态
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.tripo3d.ai/v2/openapi/task/TASK_ID
```

---

## 前端开关说明

| 开关 | 作用 |
|------|------|
| LLM 优化提示词 | 开启后 Qwen3 优化 prompt，耗时 3~5 分钟；关闭则直接用原始 prompt 发 Tripo3D |

---

## 停止

```bash
# Windows: Ctrl+C 停 uvicorn 和 npm run dev
# WSL:
docker compose down
```
