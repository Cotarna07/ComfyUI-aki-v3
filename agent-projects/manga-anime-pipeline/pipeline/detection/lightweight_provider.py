from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.detection.base import DetectionProvider


@dataclass(frozen=True)
class LightweightDetectionConfig:
    min_crop_score: float = 0.2
    avoid_text_overlap: bool = True
    center_crop_ratios: tuple[float, ...] = (0.75, 0.9, 1.0)


class LightweightDetectionProvider(DetectionProvider):
    """Rule-based detection provider using Pillow only.

    Does not load heavy models. Generates center-biased crop candidates and
    estimates scene density from edge intensity. Avoids OCR/dialogue text
    regions when computing focus boxes.
    """

    provider_name = "lightweight"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        settings = ((config or {}).get("detection", {}) or {}).get("lightweight", {}) or {}
        ratios = settings.get("center_crop_ratios", [0.75, 0.9, 1.0])
        if not isinstance(ratios, (list, tuple)) or not ratios:
            ratios = [0.75, 0.9, 1.0]
        self.config = LightweightDetectionConfig(
            min_crop_score=float(settings.get("min_crop_score", 0.2)),
            avoid_text_overlap=bool(settings.get("avoid_text_overlap", True)),
            center_crop_ratios=tuple(float(item) for item in ratios),
        )

    def analyze(self, window_packet: dict[str, Any]) -> dict[str, Any]:
        width = int(window_packet.get("width") or 0)
        height = int(window_packet.get("height") or 0)
        if width <= 0 or height <= 0:
            return _empty_result()
        image_path = _resolve_image_path(window_packet)
        density_value, density_level = _estimate_density(image_path, width, height)
        text_boxes = _collect_text_boxes(window_packet, width, height)
        focus_box = _focus_box(width, height, text_boxes)
        crop_candidates = _build_crops(width, height, self.config, text_boxes, density_value)
        object_boxes = _focus_to_object_boxes(focus_box) if focus_box else []
        focus_subjects = _focus_to_subjects(focus_box) if focus_box else []
        return {
            "object_boxes": object_boxes,
            "object_masks": [],
            "crop_candidates": crop_candidates,
            "focus_subjects": focus_subjects,
            "scene_density": {
                "value": round(density_value, 4),
                "level": density_level,
                "provider": LightweightDetectionProvider.provider_name,
            },
            "provider": LightweightDetectionProvider.provider_name,
        }


def _empty_result() -> dict[str, Any]:
    return {
        "object_boxes": [],
        "object_masks": [],
        "crop_candidates": [],
        "focus_subjects": [],
        "scene_density": {"value": 0.0, "level": "low", "provider": LightweightDetectionProvider.provider_name},
        "provider": LightweightDetectionProvider.provider_name,
    }


def _resolve_image_path(window_packet: dict[str, Any]) -> Path | None:
    value = window_packet.get("resolved_image_path") or window_packet.get("image_path")
    if not value:
        return None
    path = Path(str(value))
    if path.is_absolute():
        return path
    project_root = window_packet.get("project_root")
    if project_root:
        return Path(str(project_root)) / path
    return Path.cwd() / path


def _estimate_density(image_path: Path | None, width: int, height: int) -> tuple[float, str]:
    if image_path is None or not image_path.exists():
        return 0.0, "low"
    try:
        from PIL import Image, ImageFilter
    except Exception:
        return 0.0, "low"
    try:
        with Image.open(image_path) as image:
            gray = image.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            histogram = edges.histogram()
        total = sum(histogram)
        if total <= 0:
            return 0.0, "low"
        weighted = sum(value * count for value, count in enumerate(histogram))
        average = weighted / total
        normalized = min(1.0, max(0.0, average / 80.0))
    except Exception:
        return 0.0, "low"
    if normalized < 0.25:
        level = "low"
    elif normalized < 0.6:
        level = "medium"
    else:
        level = "high"
    return normalized, level


