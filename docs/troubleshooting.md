# 常见问题与解决方法

## 1. 浏览器白屏 / 点击按钮无反应

**原因**：`npm install` 没跑，React 依赖未安装，JS 无法编译。

**解决**：`npm install` 后重启 `npm run dev`。从 pnpm 切 npm 后需要重新安装。

---

## 2. Alembic 报错 `No config file 'alembic.ini' found`

**原因**：`alembic.ini` 不在 server 根目录。

**解决**：将 `server/alembic/alembic.ini` 移动到 `server/alembic.ini`。Docker 里 WORKDIR 是 `/app`，alembic 默认找当前目录的 `alembic.ini`。

---

## 3. Alembic 报错 `KeyError: 'formatters'` / `'logger_root'`

**原因**：`alembic.ini` 的 logging 配置不完整——缺 `[handlers]` 和 `[formatters]` keys 段，且 `[loggers_root]` 命名错误。

**解决**：
- 添加 `[handlers] keys = console` 和 `[formatters] keys = generic`
- `[loggers_root]` 改为 `[logger_root]`（loggers → logger，单数）

---

## 4. Worker 报错 `ModuleNotFoundError: No module named 'app'`

**原因**：容器里 `PYTHONPATH` 没有 `/app`。

**解决**：docker-compose.yml 的 worker 环境添加 `PYTHONPATH=/app`。

---

## 5. 提交任务后显示"提交失败"

**原因**：API 同步等待 Ollama 优化提示词（30~120 秒），前端 axios 30 秒超时先到。

**解决**：将 Ollama 调用从 API 请求处理移到 Celery 异步任务中，API 立即返回（毫秒级）。改 `generate.py` 和 `generate_tasks.py`。

---

## 6. 任务在 Redis 但 Worker 不消费（LLEN > 0 但无日志）

**原因**：`celery_app` 未在 uvicorn 进程中初始化，`shared_task.apply_async()` 无可用 broker。

**解决**：在 `generate_tasks.py` 和 `repair_tasks.py` 中加上 `from app.core.celery_app import celery_app`。

---

## 7. 报错 `Illegal header value b'Bearer '`

**原因**：`TRIPO3D_API_KEY` 环境变量为空，Header 变成 `Bearer `。

**解决**：docker-compose.yml 用 `env_file: ./server/.env` 让 Worker 读到 `.env` 里的 API Key。

---

## 8. Tripo3D API 返回 307 / 404

**原因**：API 从 v1 升到 v2，端点路径从 `/tasks` 变为 `/v2/openapi/task`。

**解决**：更新 `tripo3d.py` 的 BASE_URL 为 `https://api.tripo3d.ai/v2/openapi`。

---

## 9. 报错 `'Trimesh' object has no attribute 'boundaries'`

**原因**：trimesh 4.5 版本移除了 `boundaries` 属性。

**解决**：`defect_detector.py` 中 `mesh.boundaries` 访问包在 try/except AttributeError 中。

---

## 10. 报错 `Unable to allocate 34.0 GiB for an array`

**原因**：`edges_sparse.toarray()` 将 N×N 稀疏矩阵转为稠密数组。N=190979 时需 34GB。

**解决**：用 `edges_sparse.sum(axis=1)` 直接在稀疏结构上计算，不转稠密。内存从 34GB 降到 ~2MB。

---

## 11. 50 万面大模型 OOM (SIGKILL)

**原因**：缺陷检测对超大型模型（>10 万面）耗内存过大。

**解决**：`detect_all()` 中面数 > 10 万时先降采样到 5 万再检测，原始高面模型导出不受影响。

---

## 12. `async with' outside async function` (SyntaxError)

**原因**：Celery 同步任务中直接写 `async with`。

**解决**：Celery 任务改用同步 DB 会话（`SyncSession`），去掉 `asyncio.new_event_loop()`。

---

## 13. `Future attached to a different loop`

**原因**：`async_session` 绑定了主线程事件循环，Celery 中 `asyncio.new_event_loop()` 创建了新循环，两者冲突。

**解决**：`database.py` 增加 `SyncSession`（基于 psycopg2），Celery 任务全部用同步会话。

---

## 14. `ModuleNotFoundError: No module named 'protobuf'`

**原因**：`transformers` 库依赖 `protobuf` 但未声明。

**解决**：`requirements.txt` 显式添加 `protobuf`。

---

## 15. HuggingFace / hf-mirror 下载模型超时

**原因**：Docker 容器网络无法访问 HuggingFace 和 hf-mirror.com。

**解决**：`cache_mgr.py` 改为懒加载——Sentence-BERT 模型在首次使用时才下载，失败则降级为纯 MD5 精确匹配缓存。

---

## 16. 生成的文件在哪 / 前端找不到模型

**原因**：Worker 写到 Docker 命名卷 `/data/`，与 Windows 文件系统隔离。

**解决**：修改 `config.py` 默认 `DATA_DIR="./data"`，Worker CWD 为 `/app`，挂载到 `server/`，两边统一到 `server/data/`。

---

## 17. Alembic 报错 `KeyError: 'handlers'`（logger 段缺少 handlers/qualname）

**原因**：`alembic.ini` 的 `[logger_root]`、`[logger_sqlalchemy]`、`[logger_alembic]` 各段中只有 `level`，缺少 `handlers` 和 `qualname`。Python `logging.config.fileConfig()` 要求每个 logger 段必须指定这两个键。

**解决**：给每个 logger 段补全：
```ini
[logger_root]
level = WARN
handlers = console
qualname = root

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic
```
`handlers = console` 让 root logger 输出到控制台；sqlalchemy 和 alembic 的 `handlers` 留空，避免重复输出。

---

## 18. Alembic 报错 `FileNotFoundError: script.py.mako`

**原因**：`alembic.ini` 从 `server/alembic/` 移到 `server/` 后，`script_location = alembic` 指向的 `alembic/` 目录中缺少 `script.py.mako` 模板文件和 `versions/` 目录。

**解决**：在 `alembic/` 目录下补上两个文件：
- `script.py.mako` — Mako 模板，Alembic 生成迁移文件时使用
- `versions/` — 存放生成的迁移版本文件

这两个文件可通过 `alembic init alembic` 在新目录生成后复制过来，或直接手动创建。
