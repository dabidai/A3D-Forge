"""
Tripo3D 商用API客户端（文生3D / 图生3D）。

API文档: https://platform.tripo3d.ai

调用流程:
  1. POST /tasks 提交生成任务（prompt / image）
  2. 轮询 GET /tasks/{task_id} 等待完成（最长10分钟，每5秒一次）
  3. 下载GLB模型到本地 {DATA_DIR}/assets/{asset_id}/

费用: 约 $0.5-2/次，阶段一验证期预估 200-500 次/月
"""
import time
import httpx
from pathlib import Path
from loguru import logger

from app.core.config import settings


class Tripo3DClient:
    """
    Tripo3D API 客户端（单例）。

    支持:
      - text_to_3d(prompt, negative_prompt, style, output_dir) → 文生3D
      - image_to_3d(image_path, output_dir)                → 图生3D
    """

    def __init__(self):
        self.api_key = settings.TRIPO3D_API_KEY
        self.base_url = settings.TRIPO3D_API_URL
        # httpx.Client 复用HTTP连接，超时300s适配长轮询
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=300,
            follow_redirects=True,
        )

    def text_to_3d(
        self,
        prompt: str,
        negative_prompt: str = "",
        style: str = "realistic",
        output_dir: Path | None = None,
    ) -> dict:
        """
        提交文生3D任务 → 轮询完成 → 下载模型。

        参数:
            prompt:          优化后的正负向提示词
            negative_prompt: 负向提示词
            style:           风格 (realistic/cartoon/low_poly/sculpture)
            output_dir:      模型输出目录（若为None则不下载）

        返回:
            { task_id: str, model_url: str, format: str, face_count: int, local_path: str|None }
        """
        # 1. 提交任务
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "style": style,
            "output_format": "glb",
        }
        resp = self._client.post("/tasks", json=payload)
        resp.raise_for_status()
        data = resp.json()
        task_id = data["data"]["task_id"]
        logger.info(f"Tripo3D task submitted: {task_id}")

        # 2. 轮询等待完成
        result = self._poll_task(task_id)

        # 3. 下载模型GLB文件
        model_url = result["data"]["output"]["model_url"]
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            model_path = output_dir / f"{task_id}.glb"
            self._download(model_url, model_path)
            result["local_path"] = str(model_path)

        return {
            "task_id": task_id,
            "model_url": model_url,
            "format": result["data"]["output"].get("format", "glb"),
            "face_count": result["data"].get("face_count", 0),
            "local_path": result.get("local_path"),
        }

    def image_to_3d(
        self,
        image_path: str,
        prompt: str = "",
        output_dir: Path | None = None,
    ) -> dict:
        """
        提交图生3D任务 → 上传图片 → 轮询完成 → 下载模型。

        参数:
            image_path: 本地图片路径（PNG/JPG）
            prompt:     可选的补充提示词
            output_dir: 模型输出目录

        返回:
            { task_id, model_url, format, face_count, local_path }
        """
        # 1. 上传图片到Tripo3D，获取file_id
        with open(image_path, "rb") as f:
            upload_resp = self._client.post(
                "/files",
                files={"file": (Path(image_path).name, f, "image/png")},
            )
        upload_resp.raise_for_status()
        file_id = upload_resp.json()["data"]["file_id"]
        logger.info(f"Tripo3D file uploaded: {file_id}")

        # 2. 提交图生3D任务
        payload = {
            "type": "image_to_model",
            "file_id": file_id,
            "prompt": prompt,
            "output_format": "glb",
        }
        resp = self._client.post("/tasks", json=payload)
        resp.raise_for_status()
        data = resp.json()
        task_id = data["data"]["task_id"]
        logger.info(f"Tripo3D image-to-3d task submitted: {task_id}")

        result = self._poll_task(task_id)

        # 3. 下载模型
        model_url = result["data"]["output"]["model_url"]
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            model_path = output_dir / f"{task_id}.glb"
            self._download(model_url, model_path)
            result["local_path"] = str(model_path)

        return {
            "task_id": task_id,
            "model_url": model_url,
            "format": result["data"]["output"].get("format", "glb"),
            "face_count": result["data"].get("face_count", 0),
            "local_path": result.get("local_path"),
        }

    def _poll_task(self, task_id: str, max_wait: int = 600, interval: int = 5) -> dict:
        """
        轮询任务状态直到 completed/failed。

        参数:
            task_id:  Tripo3D任务ID
            max_wait: 最大等待秒数（默认600s = 10分钟）
            interval: 轮询间隔秒数（默认5s）

        返回:
            API完整响应JSON（status=completed时）

        异常:
            RuntimeError: 任务失败 (status=failed)
            TimeoutError: 超时未完成
        """
        start = time.time()
        while time.time() - start < max_wait:
            resp = self._client.get(f"/tasks/{task_id}")
            resp.raise_for_status()
            data = resp.json()
            status = data["data"]["status"]
            if status == "completed":
                return data
            if status == "failed":
                raise RuntimeError(f"Tripo3D task failed: {data.get('error', 'unknown')}")
            time.sleep(interval)
        raise TimeoutError(f"Tripo3D task {task_id} timed out after {max_wait}s")

    def _download(self, url: str, path: Path):
        """从URL下载文件到本地路径。"""
        with httpx.Client() as dl_client:
            resp = dl_client.get(url)
            resp.raise_for_status()
            path.write_bytes(resp.content)
            logger.info(f"Model downloaded: {path} ({len(resp.content)} bytes)")

    def health_check(self) -> bool:
        """检查API连通性。"""
        try:
            self._client.get("/health")
            return True
        except Exception:
            return False


# 全局单例
tripo3d_client = Tripo3DClient()
