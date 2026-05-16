# 工作流校验模块：聚焦真实节点、真实模型路径和必要参数
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import CUSTOM_NODES_ROOT, MODELS_ROOT


MODEL_INPUT_DIRS: dict[str, dict[str, list[str]]] = {
    "CheckpointLoaderSimple": {"ckpt_name": ["checkpoints"]},
    "CLIPLoader": {"clip_name": ["clip"]},
    "DualCLIPLoader": {"clip_name1": ["clip"], "clip_name2": ["clip"]},
    "TripleCLIPLoader": {"clip_name1": ["clip"], "clip_name2": ["clip"], "clip_name3": ["clip"]},
    "VAELoader": {"vae_name": ["vae"]},
    "UNETLoader": {"unet_name": ["diffusion_models", "unet"]},
    "LoraLoader": {"lora_name": ["loras"]},
    "LoraLoaderModelOnly": {"lora_name": ["loras"]},
    "ControlNetLoader": {"control_net_name": ["controlnet"]},
    "UpscaleModelLoader": {"model_name": ["upscale_models"]},
    "MMAudioModelLoader": {"mmaudio_model": ["mmaudio"]},
    "MMAudioFeatureUtilsLoader": {
        "vae_model": ["mmaudio"],
        "synchformer_model": ["mmaudio"],
        "clip_model": ["mmaudio"],
    },
    "MMAudioVoCoderLoader": {"vocoder_model": ["mmaudio"]},
}

UI_WIDGET_MODELS: dict[str, list[tuple[int, str, list[str]]]] = {
    "CheckpointLoaderSimple": [(0, "ckpt_name", ["checkpoints"])],
    "CLIPLoader": [(0, "clip_name", ["clip"])],
    "DualCLIPLoader": [(0, "clip_name1", ["clip"]), (1, "clip_name2", ["clip"])],
    "TripleCLIPLoader": [(0, "clip_name1", ["clip"]), (1, "clip_name2", ["clip"]), (2, "clip_name3", ["clip"])],
    "VAELoader": [(0, "vae_name", ["vae"])],
    "UNETLoader": [(0, "unet_name", ["diffusion_models", "unet"])],
    "LoraLoader": [(0, "lora_name", ["loras"])],
    "LoraLoaderModelOnly": [(0, "lora_name", ["loras"])],
    "ControlNetLoader": [(0, "control_net_name", ["controlnet"])],
    "UpscaleModelLoader": [(0, "model_name", ["upscale_models"])],
    "MMAudioModelLoader": [(0, "mmaudio_model", ["mmaudio"])],
    "MMAudioFeatureUtilsLoader": [
        (0, "vae_model", ["mmaudio"]),
        (1, "synchformer_model", ["mmaudio"]),
        (2, "clip_model", ["mmaudio"]),
    ],
    "MMAudioVoCoderLoader": [(0, "vocoder_model", ["mmaudio"])],
    "RIFEInterpolation": [(3, "model_name", ["rife_vfi"])],
}

PARAM_RANGE_CHECKS: dict[str, tuple[float, float]] = {
    "steps": (1, 150),
    "cfg": (0.0, 30.0),
    "duration": (0.1, 120.0),
    "source_fps": (1.0, 120.0),
    "target_fps": (1.0, 240.0),
    "frame_rate": (1.0, 240.0),
    "force_rate": (0.0, 240.0),
    "crf": (0, 51),
    "batch_size": (1, 64),
    "scale": (0.0, 8.0),
}


