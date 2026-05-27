from __future__ import annotations

from typing import Any

from pipeline.ocr.base import OCRProvider
from pipeline.ocr.mock import MockOCRProvider
from pipeline.ocr.paddle_provider import PaddleOCRProvider


def create_ocr_provider(name: str | None = None, config: dict[str, Any] | None = None) -> OCRProvider:
    provider_name = _normalize_name(name)
    if provider_name == "mock":
        return MockOCRProvider()
    if provider_name == "paddleocr":
        return PaddleOCRProvider(config=config)
    raise ValueError(f"Unknown OCR provider: {name!r}. Available providers: mock, paddleocr")


def _normalize_name(name: str | None) -> str:
    value = (name or "mock").strip().lower()
    aliases = {"mock_ocr": "mock", "paddle": "paddleocr"}
    return aliases.get(value, value)

