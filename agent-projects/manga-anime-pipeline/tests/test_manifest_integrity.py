from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline.common.io import resolve_project_path, write_json
from pipeline.ingest.slicer import SliceConfig
from pipeline.manifest.integrity import validate_shot_manifest_links, validate_structured_packets, validate_window_manifest
from pipeline.stage1 import run_stage1


class ManifestIntegrityTests(unittest.TestCase):
    def test_window_packet_and_shot_ids_are_traceable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            chapter_path = _make_chapter(project_root)
            report = run_stage1(
                chapter_path,
                project_root,
                project_root / "runtime",
                SliceConfig(window_height=120, overlap=20),
                config={"providers": {"ocr": "mock", "dialogue": "mock", "detection": "mock", "director": "mock"}},
            )

            chapter = _read_json(chapter_path)
            window_manifest = _read_json(project_root / report["outputs"]["window_manifest"])
            packet_index = _read_json(project_root / report["outputs"]["structured_packet_index"])
            packets = [_read_json(resolve_project_path(project_root, ref)) for ref in packet_index["packet_refs"]]
            shot_manifest = _read_json(project_root / report["outputs"]["shot_manifest"])

            validate_window_manifest(chapter, window_manifest, project_root)
            validate_structured_packets(window_manifest, packets)
            validate_shot_manifest_links(packets, shot_manifest)
            self.assertEqual({window["window_id"] for window in window_manifest["windows"]}, {packet["window_id"] for packet in packets})
            self.assertTrue(all("source_page" in window for window in window_manifest["windows"]))
            packet_ids = {packet["window_id"] for packet in packets}
            for shot in shot_manifest["shots"]:
                self.assertTrue(set(shot["source_windows"]).issubset(packet_ids))


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
