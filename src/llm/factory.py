"""LLM 工厂：根据配置自动创建对应的适配器。"""

from typing import Any

from .base import LLMBase, load_llm_config
from .claude_adapter import ClaudeAdapter
from .openai_adapter import OpenAIAdapter
from .custom_adapter import CustomAdapter


_ADAPTERS: dict[str, type[LLMBase]] = {
    "claude": ClaudeAdapter,
    "openai": OpenAIAdapter,
    "custom": CustomAdapter,
    "deepseek": CustomAdapter,
}


def create_llm(config: dict[str, Any] | str) -> LLMBase:
    """根据配置创建 LLM 适配器。

    传入 dict 时直接使用配置创建，
    传入 str 时从 YAML 文件路径加载配置。
    """
    if isinstance(config, str):
        config = load_llm_config(config)

    provider = config.pop("provider", "custom")
    cls = _ADAPTERS.get(provider)
    if cls is None:
        raise ValueError(
            f"不支持的 LLM provider: {provider}，"
            f"可用: {list(_ADAPTERS.keys())}"
        )

    return cls(config)
