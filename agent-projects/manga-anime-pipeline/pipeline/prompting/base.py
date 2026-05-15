from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class PromptOptimizerConfig:
    provider: str = "disabled"
    model: str = ""
    base_url: str = ""
    api_key_env: str = "DEEPSEEK_API_KEY"
    timeout_seconds: int = 120
    temperature: float = 0.2
    max_tokens: int = 4096
    system_prompt: str = ""


class PromptOptimizerProvider(Protocol):
    provider_name: str

    def optimize(self, prompt_pack: dict[str, Any]) -> dict[str, Any]:
        """Return an optimized prompt pack."""

