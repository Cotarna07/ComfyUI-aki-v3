from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from pipeline.common.schemas import OCR_RESULT_SCHEMA
from pipeline.common.validation import validate_json_schema
from pipeline.ocr.paddle_provider import PaddleOCRProvider


@unittest.skipIf(importlib.util.find_spec("paddleocr") is None, "paddleocr is not installed; install requirements-ocr.txt to run smoke test")
class PaddleOCRSmokeTests(unittest.TestCase):
    def test_real_paddleocr_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "ocr_smoke.png"
            image = Image.new("RGB", (260, 96), "white")
            draw = ImageDraw.Draw(image)
            draw.text((20, 32), "TEST 123", fill=(0, 0, 0))
            image.save(image_path)

            provider = PaddleOCRProvider()
            result = provider.analyze(
                {
                    "window_id": "smoke_w0001",
                    "image_path": str(image_path),
                    "source_page": "p001",
                    "source_box": [0, 0, 260, 96],
                    "width": 260,
                    "height": 96,
                }
            )
            validate_json_schema(result, OCR_RESULT_SCHEMA, "ocr_result")
            self.assertIn("ocr_blocks", result)
            self.assertIn("reading_order", result)
            self.assertIn("layout_blocks", result)


if __name__ == "__main__":
    unittest.main()
