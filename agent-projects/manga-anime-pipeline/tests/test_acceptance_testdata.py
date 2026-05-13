from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from pipeline.common.io import write_json


def make_acceptance_case(
    project_root: Path,
    ocr_provider: str = "paddleocr",
    dialogue_provider: str = "ocr_based",
    write_artifacts: bool = True,
) -> dict[str, Any]:
    runtime_root = project_root / "runtime"
    chapter = _chapter()
    input_path = runtime_root / "input" / "chapter.json"
    config_path = project_root / "configs" / "stage1.ocr.dialogue.json"
    image_path = runtime_root / "input" / "page.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (128, 120), "white").save(image_path)
    write_json(input_path, chapter)
    config = {
        "providers": {"ocr": "paddleocr", "dialogue": "ocr_based", "detection": "mock", "director": "mock"},
        "dialogue": {"ocr_based": {"min_confidence": 0.3, "max_merge_distance": 48, "min_text_length": 1}},
    }
    write_json(config_path, config)
    if write_artifacts:
        _write_artifacts(project_root, runtime_root, ocr_provider, dialogue_provider)
    return {
        "project_root": project_root,
        "runtime_root": runtime_root,
        "input_path": input_path,
        "config_path": config_path,
        "config": config,
        "chapter": chapter,
        "stage_report": {
            "providers": {"ocr": ocr_provider, "dialogue": dialogue_provider, "detection": "mock_detection", "director": "mock_director"},
            "outputs": {
                "window_manifest": "runtime/windows/series/chapter/window_manifest.json",
                "structured_packet_index": "runtime/structured/series/chapter/structured_packets.json",
                "shot_manifest": "runtime/manifests/series/chapter/shot_manifest.json",
                "status_report": "runtime/qc/series/chapter/stage1_status.json",
            },
        },
    }


def _chapter() -> dict[str, Any]:
    return {
        "series_id": "series",
        "chapter_id": "chapter",
        "input_type": "webtoon",
        "pages": [{"page_id": "p001", "image_path": "runtime/input/page.png", "width": 128, "height": 120}],
    }


def _write_artifacts(project_root: Path, runtime_root: Path, ocr_provider: str, dialogue_provider: str) -> None:
    window_dir = runtime_root / "windows" / "series" / "chapter" / "p001"
    window_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (128, 120), "white").save(window_dir / "w0000.png")
    write_json(
        runtime_root / "windows" / "series" / "chapter" / "window_manifest.json",
        {
            "series_id": "series",
            "chapter_id": "chapter",
            "generated_at": "2026-05-14T00:00:00Z",
            "window_height": 120,
            "overlap": 20,
            "windows": [
                {
                    "window_id": "chapter_p001_w0000",
                    "page_id": "p001",
                    "source_page": "p001",
                    "image_path": "runtime/windows/series/chapter/p001/w0000.png",
                    "source_box": [0, 0, 128, 120],
                    "overlap_prev": 0,
                    "overlap_next": 0,
                    "width": 128,
                    "height": 120,
                    "index": 0,
                }
            ],
        },
    )
    packet_path = runtime_root / "structured" / "series" / "chapter" / "packets" / "chapter_p001_w0000.json"
    write_json(packet_path, _packet(ocr_provider, dialogue_provider))
    write_json(
        runtime_root / "structured" / "series" / "chapter" / "structured_packets.json",
        {
            "series_id": "series",
            "chapter_id": "chapter",
            "generated_at": "2026-05-14T00:00:00Z",
            "packet_refs": ["runtime/structured/series/chapter/packets/chapter_p001_w0000.json"],
            "packets": [{"window_id": "chapter_p001_w0000", "packet_path": "runtime/structured/series/chapter/packets/chapter_p001_w0000.json"}],
        },
    )
    write_json(runtime_root / "manifests" / "series" / "chapter" / "shot_manifest.json", _shot_manifest())
    write_json(runtime_root / "qc" / "series" / "chapter" / "stage1_status.json", _status_report(ocr_provider, dialogue_provider))


