from __future__ import annotations

from typing import Any

from pipeline.prompting.base import PromptOptimizerConfig, PromptOptimizerProvider
from pipeline.prompting.deepseek_provider import DeepSeekPromptOptimizer
from pipeline.prompting.disabled_provider import DisabledPromptOptimizer


def create_prompt_optimizer(config: dict[str, Any] | None = None) -> PromptOptimizerProvider:
    settings = ((config or {}).get("prompt_optimizer") or config or {}) if isinstance(config, dict) else {}
    provider = str(settings.get("provider", "disabled")).strip().lower()
    optimizer_config = PromptOptimizerConfig(
        provider=provider,
        model=str(settings.get("model", "")),
        base_url=str(settings.get("base_url", "")),
        api_key_env=str(settings.get("api_key_env", "DEEPSEEK_API_KEY")),
        timeout_seconds=int(settings.get("timeout_seconds", 120)),
        temperature=float(settings.get("temperature", 0.2)),
        max_tokens=int(settings.get("max_tokens", 4096)),
        system_prompt=str(settings.get("system_prompt", "")),
    )
    if provider in {"deepseek", "deepseek_api"}:
        return DeepSeekPromptOptimizer(optimizer_config)
    if provider in {"disabled", "none", ""}:
        return DisabledPromptOptimizer(optimizer_config)
    raise ValueError(f"Unsupported prompt optimizer provider: {provider}")

