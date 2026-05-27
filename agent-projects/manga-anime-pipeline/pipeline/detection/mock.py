from __future__ import annotations

from typing import Any

from pipeline.detection.base import DetectionProvider


class MockDetectionProvider(DetectionProvider):
    """Grounded-SAM-2 stand-in that emits object, mask, and crop candidate fields."""

    provider_name = "mock_detection"

    def analyze(self, window: dict[str, Any]) -> dict[str, Any]:
        width = int(window.get("width", 1))
        height = int(window.get("height", 1))
        window_id = window["window_id"]
        subject_box = [int(width * 0.18), int(height * 0.25), int(width * 0.72), int(height * 0.90)]
        crop_box = _expand_box(subject_box, width, height, 0.16)
        return {
            "object_boxes": [
                {
                    "object_id": f"{window_id}_object_000",
                    "label": "mock_character",
                    "box": subject_box,
                    "confidence": 0.70,
                    "provider": self.provider_name,
                }
            ],
            "object_masks": [
                {
                    "mask_id": f"{window_id}_mask_000",
                    "object_id": f"{window_id}_object_000",
                    "format": "mock_polygon",
                    "polygon": [
                        [subject_box[0], subject_box[1]],
                        [subject_box[2], subject_box[1]],
                        [subject_box[2], subject_box[3]],
                        [subject_box[0], subject_box[3]],
                    ],
                    "provider": self.provider_name,
                }
            ],
            "crop_candidates": [
                {
                    "crop_id": f"{window_id}_crop_000",
                    "type": "medium_character_shot",
                    "box": crop_box,
                    "score": 0.68,
                    "reason": "mock focus area around the dominant character",
                    "provider": self.provider_name,
                }
            ],
            "focus_subjects": [
                {
                    "subject_id": f"{window_id}_subject_000",
                    "label": "mock_character",
                    "box": subject_box,
                    "importance": 0.73,
                }
            ],
            "scene_density": 0.48,
        }


def _expand_box(box: list[int], width: int, height: int, ratio: float) -> list[int]:
    left, top, right, bottom = box
    box_width = right - left
    box_height = bottom - top
    dx = int(box_width * ratio)
    dy = int(box_height * ratio)
    return [max(0, left - dx), max(0, top - dy), min(width, right + dx), min(height, bottom + dy)]