def _collect_text_boxes(window_packet: dict[str, Any], width: int, height: int) -> list[list[int]]:
    boxes: list[list[int]] = []
    ocr_result = window_packet.get("ocr_result") or {}
    dialogue_result = window_packet.get("dialogue_result") or {}
    for block in ocr_result.get("ocr_blocks", []):
        box = _normalize_box(block.get("box"), width, height)
        if box:
            boxes.append(box)
    for block in dialogue_result.get("dialogue_blocks", []):
        box = _normalize_box(block.get("box"), width, height)
        if box:
            boxes.append(box)
    for box_entry in dialogue_result.get("bubble_boxes", []):
        candidate = box_entry.get("box") if isinstance(box_entry, dict) else box_entry
        box = _normalize_box(candidate, width, height)
        if box:
            boxes.append(box)
    return boxes


def _normalize_box(value: Any, width: int, height: int) -> list[int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x1, y1, x2, y2 = (int(round(float(item))) for item in value)
    except (TypeError, ValueError):
        return None
    x1 = max(0, min(width, x1))
    x2 = max(0, min(width, x2))
    y1 = max(0, min(height, y1))
    y2 = max(0, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]


def _focus_box(width: int, height: int, text_boxes: list[list[int]]) -> list[int] | None:
    if width <= 0 or height <= 0:
        return None
    if not text_boxes:
        return [int(width * 0.15), int(height * 0.15), int(width * 0.85), int(height * 0.85)]
    top_text = min((box[1] for box in text_boxes), default=0)
    bottom_text = max((box[3] for box in text_boxes), default=height)
    above_space = top_text
    below_space = height - bottom_text
    if above_space >= below_space and above_space >= int(height * 0.2):
        return [int(width * 0.1), max(0, int(above_space * 0.1)), int(width * 0.9), max(int(height * 0.3), top_text)]
    if below_space >= int(height * 0.2):
        return [int(width * 0.1), min(height - 1, bottom_text), int(width * 0.9), int(height - max(0, below_space * 0.05))]
    return [int(width * 0.15), int(height * 0.15), int(width * 0.85), int(height * 0.85)]


def _build_crops(
    width: int,
    height: int,
    config: LightweightDetectionConfig,
    text_boxes: list[list[int]],
    density_value: float,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    center_x = width / 2.0
    center_y = height / 2.0
    base_score = max(config.min_crop_score, min(1.0, 0.55 + density_value * 0.3))
    for index, ratio in enumerate(config.center_crop_ratios):
        ratio = max(0.1, min(1.0, ratio))
        crop_w = max(1, int(width * ratio))
        crop_h = max(1, int(height * ratio))
        x1 = int(round(center_x - crop_w / 2.0))
        y1 = int(round(center_y - crop_h / 2.0))
        x1 = max(0, min(width - crop_w, x1))
        y1 = max(0, min(height - crop_h, y1))
        x2 = x1 + crop_w
        y2 = y1 + crop_h
        overlaps = config.avoid_text_overlap and _has_overlap([x1, y1, x2, y2], text_boxes)
        score = round(max(0.0, base_score - (0.1 * overlaps) - (0.05 * index)), 4)
        if score < config.min_crop_score:
            continue
        candidates.append(
            {
                "crop_id": f"crop_{index:04d}",
                "box": [x1, y1, x2, y2],
                "reason": "center_composition" if not overlaps else "center_with_text_overlap",
                "score": score,
                "avoid_text_overlap": config.avoid_text_overlap and not overlaps,
                "provider": LightweightDetectionProvider.provider_name,
            }
        )
    return candidates


def _has_overlap(box: list[int], others: list[list[int]]) -> bool:
    x1, y1, x2, y2 = box
    for other in others:
        ox1, oy1, ox2, oy2 = other
        if x1 < ox2 and ox1 < x2 and y1 < oy2 and oy1 < y2:
            return True
    return False


def _focus_to_object_boxes(box: list[int]) -> list[dict[str, Any]]:
    return [
        {
            "object_id": "obj_0001",
            "label": "visual_subject",
            "box": box,
            "confidence": 0.5,
            "source": "lightweight",
            "provider": LightweightDetectionProvider.provider_name,
        }
    ]


def _focus_to_subjects(box: list[int]) -> list[dict[str, Any]]:
    return [
        {
            "subject_id": "subj_0001",
            "box": box,
            "label": "main_visual_region",
            "score": 0.7,
            "provider": LightweightDetectionProvider.provider_name,
        }
    ]
