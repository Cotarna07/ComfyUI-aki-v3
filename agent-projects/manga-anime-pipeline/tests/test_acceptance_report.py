from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.qc.acceptance import evaluate_acceptance
from pipeline.qc.report import write_acceptance_reports

from test_acceptance_testdata import make_acceptance_case


class AcceptanceReportTests(unittest.TestCase):
    def test_writes_acceptance_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            case = make_acceptance_case(project_root)
            report = evaluate_acceptance(**case)
            json_path, md_path = write_acceptance_reports(project_root, project_root / "runtime", report)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            self.assertIn("# Stage Acceptance Report", md_path.read_text(encoding="utf-8"))
            self.assertEqual(report["pipeline_status"], "warning")


if __name__ == "__main__":
    unittest.main()
