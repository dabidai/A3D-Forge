"""
Meshy AI 商用API客户端（图生3D + PBR材质生成）。

API文档: https://docs.meshy.ai

调用流程:
  1. 上传图片获取临时URL
  2. POST /image-to-3d 提交生成任务（enable_pbr=True 生成四通道PBR贴图）
  3. 轮询 GET /image-to-3d/{task_id} 等待完成
  4. 下载GLB模型 + PBR贴图到本地

与Tripo3D的区别:
  - Meshy专精图生3D，PBR材质质量更高
  - 支持 enable_pbr 生成标准四通道贴图（baseColor/metallic/roughness/normal）

降级策略:
  当 MESHY_API_KEY 未配置时，generate_tasks.py 中的 image_to_3d_task 自动使用Tripo3D

费用: 约 $1-5/次，阶段一验证期预估 200-500 次/月
"""
import time
import httpx
from pathlib import Path
from loguru import logger

from app.core.config import settings


class MeshyClient:
    """
    Meshy AI API 客户端（单例）。

    支持:
      - image_to_3d(image_path, enable_pbr, output_dir) → 图生3D + PBR材质
    """

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
            follow_redirects=True,
        )

    def image_to_3d(
        self,
        image_path: str,
        enable_pbr: bool = True,
        output_dir: Path | None = None,
    ) -> dict:
        """
        图生3D：上传图片 → 生成模型 + PBR材质 → 下载到本地。

        参数:
            image_path: 本地图片路径
            enable_pbr: 是否生成PBR材质（默认True，生成四通道贴图）
            output_dir: 模型输出目录

        返回:
            { task_id: str, model_url: str, model_path: str, pbr_material_paths: {name: path} }
        """
        output_dir = Path(output_dir) if output_dir else None
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

        # 1. 上传图片获取临时URL
        image_url = self._upload_image(image_path)

        # 2. 提交图生3D任务
        payload = {
            "image_url": image_url,
            "enable_pbr": enable_pbr,
        }
        resp = self._client.post("/image-to-3d", json=payload)
        resp.raise_for_status()
        data = resp.json()
        task_id = data["result"]
        logger.info(f"Meshy image-to-3d task submitted: {task_id}")

        # 3. 轮询等待完成
        result = self._poll_task(task_id)

        # 4. 下载模型 + PBR贴图
        model_url = result.get("model_url") or result.get("model_urls", {}).get("glb")
        pbr_urls = result.get("pbr_material_urls", {})

        local_result = {"task_id": task_id, "pbr_material_paths": {}}

        if model_url and output_dir:
            model_path = output_dir / f"{task_id}.glb"
            self._download(model_url, model_path)
            local_result["model_path"] = str(model_path)
            local_result["model_url"] = model_url
        else:
            local_result["model_url"] = model_url

        # 下载PBR贴图（baseColor/metallic/roughness/normal）
        if pbr_urls and output_dir:
            pbr_dir = output_dir / "pbr"
            pbr_dir.mkdir(exist_ok=True)
            for name, url in pbr_urls.items():
                tex_path = pbr_dir / f"{name}.png"
                self._download(url, tex_path)
                local_result["pbr_material_paths"][name] = str(tex_path)

        return local_result

    def _upload_image(self, image_path: str) -> str:
        """上传图片到Meshy，返回临时URL。"""
        with open(image_path, "rb") as f:
            resp = self._client.post(
                "/image-to-3d",
                files={"image_file": (Path(image_path).name, f)},
            )
        resp.raise_for_status()
        data = resp.json()
        return data.get("image_url", "")

    def _poll_task(self, task_id: str, max_wait: int = 600, interval: int = 5) -> dict:
        """
        轮询Meshy任务状态。

        状态枚举: IN_QUEUE → IN_PROGRESS → SUCCEEDED / FAILED / EXPIRED

        参数:
            task_id:  Meshy任务ID
            max_wait: 最大等待秒数（默认600s）
            interval: 轮询间隔秒数（默认5s）

        返回:
            API完整响应JSON（status=SUCCEEDED时，含model_urls和pbr_material_urls）
        """
        start = time.time()
        while time.time() - start < max_wait:
            resp = self._client.get(f"/image-to-3d/{task_id}")
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            if status == "SUCCEEDED":
                return data
            if status in ("FAILED", "EXPIRED"):
                raise RuntimeError(f"Meshy task failed: status={status}")
            time.sleep(interval)
        raise TimeoutError(f"Meshy task {task_id} timed out after {max_wait}s")

    def _download(self, url: str, path: Path):
        """从URL下载文件到本地路径。"""
        with httpx.Client() as dl_client:
            resp = dl_client.get(url)
            resp.raise_for_status()
            path.write_bytes(resp.content)
            logger.info(f"Downloaded: {path} ({len(resp.content)} bytes)")

    @property
    def configured(self) -> bool:
        """检查是否配置了API Key（MESHY_API_KEY非空）。"""
        return bool(self.api_key)

    def health_check(self) -> bool:
        """检查API连通性。"""
        if not self.configured:
            return False
        try:
            resp = self._client.get("/image-to-3d?limit=1")
            return resp.status_code < 500
        except Exception:
            return False


# 全局单例
meshy_client = MeshyClient()
