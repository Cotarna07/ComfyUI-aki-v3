from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline.ocr.paddle_provider import PaddleOCRProvider


class PaddleOCRProviderImportTests(unittest.TestCase):
    def test_module_import_does_not_require_paddleocr(self) -> None:
        provider = PaddleOCRProvider()
        self.assertEqual(provider.provider_name, "paddleocr")

    def test_missing_dependency_raises_friendly_runtime_error(self) -> None:
        if importlib.util.find_spec("paddleocr") is not None:
            self.skipTest("paddleocr is installed in this environment")
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "page.png"
            Image.new("RGB", (120, 80), "white").save(image_path)
            provider = PaddleOCRProvider()
            with self.assertRaisesRegex(RuntimeError, "python -m pip install -r requirements-ocr.txt"):
                provider.analyze(
                    {
                        "window_id": "w0001",
                        "image_path": str(image_path),
                        "source_page": "p001",
                        "source_box": [0, 0, 120, 80],
                        "width": 120,
                        "height": 80,
                    }
                )


if __name__ == "__main__":
    unittest.main()
