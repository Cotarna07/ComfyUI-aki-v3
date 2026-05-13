from __future__ import annotations

from typing import Any

from pipeline.dialogue.base import DialogueProvider


class MockDialogueProvider(DialogueProvider):
    """Manga dialogue stand-in shaped for later Manga Image Translator replacement."""

    provider_name = "mock_dialogue"

    def analyze(self, window: dict[str, Any], ocr_result: dict[str, Any] | None = None) -> dict[str, Any]:
        window_id = window["window_id"]
        ocr_result = ocr_result or {}
        ocr_text = " ".join(block.get("text", "") for block in ocr_result.get("ocr_blocks", []))
        bubble_box = _main_bubble_box(window)
        dialogue_id = f"{window_id}_dialogue_000"
        return {
            "dialogue_blocks": [
                {
                    "dialogue_id": dialogue_id,
                    "speaker": "unknown_character",
                    "text": ocr_text or f"Mock dialogue for {window_id}",
                    "bubble_box": bubble_box,
                    "confidence": 0.64,
                    "provider": self.provider_name,
                }
            ],
            "bubble_boxes": [
                {
                    "bubble_id": f"{window_id}_bubble_000",
                    "box": bubble_box,
                    "confidence": 0.63,
                    "provider": self.provider_name,
                }
            ],
            "sfx_blocks": [],
            "cleaned_text_candidates": [ocr_text or f"Mock dialogue for {window_id}"],
        }


def _main_bubble_box(window: dict[str, Any]) -> list[int]:
    width = int(window.get("width", 1))
    height = int(window.get("height", 1))
    return [int(width * 0.10), int(height * 0.08), int(width * 0.90), int(height * 0.25)]