def load_workflow(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": f"加载失败: {exc}"}


def workflow_kind(workflow: dict[str, Any]) -> str:
    if isinstance(workflow.get("nodes"), list):
        return "ui"
    for value in workflow.values():
        if isinstance(value, dict) and "class_type" in value:
            return "api"
    return "not_workflow"


def extract_nodes(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    kind = workflow_kind(workflow)
    if kind == "ui":
        nodes = [node for node in workflow.get("nodes", []) if isinstance(node, dict)]
        definitions = workflow.get("definitions") or {}
        for subgraph in definitions.get("subgraphs", []):
            nodes.extend(node for node in subgraph.get("nodes", []) if isinstance(node, dict))
        return nodes

    if kind == "api":
        nodes: list[dict[str, Any]] = []
        for node_id, node in workflow.items():
            if not isinstance(node, dict) or "class_type" not in node:
                continue
            nodes.append({
                "id": str(node_id),
                "type": node.get("class_type", ""),
                "inputs": node.get("inputs", {}),
                "_meta": node.get("_meta", {}),
            })
        return nodes

    return []


def _input_items(node: dict[str, Any]) -> list[tuple[str, Any]]:
    inputs = node.get("inputs", {})
    if isinstance(inputs, dict):
        return list(inputs.items())
    if isinstance(inputs, list):
        items: list[tuple[str, Any]] = []
        for item in inputs:
            if isinstance(item, dict):
                items.append((str(item.get("name", "")), item.get("value", item.get("default"))))
        return items
    return []


def extract_model_refs(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    kind = workflow_kind(workflow)

    for node in extract_nodes(workflow):
        node_id = node.get("id", "?")
        node_type = node.get("type", "") or node.get("class_type", "")

        if kind == "api":
            input_map = dict(_input_items(node))
            mapping = MODEL_INPUT_DIRS.get(node_type, {})
            if node_type == "CLIPLoader" and input_map.get("type") == "wan":
                mapping = {"clip_name": ["text_encoders", "clip"]}
            for input_name, directories in mapping.items():
                value = input_map.get(input_name)
                if isinstance(value, str) and value:
                    refs.append(_make_model_ref(node_id, node_type, input_name, value, directories))
            continue

        widgets = node.get("widgets_values", [])
        if not isinstance(widgets, list):
            widgets = [widgets]
        for index, input_name, directories in UI_WIDGET_MODELS.get(node_type, []):
            if index >= len(widgets):
                continue
            value = widgets[index]
            if isinstance(value, str) and value:
                if node_type == "CLIPLoader" and len(widgets) > 1 and widgets[1] == "wan":
                    directories = ["text_encoders", "clip"]
                refs.append(_make_model_ref(node_id, node_type, input_name, value, directories))

    return refs


def _make_model_ref(node_id: Any, node_type: str, input_name: str, model_name: str, directories: list[str]) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "node_type": node_type,
        "input_name": input_name,
        "model_name": model_name,
        "expected_dirs": directories,
    }


@lru_cache(maxsize=1)
def _model_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    if MODELS_ROOT.is_dir():
        for path in MODELS_ROOT.rglob("*"):
            if path.is_file() and not path.name.startswith("put_"):
                index.setdefault(path.name, []).append(path)
    return index


def _rife_vfi_paths(name: str) -> list[Path]:
    return [
        MODELS_ROOT / "rife" / name,
        CUSTOM_NODES_ROOT / "ComfyUI-VFI" / "rife" / "train_log" / name,
        CUSTOM_NODES_ROOT / "ComfyUI-VFI" / "models" / name,
    ]


def resolve_model(name: str, expected_dirs: list[str]) -> dict[str, Any]:
    if "rife_vfi" in expected_dirs:
        candidates = _rife_vfi_paths(name)
        existing = [path for path in candidates if path.is_file()]
        return {
            "exists": bool(existing),
            "status": "ok" if existing else "missing",
            "paths": existing,
            "searched": candidates,
        }

    expected_paths = [MODELS_ROOT / directory / name for directory in expected_dirs]
    existing_expected = [path for path in expected_paths if path.is_file()]
    if existing_expected:
        return {"exists": True, "status": "ok", "paths": existing_expected, "searched": expected_paths}

    exact_elsewhere = _model_index().get(Path(name).name, [])
    if exact_elsewhere:
        return {"exists": True, "status": "wrong_dir", "paths": exact_elsewhere, "searched": expected_paths}

    return {"exists": False, "status": "missing", "paths": [], "searched": expected_paths}


def validate_node_types(workflow: dict[str, Any], node_inventory: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for node in extract_nodes(workflow):
        node_type = node.get("type", "") or node.get("class_type", "")
        if not node_type:
            issues.append({"severity": "error", "node_id": node.get("id", "?"), "message": "节点缺少 type/class_type"})
            continue
        if node_inventory and node_type not in node_inventory:
            issues.append({
                "severity": "error",
                "node_id": node.get("id", "?"),
                "node_type": node_type,
                "message": f"节点类型未注册: {node_type}",
            })
    return issues


def validate_model_refs(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for ref in extract_model_refs(workflow):
        resolution = resolve_model(ref["model_name"], ref["expected_dirs"])
        if resolution["status"] == "ok":
            issues.append({**ref, "severity": "ok", "message": f"模型就位: {ref['model_name']}"})
        elif resolution["status"] == "wrong_dir":
            found = "; ".join(str(path) for path in resolution["paths"])
            issues.append({
                **ref,
                "severity": "warning",
                "message": f"模型存在但不在预期目录: {ref['model_name']} -> {found}",
            })
        else:
            searched = "; ".join(str(path) for path in resolution["searched"])
            issues.append({
                **ref,
                "severity": "error",
                "message": f"模型缺失: {ref['model_name']}；已检查 {searched}",
            })
    return issues


def validate_params(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for node in extract_nodes(workflow):
        node_id = node.get("id", "?")
        node_type = node.get("type", "") or node.get("class_type", "")
        for key, value in _input_items(node):
            _check_param(issues, node_id, node_type, key, value)

        widgets = node.get("widgets_values", [])
        if isinstance(widgets, dict):
            for key, value in widgets.items():
                _check_param(issues, node_id, node_type, key, value)

    return issues


def _check_param(issues: list[dict[str, Any]], node_id: Any, node_type: str, key: str, value: Any) -> None:
    if not isinstance(value, (int, float)):
        return
    key_lower = key.lower()
    for param, (minimum, maximum) in PARAM_RANGE_CHECKS.items():
        if param in key_lower and not (minimum <= value <= maximum):
            issues.append({
                "severity": "warning",
                "node_id": node_id,
                "node_type": node_type,
                "param": key,
                "value": value,
                "message": f"参数超出常规范围: {key}={value}，建议范围 [{minimum}, {maximum}]",
            })


def validate_links(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    if workflow_kind(workflow) != "ui":
        return []

    issues: list[dict[str, Any]] = []
    nodes = workflow.get("nodes", [])
    node_ids = {node.get("id") for node in nodes if isinstance(node, dict)}
    for link in workflow.get("links", []) or []:
        if not isinstance(link, list) or len(link) < 5:
            continue
        origin_node = link[1]
        target_node = link[3]
        if origin_node not in node_ids:
            issues.append({"severity": "error", "message": f"链接引用了不存在的源节点: {origin_node}"})
        if target_node not in node_ids:
            issues.append({"severity": "error", "message": f"链接引用了不存在的目标节点: {target_node}"})
    return issues


def validate_workflow(path: Path, node_inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "loaded": False,
        "kind": "unknown",
        "node_count": 0,
        "link_count": 0,
        "model_refs": [],
        "issues": [],
        "score": "unknown",
    }

    workflow = load_workflow(path)
    if "_error" in workflow:
        result["issues"].append({"severity": "error", "message": workflow["_error"]})
        result["score"] = "FAIL"
        return result

    kind = workflow_kind(workflow)
    result["kind"] = kind
    if kind == "not_workflow":
        result["score"] = "SKIP"
        result["issues"].append({"severity": "info", "message": "不是 ComfyUI 工作流 JSON，已跳过"})
        return result

    result["loaded"] = True
    nodes = extract_nodes(workflow)
    result["node_count"] = len(nodes)
    result["link_count"] = len(workflow.get("links", []) or []) if kind == "ui" else 0

    if node_inventory:
        result["issues"].extend(validate_node_types(workflow, node_inventory))

    result["model_refs"] = extract_model_refs(workflow)
    result["issues"].extend(validate_model_refs(workflow))
    result["issues"].extend(validate_params(workflow))
    result["issues"].extend(validate_links(workflow))

    errors = sum(1 for item in result["issues"] if item["severity"] == "error")
    warnings = sum(1 for item in result["issues"] if item["severity"] == "warning")
    if errors:
        result["score"] = "FAIL"
    elif warnings:
        result["score"] = "WARN"
    else:
        result["score"] = "PASS"
    return result
