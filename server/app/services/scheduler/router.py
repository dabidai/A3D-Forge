"""
LLM角色路由器：识别业务场景 → 匹配合适的LLM角色 → 返回置信度。

四大LLM角色（全周期统一）:
  1. PROMPT_OPTIMIZER    3D提示词优化师 — 自然语言 → 结构化生成参数
  2. TECH_ANALYST        3D技术分析师 — 缺陷分析、等级评定、修复方案生成
  3. DATA_PROCESSOR      结构化数据处理器 — 资产标签、命名规范、批量任务解析
  4. CONTENT_AUDITOR     内容安全审核员 — 全链路输入输出合规审查

路由机制:
  精确匹配: 场景名完全命中 → 置信度 1.0
  模糊匹配: 场景名部分命中 → 按token重叠率打分 → 阈值 0.3
  默认兜底: TECH_ANALYST (置信度 0.1)
"""
from enum import Enum


class LLMRole(str, Enum):
    """
    LLM调度角色枚举。

    每个角色有独立的 System Prompt 和 Prompt 模板，
    同一模型(Qwen3-7B)以不同System Prompt被调用，实现多角色能力输出。
    """
    PROMPT_OPTIMIZER = "3d_prompt_optimizer"       # 提示词结构化优化
    TECH_ANALYST = "3d_tech_analyst"               # 缺陷分析+修复方案
    DATA_PROCESSOR = "structured_data_processor"   # 标签/命名/批次处理
    CONTENT_AUDITOR = "content_safety_auditor"     # 内容安全合规审核


# 角色System Prompt定义 — 固定角色行为边界
ROLE_SYSTEM_PROMPTS = {
    LLMRole.PROMPT_OPTIMIZER: (
        "你是一个专业的3D模型提示词优化师。"
        "你的任务是将用户的自然语言描述转化为结构化的3D生成提示词。"
        "输出必须包含：正负向提示词、风格定义、复杂度等级、比例控制参数。"
        "输出格式严格为JSON。"
    ),
    LLMRole.TECH_ANALYST: (
        "你是一个资深的3D技术分析师。"
        "你的任务是分析3D模型缺陷，给出分级定级、修复方案说明、Blender Python可执行脚本。"
        "不要执行自动修复决策，仅提供分析和修复方案。"
        "输出格式严格为JSON，包含：缺陷类型、严重等级、影响范围、修复步骤、可执行Python脚本。"
    ),
    LLMRole.DATA_PROCESSOR: (
        "你是一个3D资产结构化数据处理器。"
        "你的任务是为模型资产生成标准化标签、命名规范、版本摘要、批量任务解析。"
        "输出格式严格为JSON。"
    ),
    LLMRole.CONTENT_AUDITOR: (
        "你是一个内容安全审核员。"
        "你的任务是审查所有输入输出内容，检测违规、侵权、敏感内容。"
        "输出格式严格为JSON，包含：合规判定、违规类型、风险等级、处理建议。"
    ),
}

# 业务场景 → 角色映射表
SCENARIO_ROLE_MAP = {
    "text_to_3d_prompt": LLMRole.PROMPT_OPTIMIZER,
    "image_to_3d_prompt": LLMRole.PROMPT_OPTIMIZER,
    "defect_analysis": LLMRole.TECH_ANALYST,
    "repair_script": LLMRole.TECH_ANALYST,
    "repair_tutorial": LLMRole.TECH_ANALYST,
    "asset_tagging": LLMRole.DATA_PROCESSOR,
    "batch_parse": LLMRole.DATA_PROCESSOR,
    "version_summary": LLMRole.DATA_PROCESSOR,
    "content_audit": LLMRole.CONTENT_AUDITOR,
    "prompt_audit": LLMRole.CONTENT_AUDITOR,
}


class RoleRouter:
    """
    业务场景 → LLM角色路由器。

    用法:
      role, confidence = RoleRouter.route("defect_analysis")
      system_prompt = RoleRouter.get_system_prompt(role)
    """

    @staticmethod
    def route(scenario: str) -> tuple[LLMRole, float]:
        """
        根据业务场景名称匹配最合适的LLM角色。

        参数:
            scenario: 场景标识（如 "defect_analysis"）

        返回:
            (LLMRole, 置信度 0.0~1.0)
            精确匹配 → 1.0，模糊匹配 → 基于token重叠率，无匹配 → TECH_ANALYST + 0.1
        """
        role = SCENARIO_ROLE_MAP.get(scenario)
        if role:
            return role, 1.0

        # 模糊匹配：按下划线分词，计算重叠率
        best_match = None
        best_score = 0.0
        for key, val in SCENARIO_ROLE_MAP.items():
            overlap = len(set(scenario.split("_")) & set(key.split("_")))
            score = overlap / max(len(key.split("_")), 1)
            if score > best_score:
                best_score = score
                best_match = val

        if best_match and best_score > 0.3:
            return best_match, round(best_score, 2)

        # 默认兜底：技术分析师
        return LLMRole.TECH_ANALYST, 0.1

    @staticmethod
    def get_system_prompt(role: LLMRole) -> str:
        """
        获取指定角色的System Prompt。

        参数:
            role: LLMRole枚举值

        返回:
            角色的System Prompt文本（中文）
        """
        return ROLE_SYSTEM_PROMPTS[role]
