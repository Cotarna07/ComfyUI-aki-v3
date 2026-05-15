from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from PIL import Image

from pipeline.common.io import read_json, write_json
from pipeline.runtime_layout import prepare_runtime_for_input, prepare_runtime_for_manifest


class RuntimeLayoutTests(unittest.TestCase):
    def test_prepare_runtime_for_input_creates_scoped_folder_and_snapshots_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            runtime_root = project_root / "runtime"
            input_dir = runtime_root / "input"
            input_dir.mkdir(parents=True, exist_ok=True)
            image_path = input_dir / "page.png"
            Image.new("RGB", (64, 64), "white").save(image_path)
            input_path = input_dir / "chapter.json"
            write_json(
                input_path,
                {
                    "series_id": "海边物语",
                    "chapter_id": "ep001",
                    "pages": [
                        {
                            "page_id": "p001",
                            "image_path": "runtime/input/page.png",
                            "width": 64,
                            "height": 64,
                        }
                    ],
                },
            )

            context = prepare_runtime_for_input(project_root, runtime_root, input_path)

            self.assertEqual(context.runtime_root.parent, runtime_root)
            self.assertEqual(context.runtime_root.name, f"{date.today().isoformat()}_海边物语")
            self.assertTrue(context.input_path.exists())
            self.assertTrue((context.runtime_root / "_runtime_scope.json").exists())
            scoped_manifest = read_json(context.input_path)
            scoped_image = project_root / scoped_manifest["pages"][0]["image_path"]
            self.assertTrue(scoped_image.exists())
            self.assertEqual(scoped_image.parent, context.runtime_root / "input" / "pages")

    def test_prepare_runtime_for_input_migrates_legacy_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            runtime_root = project_root / "runtime"
            input_dir = runtime_root / "input"
            input_dir.mkdir(parents=True, exist_ok=True)
            image_path = input_dir / "page.png"
            Image.new("RGB", (32, 32), "white").save(image_path)
            input_path = input_dir / "chapter.json"
            write_json(
                input_path,
                {
                    "series_id": "picaweb_hive",
                    "chapter_id": "ep001",
                    "pages": [
                        {
                            "page_id": "p001",
                            "image_path": "runtime/input/page.png",
                            "width": 32,
                            "height": 32,
                        }
                    ],
                },
            )
            legacy_manifest = runtime_root / "windows" / "picaweb_hive" / "ep001" / "window_manifest.json"
            write_json(legacy_manifest, {"series_id": "picaweb_hive", "chapter_id": "ep001", "windows": []})

            context = prepare_runtime_for_input(project_root, runtime_root, input_path)

            migrated_manifest = context.runtime_root / "windows" / "picaweb_hive" / "ep001" / "window_manifest.json"
            self.assertTrue(migrated_manifest.exists())
            self.assertFalse(legacy_manifest.exists())

    def test_prepare_runtime_for_manifest_moves_legacy_manifest_into_scoped_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            runtime_root = project_root / "runtime"
            manifest_path = runtime_root / "manifests" / "picaweb_hive" / "ep001" / "shot_manifest.json"
            write_json(
                manifest_path,
                {
                    "manifest_version": "1",
                    "series_id": "picaweb_hive",
                    "chapter_id": "ep001",
                    "generated_at": "2026-05-15T00:00:00Z",
                    "shots": [],
                },
            )

            context = prepare_runtime_for_manifest(project_root, runtime_root, manifest_path)

            self.assertEqual(context.runtime_root.parent, runtime_root)
            self.assertTrue(context.manifest_path.exists())
            self.assertTrue(str(context.manifest_path).startswith(str(context.runtime_root)))
            self.assertFalse(manifest_path.exists())


if __name__ == "__main__":
    unittest.main()