from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline.common.io import write_json
from pipeline.ingest.slicer import SliceConfig
from scripts.run_all_gates import run_all


def _prepare(tmp: Path) -> tuple[Path, Path, Path, Path, Path]:
    image_path = tmp / "runtime" / "input" / "page.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (160, 240), "white").save(image_path)
    chapter_path = tmp / "runtime" / "input" / "chapter.json"
    write_json(
        chapter_path,
        {
            "series_id": "series",
            "chapter_id": "chapter",
            "input_type": "webtoon",
            "pages": [
                {"page_id": "p001", "image_path": "runtime/input/page.png", "width": 160, "height": 240}
            ],
        },
    )
    configs = tmp / "configs"
    configs.mkdir(parents=True, exist_ok=True)
    ocr_config = configs / "ocr.json"
    detect_config = configs / "detect.json"
    director_config = configs / "director.json"
    comfy_config = configs / "comfy.json"
    write_json(ocr_config, {"providers": {"ocr": "paddleocr", "dialogue": "ocr_based", "detection": "mock", "director": "mock"}})
    write_json(detect_config, {"providers": {"ocr": "paddleocr", "dialogue": "ocr_based", "detection": "lightweight", "director": "mock"}})
    write_json(director_config, {
        "providers": {"ocr": "paddleocr", "dialogue": "ocr_based", "detection": "lightweight", "director": "qwen3vl"},
        "director": {"qwen3vl": {"mode": "local", "model_path": str(tmp / "nonexistent_model")}},
    })
    write_json(comfy_config, {"comfy": {"server": "http://127.0.0.1:8188"}, "workflow_templates": {"dialogue_light_motion": "configs/missing.json", "skip": None}})
    return chapter_path, ocr_config, detect_config, director_config, comfy_config


class RunAllGatesCascadeTests(unittest.TestCase):
    def test_stage3a_blocked_cascades_to_all_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            chapter, ocr_cfg, detect_cfg, director_cfg, comfy_cfg = _prepare(project_root)
            report, json_path, md_path = run_all(
                input_path=chapter,
                ocr_config_path=ocr_cfg,
                detect_config_path=detect_cfg,
                director_config_path=director_cfg,
                comfy_config_path=comfy_cfg,
                project_root=project_root,
                runtime_root=project_root / "runtime",
                slice_config=SliceConfig(window_height=160, overlap=20),
                force=True,
            )
            # The exact Stage 3A status depends on whether PaddleOCR is
            # installed in the local environment. The cascade behavior is the
            # invariant: if Stage 3A does not allow the next stage, downstream
            # gates must remain blocked.
            self.assertIn(report["gates"]["stage3a"]["status"], {"blocked", "fail"})
            self.assertFalse(report["gates"]["stage3a"]["next_stage_allowed"])
            for downstream in ("stage4a", "stage5", "stage6"):
                self.assertEqual(report["gates"][downstream]["status"], "blocked")
                self.assertFalse(report["gates"][downstream]["next_stage_allowed"])
            self.assertIn(report["overall_status"], {"blocked", "fail"})
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())


if __name__ == "__main__":
    unittest.main()
