from __future__ import annotations

import unittest

from pipeline.common.schemas import OCR_RESULT_SCHEMA
from pipeline.common.validation import validate_json_schema
from pipeline.ocr.paddle_provider import normalize_paddleocr_result


class OCROutputSchemaTests(unittest.TestCase):
    def test_empty_result_has_stable_fields(self) -> None:
        result = normalize_paddleocr_result(None, _window_packet())
        self.assertEqual(result, {"ocr_blocks": [], "reading_order": [], "layout_blocks": []})
        validate_json_schema(result, OCR_RESULT_SCHEMA, "ocr_result")

    def test_classic_paddle_result_is_normalized(self) -> None:
        raw_result = [
            [
                [[[10, 12], [70, 12], [70, 24], [10, 24]], ("第一句对白", 0.95)],
                [[[5, 40], [95, 40], [95, 56], [5, 56]], ("第二句对白", 0.88)],
            ]
        ]
        result = normalize_paddleocr_result(raw_result, _window_packet())
        validate_json_schema(result, OCR_RESULT_SCHEMA, "ocr_result")
        self.assertEqual(len(result["ocr_blocks"]), 2)
        first_block = result["ocr_blocks"][0]
        self.assertEqual(first_block["block_id"], "w0001_ocr_0000")
        self.assertEqual(first_block["text"], "第一句对白")
        self.assertEqual(first_block["box"], [10, 12, 70, 24])
        self.assertIsInstance(first_block["confidence"], float)
        self.assertEqual(result["reading_order"], ["w0001_ocr_0000", "w0001_ocr_0001"])

    def test_mapping_result_is_normalized(self) -> None:
        raw_result = [
            {
                "rec_texts": ["映射格式"],
                "rec_scores": [0.91],
                "rec_boxes": [[2, 4, 80, 20]],
            }
        ]
        result = normalize_paddleocr_result(raw_result, _window_packet())
        validate_json_schema(result, OCR_RESULT_SCHEMA, "ocr_result")
        self.assertEqual(result["ocr_blocks"][0]["box"], [2, 4, 80, 20])
        self.assertIsInstance(result["ocr_blocks"][0]["confidence"], float)


def _window_packet() -> dict[str, object]:
    return {
        "window_id": "w0001",
        "image_path": "runtime/windows/example.png",
        "source_page": "p001",
        "source_box": [0, 0, 100, 80],
        "width": 100,
        "height": 80,
    }


if __name__ == "__main__":
    unittest.main()
