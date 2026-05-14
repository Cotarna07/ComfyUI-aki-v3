from __future__ import annotations

import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.common.io import resolve_project_path
from pipeline.detection.base import DetectionProvider
from pipeline.detection.lightweight_provider import LightweightDetectionProvider


class GroundedSAM2RuntimeUnavailable(RuntimeError):
    """Raised when the real detection runtime cannot be loaded."""


@dataclass(frozen=True)
class GroundedSAM2Config:
    mode: str = "auto"
    prompts: tuple[str, ...] = ("person", "face", "hand", "weapon", "phone", "vehicle", "room", "background object")
    detector_model: str = "yolo11n.pt"
    sam_model: str = "sam2.1_l.pt"
    model_dir: str = "runtime/models/detection"
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.5
    max_objects: int = 12
    crop_padding_ratio: float = 0.16
    allow_fallback: bool = True
    auto_download_weights: bool = True
    sam_download_url: str = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt"


class GroundedSAM2DetectionProvider(DetectionProvider):
    """YOLO grounding + SAM2 segmentation provider.

    SAM2 itself segments from prompts such as boxes or points; it does not
    understand text prompts. This provider therefore uses an Ultralytics YOLO
    detector as the grounding step and then passes the resulting boxes to
    Ultralytics SAM2 for masks.
    """

    provider_name = "grounded_sam2"
    replacement_point = "pipeline/detection/grounded_sam2_provider.py::GroundedSAM2DetectionProvider"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        settings = ((config or {}).get("detection", {}) or {}).get("grounded_sam2", {}) or {}
        prompts = settings.get("prompts") or GroundedSAM2Config.prompts
        if not isinstance(prompts, (list, tuple)) or not prompts:
            prompts = GroundedSAM2Config.prompts
        self.config = GroundedSAM2Config(
            mode=str(settings.get("mode", "auto")).strip().lower(),
            prompts=tuple(_normalize_prompt(str(item)) for item in prompts),
            detector_model=str(settings.get("detector_model", "yolo11n.pt")),
            sam_model=str(settings.get("sam_model", "sam2.1_l.pt")),
            model_dir=str(settings.get("model_dir", "runtime/models/detection")),
            confidence_threshold=float(settings.get("confidence_threshold", 0.25)),
            iou_threshold=float(settings.get("iou_threshold", 0.5)),
            max_objects=int(settings.get("max_objects", 12)),
            crop_padding_ratio=float(settings.get("crop_padding_ratio", 0.16)),
            allow_fallback=bool(settings.get("allow_fallback", True)),
            auto_download_weights=bool(settings.get("auto_download_weights", True)),
            sam_download_url=str(
                settings.get(
                    "sam_download_url",
                    "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt",
                )
            ),
        )
        self._fallback = LightweightDetectionProvider(config=config)

    def analyze(self, window_packet: dict[str, Any]) -> dict[str, Any]:
        image_path = _resolve_window_image_path(window_packet)
        width, height = _window_size(window_packet, image_path)
        if image_path is None or not image_path.exists() or width <= 0 or height <= 0:
            return _empty_result(width, height, "missing window image")
        mode = _normalize_mode(self.config.mode)
        if mode == "mock":
            return self._fallback_result(window_packet, width, height, "configured mode=mock")
        try:
            return self._run_ultralytics(window_packet, image_path, width, height)
        except GroundedSAM2RuntimeUnavailable as error:
            if not self.config.allow_fallback or mode == "real_strict":
                raise GroundedSAM2RuntimeUnavailable(f"{error}; replacement point: {self.replacement_point}") from error
            return self._fallback_result(window_packet, width, height, str(error))

    def _run_ultralytics(self, window_packet: dict[str, Any], image_path: Path, width: int, height: int) -> dict[str, Any]:
        detector, segmenter = self._load_ultralytics_models(window_packet)
        detections = _predict_yolo_boxes(
            detector,
            image_path,
            prompts=set(self.config.prompts),
            confidence_threshold=self.config.confidence_threshold,
            max_objects=self.config.max_objects,
        )
        detections = _augment_person_parts(detections, set(self.config.prompts), width, height, self.config.max_objects)
        detections = [_with_normalized_box(item, width, height) for item in detections]
        detections = [item for item in detections if item.get("box")]
        if not detections:
            return self._fallback_result(window_packet, width, height, "real detector returned no supported boxes")

        masks = _predict_sam_masks(segmenter, image_path, [item["box"] for item in detections])
        object_boxes: list[dict[str, Any]] = []
        object_masks: list[dict[str, Any]] = []
        for index, detection in enumerate(detections):
            object_id = f"obj_{index:04d}"
            label = str(detection["label"])
            box = detection["box"]
            confidence = round(float(detection.get("confidence", 0.0)), 4)
            object_boxes.append(
                {
                    "object_id": object_id,
                    "label": label,
                    "box": box,
                    "confidence": confidence,
                    "provider": self.provider_name,
                }
            )
            if index < len(masks) and masks[index] is not None:
                mask_path = _save_mask(
                    masks[index],
                    image_path,
                    object_id,
                    label,
                    project_root=_project_root(window_packet),
                )
                object_masks.append(
                    {
                        "mask_id": f"mask_{index:04d}",
                        "source_object_id": object_id,
                        "label": label,
                        "box": box,
                        "mask_path": mask_path,
                        "provider": self.provider_name,
                    }
                )

        crop_candidates = _build_crop_candidates(object_boxes, width, height, self.config.crop_padding_ratio)
        focus_subjects = _build_focus_subjects(object_boxes)
        return {
            "object_boxes": object_boxes,
            "object_masks": object_masks,
            "crop_candidates": crop_candidates,
            "focus_subjects": focus_subjects,
            "scene_density": _scene_density(object_boxes, width, height, self.provider_name),
            "grounding_prompts": list(self.config.prompts),
            "provider": self.provider_name,
        }

    def _load_ultralytics_models(self, window_packet: dict[str, Any]) -> tuple[Any, Any]:
        try:
            from ultralytics import SAM, YOLO
        except Exception as error:
            raise GroundedSAM2RuntimeUnavailable(
                "ultralytics is not installed; install with `python -m pip install ultralytics`"
            ) from error
        project_root = _project_root(window_packet)
        detector_ref = _ensure_model_reference(
            self.config.detector_model,
            project_root,
            self.config.model_dir,
            auto_download=False,
            download_url=None,
        )
        sam_ref = _ensure_model_reference(
            self.config.sam_model,
            project_root,
            self.config.model_dir,
            auto_download=self.config.auto_download_weights,
            download_url=self.config.sam_download_url,
        )
        try:
            return YOLO(detector_ref), SAM(sam_ref)
        except Exception as error:
            raise GroundedSAM2RuntimeUnavailable(f"failed to load YOLO/SAM2 models: {error}") from error

    def _fallback_result(self, window_packet: dict[str, Any], width: int, height: int, reason: str) -> dict[str, Any]:
        base = self._fallback.analyze(window_packet)
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
                    "subject_id": "mock_grounded_sam2_subject_0001",
                    "label": "main_character_region",
                    "box": focus_box,
                    "score": 0.62,
                    "provider": "mock_grounded_sam2",
                }
            ] if focus_box else [],
            "grounding_prompts": list(self.config.prompts),
            "mock_replacement_for": "Grounded-SAM-2",
            "replacement_point": self.replacement_point,
            "runtime_warning": reason,
            "provider": "mock_grounded_sam2",
        }


