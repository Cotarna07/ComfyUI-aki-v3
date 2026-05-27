from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.comfy.submitter import SubmitterConfig, submit_batch
from pipeline.comfy.workflow_router import TemplateMissing, WorkflowRouter
from pipeline.common.io import read_json, write_json
from pipeline.ingest.slicer import SliceConfig
from pipeline.qc.comfy_acceptance import evaluate_comfy_acceptance
import scripts.run_stage6_gate as stage6_gate
from scripts.run_stage6_gate import _template_findings_for_manifest


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


class GateFakeComfyClient(FakeComfyClient):
    last: "GateFakeComfyClient | None" = None

    def __init__(self, config=None) -> None:
        super().__init__()
        self.config = config
        GateFakeComfyClient.last = self


def _fake_stage5_gate(project_root: Path):
    def fake_run_stage5_gate(**kwargs):
        json_path = project_root / "runtime" / "stage5_gate_report.json"
        md_path = project_root / "runtime" / "stage5_gate_report.md"
        write_json(json_path, {"gate_status": "pass", "next_stage_allowed": True})
        md_path.write_text("# Stage 5\n", encoding="utf-8")
        return (
            {"gate_name": "stage5_gate", "gate_status": "pass", "next_stage_allowed": True},
            json_path,
            md_path,
        )

    return fake_run_stage5_gate


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

    def test_validate_routes_only_requires_routes_seen_in_manifest(self) -> None:
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
            light_only = router.validate_routes(["dialogue_light_motion"])
            action_needed = router.validate_routes(["action_performance"])
        self.assertEqual(light_only["missing"], [])
        self.assertEqual(light_only["valid"], ["dialogue_light_motion"])
        self.assertEqual(action_needed["missing"], [{"route": "action_performance", "path": str(Path(tmp) / "missing.json")}])

    def test_validate_routes_reports_missing_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "good.json"
            write_json(existing, {"nodes": {}})
            router = WorkflowRouter(
                {"dialogue_light_motion": "good.json"},
                Path(tmp),
                {"dialogue_light_motion": "missing.mapping.json"},
            )
            findings = router.validate_routes(["dialogue_light_motion"])
        self.assertEqual(findings["missing"], [])
        self.assertEqual(findings["mappings_missing"], [{"route": "dialogue_light_motion", "path": str(Path(tmp) / "missing.mapping.json")}])

    def test_validate_routes_treats_required_disabled_route_as_missing(self) -> None:
        router = WorkflowRouter({"action_performance": None, "skip": None}, Path("."))
        findings = router.validate_routes(["action_performance"])
        self.assertEqual(
            findings["missing"],
            [{"route": "action_performance", "path": "<route disabled in comfy config workflow_templates>"}],
        )

    def test_stage6_template_scope_defaults_to_shot_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "light.json"
            write_json(existing, {"nodes": {}})
            router = WorkflowRouter(
                {
                    "dialogue_light_motion": "light.json",
                    "action_performance": "missing-action.json",
                    "skip": None,
                },
                Path(tmp),
            )
            manifest = {"shots": [{"shot_id": "s1", "workflow_route": "dialogue_light_motion"}]}
            findings, scope, required_routes = _template_findings_for_manifest(
                router,
                manifest,
                require_all_templates=False,
            )
        self.assertEqual(scope, "shot_manifest_routes")
        self.assertEqual(required_routes, ["dialogue_light_motion"])
        self.assertEqual(findings["missing"], [])

    def test_stage6_template_scope_can_require_all_configured_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "light.json"
            write_json(existing, {"nodes": {}})
            router = WorkflowRouter(
                {
                    "dialogue_light_motion": "light.json",
                    "action_performance": "missing-action.json",
                    "skip": None,
                },
                Path(tmp),
            )
            manifest = {"shots": [{"shot_id": "s1", "workflow_route": "dialogue_light_motion"}]}
            findings, scope, required_routes = _template_findings_for_manifest(
                router,
                manifest,
                require_all_templates=True,
            )
        self.assertEqual(scope, "all_configured_routes")
        self.assertEqual(required_routes, ["dialogue_light_motion"])
        self.assertEqual(findings["missing"], [{"route": "action_performance", "path": str(Path(tmp) / "missing-action.json")}])


