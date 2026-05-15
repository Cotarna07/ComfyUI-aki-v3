from __future__ import annotations

from typing import Any

from pipeline.prompting.base import PromptOptimizerConfig


class DisabledPromptOptimizer:
    provider_name = "disabled"

    def __init__(self, config: PromptOptimizerConfig | None = None) -> None:
        self.config = config or PromptOptimizerConfig()

    def optimize(self, prompt_pack: dict[str, Any]) -> dict[str, Any]:
        return {
            "optimizer": {"provider": self.provider_name, "status": "skipped"},
            "characters": prompt_pack.get("characters", []),
            "shots": prompt_pack.get("shots", []),
        }