def _normalize_mode(value: str) -> str:
    mode = (value or "auto").strip().lower()
    if mode in {"real", "ultralytics", "auto"}:
        return "ultralytics" if mode != "real" else "real_strict"
    if mode in {"mock", "disabled"}:
        return "mock"
    return "ultralytics"


def _resolve_window_image_path(window_packet: dict[str, Any]) -> Path | None:
    raw = (
        window_packet.get("resolved_image_path")
        or window_packet.get("window_image_path")
        or window_packet.get("image_path")
    )
    if not raw:
        return None
    path = Path(str(raw))
    if path.is_absolute():
        return path
    project_root = _project_root(window_packet)
    return resolve_project_path(project_root, path) if project_root else Path.cwd() / path


def _project_root(window_packet: dict[str, Any]) -> Path:
    raw = window_packet.get("project_root")
    return Path(str(raw)).resolve() if raw else Path.cwd().resolve()


def _window_size(window_packet: dict[str, Any], image_path: Path | None) -> tuple[int, int]:
    width = int(window_packet.get("width") or 0)
    height = int(window_packet.get("height") or 0)
    if width > 0 and height > 0:
        return width, height
    if image_path and image_path.exists():
        try:
            from PIL import Image

            with Image.open(image_path) as image:
                return image.width, image.height
        except Exception:
            return width, height
    return width, height


