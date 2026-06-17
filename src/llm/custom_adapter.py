"""国产模型适配器：支持通义千问/文心等兼容 OpenAI 接口格式的模型。"""

from typing import Any
from urllib.parse import urljoin

from .base import LLMBase


class CustomAdapter(LLMBase):
    """兼容 OpenAI API 格式的第三方模型适配器。

    支持：通义千问 (DashScope)、DeepSeek、文心一言 等。

    config:
        api_key: API key
        base_url: 模型服务的 base URL
        model: 模型名称 (qwen-plus / deepseek-chat / etc)
        temperature: 0.3
        max_tokens: 4096
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.api_key = self.config.get("api_key", "")
        self.base_url = self.config.get("base_url", "")
        self.model = self.config.get("model", "qwen-plus")

    def _get_client(self):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "请安装 openai SDK: pip install openai"
            )
        return OpenAI(
            api_key=self.api_key,
            base_url=urljoin(self.base_url, "/") if self.base_url else None,
        )

    def generate(self, system_prompt: str, user_message: str) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content or ""

    def test_connection(self) -> bool:
        try:
            client = self._get_client()
            client.chat.completions.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False
