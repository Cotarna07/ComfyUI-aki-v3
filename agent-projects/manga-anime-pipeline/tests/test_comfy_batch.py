from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.comfy.submitter import SubmitterConfig, submit_batch
from pipeline.comfy.workflow_router import TemplateMissing, WorkflowRouter
from pipeline.common.io import read_json, write_json
from pipeline.qc.comfy_acceptance import evaluate_comfy_acceptance


class FakeComfyClient:
    def __init__(self, *, fail_submit: bool = False) -> None:
        self.fail_submit = fail_submit
        self.submitted: list[dict] = []

    def check_server(self) -> dict:
        return {"ok": True}

    def submit_prompt(self, payload):
        if self.fail_submit:
            raise RuntimeError("submit blew up")
        self.submitted.append(payload)
        return {"prompt_id": f"pid-{len(self.submitted)}"}

    def get_history(self, prompt_id):
        return {prompt_id: {"outputs": {"node_1": {"images": [{"filename": f"{prompt_id}.png"}]}}}}


class WorkflowRouterTests(unittest.TestCase):
    def test_missing_template_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            router = WorkflowRouter({"dialogue_light_motion": "missing.json"}, Path(tmp))
            with self.assertRaises(TemplateMissing):
                router.resolve("dialogue_light_motion")

    def test_skip_route_returns_none(self) -> None:
        router = WorkflowRouter({"skip": None}, Path("."))
        self.assertIsNone(router.resolve("skip"))

    def test_validate_all_reports_missing_and_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "good.json"
            write_json(existing, {"nodes": {}})
            router = WorkflowRouter(
                {
                    "dialogue_light_motion": "good.json",
                    "action_performance": "missing.json",
                    "skip": None,
                },
                Path(tmp),
            )
            findings = router.validate_all()
        self.assertIn("dialogue_light_motion", findings["valid"])
        self.assertIn({"route": "action_performance", "path": str(Path(tmp) / "missing.json")}, findings["missing"])
        self.assertIn("skip", findings["skipped"])


class SubmitterTests(unittest.TestCase):
    def _write_template(self, tmp: Path) -> Path:
        template = tmp / "configs" / "comfy_workflows" / "wf.json"
        write_json(template, {"nodes": {"1": {"class_type": "SaveImage"}}})
        return template

    def test_submit_records_tasks_and_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            template = self._write_template(project_root)
            router = WorkflowRouter(
                {"dialogue_light_motion": str(template.relative_to(project_root)), "skip": None},
                project_root,
            )
            client = FakeComfyClient()
            shot_manifest = {
                "shots": [
                    {"shot_id": "s1", "workflow_route": "dialogue_light_motion"},
                    {"shot_id": "s2", "workflow_route": "skip"},
                ]
            }
            output_dir = project_root / "runtime" / "comfy"
            result = submit_batch(shot_manifest, output_dir, client, router, SubmitterConfig())
            tasks = result["tasks"]
            persisted = read_json(result["output_path"])
        self.assertEqual(tasks[0]["status"], "finished")
        self.assertEqual(tasks[0]["prompt_id"], "pid-1")
        self.assertEqual(tasks[1]["status"], "skipped")
        self.assertEqual(persisted["summary"]["submitted_count"], 1)
        self.assertEqual(persisted["summary"]["finished_count"], 1)
        self.assertEqual(persisted["summary"]["skipped_count"], 1)

    def test_template_missing_fails_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            router = WorkflowRouter({"dialogue_light_motion": "missing.json"}, project_root)
            client = FakeComfyClient()
            shot_manifest = {"shots": [{"shot_id": "s1", "workflow_route": "dialogue_light_motion"}]}
            result = submit_batch(shot_manifest, project_root / "runtime" / "comfy", client, router, SubmitterConfig())
            acceptance = evaluate_comfy_acceptance(result)
        self.assertEqual(result["tasks"][0]["status"], "template_missing")
        self.assertEqual(acceptance["pipeline_status"], "fail")
        self.assertFalse(acceptance["next_stage_allowed"])


if __name__ == "__main__":
    unittest.main()
