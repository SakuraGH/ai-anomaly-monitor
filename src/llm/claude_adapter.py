"""Claude API 适配器（Anthropic SDK）。"""

from typing import Any

from .base import LLMBase


class ClaudeAdapter(LLMBase):
    """Claude API 适配器。

    config:
        api_key: Anthropic API key
        model: claude-sonnet-4-6 / claude-opus-4-6
        temperature: 0.3
        max_tokens: 4096
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.api_key = self.config.get("api_key", "")
        self.model = self.config.get("model", "claude-sonnet-4-6")

    def _get_client(self):
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "请安装 anthropic SDK: pip install anthropic"
            )
        return anthropic.Anthropic(api_key=self.api_key)

    def generate(self, system_prompt: str, user_message: str) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    def test_connection(self) -> bool:
        try:
            client = self._get_client()
            client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False
