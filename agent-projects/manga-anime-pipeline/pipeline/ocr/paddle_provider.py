from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.ocr.base import OCRProvider


class PaddleOCRProvider(OCRProvider):
    """PaddleOCR-backed OCR provider with lazy optional dependency loading."""

    provider_name = "paddleocr"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.language = str(self.config.get("language", self.config.get("lang", "ch")))
        self._engine: Any | None = None

    def analyze(self, window_packet: dict[str, Any]) -> dict[str, Any]:
        image_path = _resolve_image_path(window_packet)
        if not image_path.exists():
            raise FileNotFoundError(f"PaddleOCR input image not found: {image_path}")
        raw_result = self._run_ocr(image_path)
        return normalize_paddleocr_result(raw_result, window_packet)

    def check_runtime(self) -> None:
        self._import_paddleocr_class()

    def _run_ocr(self, image_path: Path) -> Any:
        engine = self._get_engine()
        try:
            if hasattr(engine, "ocr"):
                try:
                    return engine.ocr(str(image_path), cls=True)
                except TypeError:
                    return engine.ocr(str(image_path))
            if hasattr(engine, "predict"):
                return engine.predict(str(image_path))
        except RuntimeError:
            raise
        except Exception as error:
            raise RuntimeError(f"PaddleOCR failed while processing {image_path}: {error}") from error
        raise RuntimeError("PaddleOCR engine does not expose an ocr() or predict() method")

    def _get_engine(self) -> Any:
        if self._engine is not None:
            return self._engine
        PaddleOCR = self._import_paddleocr_class()

        init_attempts = [
            {"lang": self.language, "use_angle_cls": True, "use_gpu": False, "show_log": False},
            {"lang": self.language, "use_angle_cls": True, "use_gpu": False},
            {"lang": self.language, "device": "cpu", "enable_mkldnn": False, "cpu_threads": 4},
            {"lang": self.language, "device": "cpu", "enable_mkldnn": False},
            {"lang": self.language, "device": "cpu"},
            {"lang": self.language},
        ]
        last_error: Exception | None = None
        for kwargs in init_attempts:
            try:
                self._engine = PaddleOCR(**kwargs)
                return self._engine
            except Exception as error:
                if _is_unsupported_constructor_argument(error):
                    last_error = error
                    continue
                raise RuntimeError(f"Failed to initialize PaddleOCR CPU provider: {error}") from error
        raise RuntimeError(f"Failed to initialize PaddleOCR with supported constructor options: {last_error}")

    def _import_paddleocr_class(self) -> Any:
        try:
            from paddleocr import PaddleOCR  # type: ignore[import-not-found]
        except Exception as error:
            raise RuntimeError(
                "PaddleOCR provider requires optional OCR dependencies. Install them with: "
                "python -m pip install -r requirements-ocr.txt. Missing import: paddleocr"
            ) from error
        return PaddleOCR


def normalize_paddleocr_result(raw_result: Any, window_packet: dict[str, Any]) -> dict[str, Any]:
    width = int(window_packet.get("width", 0) or 0)
    height = int(window_packet.get("height", 0) or 0)
    window_id = str(window_packet.get("window_id", "window"))
    blocks = _extract_blocks(raw_result, window_id, width, height)
    return {
        "ocr_blocks": blocks,
        "reading_order": [block["block_id"] for block in blocks],
        "layout_blocks": [],
    }


def _extract_blocks(raw_result: Any, window_id: str, width: int, height: int) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for text, score, box in _iter_text_boxes(raw_result):
        normalized_text = str(text).strip()
        if not normalized_text:
            continue
        normalized_box = _box_to_xyxy(box, width, height)
        if normalized_box is None:
            continue
        block_id = f"{window_id}_ocr_{len(blocks):04d}"
        blocks.append(
            {
                "block_id": block_id,
                "text": normalized_text,
                "box": normalized_box,
                "confidence": _confidence_to_float(score),
                "language": "unknown",
                "provider": PaddleOCRProvider.provider_name,
            }
        )
    return blocks


def _is_unsupported_constructor_argument(error: Exception) -> bool:
    message = str(error).lower()
    return "unknown argument" in message or "unexpected keyword argument" in message


def _iter_text_boxes(raw_result: Any) -> list[tuple[Any, Any, Any]]:
    if raw_result is None:
        return []
    normalized = _to_python(raw_result)
    mapping_blocks = _iter_mapping_results(normalized)
    if mapping_blocks:
        return mapping_blocks
    return _iter_classic_results(normalized)


