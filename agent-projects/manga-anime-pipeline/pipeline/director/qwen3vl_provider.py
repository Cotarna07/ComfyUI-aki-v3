from __future__ import annotations

import base64
import json
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from pipeline.common.schemas import WORKFLOW_ROUTES
from pipeline.director.base import DirectorProvider
from pipeline.director.context import dialogue_summary


@dataclass(frozen=True)
class Qwen3VLConfig:
    mode: str = "local"
    model_path: str = ""
    api_base: str = ""
    api_model: str = ""
    api_key: str = ""
    max_retries: int = 2
    require_json: bool = True
    timeout_seconds: int = 120
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
        mode = _normalize_mode(str(settings.get("mode", "local")))
        self.config = Qwen3VLConfig(
            mode=mode,
            model_path=str(settings.get("model_path", "")),
            api_base=str(settings.get("api_base") or settings.get("base_url") or _default_api_base(mode)),
            api_model=str(settings.get("api_model") or settings.get("model_name") or ""),
            api_key=str(settings.get("api_key", "")),
            max_retries=int(settings.get("max_retries", 2)),
            require_json=bool(settings.get("require_json", True)),
            timeout_seconds=int(settings.get("timeout_seconds", 120)),
            device=str(settings.get("device", "auto")),
            dtype=str(settings.get("dtype", "auto")),
        )
        self._model: Any | None = None
        self._processor: Any | None = None

    def check_runtime(self) -> None:
        if self.config.mode == "dry_run_blocked":
            raise Qwen3VLBlockedError(
                "Qwen3VL provider mode=dry_run_blocked. Set director.qwen3vl.mode to local, ollama, or openai_compatible to run for real."
            )
        if self.config.mode == "local":
            if not self.config.model_path:
                raise Qwen3VLBlockedError(
                    "Qwen3VL local mode requires director.qwen3vl.model_path. None configured."
                )
            if not Path(self.config.model_path).exists():
                raise Qwen3VLBlockedError(
                    f"Qwen3VL model_path does not exist: {self.config.model_path}. Download the weights and configure director.qwen3vl.model_path."
                )
            self._import_dependencies()
            return
        if self.config.mode in {"ollama", "openai_compatible"}:
            if not self.config.api_base:
                raise Qwen3VLBlockedError(
                    f"Qwen3VL {self.config.mode} mode requires director.qwen3vl.api_base. None configured."
                )
            if not self.config.api_model:
                raise Qwen3VLBlockedError(
                    f"Qwen3VL {self.config.mode} mode requires director.qwen3vl.api_model (or model_name). None configured."
                )
            return
        raise Qwen3VLBlockedError(
            f"Unsupported director.qwen3vl.mode: {self.config.mode}. Supported: local, ollama, openai_compatible, dry_run_blocked."
        )

    def create_shots(self, structured_packet: dict[str, Any], context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        context = context or {}
        shot_index = int(context.get("shot_index", 0))
        text = self._call_model(structured_packet, context)
        shot = self._build_shot(structured_packet, context, shot_index, text)
        return [shot]

    def _call_model(self, packet: dict[str, Any], context: dict[str, Any]) -> str:
        mode = self.config.mode
        last_error: Exception | None = None
        for _attempt in range(self.config.max_retries + 1):
            try:
                if mode == "local":
                    return self._call_local_model_once(packet, context)
                if mode == "ollama":
                    return self._call_ollama_once(packet, context)
                if mode == "openai_compatible":
                    return self._call_openai_compatible_once(packet, context)
                raise Qwen3VLBlockedError(
                    f"Unsupported director.qwen3vl.mode: {mode}. Supported: local, ollama, openai_compatible, dry_run_blocked."
                )
            except Qwen3VLBlockedError:
                raise
            except Exception as error:
                last_error = error
        raise RuntimeError(f"Qwen3VL generation failed after retries: {last_error}")

    def _call_local_model_once(self, packet: dict[str, Any], context: dict[str, Any]) -> str:
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
        inputs = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, return_tensors="pt")
        if hasattr(inputs, "to") and torch_module is not None:
            inputs = inputs.to(_model_input_device(model, torch_module))
        output_ids = model.generate(**inputs, max_new_tokens=1024) if isinstance(inputs, dict) else model.generate(inputs, max_new_tokens=1024)
        decoded = processor.batch_decode(output_ids, skip_special_tokens=True)
        return decoded[0] if decoded else ""

    def _call_ollama_once(self, packet: dict[str, Any], context: dict[str, Any]) -> str:
        prompt = _build_prompt(packet, context)
        payload: dict[str, Any] = {
            "model": self.config.api_model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "options": {"temperature": 0},
        }
        image_base64 = _encode_image_base64(packet)
        if image_base64:
            payload["messages"][0]["images"] = [image_base64]
        response = _post_json(
            _ollama_api_url(self.config.api_base, "/api/chat"),
            payload,
            timeout_seconds=self.config.timeout_seconds,
        )
        message = response.get("message") or {}
        content = message.get("content") or response.get("response") or ""
        if not content:
            raise RuntimeError("Ollama response did not include message.content")
        return str(content)

    def _call_openai_compatible_once(self, packet: dict[str, Any], context: dict[str, Any]) -> str:
        prompt = _build_prompt(packet, context)
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        data_url = _image_data_url(packet)
        if data_url:
            content.insert(0, {"type": "image_url", "image_url": {"url": data_url}})
        payload: dict[str, Any] = {
            "model": self.config.api_model,
            "stream": False,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0,
            "max_tokens": 1024,
        }
        headers: dict[str, str] | None = None
        if self.config.api_key:
            headers = {"Authorization": f"Bearer {self.config.api_key}"}
        response = _post_json(
            _openai_api_url(self.config.api_base, "/chat/completions"),
            payload,
            headers=headers,
            timeout_seconds=self.config.timeout_seconds,
        )
        choices = response.get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI-compatible response did not include choices")
        message = (choices[0] or {}).get("message") or {}
        content_value = _coerce_openai_message_content(message.get("content"))
        if not content_value:
            raise RuntimeError("OpenAI-compatible response did not include message.content")
        return content_value

    def _load_engine(self) -> tuple[Any, Any, Any]:
        if self._model is not None and self._processor is not None:
            return self._model, self._processor, _safe_import_torch()
        torch_module, AutoProcessor, ModelClass = self._import_dependencies()
        model_path = self.config.model_path
        try:
            processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
            dtype = _resolve_torch_dtype(torch_module, self.config.dtype, self.config.device)
            load_kwargs: dict[str, Any] = {
                "trust_remote_code": True,
                "low_cpu_mem_usage": True,
            }
            if dtype is not None:
                load_kwargs["torch_dtype"] = dtype
            if self.config.device == "auto":
                load_kwargs["device_map"] = "auto"
                model = ModelClass.from_pretrained(model_path, **load_kwargs)
            else:
                model = ModelClass.from_pretrained(model_path, **load_kwargs)
                if hasattr(model, "to"):
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


