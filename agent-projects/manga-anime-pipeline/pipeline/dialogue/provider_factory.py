from __future__ import annotations

from typing import Any

from pipeline.dialogue.base import DialogueProvider
from pipeline.dialogue.mock import MockDialogueProvider
from pipeline.dialogue.ocr_based_provider import OCRBasedDialogueProvider


def create_dialogue_provider(name: str | None = None, config: dict[str, Any] | None = None) -> DialogueProvider:
    provider_name = _normalize_name(name)
    if provider_name == "mock":
        return MockDialogueProvider()
    if provider_name == "ocr_based":
        return OCRBasedDialogueProvider(config=config)
    raise ValueError(f"Unknown dialogue provider: {name!r}. Available providers: mock, ocr_based")


def _normalize_name(name: str | None) -> str:
    value = (name or "mock").strip().lower()
    aliases = {"mock_dialogue": "mock", "ocr-based": "ocr_based", "ocrbased": "ocr_based"}
    return aliases.get(value, value)

