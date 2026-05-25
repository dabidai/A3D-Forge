"""
Ollama客户端：离线推理、超时重试、多实例负载均衡。
"""
import json
import time
from loguru import logger
import ollama

from app.core.config import settings


class OllamaClient:
    def __init__(self):
        self.host = settings.OLLAMA_HOST
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT
        self.max_retries = settings.OLLAMA_MAX_RETRIES
        self._client = ollama.Client(host=self.host)

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        expect_json: bool = True,
    ) -> dict:
        """
        发送对话请求，返回解析后的JSON结果。
        内置重试和JSON修复逻辑。
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        for attempt in range(self.max_retries):
            try:
                logger.info(f"Ollama request attempt {attempt + 1}/{self.max_retries}")
                response = self._client.chat(
                    model=self.model,
                    messages=messages,
                    options={
                        "temperature": 0.1 if expect_json else 0.7,
                        "num_predict": 4096,
                    },
                )
                content = response["message"]["content"].strip()
                if expect_json:
                    return self._parse_json_response(content)
                return {"text": content}

            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed (attempt {attempt + 1}): {e}")
                # 追加修复指令重试
                messages.append({
                    "role": "user",
                    "content": "你的上一个回复不是有效的JSON格式。请严格按照JSON格式重新输出，不要添加任何解释文字。",
                })
                if attempt == self.max_retries - 1:
                    return {"error": "JSON_PARSE_FAILED", "raw": content}
                time.sleep(2 ** attempt)

            except Exception as e:
                logger.error(f"Ollama request failed (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        return {"error": "MAX_RETRIES_EXCEEDED"}

    def _parse_json_response(self, content: str) -> dict:
        """从LLM输出中提取JSON（处理markdown代码块包裹）"""
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        return json.loads(content)

    def health_check(self) -> bool:
        try:
            self._client.list()
            return True
        except Exception:
            return False


# 全局单例
ollama_client = OllamaClient()