class Stage6GateRunTests(unittest.TestCase):
    def _write_gate_inputs(self, project_root: Path, *, template_exists: bool, input_dir: str | None = None) -> tuple[Path, Path, Path]:
        input_path = project_root / "runtime" / "input" / "chapter.json"
        write_json(
            input_path,
            {
                "series_id": "series",
                "chapter_id": "chapter",
                "input_type": "webtoon",
                "pages": [],
            },
        )
        manifest_path = project_root / "runtime" / "manifests" / "series" / "chapter" / "shot_manifest.json"
        write_json(
            manifest_path,
            {
                "series_id": "series",
                "chapter_id": "chapter",
                "shots": [
                    {
                        "shot_id": "s1",
                        "workflow_route": "dialogue_light_motion",
                        "positive_prompt": "anime dialogue closeup",
                        "negative_prompt": "bad hands",
                    }
                ],
            },
        )
        workflow_rel = "agent-skills/comfyui/workflows/02-project/manga-anime-pipeline/light.json"
        if template_exists:
            write_json(
                project_root / workflow_rel,
                {
                    "1": {
                        "class_type": "CLIPTextEncode",
                        "inputs": {"text": "old"},
                        "_meta": {"title": "Positive Prompt"},
                    },
                    "2": {"class_type": "KSampler", "inputs": {"seed": 1}},
                    "3": {"class_type": "SaveImage", "inputs": {"filename_prefix": "old"}},
                },
            )
        comfy_settings = {"server": "http://127.0.0.1:8188", "history_poll_attempts": 1}
        if input_dir is not None:
            comfy_settings["input_dir"] = input_dir
        comfy_config_path = project_root / "configs" / "comfy.json"
        write_json(
            comfy_config_path,
            {
                "comfy": comfy_settings,
                "workflow_templates": {
                    "dialogue_light_motion": workflow_rel,
                    "skip": None,
                },
            },
        )
        return input_path, comfy_config_path, manifest_path

    def test_stage6_gate_submits_when_templates_ok_without_input_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            input_path, comfy_config_path, _ = self._write_gate_inputs(project_root, template_exists=True)
            GateFakeComfyClient.last = None
            with (
                patch.object(stage6_gate, "run_stage5_gate", _fake_stage5_gate(project_root)),
                patch.object(stage6_gate, "ComfyClient", GateFakeComfyClient),
            ):
                report, _, _ = stage6_gate.run_gate(
                    input_path=input_path,
                    pipeline_config_path=project_root / "configs" / "director.json",
                    detection_config_path=project_root / "configs" / "detect.json",
                    upstream_config_path=project_root / "configs" / "detect.json",
                    comfy_config_path=comfy_config_path,
                    project_root=project_root,
                    runtime_root=project_root / "runtime",
                    slice_config=SliceConfig(),
                    force=True,
                )
        self.assertEqual(report["gate_status"], "pass")
        self.assertTrue(report["checks"]["submission_ran"])
        self.assertEqual(len(GateFakeComfyClient.last.submitted), 1)
        self.assertEqual(report["comfy_config_summary"]["validation_scope"], "shot_manifest_routes")

    def test_stage6_gate_does_not_submit_when_required_template_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            input_path, comfy_config_path, _ = self._write_gate_inputs(
                project_root,
                template_exists=False,
                input_dir="ComfyUI/input",
            )
            GateFakeComfyClient.last = None
            with (
                patch.object(stage6_gate, "run_stage5_gate", _fake_stage5_gate(project_root)),
                patch.object(stage6_gate, "ComfyClient", GateFakeComfyClient),
            ):
                report, _, _ = stage6_gate.run_gate(
                    input_path=input_path,
                    pipeline_config_path=project_root / "configs" / "director.json",
                    detection_config_path=project_root / "configs" / "detect.json",
                    upstream_config_path=project_root / "configs" / "detect.json",
                    comfy_config_path=comfy_config_path,
                    project_root=project_root,
                    runtime_root=project_root / "runtime",
                    slice_config=SliceConfig(),
                    force=True,
                )
        self.assertEqual(report["gate_status"], "fail")
        self.assertFalse(report["checks"]["submission_ran"])
        self.assertEqual(GateFakeComfyClient.last.submitted, [])
        self.assertIn("template missing", report["errors"][0])


