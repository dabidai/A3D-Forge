"""
3D后处理引擎：基于Trimesh + PyMeshLab 实现自动轻修复 + 多格式导出。
"""
import numpy as np
import trimesh
import pymeshlab
from pathlib import Path
from loguru import logger

from app.core.config import settings


class PostProcessEngine:
    """
    阶段一后处理：自动轻修复 + 缺陷标注双路径。
    轻微缺陷自动修复，复杂缺陷标注后流转人工。
    """

    # 轻修复阈值
    SMALL_HOLE_MAX_RATIO = 0.05  # 孔洞直径 < 包围盒对角5%
    ISOLATED_VERTEX_DISTANCE = 0.0001  # 孤立顶点判定距离

    def __init__(self):
        pass

    def load_model(self, path: str) -> trimesh.Trimesh:
        mesh = trimesh.load(path, force="mesh")
        logger.info(f"Loaded mesh: {path}, faces={len(mesh.faces)}, vertices={len(mesh.vertices)}")
        return mesh

    def auto_light_repair(self, mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, dict]:
        """
        自动轻修复：小孔洞填充、法线翻转修正、孤立顶点清理、重合面清理。
        返回 (修复后的mesh, 修复报告)
        """
        report = {"original_faces": len(mesh.faces), "repairs": []}

        # 1. 填充小孔洞
        holes = self._detect_holes(mesh)
        small_holes = [h for h in holes if h["ratio"] < self.SMALL_HOLE_MAX_RATIO]
        if small_holes:
            mesh = self._fill_small_holes_pymeshlab(Path("_temp.obj"), small_holes)
            report["repairs"].append({
                "type": "hole_filling",
                "count": len(small_holes),
                "details": [{"boundary_edges": h["boundary_edges"]} for h in small_holes],
            })

        # 2. 法线一致性修正
        mesh.fix_normals()
        report["repairs"].append({"type": "normal_fix"})

        # 3. 清理孤立顶点
        mesh.remove_unreferenced_vertices()
        report["repairs"].append({"type": "remove_isolated_vertices"})

        # 4. 合并重合顶点
        mesh.merge_vertices(digits_vertex=4)
        report["repairs"].append({"type": "merge_duplicate_vertices"})

        # 5. 基础水密修复 (Trimesh内置)
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
        """导出 GLB/FBX/OBJ 多格式"""
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

        # FBX (Trimesh supports)
        fbx_path = output_dir / f"{name}.fbx"
        try:
            mesh.export(fbx_path)
            formats["fbx"] = str(fbx_path)
        except Exception as e:
            logger.warning(f"FBX export failed: {e}")

        return formats

    def get_mesh_stats(self, mesh: trimesh.Trimesh) -> dict:
        """提取模型基础统计信息"""
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
        """生成模型预览图（使用Trimesh内置光栅化）"""
        try:
            scene = trimesh.Scene(mesh)
            png = scene.save_image(resolution=[800, 600])
            Path(output_path).write_bytes(png)
            logger.info(f"Preview image saved: {output_path}")
        except Exception as e:
            logger.warning(f"Preview generation failed: {e}")

    def decimate(self, mesh: trimesh.Trimesh, target_faces: int = 10000) -> trimesh.Trimesh:
        """减面生成轻量预览模型"""
        if len(mesh.faces) <= target_faces:
            return mesh
        ratio = target_faces / len(mesh.faces)
        return mesh.simplify_quadratic_decimation(len(mesh.faces) - target_faces)

    def _detect_holes(self, mesh: trimesh.Trimesh) -> list[dict]:
        """检测并分类孔洞"""
        holes = []
        bbox_diag = np.linalg.norm(mesh.bounds[1] - mesh.bounds[0])
        for boundary in mesh.boundaries:
            edges = boundary.entities
            hole_diag = np.linalg.norm(boundary.bounds[1] - boundary.bounds[0]) if len(boundary.bounds) > 0 else 0
            holes.append({
                "boundary_edges": len(edges),
                "ratio": hole_diag / bbox_diag if bbox_diag > 0 else 0,
            })
        return holes

    def _fill_small_holes_pymeshlab(self, temp_path: Path, holes: list) -> trimesh.Trimesh:
        """使用PyMeshLab填充小孔洞"""
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(temp_path))
        ms.meshing_close_holes(maxholesize=int(max(h["boundary_edges"] for h in holes)))
        ms.save_current_mesh(str(temp_path))
        return trimesh.load(temp_path, force="mesh")


post_process_engine = PostProcessEngine()
