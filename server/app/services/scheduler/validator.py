"""
输出校验器：JSON Schema 强校验、技术参数校验、安全规则过滤。
"""
import re
from loguru import logger


# 各角色输出的期望 JSON Schema (简化版：检查必需字段)
ROLE_OUTPUT_SCHEMAS = {
    "3d_prompt_optimizer": {
        "required": ["positive_prompt", "negative_prompt", "style", "complexity"],
        "optional": ["ratio_control", "detail_level", "reference_hint"],
    },
    "3d_tech_analyst": {
        "required": ["defects"],
        "optional": ["summary", "overall_severity"],
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

# 安全敏感词库 (简化版)
SENSITIVE_PATTERNS = [
    r"(?i)\b(weapon|violence|explicit|nsfw|gore)\b",
]


class OutputValidator:
    """校验LLM输出是否符合预期Schema与安全规则"""

    @staticmethod
    def validate(role: str, output: dict) -> tuple[bool, list[str]]:
        """
        返回 (是否通过, 错误列表)
        """
        errors = []
        schema = ROLE_OUTPUT_SCHEMAS.get(role, {})

        # 必需字段检查
        for field in schema.get("required", []):
            if field not in output:
                errors.append(f"缺少必需字段: {field}")

        # 子结构校验 (defect_fields)
        if "defect_fields" in schema and "defects" in output:
            df = schema["defect_fields"]
            for i, defect in enumerate(output["defects"]):
                for field in df.get("required", []):
                    if field not in defect:
                        errors.append(f"defects[{i}] 缺少字段: {field}")

        # 安全规则过滤
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
        """对输入内容做敏感信息脱敏"""
        # 移除潜在的注入模式
        filtered = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.IGNORECASE)
        filtered = re.sub(r"```\w*\n.*?\n```", "[CODE_BLOCK_REMOVED]", filtered, flags=re.DOTALL)
        return filtered
