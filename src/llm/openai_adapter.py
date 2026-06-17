"""OpenAI API 适配器。"""

from typing import Any

from .base import LLMBase


class OpenAIAdapter(LLMBase):
    """OpenAI API 适配器。

    config:
        api_key: OpenAI API key
        model: gpt-4o / gpt-4-turbo / etc
        temperature: 0.3
        max_tokens: 4096
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.api_key = self.config.get("api_key", "")
        self.model = self.config.get("model", "gpt-4o")

    def _get_client(self):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "请安装 openai SDK: pip install openai"
            )
        return OpenAI(api_key=self.api_key)

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
