from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipeline.detection.base import DetectionProvider
from pipeline.detection.lightweight_provider import LightweightDetectionProvider


@dataclass(frozen=True)
class GroundedSAM2Config:
    mode: str = "mock"
    prompts: tuple[str, ...] = ("person", "face", "hand", "weapon", "phone", "vehicle", "room", "background object")


class GroundedSAM2DetectionProvider(DetectionProvider):
    """Grounded-SAM-2 compatible detection provider.

    The real Grounded-SAM-2 integration belongs in this file. Until the
    repository has the model weights and runtime dependencies pinned, the
    default mock mode keeps the same provider interface and returns
    deterministic anime-friendly boxes derived from the lightweight provider.
    """

    provider_name = "grounded_sam2_mock"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        settings = ((config or {}).get("detection", {}) or {}).get("grounded_sam2", {}) or {}
        prompts = settings.get("prompts") or GroundedSAM2Config.prompts
        if not isinstance(prompts, (list, tuple)) or not prompts:
            prompts = GroundedSAM2Config.prompts
        self.config = GroundedSAM2Config(
            mode=str(settings.get("mode", "mock")).strip().lower(),
            prompts=tuple(str(item) for item in prompts),
        )
        if self.config.mode not in {"mock", "disabled"}:
            raise RuntimeError(
                "Grounded-SAM-2 real mode is not available yet. "
                "Install the real model runtime and replace "
                "GroundedSAM2DetectionProvider.analyze() in "
                "pipeline/detection/grounded_sam2_provider.py."
            )
        self._fallback = LightweightDetectionProvider(config=config)

    def analyze(self, window_packet: dict[str, Any]) -> dict[str, Any]:
        base = self._fallback.analyze(window_packet)
        width = int(window_packet.get("width") or 0)
        height = int(window_packet.get("height") or 0)
        focus_box = _primary_focus_box(base, width, height)
        object_boxes = _anime_subject_boxes(focus_box, width, height)
        crop_candidates = _tag_crop_candidates(base.get("crop_candidates", []), focus_box)
        return {
            **base,
            "object_boxes": object_boxes,
            "object_masks": [],
            "crop_candidates": crop_candidates,
            "focus_subjects": [
                {
                    "subject_id": "grounded_sam2_mock_subject_0001",
                    "label": "main_character_region",
                    "box": focus_box,
                    "score": 0.62,
                    "provider": self.provider_name,
                }
            ] if focus_box else [],
            "grounding_prompts": list(self.config.prompts),
            "mock_replacement_for": "Grounded-SAM-2",
            "replacement_point": "pipeline/detection/grounded_sam2_provider.py::GroundedSAM2DetectionProvider.analyze",
            "provider": self.provider_name,
        }


def _primary_focus_box(base: dict[str, Any], width: int, height: int) -> list[int] | None:
    subjects = base.get("focus_subjects") or []
    for subject in subjects:
        box = subject.get("box") if isinstance(subject, dict) else None
        normalized = _normalize_box(box, width, height)
        if normalized:
            return normalized
    objects = base.get("object_boxes") or []
    for obj in objects:
        box = obj.get("box") if isinstance(obj, dict) else None
        normalized = _normalize_box(box, width, height)
        if normalized:
            return normalized
    if width <= 0 or height <= 0:
        return None
    return [int(width * 0.15), int(height * 0.15), int(width * 0.85), int(height * 0.85)]


def _anime_subject_boxes(focus_box: list[int] | None, width: int, height: int) -> list[dict[str, Any]]:
    if focus_box is None:
        return []
    x1, y1, x2, y2 = focus_box
    box_w = max(1, x2 - x1)
    box_h = max(1, y2 - y1)
    face = _normalize_box(
        [
            x1 + int(box_w * 0.28),
            y1 + int(box_h * 0.08),
            x1 + int(box_w * 0.72),
            y1 + int(box_h * 0.38),
        ],
        width,
        height,
    )
    left_hand = _normalize_box(
        [
            x1 + int(box_w * 0.08),
            y1 + int(box_h * 0.48),
            x1 + int(box_w * 0.30),
            y1 + int(box_h * 0.72),
        ],
        width,
        height,
    )
    right_hand = _normalize_box(
        [
            x1 + int(box_w * 0.70),
            y1 + int(box_h * 0.48),
            x1 + int(box_w * 0.92),
            y1 + int(box_h * 0.72),
        ],
        width,
        height,
    )
    boxes = [
        ("main_character", focus_box, 0.62),
        ("face", face, 0.48),
        ("hand", left_hand, 0.34),
        ("hand", right_hand, 0.34),
    ]
    return [
        {
            "object_id": f"grounded_sam2_mock_obj_{index:04d}",
            "label": label,
            "box": box,
            "confidence": confidence,
            "source": "grounded_sam2_mock_geometry",
            "provider": GroundedSAM2DetectionProvider.provider_name,
        }
        for index, (label, box, confidence) in enumerate(boxes)
        if box is not None
    ]


def _tag_crop_candidates(candidates: list[dict[str, Any]], focus_box: list[int] | None) -> list[dict[str, Any]]:
    tagged: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        item["provider"] = GroundedSAM2DetectionProvider.provider_name
        item["framing"] = _framing_for_box(item.get("box"), focus_box)
        tagged.append(item)
    return tagged


def _framing_for_box(box: Any, focus_box: list[int] | None) -> str:
    if focus_box is None or not isinstance(box, list) or len(box) != 4:
        return "unknown"
    focus_area = max(1, (focus_box[2] - focus_box[0]) * (focus_box[3] - focus_box[1]))
    crop_area = max(1, (box[2] - box[0]) * (box[3] - box[1]))
    ratio = focus_area / crop_area
    if ratio >= 0.75:
        return "close_up"
    if ratio >= 0.45:
        return "medium_shot"
    return "wide_shot"


def _normalize_box(value: Any, width: int, height: int) -> list[int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x1, y1, x2, y2 = (int(round(float(item))) for item in value)
    except (TypeError, ValueError):
        return None
    if width > 0:
        x1 = max(0, min(width, x1))
        x2 = max(0, min(width, x2))
    if height > 0:
        y1 = max(0, min(height, y1))
        y2 = max(0, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]
