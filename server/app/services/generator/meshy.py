"""
Meshy AI 商用API客户端：图生3D + PBR材质生成。
"""
import time
import httpx
from pathlib import Path
from loguru import logger

from app.core.config import settings


class MeshyClient:
    def __init__(self):
        self.api_key = settings.MESHY_API_KEY
        self.base_url = settings.MESHY_API_URL
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=300,
        )

    def image_to_3d(
        self,
        image_path: str,
        output_dir: Path | None = None,
    ) -> dict:
        """
        提交图生3D任务并轮询等待完成。
        返回包含model路径和PBR材质路径的字典。
        """
        # 上传图片后提交任务
        with open(image_path, "rb") as f:
            upload_resp = self._client.post(
                "/files",
                files={"file": (Path(image_path).name, f, "image/png")},
            )
        upload_resp.raise_for_status()
        file_id = upload_resp.json()["data"]["file_id"]

        payload = {
            "image_url": file_id,
            "output_format": "glb",
            "enable_pbr": True,
        }
        resp = self._client.post("/image-to-3d", json=payload)
        resp.raise_for_status()
        task_id = resp.json()["data"]["task_id"]
        logger.info(f"Meshy task submitted: {task_id}")

        result = self._poll_task(task_id)

        output_dir = Path(output_dir or settings.ASSETS_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 下载模型
        model_url = result["data"]["output"]["model_url"]
        model_path = output_dir / f"{task_id}.glb"
        self._download(model_url, model_path)

        # 下载PBR材质
        pbr_paths = {}
        pbr_maps = result["data"]["output"].get("pbr_materials", {})
        for map_type, url in pbr_maps.items():
            tex_path = output_dir / f"{task_id}_{map_type}.png"
            self._download(url, tex_path)
            pbr_paths[map_type] = str(tex_path)

        return {
            "task_id": task_id,
            "model_path": str(model_path),
            "pbr_materials": pbr_paths,
            "face_count": result["data"].get("face_count", 0),
        }

    def _poll_task(self, task_id: str, max_wait: int = 600, interval: int = 5) -> dict:
        start = time.time()
        while time.time() - start < max_wait:
            resp = self._client.get(f"/tasks/{task_id}")
            resp.raise_for_status()
            data = resp.json()
            status = data["data"]["status"]
            if status == "completed":
                return data
            if status == "failed":
                raise RuntimeError(f"Meshy task failed: {data.get('error', 'unknown')}")
            time.sleep(interval)
        raise TimeoutError(f"Meshy task {task_id} timed out after {max_wait}s")

    def _download(self, url: str, path: Path):
        with httpx.Client() as dl_client:
            resp = dl_client.get(url)
            resp.raise_for_status()
            path.write_bytes(resp.content)
            logger.info(f"Downloaded: {path}")


meshy_client = MeshyClient()
