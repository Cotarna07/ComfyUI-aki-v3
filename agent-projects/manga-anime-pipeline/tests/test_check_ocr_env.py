from __future__ import annotations

import unittest

from scripts.check_ocr_env import check_ocr_environment


class CheckOcrEnvTests(unittest.TestCase):
    def test_returns_dict_without_raising(self) -> None:
        findings = check_ocr_environment()
        for key in (
            "python_version",
            "paddleocr_import_ok",
            "paddle_import_ok",
            "provider_ready",
            "ocr_env_ready",
            "install_command",
        ):
            self.assertIn(key, findings)
        # paddleocr is not installed in this env; gate must be honest
        if not findings["paddleocr_import_ok"]:
            self.assertFalse(findings["ocr_env_ready"])
            self.assertTrue(findings["errors"])


if __name__ == "__main__":
    unittest.main()
