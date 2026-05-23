from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from .config import LmStudioConfig, ParameterSet
from .http_json import request_json


@dataclass(frozen=True)
class LmStudioResult:
    model: str
    parameter_key: str
    response_text: str
    elapsed_sec: float
    completion_tokens: int
    tokens_per_sec: float
    raw: dict[str, Any]


class LmStudioClient:
    def __init__(self, config: LmStudioConfig) -> None:
        self.config = config

    def list_models(self) -> list[str]:
        data = request_json(
            "GET",
            f"{self.config.base_url}/models",
            headers=self._headers(),
            timeout=self.config.request_timeout_sec,
        )
        return [str(item["id"]) for item in data.get("data", []) if "id" in item]

    def generate(self, model: str, parameter: ParameterSet, instruction: str) -> LmStudioResult:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": instruction,
                }
            ],
            "temperature": parameter.temperature,
            "top_p": parameter.top_p,
            "max_tokens": parameter.max_tokens,
            "stream": False,
        }
        started = time.perf_counter()
        raw = request_json(
            "POST",
            f"{self.config.base_url}/chat/completions",
            payload=payload,
            headers=self._headers(),
            timeout=self.config.request_timeout_sec,
        )
        elapsed = max(time.perf_counter() - started, 0.001)
        response_text = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = raw.get("usage", {})
        completion_tokens = int(usage.get("completion_tokens") or estimate_tokens(response_text))
        return LmStudioResult(
            model=model,
            parameter_key=parameter.key,
            response_text=str(response_text),
            elapsed_sec=elapsed,
            completion_tokens=completion_tokens,
            tokens_per_sec=completion_tokens / elapsed,
            raw=raw,
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.api_key}"}


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))