def _normalize_mode(mode: str) -> str:
    value = (mode or "local").strip().lower()
    aliases = {
        "lmstudio": "openai_compatible",
        "lm_studio": "openai_compatible",
        "openai": "openai_compatible",
        "openai-compatible": "openai_compatible",
    }
    return aliases.get(value, value)


def _default_api_base(mode: str) -> str:
    if mode == "ollama":
        return "http://127.0.0.1:11434"
    if mode == "openai_compatible":
        return "http://127.0.0.1:1234/v1"
    return ""


def _resolve_torch_dtype(torch_module: Any, dtype_name: str, device_name: str) -> Any:
    normalized = (dtype_name or "auto").strip().lower()
    if normalized == "auto":
        wants_cuda = device_name == "auto" and bool(torch_module.cuda.is_available())
        if wants_cuda:
            return getattr(torch_module, "bfloat16", None) or getattr(torch_module, "float16", None)
        return getattr(torch_module, "float32", None)

    mapping = {
        "bfloat16": getattr(torch_module, "bfloat16", None),
        "bf16": getattr(torch_module, "bfloat16", None),
        "float16": getattr(torch_module, "float16", None),
        "fp16": getattr(torch_module, "float16", None),
        "float32": getattr(torch_module, "float32", None),
        "fp32": getattr(torch_module, "float32", None),
    }
    resolved = mapping.get(normalized)
    if resolved is None:
        raise Qwen3VLBlockedError(
            f"Unsupported director.qwen3vl.dtype: {dtype_name}. Supported: auto, bfloat16, float16, float32."
        )
    return resolved


def _model_input_device(model: Any, torch_module: Any) -> Any:
    device = getattr(model, "device", None)
    if device is not None and str(device) != "meta":
        return device
    try:
        return next(model.parameters()).device
    except Exception:
        return torch_module.device("cuda" if torch_module.cuda.is_available() else "cpu")


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


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urlrequest.Request(url, data=body, headers=request_headers, method="POST")
    try:
        with urlrequest.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
    except urlerror.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code} calling {url}: {detail or error.reason}") from error
    except urlerror.URLError as error:
        raise RuntimeError(f"Could not reach {url}: {error.reason}") from error
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _encode_image_base64(packet: dict[str, Any]) -> str | None:
    image_path = _resolve_packet_image(packet)
    if image_path is None:
        return None
    return base64.b64encode(image_path.read_bytes()).decode("ascii")


def _image_data_url(packet: dict[str, Any]) -> str | None:
    image_path = _resolve_packet_image(packet)
    if image_path is None:
        return None
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _resolve_packet_image(packet: dict[str, Any]) -> Path | None:
    raw_path = packet.get("window_image_path") or packet.get("image_path")
    if not raw_path:
        return None
    path = Path(str(raw_path))
    if path.exists():
        return path
    return None


def _coerce_openai_message_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    parts.append(text)
        return "\n".join(parts)
    return str(value or "")


def _openai_api_url(base_url: str, endpoint: str) -> str:
    base = (base_url or _default_api_base("openai_compatible")).rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return f"{base}{endpoint}"


def _ollama_api_url(base_url: str, endpoint: str) -> str:
    base = (base_url or _default_api_base("ollama")).rstrip("/")
    return f"{base}{endpoint}"


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
