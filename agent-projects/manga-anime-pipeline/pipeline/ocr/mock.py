from __future__ import annotations

from typing import Any

from pipeline.ocr.base import OCRProvider


class MockOCRProvider(OCRProvider):
    """Deterministic OCR stand-in with the same output shape expected from real OCR."""

    provider_name = "mock_ocr"

    def analyze(self, window: dict[str, Any]) -> dict[str, Any]:
        width = int(window.get("width", 1))
        height = int(window.get("height", 1))
        window_id = window["window_id"]
        block_id = f"{window_id}_ocr_000"
        text_box = _box(width, height, 0.12, 0.10, 0.88, 0.22)
        return {
            "ocr_blocks": [
                {
                    "block_id": block_id,
                    "text": f"Mock OCR text for {window_id}",
                    "box": text_box,
                    "confidence": 0.72,
                    "language": "mock",
                    "provider": self.provider_name,
                }
            ],
            "reading_order": [block_id],
            "layout_blocks": [
                {
                    "layout_id": f"{window_id}_layout_000",
                    "type": "dialogue_region",
                    "box": text_box,
                    "confidence": 0.66,
                    "provider": self.provider_name,
                }
            ],
        }


def _box(width: int, height: int, left: float, top: float, right: float, bottom: float) -> list[int]:
    return [
        max(0, min(width, int(width * left))),
        max(0, min(height, int(height * top))),
        max(0, min(width, int(width * right))),
        max(0, min(height, int(height * bottom))),
    ]
