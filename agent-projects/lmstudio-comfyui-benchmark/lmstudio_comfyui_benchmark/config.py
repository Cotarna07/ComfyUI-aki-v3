from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # Python 3.10 fallback.
    from . import simple_toml as tomllib  # type: ignore[no-redef]


@dataclass(frozen=True)
class RunConfig:
    name: str
    output_dir: Path
    fixed_instruction: str


@dataclass(frozen=True)
class LmStudioConfig:
    base_url: str
    api_key: str
    request_timeout_sec: int
    retries: int
    retry_sleep_sec: int
    models: list[str]


@dataclass(frozen=True)
class ParameterSet:
    temperature: float
    top_p: float
    max_tokens: int

    @property
    def key(self) -> str:
        return f"temp{self.temperature:g}_top{self.top_p:g}_max{self.max_tokens}"


@dataclass(frozen=True)
class QualityConfig:
    min_positive_chars: int
    min_negative_chars: int
    required_positive_terms: list[str]
    required_negative_terms: list[str]
    penalize_non_english_prompt: bool


@dataclass(frozen=True)
class ComfyUiConfig:
    enabled: bool
    base_url: str
    workflow_path: Path
    client_id: str
    poll_interval_sec: int
    prompt_timeout_sec: int
    retries: int
    positive_prompt_path: str
    negative_prompt_path: str
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppConfig:
    run: RunConfig
    lmstudio: LmStudioConfig
    parameters: list[ParameterSet]
    quality: QualityConfig
    comfyui: ComfyUiConfig


def load_config(path: Path) -> AppConfig:
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    base_dir = path.parent.parent
    run_raw = raw["run"]
    lm_raw = raw["lmstudio"]
    quality_raw = raw.get("quality", {})
    comfy_raw = raw.get("comfyui", {})

    parameters = [
        ParameterSet(
            temperature=float(item.get("temperature", 0.7)),
            top_p=float(item.get("top_p", 0.95)),
            max_tokens=int(item.get("max_tokens", 512)),
        )
        for item in raw.get("parameters", [])
    ]
    if not parameters:
        raise ValueError("At least one [[parameters]] entry is required.")

    workflow_path = Path(comfy_raw.get("workflow_path", ""))
    if workflow_path and not workflow_path.is_absolute():
        workflow_path = base_dir.parent.parent / workflow_path

    output_dir = Path(run_raw.get("output_dir", "runtime"))
    if not output_dir.is_absolute():
        output_dir = base_dir / output_dir

    return AppConfig(
        run=RunConfig(
            name=str(run_raw.get("name", "lmstudio-comfyui-benchmark")),
            output_dir=output_dir,
            fixed_instruction=str(run_raw["fixed_instruction"]),
        ),
        lmstudio=LmStudioConfig(
            base_url=str(lm_raw.get("base_url", "http://localhost:1234/v1")).rstrip("/"),
            api_key=str(lm_raw.get("api_key", "lm-studio")),
            request_timeout_sec=int(lm_raw.get("request_timeout_sec", 240)),
            retries=int(lm_raw.get("retries", 2)),
            retry_sleep_sec=int(lm_raw.get("retry_sleep_sec", 8)),
            models=[str(model) for model in lm_raw.get("models", [])],
        ),
        parameters=parameters,
        quality=QualityConfig(
            min_positive_chars=int(quality_raw.get("min_positive_chars", 160)),
            min_negative_chars=int(quality_raw.get("min_negative_chars", 60)),
            required_positive_terms=[str(item).lower() for item in quality_raw.get("required_positive_terms", [])],
            required_negative_terms=[str(item).lower() for item in quality_raw.get("required_negative_terms", [])],
            penalize_non_english_prompt=bool(quality_raw.get("penalize_non_english_prompt", True)),
        ),
        comfyui=ComfyUiConfig(
            enabled=bool(comfy_raw.get("enabled", False)),
            base_url=str(comfy_raw.get("base_url", "http://127.0.0.1:8188")).rstrip("/"),
            workflow_path=workflow_path,
            client_id=str(comfy_raw.get("client_id", "lmstudio-comfyui-benchmark")),
            poll_interval_sec=int(comfy_raw.get("poll_interval_sec", 3)),
            prompt_timeout_sec=int(comfy_raw.get("prompt_timeout_sec", 1800)),
            retries=int(comfy_raw.get("retries", 1)),
            positive_prompt_path=str(comfy_raw.get("positive_prompt_path", "")),
            negative_prompt_path=str(comfy_raw.get("negative_prompt_path", "")),
            overrides=dict(comfy_raw.get("overrides", {})),
        ),
    )