def _iter_mapping_results(value: Any) -> list[tuple[Any, Any, Any]]:
    blocks: list[tuple[Any, Any, Any]] = []
    for mapping in _iter_mappings(value):
        texts = _to_python(_mapping_get(mapping, "rec_texts", "texts", "text"))
        scores = _to_python(_mapping_get(mapping, "rec_scores", "scores", "confidence"))
        boxes = _to_python(_mapping_get(mapping, "rec_boxes", "dt_boxes", "dt_polys", "rec_polys", "boxes"))
        if isinstance(texts, str):
            texts = [texts]
        if not isinstance(texts, list):
            continue
        if not isinstance(scores, list):
            scores = [scores for _ in texts]
        if not isinstance(boxes, list):
            boxes = [boxes for _ in texts]
        for index, text in enumerate(texts):
            score = scores[index] if index < len(scores) else 0.0
            box = boxes[index] if index < len(boxes) else None
            blocks.append((text, score, box))
    return blocks


def _iter_mappings(value: Any) -> list[Any]:
    if isinstance(value, dict) or _has_any_attr(value, ("rec_texts", "texts", "rec_boxes", "dt_polys")):
        return [value]
    if isinstance(value, list):
        mappings: list[Any] = []
        for item in value:
            mappings.extend(_iter_mappings(item))
        return mappings
    return []


def _iter_classic_results(value: Any) -> list[tuple[Any, Any, Any]]:
    lines = _flatten_classic_lines(value)
    blocks: list[tuple[Any, Any, Any]] = []
    for line in lines:
        if not isinstance(line, (list, tuple)) or len(line) < 2:
            continue
        box = line[0]
        payload = line[1]
        if isinstance(payload, (list, tuple)) and payload:
            text = payload[0]
            score = payload[1] if len(payload) > 1 else 0.0
        else:
            text = payload
            score = 0.0
        blocks.append((text, score, box))
    return blocks


def _flatten_classic_lines(value: Any) -> list[Any]:
    value = _to_python(value)
    if value is None:
        return []
    if _looks_like_classic_line(value):
        return [value]
    if isinstance(value, list):
        lines: list[Any] = []
        for item in value:
            lines.extend(_flatten_classic_lines(item))
        return lines
    return []


def _looks_like_classic_line(value: Any) -> bool:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return False
    payload = value[1]
    return isinstance(payload, (list, tuple)) and bool(payload) and isinstance(payload[0], str)


def _box_to_xyxy(value: Any, width: int, height: int) -> list[int] | None:
    value = _to_python(value)
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 4 and all(_is_number(item) for item in value):
        x1, y1, x2, y2 = [float(item) for item in value]
    else:
        points = _points_from_value(value)
        if not points:
            return None
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)
    left = _clamp_int(x1, 0, width)
    top = _clamp_int(y1, 0, height)
    right = _clamp_int(x2, 0, width)
    bottom = _clamp_int(y2, 0, height)
    if right <= left or bottom <= top:
        return None
    return [left, top, right, bottom]


def _points_from_value(value: Any) -> list[tuple[float, float]]:
    value = _to_python(value)
    if not isinstance(value, (list, tuple)):
        return []
    points: list[tuple[float, float]] = []
    for item in value:
        item = _to_python(item)
        if isinstance(item, (list, tuple)) and len(item) >= 2 and _is_number(item[0]) and _is_number(item[1]):
            points.append((float(item[0]), float(item[1])))
    return points


def _confidence_to_float(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(1.0, score))


def _resolve_image_path(window_packet: dict[str, Any]) -> Path:
    value = window_packet.get("resolved_image_path") or window_packet.get("image_path")
    if not value:
        raise ValueError("window_packet must include image_path or resolved_image_path for PaddleOCR")
    path = Path(str(value))
    if path.is_absolute():
        return path
    project_root = window_packet.get("project_root")
    if project_root:
        return Path(str(project_root)) / path
    return Path.cwd() / path


def _mapping_get(mapping: Any, *keys: str) -> Any:
    for key in keys:
        if isinstance(mapping, dict) and key in mapping:
            return mapping[key]
        if hasattr(mapping, key):
            return getattr(mapping, key)
    return None


def _has_any_attr(value: Any, names: tuple[str, ...]) -> bool:
    return any(hasattr(value, name) for name in names)


def _to_python(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _clamp_int(value: float, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(round(value))))