def _ensure_model_reference(
    model_name: str,
    project_root: Path,
    model_dir: str,
    *,
    auto_download: bool,
    download_url: str | None,
) -> str:
    path = Path(model_name)
    if path.is_absolute():
        if path.exists():
            return str(path)
        if auto_download and download_url:
            return str(_download_file(download_url, path))
        return str(path)
    if "/" in model_name or "\\" in model_name:
        candidate = resolve_project_path(project_root, path)
        if candidate.exists():
            return str(candidate)
        if auto_download and download_url:
            return str(_download_file(download_url, candidate))
        return str(candidate)
    candidate = resolve_project_path(project_root, Path(model_dir) / model_name)
    if candidate.exists():
        return str(candidate)
    if auto_download and download_url and model_name in {"sam2_hiera_large.pt", "sam2.1_hiera_large.pt"}:
        return str(_download_file(download_url, candidate))
    return model_name


def _download_file(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    temp_path = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=120) as response, temp_path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        temp_path.replace(destination)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
    return destination


def _predict_yolo_boxes(
    detector: Any,
    image_path: Path,
    *,
    prompts: set[str],
    confidence_threshold: float,
    max_objects: int,
) -> list[dict[str, Any]]:
    try:
        raw_results = detector.predict(source=str(image_path), conf=confidence_threshold, verbose=False)
    except TypeError:
        raw_results = detector(str(image_path), conf=confidence_threshold, verbose=False)
    results = raw_results if isinstance(raw_results, list) else [raw_results]
    detections: list[dict[str, Any]] = []
    for result in results:
        for item in _iter_result_boxes(result, getattr(detector, "names", {})):
            label = _normalize_prompt(str(item.get("label", "")))
            confidence = float(item.get("confidence", 0.0))
            if confidence < confidence_threshold:
                continue
            if not _label_matches_prompts(label, prompts):
                continue
            detections.append(
                {
                    "label": label,
                    "box": item["box"],
                    "confidence": confidence,
                    "source": "yolo",
                }
            )
    detections.sort(key=lambda item: float(item.get("confidence", 0.0)), reverse=True)
    return detections[:max_objects]


def _iter_result_boxes(result: Any, fallback_names: Any) -> list[dict[str, Any]]:
    boxes = getattr(result, "boxes", None)
    names = getattr(result, "names", None) or fallback_names or {}
    if isinstance(boxes, list):
        return [_dict_box(item, names) for item in boxes if _dict_box(item, names) is not None]
    if boxes is None:
        return []
    xyxy = _tensor_to_list(getattr(boxes, "xyxy", []))
    conf = _tensor_to_list(getattr(boxes, "conf", []))
    cls = _tensor_to_list(getattr(boxes, "cls", []))
    out: list[dict[str, Any]] = []
    for index, box in enumerate(xyxy):
        class_id = int(cls[index]) if index < len(cls) else -1
        label = str(names.get(class_id, class_id)) if isinstance(names, dict) else str(class_id)
        out.append(
            {
                "box": [int(round(float(value))) for value in box[:4]],
                "confidence": float(conf[index]) if index < len(conf) else 0.0,
                "label": label,
            }
        )
    return out


def _dict_box(item: Any, names: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    raw_box = item.get("box") or item.get("xyxy")
    if not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4:
        return None
    class_id = item.get("class_id", item.get("cls", -1))
    label = item.get("label")
    if label is None and isinstance(names, dict):
        label = names.get(int(class_id), str(class_id))
    return {
        "box": [int(round(float(value))) for value in raw_box],
        "confidence": float(item.get("confidence", item.get("conf", 0.0))),
        "label": str(label or class_id),
    }


def _tensor_to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value) if isinstance(value, (list, tuple)) else []


def _predict_sam_masks(segmenter: Any, image_path: Path, boxes: list[list[int]]) -> list[Any | None]:
    if not boxes:
        return []
    try:
        raw_results = segmenter.predict(source=str(image_path), bboxes=boxes, verbose=False)
    except TypeError:
        raw_results = segmenter(str(image_path), bboxes=boxes, verbose=False)
    results = raw_results if isinstance(raw_results, list) else [raw_results]
    masks: list[Any | None] = []
    for result in results:
        masks.extend(_extract_masks(result))
    while len(masks) < len(boxes):
        masks.append(None)
    return masks[: len(boxes)]


