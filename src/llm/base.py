"""LLM 抽象基类：统一接口、错误处理与重试机制。"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMBase(ABC):
    """LLM 抽象基类。

    配置参数（可被子类覆盖的默认值）：
    - temperature: 0.3
    - max_tokens: 4096
    - max_retries: 3
    - retry_delay: 2 (秒)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.temperature = self.config.get("temperature", 0.3)
        self.max_tokens = self.config.get("max_tokens", 4096)
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay = self.config.get("retry_delay", 2)

    @abstractmethod
    def generate(self, system_prompt: str, user_message: str) -> str:
        """发送请求到 LLM 并返回生成的文本。"""

    def generate_with_retry(
        self,
        system_prompt: str,
        user_message: str,
    ) -> str:
        """带重试机制的 generate 调用。"""
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return self.generate(system_prompt, user_message)
            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM 调用失败 (attempt %d/%d): %s",
                    attempt + 1, self.max_retries, e,
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        raise LLMError(
            f"LLM 调用失败，已重试 {self.max_retries} 次"
        ) from last_error

    @abstractmethod
    def test_connection(self) -> bool:
        """测试与 LLM 服务的连接是否正常。"""


def load_llm_config(config_path: str) -> dict[str, Any]:
    """从 YAML 加载 LLM 配置。"""
    from pathlib import Path
    import os
    import yaml

    path = Path(config_path)
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    for var in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "CUSTOM_API_KEY"]:
        raw = raw.replace(f"${{{var}}}", os.environ.get(var, ""))

    data = yaml.safe_load(raw)
    provider = data["active_provider"]
    return {**data["providers"][provider], "provider": provider}
