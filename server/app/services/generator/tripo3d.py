"""
Tripo3D 商用API客户端（httpx + REST API）。

API文档: https://platform.tripo3d.ai
API基础路径: https://api.tripo3d.ai/v2/openapi
"""
import time
import httpx
from pathlib import Path
from loguru import logger

from app.core.config import settings


class Tripo3DClient:
    """Tripo3D API 客户端（单例）。"""

    BASE_URL = "https://api.tripo3d.ai/v2/openapi"

    def __init__(self):
        self.api_key = settings.TRIPO3D_API_KEY
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=300,
        )

    def text_to_3d(
        self,
        prompt: str,
        negative_prompt: str = "",
        style: str = "realistic",
        output_dir: Path | None = None,
    ) -> dict:
        """提交文生3D任务 → 轮询完成 → 下载模型。"""
        # 1. 提交任务
        payload = {"type": "text_to_model", "prompt": prompt}
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if style:
            payload["style"] = style

        resp = self._client.post("/task", json=payload)
        resp.raise_for_status()
        task_id = resp.json()["data"]["task_id"]
        logger.info(f"Tripo3D task submitted: {task_id}")

        # 2. 轮询等待完成
        result = self._poll_task(task_id)

        # 3. 下载模型
        output = result["data"]["output"]
        model_url = output.get("model") or output.get("pbr_model")
        face_count = result["data"].get("face_count", 0)
        local_path = None

        if output_dir and model_url:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            model_path = output_dir / f"{task_id}.glb"
            self._download(model_url, model_path)
            local_path = str(model_path)

        return {
            "task_id": task_id,
            "model_url": model_url,
            "format": "glb",
            "face_count": face_count,
            "local_path": local_path,
        }

    def image_to_3d(
        self,
        image_path: str,
        prompt: str = "",
        output_dir: Path | None = None,
    ) -> dict:
        """提交图生3D任务 → 轮询完成 → 下载模型。"""
        # SDK 源码: 图片需先上传获取 file_token
        # 阶段一优先文生3D，图生3D暂用简化路径
        with open(image_path, "rb") as f:
            file_resp = self._client.post(
                "/upload/sts/token",
                json={"format": "jpeg"},
            )
            file_resp.raise_for_status()

        # 暂不支持图生3D的完整STS上传流程，回退到简单的直接上传
        logger.warning("Image-to-3D via REST is complex; consider using text-to-3D for now")
        raise NotImplementedError("Image-to-3D REST path not yet implemented; use text-to-3D")

    def _poll_task(self, task_id: str, max_wait: int = 600, interval: int = 5) -> dict:
        """轮询任务状态直到 success/failed，网络错误自动重试。"""
        start = time.time()
        net_errors = 0
        while time.time() - start < max_wait:
            try:
                resp = self._client.get(f"/task/{task_id}")
                resp.raise_for_status()
                net_errors = 0  # 成功后重置
                data = resp.json()
                status = data["data"]["status"]
                if status == "success":
                    return data
                if status == "failed":
                    raise RuntimeError(f"Tripo3D task failed: {data['data'].get('error', 'unknown')}")
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as e:
                net_errors += 1
                if net_errors > 5:
                    raise RuntimeError(f"Tripo3D poll failed after {net_errors} network errors: {e}")
                logger.warning(f"Tripo3D poll network error ({net_errors}/5), retrying in 10s: {e}")
                time.sleep(10)
                continue
            time.sleep(interval)
        raise TimeoutError(f"Tripo3D task {task_id} timed out after {max_wait}s")

    def _download(self, url: str, path: Path):
        """从URL下载文件到本地路径。"""
        resp = self._client.get(url)
        resp.raise_for_status()
        path.write_bytes(resp.content)
        logger.info(f"Model downloaded: {path} ({len(resp.content)} bytes)")

    def health_check(self) -> bool:
        try:
            return bool(self.api_key)
        except Exception:
            return False


tripo3d_client = Tripo3DClient()
