"""
LLM输出校验器：JSON Schema强校验 + 技术参数校验 + 安全规则二次过滤。

校验流程:
  1. 角色Schema校验   → 检查必需字段是否存在
  2. 子结构校验       → 检查缺陷数组中的每个元素字段完整性
  3. 安全规则过滤     → 扫描输出中是否包含违规敏感词

各角色输出期望Schema:
  PROMPT_OPTIMIZER → { positive_prompt*, negative_prompt*, style*, complexity* }
  TECH_ANALYST     → { defects*: [{ type*, level*, description*, repairable* }] }
  DATA_PROCESSOR   → { result* }
  CONTENT_AUDITOR  → { compliant*, risk_level* }
  (* 表示必需字段)

安全过滤:
  - 敏感词检测（武器/暴力/色情等关键词）
  - 脚本注入防护（移除 <script> 标签）
  - 代码块移除（避免LLM注入恶意代码）

注意: 安全过滤为辅助手段，不能替代Qwen3 CONTENT_AUDITOR的深度审核。
"""
import re
from loguru import logger


# ---- 各角色输出的期望JSON Schema（简化版：检查必需字段） ----
ROLE_OUTPUT_SCHEMAS = {
    "3d_prompt_optimizer": {
        "required": ["positive_prompt", "negative_prompt", "style", "complexity"],
        "optional": ["ratio_control", "detail_level", "reference_hint"],
    },
    "3d_tech_analyst": {
        "required": ["defects"],
        "optional": ["summary", "overall_severity"],
        # defects 数组中每个元素的必需字段
        "defect_fields": {
            "required": ["type", "level", "description", "repairable"],
            "optional": ["region", "repair_steps", "blender_script", "tutorial"],
        },
    },
    "structured_data_processor": {
        "required": ["result"],
        "optional": ["tags", "name", "version_summary", "batch_report"],
    },
    "content_safety_auditor": {
        "required": ["compliant", "risk_level"],
        "optional": ["violation_type", "violation_detail", "action"],
    },
}

# 敏感词过滤正则（简化版，生产需扩充）
SENSITIVE_PATTERNS = [
    r"(?i)\b(weapon|violence|explicit|nsfw|gore)\b",
]


class OutputValidator:
    """
    校验LLM输出是否符合预期的JSON Schema和安全规则。

    用法:
      is_valid, errors = OutputValidator.validate("3d_tech_analyst", llm_result)
      if not is_valid:
          logger.warning(f"LLM output issues: {errors}")
    """

    @staticmethod
    def validate(role: str, output: dict) -> tuple[bool, list[str]]:
        """
        校验LLM输出。

        参数:
            role:   角色标识字符串（与 ROLE_OUTPUT_SCHEMAS 的key对应）
            output: LLM返回的JSON dict

        返回:
            (是否通过校验, 错误信息列表)
        """
        errors = []
        schema = ROLE_OUTPUT_SCHEMAS.get(role, {})

        # 1. 必需字段检查
        for field in schema.get("required", []):
            if field not in output:
                errors.append(f"缺少必需字段: {field}")

        # 2. 子结构校验（仅defects数组）
        if "defect_fields" in schema and "defects" in output:
            df = schema["defect_fields"]
            for i, defect in enumerate(output["defects"]):
                for field in df.get("required", []):
                    if field not in defect:
                        errors.append(f"defects[{i}] 缺少字段: {field}")

        # 3. 安全规则过滤
        output_str = str(output)
        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, output_str):
                errors.append(f"内容命中安全规则: {pattern}")
                break

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning(f"Output validation failed for role={role}: {errors}")

        return is_valid, errors

    @staticmethod
    def filter_sensitive(content: str) -> str:
        """
        对输入内容做安全脱敏预处理。

        处理:
          - 移除 <script> 标签（防XSS注入）
          - 移除代码块（防LLM注入恶意代码）
          - 移除多余空白

        参数:
            content: 原始文本

        返回:
            脱敏后的安全文本
        """
        filtered = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.IGNORECASE)
        filtered = re.sub(r"```\w*\n.*?\n```", "[CODE_BLOCK_REMOVED]", filtered, flags=re.DOTALL)
        return filtered
