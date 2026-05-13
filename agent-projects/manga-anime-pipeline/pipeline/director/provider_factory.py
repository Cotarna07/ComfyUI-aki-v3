from __future__ import annotations

from typing import Any

from pipeline.director.base import DirectorProvider
from pipeline.director.mock import MockDirector
from pipeline.director.qwen3vl_provider import Qwen3VLDirector


def create_director_provider(name: str | None = None, config: dict[str, Any] | None = None) -> DirectorProvider:
    provider_name = _normalize_name(name)
    if provider_name == "mock":
        return MockDirector()
    if provider_name == "qwen3vl":
        return Qwen3VLDirector(config=config)
    raise ValueError(f"Unknown director provider: {name!r}. Available providers: mock, qwen3vl")


def _normalize_name(name: str | None) -> str:
    value = (name or "mock").strip().lower()
    aliases = {
        "mock_director": "mock",
        "qwen3-vl": "qwen3vl",
        "qwen_vl": "qwen3vl",
        "qwen-vl": "qwen3vl",
    }
    return aliases.get(value, value)
