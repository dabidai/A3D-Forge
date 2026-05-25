"""
缺陷检测器：自动检测、分类、定级模型缺陷。
"""
import numpy as np
import trimesh
from loguru import logger


class DefectDetector:
    """
    检测3D模型的各类缺陷：
    - 拓扑混乱 (非流形边/顶点)
    - UV错乱 (UV岛重叠、越界)
    - 非流形结构
    - 孤立面/顶点
    - 法线异常
    """

    def detect_all(self, mesh: trimesh.Trimesh) -> list[dict]:
        """全量缺陷检测，返回缺陷列表"""
        defects = []

        defects.extend(self.detect_non_manifold(mesh))
        defects.extend(self.detect_degenerate_faces(mesh))
        defects.extend(self.detect_inconsistent_normals(mesh))
        defects.extend(self.detect_isolated_components(mesh))

        logger.info(f"Defect detection complete: {len(defects)} defects found")
        return defects

    def detect_non_manifold(self, mesh: trimesh.Trimesh) -> list[dict]:
        """非流形边/顶点检测"""
        defects = []
        # 非流形边（连接面数!=2）
        non_manifold_edges = mesh.edges[
            np.where(mesh.edges_sparse.toarray().sum(axis=1) != 2)[0]
        ] if hasattr(mesh, 'edges_sparse') and mesh.edges_sparse is not None else []
        if len(non_manifold_edges) > 0:
            defects.append({
                "type": "non_manifold_edge",
                "level": "severe",
                "description": f"发现 {len(non_manifold_edges)} 条非流形边",
                "repairable": False,
                "count": len(non_manifold_edges),
            })

        # 非流形顶点
        if hasattr(mesh, 'vertex_defects'):
            vd = mesh.vertex_defects
            if vd is not None and np.any(vd > 0):
                count = int(np.sum(vd > 0))
                defects.append({
                    "type": "non_manifold_vertex",
                    "level": "severe",
                    "description": f"发现 {count} 个非流形顶点",
                    "repairable": False,
                    "count": count,
                })
        return defects

    def detect_degenerate_faces(self, mesh: trimesh.Trimesh) -> list[dict]:
        """退化面检测（零面积三角形、极短边）"""
        defects = []
        areas = mesh.area_faces
        if areas is not None and len(areas) > 0:
            zero_area_mask = areas < 1e-12
            if np.any(zero_area_mask):
                count = int(np.sum(zero_area_mask))
                defects.append({
                    "type": "degenerate_face",
                    "level": "moderate",
                    "description": f"发现 {count} 个退化面（零面积三角形）",
                    "repairable": True,
                    "count": count,
                })
        return defects

    def detect_inconsistent_normals(self, mesh: trimesh.Trimesh) -> list[dict]:
        """法线方向异常检测"""
        defects = []
        if mesh.face_normals is not None:
            # 检查是否有大幅偏离相邻面法线的面
            if hasattr(mesh, 'face_adjacency_angles') and mesh.face_adjacency_angles is not None:
                angles = mesh.face_adjacency_angles
                if len(angles) > 0:
                    inverted = np.sum(angles > np.pi / 2)
                    if inverted > 0:
                        defects.append({
                            "type": "inverted_normal",
                            "level": "mild",
                            "description": f"发现 {inverted} 处法线翻转或大角度偏移",
                            "repairable": True,
                            "count": int(inverted),
                        })
        return defects

    def detect_isolated_components(self, mesh: trimesh.Trimesh) -> list[dict]:
        """孤立面/顶点检测"""
        defects = []
        split = mesh.split(only_watertight=False)
        if len(split) > 1:
            main = max(split, key=lambda m: len(m.faces))
            for i, comp in enumerate(split):
                if comp is main:
                    continue
                if len(comp.faces) < 10:
                    defects.append({
                        "type": "isolated_component",
                        "level": "mild",
                        "description": f"孤立碎片: {len(comp.faces)} 面",
                        "repairable": True,
                        "count": len(comp.faces),
                    })
                else:
                    defects.append({
                        "type": "disconnected_component",
                        "level": "moderate",
                        "description": f"分离组件: {len(comp.faces)} 面",
                        "repairable": False,
                        "count": len(comp.faces),
                    })
        return defects

    def classify_severity(self, defects: list[dict]) -> dict:
        """对缺陷汇总定级"""
        sev_count = {"mild": 0, "moderate": 0, "severe": 0}
        for d in defects:
            sev_count[d.get("level", "mild")] += 1
        if sev_count["severe"] > 0:
            overall = "severe"
        elif sev_count["moderate"] > 2:
            overall = "moderate"
        else:
            overall = "mild"
        return {"overall": overall, "breakdown": sev_count, "total": sum(sev_count.values())}


defect_detector = DefectDetector()
