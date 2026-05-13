from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline.common.io import write_json
from pipeline.ingest.slicer import SliceConfig
from pipeline.stage1 import run_stage1


class Stage1RerunTests(unittest.TestCase):
    def test_rerun_reuses_outputs_without_force_and_rebuilds_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            chapter_path = _make_chapter(project_root)
            config = {"providers": {"ocr": "mock", "dialogue": "mock", "detection": "mock", "director": "mock"}}

            first_report = run_stage1(
                chapter_path,
                project_root,
                project_root / "runtime",
                SliceConfig(window_height=120, overlap=20),
                config=config,
            )
            shot_manifest_path = project_root / first_report["outputs"]["shot_manifest"]
            manifest = _read_json(shot_manifest_path)
            manifest["sentinel"] = "keep-on-reuse"
            write_json(shot_manifest_path, manifest)

            second_report = run_stage1(
                chapter_path,
                project_root,
                project_root / "runtime",
                SliceConfig(window_height=120, overlap=20),
                config=config,
            )
            reused_statuses = {status["stage"]: status["status"] for status in second_report["statuses"]}
            self.assertEqual(reused_statuses["slice_windows"], "reused")
            self.assertEqual(reused_statuses["build_structured_packets"], "reused")
            self.assertEqual(reused_statuses["draft_shot_manifest"], "reused")
            self.assertEqual(_read_json(shot_manifest_path)["sentinel"], "keep-on-reuse")

            run_stage1(
                chapter_path,
                project_root,
                project_root / "runtime",
                SliceConfig(window_height=120, overlap=20),
                config=config,
                force=True,
            )
            self.assertNotIn("sentinel", _read_json(shot_manifest_path))


def _make_chapter(project_root: Path) -> Path:
    image_path = project_root / "runtime" / "input" / "page.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (128, 260), "white").save(image_path)
    chapter_path = project_root / "runtime" / "input" / "chapter.json"
    write_json(
        chapter_path,
        {
            "series_id": "series",
            "chapter_id": "chapter",
            "input_type": "webtoon",
            "pages": [{"page_id": "p001", "image_path": "runtime/input/page.png", "width": 128, "height": 260}],
        },
    )
    return chapter_path


def _read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


if __name__ == "__main__":
    unittest.main()