def _packet(ocr_provider: str, dialogue_provider: str) -> dict[str, Any]:
    dialogue_text = "你好，世界"
    dialogue_block = {
        "dialogue_id": "chapter_p001_w0000_dlg_0000",
        "text": dialogue_text,
        "source_ocr_blocks": ["chapter_p001_w0000_ocr_0000"],
        "box": [10, 10, 80, 28],
        "confidence": 0.91,
        "dialogue_type": "speech",
        "speaker": None,
        "provider": dialogue_provider,
    }
    return {
        "packet_version": "stage1.mock.v1",
        "series_id": "series",
        "chapter_id": "chapter",
        "window_id": "chapter_p001_w0000",
        "page_id": "p001",
        "source_page": "p001",
        "window_image_path": "runtime/windows/series/chapter/p001/w0000.png",
        "source_box": [0, 0, 128, 120],
        "created_at": "2026-05-14T00:00:00Z",
        "ocr_blocks": [
            {
                "block_id": "chapter_p001_w0000_ocr_0000",
                "text": dialogue_text,
                "box": [10, 10, 80, 28],
                "confidence": 0.92,
                "language": "unknown",
                "provider": ocr_provider,
            }
        ],
        "reading_order": ["chapter_p001_w0000_ocr_0000"],
        "layout_blocks": [],
        "dialogue_blocks": [dialogue_block],
        "bubble_boxes": [],
        "sfx_blocks": [],
        "cleaned_text_candidates": [
            {
                "candidate_id": "chapter_p001_w0000_txt_0000",
                "text": dialogue_text,
                "source_dialogue_id": dialogue_block["dialogue_id"],
                "confidence": 0.91,
                "provider": dialogue_provider,
            }
        ],
        "object_boxes": [],
        "object_masks": [],
        "crop_candidates": [{"crop_id": "crop_0000", "type": "full_window", "box": [0, 0, 128, 120], "score": 0.5}],
        "focus_subjects": [],
        "scene_density": 0.5,
        "provider": dialogue_provider,
    }


def _shot_manifest() -> dict[str, Any]:
    return {
        "manifest_version": "stage1.mock.v1",
        "series_id": "series",
        "chapter_id": "chapter",
        "generated_at": "2026-05-14T00:00:00Z",
        "director": {"provider": "mock_director", "model": "mock"},
        "source_packet_refs": ["runtime/structured/series/chapter/packets/chapter_p001_w0000.json"],
        "shots": [
            {
                "shot_id": "chapter_s0000",
                "source_pages": ["p001"],
                "source_windows": ["chapter_p001_w0000"],
                "source_ranges": [{"page_id": "p001", "box": [0, 0, 128, 120]}],
                "merge_with_prev": False,
                "merge_with_next": False,
                "story_role": "scene_setup",
                "shot_type": "dialogue",
                "anime_fit_score": 0.8,
                "main_characters": ["unknown_character"],
                "support_characters": [],
                "emotion": "neutral",
                "action_level": "low",
                "dialogue_summary": "你好，世界",
                "continuity_notes": [],
                "crop_recommendation": {"type": "full_window", "box": [0, 0, 128, 120]},
                "positive_prompt": "anime dialogue",
                "negative_prompt": "bad anatomy",
                "style_anchor": "style",
                "workflow_route": "dialogue_light_motion",
                "confidence": 0.8,
            }
        ],
    }


def _status_report(ocr_provider: str, dialogue_provider: str) -> dict[str, Any]:
    return {
        "run_id": "stage1-test",
        "series_id": "series",
        "chapter_id": "chapter",
        "overall_status": "succeeded",
        "started_at": "2026-05-14T00:00:00Z",
        "finished_at": "2026-05-14T00:00:01Z",
        "outputs": {},
        "providers": {"ocr": ocr_provider, "dialogue": dialogue_provider, "detection": "mock_detection", "director": "mock_director"},
        "statuses": [
            {
                "task_id": "load_chapter-test",
                "stage": "load_chapter",
                "status": "succeeded",
                "started_at": "2026-05-14T00:00:00Z",
                "finished_at": "2026-05-14T00:00:01Z",
                "input_refs": [],
                "output_refs": [],
                "error_message": None,
                "retry_count": 0,
            }
        ],
    }
