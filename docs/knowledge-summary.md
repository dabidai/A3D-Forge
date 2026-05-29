# 技术知识点总结

## 一、稀疏矩阵与内存优化

### 问题本质

稠密矩阵大小 = N²。当 N=190979 时，一个 bool 矩阵需要 190979² ≈ 360 亿个元素 × 1 byte = **34GB**。而实际数据（非零元素）只有约 50 万个（每边邻居 2~3 个）。

### CSR 稀疏格式

CSR (Compressed Sparse Row) 不存 N² 个值，只存三个数组：
- `data`：非零值（~50 万个）
- `indices`：列索引（~50 万个）
- `indptr`：行偏移（N+1 个）

总内存 = 50万 + 50万 + 19万 ≈ 120 万个整数 ≈ **5MB**。

### 运算策略

```python
# 错误：转稠密后计算 — O(N²) 内存
mesh.edges_sparse.toarray().sum(axis=1)

# 正确：稀疏直接计算 — O(N) 内存
mesh.edges_sparse.sum(axis=1)
```

scipy 的稀疏矩阵支持就地数学运算（sum、multiply、dot），不需要展开。

---

## 二、Celery + FastAPI 的异步架构

### 同步 vs 异步的分界线

```
FastAPI (async)          Celery Worker (sync)
───────────────          ──────────────────
HTTP 请求处理             后台任务执行
    ↓                         ↓
async DB session           sync DB session
(asyncpg)                  (psycopg2)
    ↓                         ↓
立即返回给前端              轮询 Tripo3D API
```

### 为什么 Celery 用同步？

1. **事件循环隔离**：Celery 多进程，每个进程独立事件循环，async session 不乱串
2. **长耗时友好**：3D 生成可能 5~10 分钟，同步阻塞不影响其他任务
3. **避免 Future 跨循环**：`async_session` 绑定在主线程循环，`new_event_loop()` 再建新循环会报 `attached to a different loop`

### 关键实践

- FastAPI 路由用 `async_session`（asyncpg）
- Celery 任务用 `SyncSession`（psycopg2）
- 两种 session 共享同一套 Model 定义

---

## 三、pydantic-settings 配置优先级

```
命令行环境变量 > .env 文件 > 代码默认值
```

### 陷阱

`.env` 文件中的相对路径（如 `./data`）在 Docker 容器中相对于 WORKDIR（`/app`），在 Windows 上相对于 uvicorn 启动目录（`server/`）。需要确保两边相对路径解析到同一实际目录。

### 最佳实践

- 默认值设为相对路径（如 `Path("./data")`）
- Docker 中通过 `environment` 覆盖为绝对路径（`/app/data`）
- Windows 用默认相对路径即可
- 定期用 `docker exec xxx python -c "from app.core.config import settings; print(settings.DATA_DIR)"` 验证

---

## 四、Tripo3D API v2 调用

### 端点

```
Base: https://api.tripo3d.ai/v2/openapi
POST /task        创建任务  body: {"type":"text_to_model", "prompt":"..."}
GET  /task/{id}   查询状态  返回: {"data":{"status":"success", "output":{"model":"url"}}}
```

### 鉴权

```
Authorization: Bearer tsk_xxxxx
```

API Key 以 `tsk_` 开头，可在 https://platform.tripo3d.ai 获取。

### 轮询

Tripo3D 生成通常 1~3 分钟。需要每 5~6 秒轮询一次，网络不稳定时加 5 次重试容错。

---

## 五、Docker 挂载与文件可见性

### 两种 Volume

| 类型 | 写法 | Windows 可见 | 用途 |
|------|------|-------------|------|
| 绑定挂载 | `./server:/app` | ✅ 是 | 代码同步 |
| 命名卷 | `asset_data:/data` | ❌ 否 | 生产数据 |

### 当前架构

```
./server:/app    → 代码和生成结果都通过这个挂载同步
./data:/data     → 不再使用，改为 /app/data 统一到绑定挂载
```

### 检查命令

```bash
docker exec a3d-worker ls /app/data/assets/   # 容器内路径
ls f:/company/A3D-Forge/server/data/assets/   # Windows 路径（应一致）
```

---

## 六、大模型处理策略

### 分级处理

| 面数 | 策略 |
|------|------|
| < 10 万 | 全量缺陷检测 |
| 10~50 万 | 降采样到 5 万后检测 |
| > 50 万 | 考虑跳过或深度降采样 |

### 为什么 50 万面 = 15MB 文件，但分析却要 GB 级内存？

GLB 文件是压缩过的几何数据（顶点缓冲），而拓扑分析需要构建边/面的邻接图，这是 O(N²) 的关系。N 越大，这个差距越剧烈。

---

## 七、Ollama CPU 推理耗时

| 任务 | 耗时 | 建议 |
|------|------|------|
| 提示词优化 | 3~5 分钟 | 调试时可关闭 |
| 内容安全审核 | 1~2 分钟 | 调试时可关闭 |
| 缺陷分析 | 1~3 分钟 | 按需触发 |

前端「LLM 优化提示词」开关对应 `skip_optimization` 参数，关闭后跳过 Ollama 直接调 Tripo3D。
