"""
3D模型缺陷检测器：自动检测、分类、定级。

检测类型（4类）:
  1. 非流形边/顶点检测    — 边连接面数 != 2 的拓扑异常 → 等级: severe
  2. 退化面检测           — 零面积三角形或极短边 → 等级: moderate
  3. 法线异常检测         — 相邻面法线夹角 > 90° → 等级: mild
  4. 孤立组件检测         — 脱离主体的碎片/分离面片 → 等级: mild~moderate

评级规则:
  - severe > 0    → overall = severe（严重，需人工修复）
  - moderate > 2  → overall = moderate（中等，建议检查）
  - 其余          → overall = mild（轻微，可自动修复）
"""
import numpy as np
import trimesh
from loguru import logger


class DefectDetector:
    """
    3D模型缺陷自动检测器。

    每个检测方法返回 list[dict]，每条缺陷包含:
      { type: str, level: str, description: str, repairable: bool, count: int }
    """

    def detect_all(self, mesh: trimesh.Trimesh) -> list[dict]:
        """
        执行全量缺陷检测，汇总所有检测结果。

        参数:
            mesh: Trimesh网格对象

        返回:
            缺陷信息列表，按检测顺序排列
        """
        defects = []

        defects.extend(self.detect_non_manifold(mesh))
        defects.extend(self.detect_degenerate_faces(mesh))
        defects.extend(self.detect_inconsistent_normals(mesh))
        defects.extend(self.detect_isolated_components(mesh))

        logger.info(f"Defect detection complete: {len(defects)} defects found")
        return defects

    def detect_non_manifold(self, mesh: trimesh.Trimesh) -> list[dict]:
        """
        非流形边/顶点检测。

        非流形边: 一条边连接的不是恰好2个面 → 拓扑错误，不可3D打印
        非流形顶点: 该顶点邻接面不构成闭合盘拓扑
        """
        defects = []
        # 检测非流形边
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

        # 检测非流形顶点
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
        """
        退化面检测。

        退化面: 面积接近0的三角形（面积 < 1e-12），无法正常渲染/打印。
        """
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
        """
        法线方向异常检测。

        原理: 检查相邻面的法线夹角，若 > 90° 则说明法线翻转或大幅偏移。
        """
        defects = []
        if mesh.face_normals is not None:
            if hasattr(mesh, 'face_adjacency_angles') and mesh.face_adjacency_angles is not None:
                angles = mesh.face_adjacency_angles
                if len(angles) > 0:
                    inverted = np.sum(angles > np.pi / 2)  # pi/2 = 90°
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
        """
        孤立组件检测。

        将网格拆分为连通组件，识别脱离主体的碎片:
          - 面数 < 10  → 孤立碎片（mild，可自动删除）
          - 面数 >= 10 → 分离组件（moderate，需手动确认是否保留）
        """
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
        """
        对一批缺陷汇总定级。

        参数:
            defects: detect_all() 返回的缺陷列表

        返回:
            { overall: str, breakdown: {mild: n, moderate: n, severe: n}, total: int }
        """
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


# 全局单例
defect_detector = DefectDetector()
