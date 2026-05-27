from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline.comfy.template_patcher import TemplatePatchError, patch_workflow_template
from pipeline.common.io import write_json


def _shot() -> dict:
    return {
        "shot_id": "ch01_s0001",
        "source_pages": ["p001"],
        "source_windows": ["w001"],
        "source_ranges": [{"page_id": "p001", "box": [0, 0, 200, 300]}],
        "workflow_route": "dialogue_light_motion",
        "positive_prompt": "anime girl quietly answering a friend",
        "negative_prompt": "blurry",
        "style_anchor": "clean shonen line art",
        "emotion": "soft worry",
        "dialogue_summary": "I am fine.",
        "main_characters": ["heroine"],
        "crop_recommendation": {"type": "medium_shot", "box": [20, 30, 180, 260]},
    }


def _workflow() -> dict:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": "example.png"}},
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "old positive"},
            "_meta": {"title": "Positive Prompt"},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "old negative"},
            "_meta": {"title": "Negative Prompt"},
        },
        "4": {"class_type": "KSamplerAdvanced", "inputs": {"noise_seed": 1}},
        "5": {"class_type": "SaveVideo", "inputs": {"filename_prefix": "old/output"}},
    }


def _write_packet(project_root: Path, window_id: str, image_rel: str, size: tuple[int, int]) -> str:
    image_path = project_root / image_rel
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(image_path)
    packet_path = project_root / "runtime" / "structured" / "series" / "chapter" / "packets" / f"{window_id}.json"
    write_json(
        packet_path,
        {
            "window_id": window_id,
            "window_image_path": image_rel,
            "source_box": [0, 0, size[0], size[1]],
        },
    )
    return str(packet_path.relative_to(project_root))