def _extract_masks(result: Any) -> list[Any]:
    if isinstance(result, dict):
        raw = result.get("masks") or []
        if isinstance(raw, list):
            return raw
        return _tensor_to_list(raw)
    masks = getattr(result, "masks", None)
    if masks is None:
        return []
    data = getattr(masks, "data", masks)
    if hasattr(data, "detach"):
        data = data.detach()
    if hasattr(data, "cpu"):
        data = data.cpu()
    if hasattr(data, "numpy"):
        data = data.numpy()
    try:
        return [data[index] for index in range(len(data))]
    except TypeError:
        return [data]


def _save_mask(mask: Any, image_path: Path, object_id: str, label: str, project_root: Path) -> str:
    from PIL import Image
    import numpy as np

    array = np.asarray(mask)
    if array.ndim == 3:
        array = array[0]
    array = (array > 0).astype("uint8") * 255
    safe_label = _safe_path_part(label)
    path = image_path.parent / f"{image_path.stem}_{object_id}_{safe_label}_mask.png"
    Image.fromarray(array, mode="L").save(path)
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _augment_person_parts(
    detections: list[dict[str, Any]],
    prompts: set[str],
    width: int,
    height: int,
    max_objects: int,
) -> list[dict[str, Any]]:
    out = list(detections)
    wants_face = "face" in prompts
    wants_hand = "hand" in prompts or "hands" in prompts
    if not (wants_face or wants_hand):
        return out[:max_objects]
    for detection in detections:
        if detection.get("label") not in {"person", "main_character"}:
            continue
        box = _normalize_box(detection.get("box"), width, height)
        if not box:
            continue
        x1, y1, x2, y2 = box
        box_w = max(1, x2 - x1)
        box_h = max(1, y2 - y1)
        if wants_face:
            out.append(
                {
                    "label": "face",
                    "box": [x1 + int(box_w * 0.30), y1 + int(box_h * 0.05), x1 + int(box_w * 0.70), y1 + int(box_h * 0.32)],
                    "confidence": min(0.8, float(detection.get("confidence", 0.0)) * 0.72),
                    "source": "person_derived_geometry",
                }
            )
        if wants_hand:
            out.extend(
                [
                    {
                        "label": "hand",
                        "box": [x1 + int(box_w * 0.06), y1 + int(box_h * 0.45), x1 + int(box_w * 0.28), y1 + int(box_h * 0.68)],
                        "confidence": min(0.7, float(detection.get("confidence", 0.0)) * 0.55),
                        "source": "person_derived_geometry",
                    },
                    {
                        "label": "hand",
                        "box": [x1 + int(box_w * 0.72), y1 + int(box_h * 0.45), x1 + int(box_w * 0.94), y1 + int(box_h * 0.68)],
                        "confidence": min(0.7, float(detection.get("confidence", 0.0)) * 0.55),
                        "source": "person_derived_geometry",
                    },
                ]
            )
    return out[:max_objects]


def _with_normalized_box(item: dict[str, Any], width: int, height: int) -> dict[str, Any]:
    return {**item, "box": _normalize_box(item.get("box"), width, height)}


def _build_crop_candidates(object_boxes: list[dict[str, Any]], width: int, height: int, padding_ratio: float) -> list[dict[str, Any]]:
    primary = [box for box in object_boxes if box.get("label") in {"person", "main_character"}]
    if not primary:
        primary = object_boxes[:1]
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(primary[:3]):
        box = _pad_box(item["box"], width, height, padding_ratio)
        candidates.append(
            {
                "crop_id": f"crop_{index:04d}",
                "box": box,
                "reason": f"main_subject:{item.get('label')}",
                "score": round(min(1.0, 0.62 + float(item.get("confidence", 0.0)) * 0.3), 4),
                "provider": GroundedSAM2DetectionProvider.provider_name,
            }
        )
    if len(object_boxes) > 1:
        union = _union_box([item["box"] for item in object_boxes if item.get("box")], width, height)
        if union:
            candidates.append(
                {
                    "crop_id": f"crop_{len(candidates):04d}",
                    "box": _pad_box(union, width, height, padding_ratio * 0.5),
                    "reason": "multi_subject_union",
                    "score": 0.72,
                    "provider": GroundedSAM2DetectionProvider.provider_name,
                }
            )
    return candidates


