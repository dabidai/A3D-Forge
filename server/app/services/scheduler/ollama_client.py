"""
Ollama客户端：离线LLM推理、JSON解析、指数退避重试。

核心功能:
  - chat(system_prompt, user_message, expect_json) → 发送对话，返回解析后的dict
  - health_check() → 检查Ollama服务连通性

重试策略:
  - JSON解析失败 → 追加修复指令重试（最多3次，间隔 1s/2s/4s）
  - 网络/超时异常 → 指数退避重试（间隔 1s/2s/4s）

JSON解析处理:
  - 自动剥离Markdown代码块（```json ... ```）
  - 解析失败时追加"请输出有效JSON"指令重试

模型配置:
  Qwen3-7B-Instruct 4bit量化版（约4GB）
  推理参数: temperature=0.1(JSON模式保证稳定) / num_predict=4096(最大输出token)
"""
import json
import time
from loguru import logger
import ollama

from app.core.config import settings


class OllamaClient:
    """
    Ollama LLM推理客户端（单例）。

    通过 add_in_executor 在线程池中运行同步调用，
    避免阻塞 FastAPI 的 asyncio 事件循环。
    """

    def __init__(self):
        self.host = settings.OLLAMA_HOST        # 默认 http://ollama:11434
        self.model = settings.OLLAMA_MODEL      # qwen3:7b-instruct-q4_K_M
        self.timeout = settings.OLLAMA_TIMEOUT  # 180s（CPU推理慢）
        self.max_retries = settings.OLLAMA_MAX_RETRIES  # 3次
        self._client = ollama.Client(host=self.host)

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        expect_json: bool = True,
    ) -> dict:
        """
        发送对话请求到本地Ollama服务，返回解析后的结果。

        参数:
            system_prompt: 系统提示词（定义LLM角色行为）
            user_message:  用户消息内容
            expect_json:   是否期望JSON输出（True时设置temperature=0.1）

        返回:
            dict: JSON解析后的结果
                  - 成功: 正常JSON内容
                  - 失败: {"error": "JSON_PARSE_FAILED" | "MAX_RETRIES_EXCEEDED"}
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
                        "temperature": 0.1 if expect_json else 0.7,  # JSON模式低温度保证稳定
                        "num_predict": 4096,                          # 最大输出4096 tokens
                        "enable_thinking": False,                     # 禁用Qwen3 thinking模式（避免JSON前插入推理文本）
                    },
                )
                content = response["message"]["content"].strip()
                if expect_json:
                    return self._parse_json_response(content)
                return {"text": content}

            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed (attempt {attempt + 1}): {e}")
                # 追加修复指令，让LLM重新输出有效JSON
                messages.append({
                    "role": "user",
                    "content": "你的上一个回复不是有效的JSON格式。请严格按照JSON格式重新输出，不要添加任何解释文字。",
                })
                if attempt == self.max_retries - 1:
                    return {"error": "JSON_PARSE_FAILED", "raw": content}
                time.sleep(2 ** attempt)  # 指数退避: 1s, 2s, 4s

            except Exception as e:
                logger.error(f"Ollama request failed (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        return {"error": "MAX_RETRIES_EXCEEDED"}

    def _parse_json_response(self, content: str) -> dict:
        """
        从LLM输出中提取JSON。

        处理LLM常见的输出格式问题:
          - Markdown代码块包裹: ```json\n{...}\n```
          - 首尾空白/换行
        """
        content = content.strip()
        # 剥离 Markdown 代码块
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        return json.loads(content)

    def health_check(self) -> bool:
        """检查Ollama服务是否运行（调用 list 接口验证连通性）。"""
        try:
            self._client.list()
            return True
        except Exception:
            return False


# 全局单例
ollama_client = OllamaClient()
