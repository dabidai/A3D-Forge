"""
Tripo3D 商用API客户端：文生3D。
"""
import time
import httpx
from pathlib import Path
from loguru import logger

from app.core.config import settings


class Tripo3DClient:
    def __init__(self):
        self.api_key = settings.TRIPO3D_API_KEY
        self.base_url = settings.TRIPO3D_API_URL
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=300,
        )

    def text_to_3d(
        self,
        prompt: str,
        negative_prompt: str = "",
        style: str = "realistic",
        output_dir: Path | None = None,
    ) -> dict:
        """
        提交文生3D任务并轮询等待完成。
        返回 {"task_id": str, "model_path": str, "format": str, "face_count": int}
        """
        # 提交任务
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

        # 轮询等待
        result = self._poll_task(task_id)

        # 下载模型
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
        """轮询任务状态直到完成"""
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
        with httpx.Client() as dl_client:
            resp = dl_client.get(url)
            resp.raise_for_status()
            path.write_bytes(resp.content)
            logger.info(f"Model downloaded: {path} ({len(resp.content)} bytes)")

    def health_check(self) -> bool:
        try:
            self._client.get("/health")
            return True
        except Exception:
            return False


tripo3d_client = Tripo3DClient()
