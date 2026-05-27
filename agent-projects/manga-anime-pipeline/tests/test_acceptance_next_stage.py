from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.qc.acceptance import evaluate_acceptance

from test_acceptance_testdata import make_acceptance_case


class AcceptanceNextStageTests(unittest.TestCase):
    def test_valid_paddleocr_and_ocr_based_dialogue_allows_next_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            case = make_acceptance_case(project_root)
            report = evaluate_acceptance(**case)
            self.assertTrue(report["next_stage_allowed"])

    def test_mock_dialogue_blocks_next_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            case = make_acceptance_case(project_root, dialogue_provider="mock_dialogue")
            report = evaluate_acceptance(**case)
            self.assertFalse(report["next_stage_allowed"])


if __name__ == "__main__":
    unittest.main()
