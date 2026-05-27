from __future__ import annotations

import unittest

from pipeline.dialogue.ocr_based_provider import OCRBasedDialogueProvider


class OCRBasedDialogueProviderTests(unittest.TestCase):
    def test_generates_dialogue_blocks_in_reading_order(self) -> None:
        provider = OCRBasedDialogueProvider(_config())
        result = provider.analyze(_window(), _ocr_result())
        self.assertEqual(result["provider"], "ocr_based")
        self.assertEqual(len(result["dialogue_blocks"]), 2)
        self.assertIn("第一句 第二句", result["dialogue_blocks"][0]["text"])
        self.assertEqual(result["dialogue_blocks"][0]["source_ocr_blocks"], ["ocr_0001", "ocr_0002"])
        self.assertEqual(result["cleaned_text_candidates"][0]["source_dialogue_id"], result["dialogue_blocks"][0]["dialogue_id"])
        self.assertEqual(len(result["bubble_boxes"]), 2)
        self.assertEqual(result["bubble_boxes"][0]["source_dialogue_id"], result["dialogue_blocks"][0]["dialogue_id"])
        self.assertEqual(result["bubble_boxes"][0]["box"], [0, 0, 96, 44])
        self.assertEqual(result["bubble_boxes"][0]["speaker_hint"], {"horizontal": "left", "vertical": "top"})

    def test_filters_low_confidence_and_empty_text(self) -> None:
        provider = OCRBasedDialogueProvider(_config(min_confidence=0.8))
        result = provider.analyze(_window(), _ocr_result())
        texts = [block["text"] for block in result["dialogue_blocks"]]
        self.assertNotIn("低置信度", " ".join(texts))
        self.assertNotIn("!!!", " ".join(texts))

    def test_empty_ocr_returns_stable_empty_shape(self) -> None:
        provider = OCRBasedDialogueProvider(_config())
        result = provider.analyze(_window(), {"ocr_blocks": [], "reading_order": [], "layout_blocks": []})
        self.assertEqual(
            result,
            {"dialogue_blocks": [], "bubble_boxes": [], "sfx_blocks": [], "cleaned_text_candidates": [], "provider": "ocr_based"},
        )


def _config(min_confidence: float = 0.3) -> dict[str, object]:
    return {"dialogue": {"ocr_based": {"min_confidence": min_confidence, "max_merge_distance": 24, "min_text_length": 1}}}


def _window() -> dict[str, object]:
    return {"window_id": "w0001", "width": 200, "height": 120}


def _ocr_result() -> dict[str, object]:
    return {
        "ocr_blocks": [
            {"block_id": "ocr_0002", "text": "第二句", "box": [42, 10, 80, 28], "confidence": 0.9, "language": "unknown"},
            {"block_id": "ocr_low", "text": "低置信度", "box": [0, 60, 30, 80], "confidence": 0.1, "language": "unknown"},
            {"block_id": "ocr_symbol", "text": "!!!", "box": [0, 85, 30, 95], "confidence": 0.9, "language": "unknown"},
            {"block_id": "ocr_0001", "text": "第一句", "box": [10, 10, 36, 28], "confidence": 0.95, "language": "unknown"},
            {"block_id": "ocr_0003", "text": "远处旁白", "box": [140, 90, 190, 110], "confidence": 0.85, "language": "unknown"},
        ],
        "reading_order": ["ocr_0001", "ocr_0002", "ocr_low", "ocr_symbol", "ocr_0003"],
        "layout_blocks": [],
    }


if __name__ == "__main__":
    unittest.main()
