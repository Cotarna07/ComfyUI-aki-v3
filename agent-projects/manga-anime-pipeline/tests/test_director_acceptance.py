from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.common.io import write_json
from pipeline.common.schemas import WORKFLOW_ROUTES
from pipeline.qc.director_acceptance import evaluate_director_acceptance


def _make_chapter() -> dict:
    return {"series_id": "series", "chapter_id": "chapter", "pages": []}


def _make_shot(shot_id: str, route: str, provider: str = "qwen3vl") -> dict:
    return {
        "shot_id": shot_id,
        "source_pages": ["p001"],
        "source_windows": ["w001"],
        "workflow_route": route,
        "positive_prompt": "anime style girl talking",
        "negative_prompt": "blurry, low quality",
        "anime_fit_score": 0.8,
        "confidence": 0.7,
        "provider": provider,
        "story_role": "scene_setup",
        "shot_type": "dialogue",
    }


class DirectorAcceptanceTests(unittest.TestCase):
    def _write_manifest(self, tmp: Path, shots: list[dict]) -> None:
        manifest_path = tmp / "runtime" / "manifests" / "series" / "chapter" / "shot_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(manifest_path, {"series_id": "series", "chapter_id": "chapter", "shots": shots})

    def test_qwen3vl_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_manifest(
                project_root,
                [
                    _make_shot("s1", "dialogue_light_motion"),
                    _make_shot("s2", "action_performance"),
                ],
            )
            result = evaluate_director_acceptance(
                project_root=project_root,
                runtime_root=project_root / "runtime",
                config={"providers": {"director": "qwen3vl"}},
                chapter=_make_chapter(),
            )
        self.assertEqual(result["pipeline_status"], "pass")
        self.assertTrue(result["next_stage_allowed"])

    def test_mock_director_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_manifest(project_root, [_make_shot("s1", "dialogue_light_motion", provider="mock_director")])
            result = evaluate_director_acceptance(
                project_root=project_root,
                runtime_root=project_root / "runtime",
                config={"providers": {"director": "qwen3vl"}},
                chapter=_make_chapter(),
            )
        self.assertEqual(result["pipeline_status"], "fail")
        self.assertFalse(result["next_stage_allowed"])

    def test_invalid_route_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            shot = _make_shot("s1", "bogus_route")
            self._write_manifest(project_root, [shot])
            result = evaluate_director_acceptance(
                project_root=project_root,
                runtime_root=project_root / "runtime",
                config={"providers": {"director": "qwen3vl"}},
                chapter=_make_chapter(),
            )
        self.assertEqual(result["pipeline_status"], "fail")
        self.assertIn("invalid workflow_route", " ".join(result["errors"]))

    def test_workflow_routes_known(self) -> None:
        self.assertIn("dialogue_light_motion", WORKFLOW_ROUTES)
        self.assertIn("skip", WORKFLOW_ROUTES)


if __name__ == "__main__":
    unittest.main()