def _build_focus_subjects(object_boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(object_boxes, key=lambda item: (float(item.get("confidence", 0.0)), _box_area(item.get("box"))), reverse=True)
    return [
        {
            "subject_id": f"subject_{index:04d}",
            "source_object_id": item["object_id"],
            "label": item["label"],
            "box": item["box"],
            "score": round(float(item.get("confidence", 0.0)), 4),
            "provider": GroundedSAM2DetectionProvider.provider_name,
        }
        for index, item in enumerate(ranked[:3])
    ]


def _scene_density(object_boxes: list[dict[str, Any]], width: int, height: int, provider: str) -> dict[str, Any]:
    image_area = max(1, width * height)
    object_area = sum(_box_area(item.get("box")) for item in object_boxes)
    value = max(0.0, min(1.0, object_area / image_area))
    if value < 0.18:
        level = "low"
    elif value < 0.48:
        level = "medium"
    else:
        level = "high"
    return {"value": round(value, 4), "level": level, "provider": provider, "object_count": len(object_boxes)}


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
    boxes = [
        ("main_character", focus_box, 0.62),
        ("face", [x1 + int(box_w * 0.28), y1 + int(box_h * 0.08), x1 + int(box_w * 0.72), y1 + int(box_h * 0.38)], 0.48),
        ("hand", [x1 + int(box_w * 0.08), y1 + int(box_h * 0.48), x1 + int(box_w * 0.30), y1 + int(box_h * 0.72)], 0.34),
        ("hand", [x1 + int(box_w * 0.70), y1 + int(box_h * 0.48), x1 + int(box_w * 0.92), y1 + int(box_h * 0.72)], 0.34),
    ]
    return [
        {
            "object_id": f"mock_grounded_sam2_obj_{index:04d}",
            "label": label,
            "box": normalized,
            "confidence": confidence,
            "source": "mock_grounded_sam2_geometry",
            "provider": "mock_grounded_sam2",
        }
        for index, (label, box, confidence) in enumerate(boxes)
        if (normalized := _normalize_box(box, width, height)) is not None
    ]


def _tag_crop_candidates(candidates: list[dict[str, Any]], focus_box: list[int] | None) -> list[dict[str, Any]]:
    tagged: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        item["provider"] = "mock_grounded_sam2"
        item["framing"] = _framing_for_box(item.get("box"), focus_box)
        tagged.append(item)
    return tagged


def _empty_result(width: int, height: int, reason: str) -> dict[str, Any]:
    return {
        "object_boxes": [],
        "object_masks": [],
        "crop_candidates": [],
        "focus_subjects": [],
        "scene_density": {"value": 0.0, "level": "low", "provider": "mock_grounded_sam2", "object_count": 0},
        "grounding_prompts": list(GroundedSAM2Config.prompts),
        "mock_replacement_for": "Grounded-SAM-2",
        "runtime_warning": reason,
        "provider": "mock_grounded_sam2",
    }


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


def _normalize_prompt(value: str) -> str:
    return value.strip().lower().replace("_", " ")


def _label_matches_prompts(label: str, prompts: set[str]) -> bool:
    if label in prompts:
        return True
    aliases = {
        "cell phone": {"phone"},
        "mobile phone": {"phone"},
        "car": {"vehicle"},
        "truck": {"vehicle"},
        "bus": {"vehicle"},
        "motorcycle": {"vehicle"},
        "bicycle": {"vehicle"},
        "person": {"character", "main character", "human"},
    }
    return bool(aliases.get(label, set()) & prompts)


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


def _pad_box(box: list[int], width: int, height: int, ratio: float) -> list[int]:
    x1, y1, x2, y2 = box
    pad_x = int((x2 - x1) * max(0.0, ratio))
    pad_y = int((y2 - y1) * max(0.0, ratio))
    return _normalize_box([x1 - pad_x, y1 - pad_y, x2 + pad_x, y2 + pad_y], width, height) or box


def _union_box(boxes: list[list[int]], width: int, height: int) -> list[int] | None:
    if not boxes:
        return None
    return _normalize_box(
        [
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        ],
        width,
        height,
    )


def _box_area(box: Any) -> int:
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return 0
    return max(0, int(box[2]) - int(box[0])) * max(0, int(box[3]) - int(box[1]))


def _safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"