class SubmitterTests(unittest.TestCase):
    def _write_template(self, tmp: Path) -> Path:
        template = tmp / "configs" / "comfy_workflows" / "wf.json"
        write_json(
            template,
            {
                "1": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "old"},
                    "_meta": {"title": "Positive Prompt"},
                },
                "2": {"class_type": "KSampler", "inputs": {"seed": 1}},
                "3": {"class_type": "SaveImage", "inputs": {"filename_prefix": "old"}},
            },
        )
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
                "series_id": "series",
                "chapter_id": "chapter",
                "shots": [
                    {
                        "shot_id": "s1",
                        "workflow_route": "dialogue_light_motion",
                        "positive_prompt": "anime dialogue closeup",
                        "negative_prompt": "bad hands",
                    },
                    {"shot_id": "s2", "workflow_route": "skip"},
                ]
            }
            output_dir = project_root / "runtime" / "comfy"
            result = submit_batch(shot_manifest, output_dir, client, router, SubmitterConfig())
            tasks = result["tasks"]
            persisted = read_json(result["output_path"])
            self.assertEqual(tasks[0]["status"], "finished")
            self.assertEqual(tasks[0]["prompt_id"], "pid-1")
            self.assertIn("positive_prompt:1.text", tasks[0]["patched_fields"])
            self.assertIn("anime dialogue closeup", client.submitted[0]["prompt"]["1"]["inputs"]["text"])
            self.assertEqual(client.submitted[0]["prompt"]["2"]["inputs"]["seed"], tasks[0]["seed"])
            self.assertTrue(Path(tasks[0]["patched_workflow_path"]).exists())
            self.assertEqual(len(tasks[0]["provenance_files"]), 1)
            provenance = read_json(Path(tasks[0]["provenance_files"][0]))
            self.assertEqual(provenance["output_file"], "pid-1.png")
            self.assertEqual(provenance["workflow_api"]["2"]["inputs"]["seed"], tasks[0]["seed"])
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

    def test_acceptance_can_require_finished_tasks(self) -> None:
        result = {
            "summary": {
                "shot_count": 1,
                "submitted_count": 1,
                "finished_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "template_missing_routes": [],
            },
            "tasks": [{"shot_id": "s1", "status": "submitted", "output_files": []}],
        }
        acceptance = evaluate_comfy_acceptance(result, require_finished=True)
        self.assertEqual(acceptance["pipeline_status"], "fail")
        self.assertIn("submitted shots not finished yet: s1", acceptance["errors"])
        self.assertEqual(acceptance["comfy_quality"]["submitted_unfinished_count"], 1)

    def test_acceptance_can_require_output_files(self) -> None:
        result = {
            "summary": {
                "shot_count": 1,
                "submitted_count": 1,
                "finished_count": 1,
                "failed_count": 0,
                "skipped_count": 0,
                "template_missing_routes": [],
            },
            "tasks": [{"shot_id": "s1", "status": "finished", "output_files": []}],
        }
        acceptance = evaluate_comfy_acceptance(result, require_outputs=True)
        self.assertEqual(acceptance["pipeline_status"], "fail")
        self.assertIn("finished shots missing ComfyUI output files: s1", acceptance["errors"])
        self.assertEqual(acceptance["comfy_quality"]["finished_without_outputs_count"], 1)

    def test_unpatched_template_fails_before_submit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            template = project_root / "configs" / "comfy_workflows" / "wf.json"
            write_json(template, {"1": {"class_type": "PreviewImage", "inputs": {"images": ["0", 0]}}})
            router = WorkflowRouter({"dialogue_light_motion": str(template.relative_to(project_root))}, project_root)
            client = FakeComfyClient()
            shot_manifest = {
                "series_id": "series",
                "chapter_id": "chapter",
                "shots": [
                    {
                        "shot_id": "s1",
                        "workflow_route": "dialogue_light_motion",
                        "positive_prompt": "anime dialogue closeup",
                        "negative_prompt": "bad hands",
                    }
                ],
            }
            result = submit_batch(shot_manifest, project_root / "runtime" / "comfy", client, router, SubmitterConfig())
        self.assertEqual(result["tasks"][0]["status"], "failed")
        self.assertIn("no workflow fields were patched", result["tasks"][0]["error_message"])
        self.assertEqual(client.submitted, [])


if __name__ == "__main__":
    unittest.main()
