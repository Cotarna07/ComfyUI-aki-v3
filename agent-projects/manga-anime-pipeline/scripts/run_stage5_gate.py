"""Stage 5 gate: Qwen3-VL director."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.common.io import as_project_path, read_json  # noqa: E402
from pipeline.ingest.slicer import SliceConfig  # noqa: E402
from pipeline.qc.director_acceptance import evaluate_director_acceptance  # noqa: E402
from pipeline.qc.gate_common import load_input_metadata, project_ref, render_simple_markdown, write_gate_reports  # noqa: E402
from pipeline.stage1 import run_stage1  # noqa: E402
from scripts.run_stage4a_gate import run_gate as run_stage4a_gate  # noqa: E402

GATE_NAME = "stage5_gate"
GATE_TITLE = "Stage 5 Gate (Qwen3-VL Director)"


def check_qwen_env(settings: dict[str, Any] | None) -> dict[str, Any]:
    settings = settings or {}
    mode = _normalize_mode(str(settings.get("mode", "local")))
    model_path = str(settings.get("model_path") or "")
    api_base = str(settings.get("api_base") or settings.get("base_url") or _default_api_base(mode))
    api_model = str(settings.get("api_model") or settings.get("model_name") or "")
    findings: dict[str, Any] = {
        "mode": mode,
        "api_base": api_base,
        "api_model": api_model,
        "transformers_import_ok": False,
        "torch_import_ok": False,
        "model_path_configured": bool(model_path),
        "model_path_exists": False,
        "api_base_configured": bool(api_base),
        "api_model_configured": bool(api_model),
        "api_server_reachable": False,
        "api_model_available": False,
        "errors": [],
        "warnings": [],
    }
    if mode == "local":
        try:
            importlib.import_module("torch")
            findings["torch_import_ok"] = True
        except Exception as error:
            findings["errors"].append(f"torch import failed: {error}")
        try:
            importlib.import_module("transformers")
            findings["transformers_import_ok"] = True
        except Exception as error:
            findings["errors"].append(f"transformers import failed: {error}")
        if model_path:
            findings["model_path_exists"] = Path(model_path).exists()
            if not findings["model_path_exists"]:
                findings["errors"].append(f"model_path does not exist: {model_path}")
        else:
            findings["errors"].append("director.qwen3vl.model_path not configured")
        findings["env_ready"] = (
            findings["transformers_import_ok"]
            and findings["torch_import_ok"]
            and findings["model_path_configured"]
            and findings["model_path_exists"]
        )
        return findings

    if mode in {"ollama", "openai_compatible"}:
        if not api_base:
            findings["errors"].append("director.qwen3vl.api_base not configured")
        if not api_model:
            findings["errors"].append("director.qwen3vl.api_model (or model_name) not configured")
        if findings["api_base_configured"] and findings["api_model_configured"]:
            try:
                if mode == "ollama":
                    payload = _get_json(_ollama_api_url(api_base, "/api/tags"))
                    models = [
                        str(item.get("model") or item.get("name") or "")
                        for item in (payload.get("models") or [])
                    ]
                else:
                    payload = _get_json(_openai_api_url(api_base, "/models"))
                    models = [str(item.get("id") or "") for item in (payload.get("data") or [])]
                findings["api_server_reachable"] = True
                findings["api_model_available"] = api_model in models
                if not findings["api_model_available"]:
                    findings["errors"].append(f"configured api_model not available from {mode} backend: {api_model}")
            except Exception as error:
                findings["errors"].append(f"{mode} api probe failed: {error}")
        findings["env_ready"] = (
            findings["api_base_configured"]
            and findings["api_model_configured"]
            and findings["api_server_reachable"]
            and findings["api_model_available"]
        )
        return findings

    findings["errors"].append(
        f"unsupported director.qwen3vl.mode: {mode}. Supported: local, ollama, openai_compatible, dry_run_blocked"
    )
    findings["env_ready"] = False
    return findings


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


def _get_json(url: str, timeout_seconds: int = 8) -> dict[str, Any]:
    request = urlrequest.Request(url, method="GET")
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


def _ollama_api_url(base_url: str, endpoint: str) -> str:
    return f"{(base_url or _default_api_base('ollama')).rstrip('/')}{endpoint}"


def _openai_api_url(base_url: str, endpoint: str) -> str:
    base = (base_url or _default_api_base("openai_compatible")).rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return f"{base}{endpoint}"


def run_gate(
    input_path: Path,
    pipeline_config_path: Path,
    upstream_config_path: Path,
    detection_config_path: Path,
    project_root: Path,
    runtime_root: Path,
    slice_config: SliceConfig,
    force: bool,
) -> tuple[dict[str, Any], Path, Path]:
    series_id, chapter_id = load_input_metadata(input_path)
    upstream_report, upstream_json, upstream_md = run_stage4a_gate(
        input_path=input_path,
        pipeline_config_path=detection_config_path,
        upstream_config_path=upstream_config_path,
        project_root=project_root,
        runtime_root=runtime_root,
        slice_config=slice_config,
        force=force,
    )
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {
        "stage4a_status": upstream_report["gate_status"],
        "stage4a_next_stage_allowed": upstream_report["next_stage_allowed"],
        "qwen_env_ready": False,
        "director_mode": None,
        "transformers_import_ok": False,
        "torch_import_ok": False,
        "model_path_configured": False,
        "model_path_exists": False,
        "api_base_configured": False,
        "api_model_configured": False,
        "api_server_reachable": False,
        "api_model_available": False,
        "pipeline_ran": False,
        "director_acceptance_ran": False,
        "director_acceptance_status": None,
        "director_acceptance_next_stage_allowed": False,
    }
    director_quality: dict[str, Any] | None = None
    pipeline_config = read_json(pipeline_config_path)
    qwen_settings = ((pipeline_config.get("director") or {}).get("qwen3vl") or {})
    env = check_qwen_env(qwen_settings)
    checks.update(
        {
            "qwen_env_ready": env["env_ready"],
            "director_mode": env["mode"],
            "transformers_import_ok": env["transformers_import_ok"],
            "torch_import_ok": env["torch_import_ok"],
            "model_path_configured": env["model_path_configured"],
            "model_path_exists": env["model_path_exists"],
            "api_base_configured": env["api_base_configured"],
            "api_model_configured": env["api_model_configured"],
            "api_server_reachable": env["api_server_reachable"],
            "api_model_available": env["api_model_available"],
        }
    )

    if not upstream_report["next_stage_allowed"]:
        gate_status = "blocked"
        next_stage_allowed = False
        next_action = "Stage 4A 未通过，先修复 detection 门禁后再重跑 Stage 5。"
        errors.append("upstream Stage 4A gate not passed; downstream blocked")
    elif not env["env_ready"]:
        gate_status = "blocked"
        next_stage_allowed = False
        next_action = _next_action_for_mode(env["mode"])
        errors.extend(env["errors"])
    else:
        chapter = read_json(input_path)
        pipeline_error: str | None = None
        stage_report = None
        try:
            stage_report = run_stage1(
                input_path=input_path,
                project_root=project_root,
                runtime_root=runtime_root,
                slice_config=slice_config,
                config=pipeline_config,
                config_ref=as_project_path(project_root, pipeline_config_path),
                force=force,
            )
            checks["pipeline_ran"] = True
        except Exception as error:
            pipeline_error = str(error)
            errors.append(f"pipeline execution failed: {pipeline_error}")
        acceptance_report = evaluate_director_acceptance(
            project_root=project_root,
            runtime_root=runtime_root,
            config=pipeline_config,
            chapter=chapter,
            stage_report=stage_report,
            pipeline_error=pipeline_error,
        )
        checks["director_acceptance_ran"] = True
        checks["director_acceptance_status"] = acceptance_report["pipeline_status"]
        checks["director_acceptance_next_stage_allowed"] = bool(acceptance_report["next_stage_allowed"])
        director_quality = acceptance_report["director_quality"]
        errors.extend(acceptance_report["errors"])
        warnings.extend(acceptance_report["warnings"])
        if errors:
            gate_status = "fail"
            next_stage_allowed = False
            next_action = "director 门禁失败，查看 director_quality 后调整 Qwen3-VL prompt / 配置后重跑。"
        else:
            gate_status = "pass"
            next_stage_allowed = True
            next_action = "可以继续 Stage 6 (ComfyUI 投递)。"

    commands = {
        "run_stage4a_gate": f"python scripts/run_stage4a_gate.py --input {input_path} --pipeline-config {detection_config_path} --force",
        "run_stage5_gate": f"python scripts/run_stage5_gate.py --input {input_path} --pipeline-config {pipeline_config_path} --force",
    }
    if env["mode"] == "local":
        commands["install_director"] = "python -m pip install -r requirements-director.txt"
    elif env["mode"] == "ollama":
        commands["check_ollama"] = f"Invoke-RestMethod {env.get('api_base') or _default_api_base('ollama')}/api/tags"
    elif env["mode"] == "openai_compatible":
        commands["check_openai_compatible"] = "Invoke-RestMethod http://127.0.0.1:1234/v1/models"
    report = {
        "gate_name": GATE_NAME,
        "gate_status": gate_status,
        "next_stage_allowed": next_stage_allowed,
        "required_stage": "Stage 2 + Stage 3A + Stage 4A + Stage 5",
        "series_id": series_id,
        "chapter_id": chapter_id,
        "input_path": project_ref(input_path, project_root),
        "pipeline_config_path": project_ref(pipeline_config_path, project_root),
        "upstream_gate": {
            "name": upstream_report["gate_name"],
            "status": upstream_report["gate_status"],
            "next_stage_allowed": upstream_report["next_stage_allowed"],
            "report_json": project_ref(upstream_json, project_root),
            "report_md": project_ref(upstream_md, project_root),
        },
        "checks": checks,
        "qwen_env": env,
        "director_quality": director_quality,
        "commands": commands,
        "errors": errors,
        "warnings": warnings,
        "next_action": next_action,
    }
    markdown = render_simple_markdown(GATE_TITLE, report)
    json_path, md_path = write_gate_reports(project_root, runtime_root, GATE_NAME, report, markdown)
    return report, json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 5 gate runner")
    parser.add_argument("--input", required=True)
    parser.add_argument("--pipeline-config", required=True, help="config that enables director=qwen3vl")
    parser.add_argument("--detection-config", default=None, help="Stage 4A pipeline config; defaults to pipeline-config")
    parser.add_argument("--upstream-config", default=None, help="Stage 3A acceptance config; defaults to detection-config")
    parser.add_argument("--runtime-root", default="runtime")
    parser.add_argument("--window-height", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=160)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = _resolve(args.input)
    pipeline_config_path = _resolve(args.pipeline_config)
    detection_config_path = _resolve(args.detection_config) if args.detection_config else pipeline_config_path
    upstream_config_path = _resolve(args.upstream_config) if args.upstream_config else detection_config_path
    runtime_root = _resolve_runtime(args.runtime_root)
    report, json_path, md_path = run_gate(
        input_path=input_path,
        pipeline_config_path=pipeline_config_path,
        upstream_config_path=upstream_config_path,
        detection_config_path=detection_config_path,
        project_root=PROJECT_ROOT,
        runtime_root=runtime_root,
        slice_config=SliceConfig(window_height=args.window_height, overlap=args.overlap),
        force=args.force,
    )
    print(
        json.dumps(
            {
                "gate_name": report["gate_name"],
                "gate_status": report["gate_status"],
                "next_stage_allowed": report["next_stage_allowed"],
                "report_json": project_ref(json_path, PROJECT_ROOT),
                "report_md": project_ref(md_path, PROJECT_ROOT),
                "errors": report["errors"],
                "warnings": report["warnings"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["gate_status"] == "pass" else 1


def _resolve(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (PROJECT_ROOT / path).resolve()


def _resolve_runtime(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def _next_action_for_mode(mode: str) -> str:
    if mode == "local":
        return "Qwen3-VL 本地权重环境未就绪，安装 requirements-director.txt 并配置 director.qwen3vl.model_path 后重跑。"
    if mode == "ollama":
        return "Ollama Director 环境未就绪，确认 api_base 可达且 api_model 已拉取后重跑 Stage 5。支持改为局域网内 Ollama 服务地址。"
    if mode == "openai_compatible":
        return "LM Studio / OpenAI 兼容 Director 环境未就绪，启动服务并确保 model 已加载到 /v1/models 后重跑 Stage 5。支持改为局域网内服务地址。"
    return "Qwen3-VL Director 环境未就绪，修复配置后重跑 Stage 5。"


if __name__ == "__main__":
    raise SystemExit(main())
