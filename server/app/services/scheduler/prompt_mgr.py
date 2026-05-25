"""
提示词管理器：管理Prompt模板，集成3D领域RAG知识库。
"""
from app.services.scheduler.router import LLMRole

# 3D领域知识库：Blender API、拓扑规范、PBR参数、缺陷修复方案
RAG_KNOWLEDGE_BASE = {
    "blender_api": {
        "mesh_cleanup": (
            "bpy.ops.mesh.select_all(action='SELECT'); "
            "bpy.ops.mesh.remove_doubles(threshold=0.0001); "
            "bpy.ops.mesh.fill_holes(sides=128); "
            "bpy.ops.mesh.normals_make_consistent(inside=False)"
        ),
        "decimate": "bpy.ops.mesh.decimate(ratio=0.5)",
        "export_glb": "bpy.ops.export_scene.gltf(filepath=path, export_format='GLB')",
    },
    "topology_rules": {
        "watertight": "所有边必须属于恰好两个面，无边界边",
        "manifold": "每个顶点的邻接面构成一个闭合圆盘拓扑",
        "no_degenerate": "无零面积三角面，无边长小于0.0001的边",
        "uv_no_overlap": "UV岛之间无重叠，间隔至少2像素(1024分辨率)",
        "face_uniform": "三角面面积方差不超过均值±2标准差",
    },
    "pbr_parameters": {
        "metallic_workflow": "baseColor + metallic + roughness + normal (OpenGL)",
        "specular_workflow": "diffuse + specular + glossiness + normal",
        "standard_resolution": "2048x2048 或 4096x4096, PNG 8bit",
    },
    "defect_patterns": {
        "hole_small": "直径<模型包围盒对角5%的孔洞，可用fill_holes自动修复",
        "hole_large": "直径>5%的孔洞，需要拓扑重布+曲面重建",
        "inverted_normal": "法线方向与相邻面平均值偏差>90度",
        "non_manifold_edge": "边连接面数!=2，需手动切割或删除孤立面",
        "uv_island_overlap": "UV岛间像素重叠，需松驰展开+手调",
        "isolated_vertex": "不属于任何面的孤立顶点",
    },
}

TASK_TEMPLATES = {
    LLMRole.PROMPT_OPTIMIZER: {
        "system_prompt": "{role_prompt}",
        "user_template": (
            "用户输入: {user_input}\n"
            "输出风格偏好: {style}\n"
            "目标复杂度: {complexity}\n"
            "请输出结构化的3D生成提示词JSON。"
        ),
        "rag_contexts": ["pbr_parameters", "topology_rules"],
    },
    LLMRole.TECH_ANALYST: {
        "system_prompt": "{role_prompt}",
        "user_template": (
            "模型文件: {model_path}\n"
            "模型面数: {face_count}\n"
            "检测到的异常: {anomalies}\n"
            "请进行缺陷分析并输出JSON。"
        ),
        "rag_contexts": ["defect_patterns", "blender_api", "topology_rules"],
    },
    LLMRole.DATA_PROCESSOR: {
        "system_prompt": "{role_prompt}",
        "user_template": "资产信息: {asset_info}\n请输出标准化处理结果JSON。",
        "rag_contexts": [],
    },
    LLMRole.CONTENT_AUDITOR: {
        "system_prompt": "{role_prompt}",
        "user_template": "待审核内容: {content}\n内容来源: {source}\n请进行内容安全审核并输出JSON。",
        "rag_contexts": [],
    },
}


class PromptManager:
    """构建完整的LLM Prompt，嵌入RAG知识库上下文"""

    @staticmethod
    def build_prompt(
        role: LLMRole,
        system_prompt: str,
        template_vars: dict[str, str],
    ) -> tuple[str, str]:
        """
        返回 (system_message, user_message)
        template_vars 会被注入到 user_template 中
        """
        template = TASK_TEMPLATES.get(role, TASK_TEMPLATES[LLMRole.TECH_ANALYST])
        system_msg = template["system_prompt"].format(role_prompt=system_prompt)
        user_msg = template["user_template"].format(**template_vars)
        return system_msg, user_msg

    @staticmethod
    def get_rag_context(role: LLMRole) -> dict:
        """获取该角色关联的RAG知识库内容"""
        template = TASK_TEMPLATES.get(role, TASK_TEMPLATES[LLMRole.TECH_ANALYST])
        contexts = {}
        for ctx_key in template["rag_contexts"]:
            if ctx_key in RAG_KNOWLEDGE_BASE:
                contexts[ctx_key] = RAG_KNOWLEDGE_BASE[ctx_key]
        return contexts