class TemplatePatcherTests(unittest.TestCase):
    def test_mapping_patches_prompt_seed_prefix_and_prepares_crop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            input_dir = project_root / "ComfyUI" / "input"
            source = project_root / "runtime" / "windows" / "series" / "chapter" / "p001" / "w001.png"
            source.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (200, 300), "white").save(source)
            packet_path = project_root / "runtime" / "structured" / "series" / "chapter" / "packets" / "w001.json"
            write_json(
                packet_path,
                {
                    "window_id": "w001",
                    "window_image_path": "runtime/windows/series/chapter/p001/w001.png",
                    "source_box": [0, 0, 200, 300],
                },
            )
            manifest = {
                "series_id": "series",
                "chapter_id": "chapter",
                "source_packet_refs": ["runtime/structured/series/chapter/packets/w001.json"],
            }
            mapping = {
                "positive_prompt": {"node_id": "2", "input": "text"},
                "negative_prompt": {"node_id": "3", "input": "text"},
                "input_image": {"node_id": "1", "input": "image"},
                "seed": {"node_id": "4", "input": "noise_seed"},
                "output_prefix": {"node_id": "5", "input": "filename_prefix"},
            }

            result = patch_workflow_template(
                _workflow(),
                _shot(),
                manifest,
                project_root=project_root,
                mapping=mapping,
                comfy_input_dir=input_dir,
            )
            self.assertIn("light dialogue motion", result.workflow["2"]["inputs"]["text"])
            self.assertIn("large mouth movement", result.workflow["3"]["inputs"]["text"])
            self.assertEqual(result.workflow["4"]["inputs"]["noise_seed"], result.seed)
            self.assertEqual(result.workflow["5"]["inputs"]["filename_prefix"], result.output_prefix)
            self.assertEqual(result.workflow["1"]["inputs"]["image"], "manga_anime_pipeline/series/chapter/ch01_s0001_crop.png")
            self.assertIsNotNone(result.input_image)
            assert result.input_image is not None
            self.assertEqual(result.input_image.crop_box, [20, 30, 180, 260])
            self.assertTrue(Path(result.input_image.output_path).exists())

    def test_auto_mapping_patches_common_comfy_nodes(self) -> None:
        manifest = {"series_id": "series", "chapter_id": "chapter", "source_packet_refs": []}
        result = patch_workflow_template(
            {
                "2": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "old"},
                    "_meta": {"title": "Positive Prompt"},
                },
                "4": {"class_type": "KSampler", "inputs": {"seed": 99}},
                "5": {"class_type": "SaveImage", "inputs": {"filename_prefix": "old"}},
            },
            {**_shot(), "crop_recommendation": {}},
            manifest,
            project_root=Path("."),
            mapping=None,
            comfy_input_dir=None,
        )
        self.assertIn("anime girl quietly answering", result.workflow["2"]["inputs"]["text"])
        self.assertEqual(result.workflow["4"]["inputs"]["seed"], result.seed)
        self.assertEqual(result.workflow["5"]["inputs"]["filename_prefix"], result.output_prefix)

    def test_missing_mapping_node_fails_clearly(self) -> None:
        with self.assertRaisesRegex(TemplatePatchError, "missing node_id=999"):
            patch_workflow_template(
                {"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}}},
                _shot(),
                {"series_id": "series", "chapter_id": "chapter"},
                project_root=Path("."),
                mapping={"positive_prompt": {"node_id": "999", "input": "text"}},
            )

    def test_no_patch_targets_fails_in_strict_mode(self) -> None:
        with self.assertRaisesRegex(TemplatePatchError, "no workflow fields were patched"):
            patch_workflow_template(
                {"1": {"class_type": "PreviewImage", "inputs": {"images": ["0", 0]}}},
                _shot(),
                {"series_id": "series", "chapter_id": "chapter"},
                project_root=Path("."),
                mapping=None,
            )

    def test_multi_input_mapping_patches_multiple_source_and_reference_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            input_dir = project_root / "ComfyUI" / "input"
            packet_1 = _write_packet(project_root, "w001", "runtime/windows/series/chapter/p001/w001.png", (200, 300))
            packet_2 = _write_packet(project_root, "w002", "runtime/windows/series/chapter/p001/w002.png", (220, 320))
            pose_path = project_root / "runtime" / "refs" / "pose.png"
            pose_path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (64, 64), "black").save(pose_path)
            manifest = {
                "series_id": "series",
                "chapter_id": "chapter",
                "source_packet_refs": [packet_1, packet_2],
            }
            workflow = {
                "10": {"class_type": "LoadImage", "inputs": {"image": "old-a.png"}},
                "11": {"class_type": "LoadImage", "inputs": {"image": "old-b.png"}},
                "12": {"class_type": "LoadImage", "inputs": {"image": "old-pose.png"}},
            }
            shot = {
                **_shot(),
                "source_windows": ["w001", "w002"],
                "pose_image_path": str(pose_path.relative_to(project_root)),
            }
            result = patch_workflow_template(
                workflow,
                shot,
                manifest,
                project_root=project_root,
                mapping={
                    "source_image_0": {"node_id": "10", "input": "image"},
                    "source_image_1": {"node_id": "11", "input": "image"},
                    "pose_image": {"node_id": "12", "input": "image"},
                },
                comfy_input_dir=input_dir,
            )

        self.assertEqual(result.workflow["10"]["inputs"]["image"], "manga_anime_pipeline/series/chapter/ch01_s0001_source_image_0.png")
        self.assertEqual(result.workflow["11"]["inputs"]["image"], "manga_anime_pipeline/series/chapter/ch01_s0001_source_image_1.png")
        self.assertEqual(result.workflow["12"]["inputs"]["image"], "manga_anime_pipeline/series/chapter/ch01_s0001_pose_image.png")
        self.assertIn("source_image_0", result.input_assets)
        self.assertIn("source_image_1", result.input_assets)
        self.assertIn("pose_image", result.input_assets)


if __name__ == "__main__":
    unittest.main()
