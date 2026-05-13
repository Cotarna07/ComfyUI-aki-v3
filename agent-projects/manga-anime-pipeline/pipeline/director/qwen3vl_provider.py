from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.common.schemas import WORKFLOW_ROUTES
from pipeline.director.base import DirectorProvider
from pipeline.director.context import dialogue_summary


@dataclass(frozen=True)
class Qwen3VLConfig:
    mode: str = "local"
    model_path: str = ""
    max_retries: int = 2
    require_json: bool = True
    device: str = "auto"
    dtype: str = "auto"


class Qwen3VLBlockedError(RuntimeError):
    """Raised when Qwen3VL provider cannot run for environmental reasons."""


class Qwen3VLDirector(DirectorProvider):
    """Qwen3-VL backed director provider.

    Heavy dependencies (transformers / torch / qwen-vl-utils) are imported
    lazily. Missing dependencies or missing model path do NOT crash module
    import, but raise Qwen3VLBlockedError at runtime so callers (gate scripts)
    can clearly mark the run as blocked rather than failed.
    """

    provider_name = "qwen3vl"
    model_name = "qwen3-vl"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        settings = ((config or {}).get("director", {}) or {}).get("qwen3vl", {}) or {}
        self.config = Qwen3VLConfig(
            mode=str(settings.get("mode", "local")),
            model_path=str(settings.get("model_path", "")),
            max_retries=int(settings.get("max_retries", 2)),
            require_json=bool(settings.get("require_json", True)),
            device=str(settings.get("device", "auto")),
            dtype=str(settings.get("dtype", "auto")),
        )
        self._model: Any | None = None
        self._processor: Any | None = None

    def check_runtime(self) -> None:
        if self.config.mode == "dry_run_blocked":
            raise Qwen3VLBlockedError(
                "Qwen3VL provider mode=dry_run_blocked. Set director.qwen3vl.mode=local and provide a model_path to run for real."
            )
        if not self.config.model_path:
            raise Qwen3VLBlockedError(
                "Qwen3VL provider requires director.qwen3vl.model_path. None configured."
            )
        if not Path(self.config.model_path).exists():
            raise Qwen3VLBlockedError(
                f"Qwen3VL model_path does not exist: {self.config.model_path}. Download the weights and configure director.qwen3vl.model_path."
            )
        self._import_dependencies()

    def create_shots(self, structured_packet: dict[str, Any], context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        context = context or {}
        shot_index = int(context.get("shot_index", 0))
        text = self._call_model(structured_packet, context)
        shot = self._build_shot(structured_packet, context, shot_index, text)
        return [shot]

    def _call_model(self, packet: dict[str, Any], context: dict[str, Any]) -> str:
        model, processor, torch_module = self._load_engine()
        prompt = _build_prompt(packet, context)
        image_path = packet.get("window_image_path") or packet.get("image_path")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": str(image_path)} if image_path else {"type": "text", "text": "(no image)"},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                inputs = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, return_tensors="pt")
                if hasattr(inputs, "to") and torch_module is not None:
                    inputs = inputs.to(model.device)
                output_ids = model.generate(**inputs, max_new_tokens=1024) if isinstance(inputs, dict) else model.generate(inputs, max_new_tokens=1024)
                decoded = processor.batch_decode(output_ids, skip_special_tokens=True)
                return decoded[0] if decoded else ""
            except Exception as error:
                last_error = error
        raise RuntimeError(f"Qwen3VL generation failed after retries: {last_error}")

    def _load_engine(self) -> tuple[Any, Any, Any]:
        if self._model is not None and self._processor is not None:
            return self._model, self._processor, _safe_import_torch()
        torch_module, AutoProcessor, ModelClass = self._import_dependencies()
        model_path = self.config.model_path
        try:
            processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
            model = ModelClass.from_pretrained(model_path, trust_remote_code=True)
            if torch_module is not None and hasattr(model, "to"):
                if self.config.device == "auto":
                    model = model.to("cuda" if torch_module.cuda.is_available() else "cpu")
                else:
                    model = model.to(self.config.device)
        except Exception as error:
            raise Qwen3VLBlockedError(
                f"Failed to load Qwen3VL from {model_path}: {error}"
            ) from error
        self._processor = processor
        self._model = model
        return model, processor, torch_module

    def _import_dependencies(self) -> tuple[Any, Any, Any]:
        try:
            import torch  # type: ignore[import-not-found]
        except Exception as error:
            raise Qwen3VLBlockedError(
                "Qwen3VL requires torch. Install via: python -m pip install -r requirements-director.txt. Missing import: torch"
            ) from error
        try:
            from transformers import AutoProcessor  # type: ignore[import-not-found]
        except Exception as error:
            raise Qwen3VLBlockedError(
                "Qwen3VL requires transformers. Install via: python -m pip install -r requirements-director.txt. Missing import: transformers"
            ) from error
        ModelClass = _load_model_class()
        return torch, AutoProcessor, ModelClass

    def _build_shot(self, packet: dict[str, Any], context: dict[str, Any], shot_index: int, raw_text: str) -> dict[str, Any]:
        data = _parse_strict_json(raw_text, self.config.require_json)
        shot = _normalize_shot_payload(data, packet, context, shot_index)
        shot["provider"] = self.provider_name
        return shot


def _load_model_class() -> Any:
    try:
        from transformers import Qwen3VLForConditionalGeneration  # type: ignore[import-not-found]

        return Qwen3VLForConditionalGeneration
    except Exception:
        pass
    try:
        from transformers import Qwen2VLForConditionalGeneration  # type: ignore[import-not-found]

        return Qwen2VLForConditionalGeneration
    except Exception:
        pass
    try:
        from transformers import AutoModelForCausalLM  # type: ignore[import-not-found]

        return AutoModelForCausalLM
    except Exception as error:
        raise Qwen3VLBlockedError(
            "Could not load a Qwen3VL-compatible model class from transformers."
        ) from error


def _safe_import_torch() -> Any:
    try:
        import torch  # type: ignore[import-not-found]

        return torch
    except Exception:
        return None


def _build_prompt(packet: dict[str, Any], context: dict[str, Any]) -> str:
    text = dialogue_summary_for_prompt(packet)
    return (
        "你是漫画分镜导演 Qwen3-VL。仅输出严格 JSON。\n"
        "必须包含字段：story_role, shot_type, anime_fit_score, emotion, action_level, "
        "dialogue_summary, positive_prompt, negative_prompt, style_anchor, workflow_route, confidence, "
        "main_characters, support_characters, continuity_notes。\n"
        f"workflow_route 必须为以下之一：{WORKFLOW_ROUTES}。\n"
        f"anime_fit_score 和 confidence 范围在 0 到 1。\n"
        f"window_id={packet.get('window_id')}，page_id={packet.get('page_id')}，"
        f"shot_index={context.get('shot_index')}，对白参考：{text}\n"
        "不要输出 Markdown，不要输出注释。"
    )


def dialogue_summary_for_prompt(packet: dict[str, Any]) -> str:
    return dialogue_summary(packet)


def _parse_strict_json(raw_text: str, require_json: bool) -> dict[str, Any]:
    text = (raw_text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    if require_json:
        raise ValueError("Qwen3VL output is not valid JSON")
    return {}


def _normalize_shot_payload(data: dict[str, Any], packet: dict[str, Any], context: dict[str, Any], shot_index: int) -> dict[str, Any]:
    route = str(data.get("workflow_route") or "dialogue_light_motion")
    if route not in WORKFLOW_ROUTES:
        raise ValueError(f"Qwen3VL returned invalid workflow_route: {route}")
    anime_fit_score = _clamp(_to_float(data.get("anime_fit_score"), 0.7))
    confidence = _clamp(_to_float(data.get("confidence"), 0.7))
    positive_prompt = str(data.get("positive_prompt") or "").strip()
    negative_prompt = str(data.get("negative_prompt") or "").strip()
    if not positive_prompt or not negative_prompt:
        raise ValueError("Qwen3VL must produce non-empty positive_prompt and negative_prompt")
    crop = data.get("crop_recommendation")
    if not isinstance(crop, dict):
        crop = {"type": "full_window", "box": packet["source_box"]}
    main_characters = _ensure_str_list(data.get("main_characters"), default=["unknown_character"])
    support_characters = _ensure_str_list(data.get("support_characters"), default=[])
    continuity_notes = _ensure_str_list(data.get("continuity_notes"), default=[])
    return {
        "shot_id": f"{_safe_id(packet['chapter_id'])}_s{shot_index:04d}",
        "source_pages": [packet["page_id"]],
        "source_windows": [packet["window_id"]],
        "source_ranges": [{"page_id": packet["page_id"], "box": packet["source_box"]}],
        "merge_with_prev": bool(data.get("merge_with_prev", False)),
        "merge_with_next": bool(data.get("merge_with_next", False)),
        "story_role": str(data.get("story_role") or "scene_setup"),
        "shot_type": str(data.get("shot_type") or "dialogue"),
        "anime_fit_score": anime_fit_score,
        "main_characters": main_characters,
        "support_characters": support_characters,
        "emotion": str(data.get("emotion") or "neutral"),
        "action_level": str(data.get("action_level") or "low"),
        "dialogue_summary": str(data.get("dialogue_summary") or dialogue_summary(packet)),
        "continuity_notes": continuity_notes,
        "crop_recommendation": crop,
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "style_anchor": str(data.get("style_anchor") or "series_default_style"),
        "workflow_route": route,
        "confidence": confidence,
    }


def _ensure_str_list(value: Any, default: list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return list(default)


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"
