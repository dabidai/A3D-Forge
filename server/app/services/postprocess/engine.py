"""
3D后处理引擎：基于 Trimesh + PyMeshLab 实现自动轻修复 + 多格式导出。

核心功能:
  - load_model(path)                    → 加载GLB/FBX/OBJ模型
  - auto_light_repair(mesh)            → 5步自动轻修复（孔洞/法线/孤立顶点/重合顶点/水密）
  - export_formats(mesh, dir, name)    → 导出 GLB + FBX + OBJ 多格式
  - get_mesh_stats(mesh)               → 获取面数/顶点数/水密性/包围盒等统计
  - generate_preview_image(mesh, path) → 渲染800x600 PNG预览图
  - decimate(mesh, target_faces)      → 减面生成轻量预览模型

修复策略（阶段一）:
  - 轻微缺陷（孔洞<包围盒5%/法线翻转/孤立顶点/重合面）→ 自动修复
  - 复杂缺陷（非流形/UV错乱/大面积孔洞）→ 标注后流转人工修复

工具栈: Trimesh(几何处理) + PyMeshLab(高级修复) + NumPy(数值计算)
"""
import numpy as np
import trimesh
import pymeshlab
from pathlib import Path
from loguru import logger

from app.core.config import settings


class PostProcessEngine:
    """
    3D模型后处理引擎。

    阶段一实现自动轻修复+缺陷标注双路径:
      轻缺陷 → 自动修复管线
      重缺陷 → 分类标注 → 流转LLM分析 → 人工修复

    修复管线（5步）:
      1. 小孔洞填充（直径 < 包围盒对角线5%）
      2. 法线方向一致性修正
      3. 孤立顶点清理
      4. 重合顶点合并
      5. 基础水密修复
    """

    # 轻修复阈值
    SMALL_HOLE_MAX_RATIO = 0.05       # 孔洞直径 < 包围盒对角5% → 自动填充
    ISOLATED_VERTEX_DISTANCE = 0.0001 # 孤立顶点判定距离

    def __init__(self):
        pass

    def load_model(self, path: str) -> trimesh.Trimesh:
        """
        加载3D模型文件。

        参数:
            path: 模型文件路径（GLB/FBX/OBJ/STL）

        返回:
            trimesh.Trimesh 对象
        """
        mesh = trimesh.load(path, force="mesh")
        logger.info(f"Loaded mesh: {path}, faces={len(mesh.faces)}, vertices={len(mesh.vertices)}")
        return mesh

    def auto_light_repair(self, mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, dict]:
        """
        自动轻修复管线（5步）。

        参数:
            mesh: Trimesh 网格对象

        返回:
            (修复后的mesh, 修复报告)
            报告结构: { original_faces, repairs: [{type, count, details}, ...], final_faces }
        """
        report = {"original_faces": len(mesh.faces), "repairs": []}

        # 1. 自动填充小孔洞（PyMeshLab实现）
        holes = self._detect_holes(mesh)
        small_holes = [h for h in holes if h["ratio"] < self.SMALL_HOLE_MAX_RATIO]
        if small_holes:
            mesh = self._fill_small_holes_pymeshlab(Path("_temp.obj"), small_holes)
            report["repairs"].append({
                "type": "hole_filling",
                "count": len(small_holes),
                "details": [{"boundary_edges": h["boundary_edges"]} for h in small_holes],
            })

        # 2. 法线方向一致性修正
        mesh.fix_normals()
        report["repairs"].append({"type": "normal_fix"})

        # 3. 移除孤立顶点
        mesh.remove_unreferenced_vertices()
        report["repairs"].append({"type": "remove_isolated_vertices"})

        # 4. 合并重合顶点（精度0.0001）
        mesh.merge_vertices(digits_vertex=4)
        report["repairs"].append({"type": "merge_duplicate_vertices"})

        # 5. 基础水密修复（Trimesh内置fill_holes）
        if not mesh.is_watertight:
            try:
                mesh.fill_holes()
                report["repairs"].append({"type": "watertight_fill"})
            except Exception as e:
                logger.warning(f"Watertight fill failed: {e}")

        report["final_faces"] = len(mesh.faces)
        logger.info(f"Auto repair complete: {report['original_faces']} → {report['final_faces']} faces")
        return mesh, report

    def export_formats(self, mesh: trimesh.Trimesh, output_dir: Path, name: str) -> dict[str, str]:
        """
        导出多格式模型文件。

        参数:
            mesh:       Trimesh网格对象
            output_dir: 输出目录
            name:       文件名（不含后缀）

        返回:
            { glb: path, fbx: path, obj: path }
            FBX导出失败时该键不存在（Trimesh的FBX支持有限）
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        formats = {}
        # GLB
        glb_path = output_dir / f"{name}.glb"
        mesh.export(glb_path)
        formats["glb"] = str(glb_path)

        # OBJ
        obj_path = output_dir / f"{name}.obj"
        mesh.export(obj_path)
        formats["obj"] = str(obj_path)

        # FBX（Trimesh支持有限，导出失败不阻塞）
        fbx_path = output_dir / f"{name}.fbx"
        try:
            mesh.export(fbx_path)
            formats["fbx"] = str(fbx_path)
        except Exception as e:
            logger.warning(f"FBX export failed: {e}")

        return formats

    def get_mesh_stats(self, mesh: trimesh.Trimesh) -> dict:
        """
        提取模型基础统计信息。

        参数:
            mesh: Trimesh网格对象

        返回:
            {
              face_count: int,      # 三角面数
              vertex_count: int,    # 顶点数
              is_watertight: bool,  # 是否水密
              is_empty: bool,       # 是否空模型
              bounding_box: list,   # 包围盒坐标 [[min_x,min_y,min_z],[max_x,max_y,max_z]]
              center_mass: list,    # 质心坐标 [x,y,z]
              area: float,          # 表面积
            }
        """
        return {
            "face_count": len(mesh.faces),
            "vertex_count": len(mesh.vertices),
            "is_watertight": mesh.is_watertight,
            "is_empty": mesh.is_empty,
            "bounding_box": mesh.bounds.tolist(),
            "center_mass": mesh.center_mass.tolist(),
            "area": float(mesh.area),
        }

    def generate_preview_image(self, mesh: trimesh.Trimesh, output_path: str):
        """
        生成模型预览图（Trimesh内置光栅化渲染）。

        参数:
            mesh:        Trimesh网格对象
            output_path: 输出PNG路径

        输出: 800x600 RGB PNG
        """
        try:
            scene = trimesh.Scene(mesh)
            png = scene.save_image(resolution=[800, 600])
            Path(output_path).write_bytes(png)
            logger.info(f"Preview image saved: {output_path}")
        except Exception as e:
            logger.warning(f"Preview generation failed: {e}")

    def decimate(self, mesh: trimesh.Trimesh, target_faces: int = 10000) -> trimesh.Trimesh:
        """
        减面生成轻量预览/低模代理。

        参数:
            mesh:         Trimesh网格对象
            target_faces: 目标面数

        返回:
            减面后的Trimesh网格（若原始面数<=目标则返回原mesh）
        """
        if len(mesh.faces) <= target_faces:
            return mesh
        ratio = target_faces / len(mesh.faces)
        return mesh.simplify_quadratic_decimation(len(mesh.faces) - target_faces)

    def _detect_holes(self, mesh: trimesh.Trimesh) -> list[dict]:
        """检测模型孔洞，返回孔洞信息列表。"""
        holes = []
        try:
            boundaries = mesh.boundaries
        except AttributeError:
            return holes
        bbox_diag = np.linalg.norm(mesh.bounds[1] - mesh.bounds[0])
        for boundary in boundaries:
            edges = boundary.entities
            hole_diag = np.linalg.norm(boundary.bounds[1] - boundary.bounds[0]) if len(boundary.bounds) > 0 else 0
            holes.append({
                "boundary_edges": len(edges),
                "ratio": hole_diag / bbox_diag if bbox_diag > 0 else 0,  # 孔洞直径 / 包围盒对角线
            })
        return holes

    def _fill_small_holes_pymeshlab(self, temp_path: Path, holes: list) -> trimesh.Trimesh:
        """使用PyMeshLab填充小孔洞（Trimesh内置方法对有复杂边界的孔洞效果不好）。"""
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(temp_path))
        ms.meshing_close_holes(maxholesize=int(max(h["boundary_edges"] for h in holes)))
        ms.save_current_mesh(str(temp_path))
        return trimesh.load(temp_path, force="mesh")


# 全局单例
post_process_engine = PostProcessEngine()
