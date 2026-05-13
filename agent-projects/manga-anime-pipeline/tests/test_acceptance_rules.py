from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.common.io import write_json
from pipeline.qc.acceptance import evaluate_acceptance

from test_acceptance_testdata import make_acceptance_case


class AcceptanceRulesTests(unittest.TestCase):
    def test_missing_artifacts_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            case = make_acceptance_case(project_root, write_artifacts=False)
            report = evaluate_acceptance(**case)
            self.assertEqual(report["pipeline_status"], "fail")
            self.assertTrue(any("required artifact missing" in error for error in report["errors"]))

    def test_schema_error_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            case = make_acceptance_case(project_root)
            window_manifest_path = project_root / "runtime" / "windows" / "series" / "chapter" / "window_manifest.json"
            write_json(window_manifest_path, {"series_id": "series", "chapter_id": "chapter", "windows": [{"window_id": "broken"}]})
            report = evaluate_acceptance(**case)
            self.assertEqual(report["pipeline_status"], "fail")
            self.assertFalse(report["schema_check"]["valid"])

    def test_mock_ocr_fails_when_config_requires_paddleocr(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            case = make_acceptance_case(project_root, ocr_provider="mock_ocr")
            report = evaluate_acceptance(**case)
            self.assertEqual(report["pipeline_status"], "fail")
            self.assertTrue(any("mock OCR" in error for error in report["errors"]))

    def test_mock_dialogue_fails_when_config_requires_ocr_based(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            case = make_acceptance_case(project_root, dialogue_provider="mock_dialogue")
            report = evaluate_acceptance(**case)
            self.assertEqual(report["pipeline_status"], "fail")
            self.assertTrue(any("mock dialogue" in error for error in report["errors"]))

    def test_mock_detection_and_director_are_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            case = make_acceptance_case(project_root)
            report = evaluate_acceptance(**case)
            self.assertIn("detection provider is still mock", report["warnings"])
            self.assertIn("director provider is still mock", report["warnings"])


if __name__ == "__main__":
    unittest.main()
