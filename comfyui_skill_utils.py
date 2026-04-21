from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "agent-skills" / "comfyui" / "registry.json"


NEGATIVE_KEYWORDS = (
    "negative",
    "worst quality",
    "low quality",
    "bad hands",
    "nsfw",
    "jpeg",
    "artifacts",
    "blurry",
    "deformed",
)


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path else REGISTRY_PATH
    with registry_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def workspace_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def relative_to_root(path: str | Path) -> str:
    resolved = workspace_path(path)
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def collect_nodes(workflow_data: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    top_level = workflow_data.get("nodes")
    if isinstance(top_level, list):
        nodes.extend(node for node in top_level if isinstance(node, dict))

    definitions = workflow_data.get("definitions") or {}
    for subgraph in definitions.get("subgraphs") or []:
        subgraph_nodes = subgraph.get("nodes") or []
        nodes.extend(node for node in subgraph_nodes if isinstance(node, dict))

    return nodes


def dedupe_model_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        name = entry.get("name")
        directory = entry.get("directory")
        if not name or not directory:
            continue
        key = (directory, name)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = dict(entry)
            continue
        if not existing.get("url") and entry.get("url"):
            existing["url"] = entry["url"]
        if not existing.get("source") and entry.get("source"):
            existing["source"] = entry["source"]
        if not existing.get("description") and entry.get("description"):
            existing["description"] = entry["description"]
    return sorted(deduped.values(), key=lambda item: (item["directory"], item["name"]))


def infer_directory(name: str, url: str = "") -> str | None:
    text = f"{name} {url}".lower()
    checks = (
        ("/diffusion_models/", "diffusion_models"),
        ("/text_encoders/", "text_encoders"),
        ("/clip_vision/", "clip_vision"),
        ("/controlnet/", "controlnet"),
        ("/upscale_models/", "upscale_models"),
        ("/audio_encoders/", "audio_encoders"),
        ("/embeddings/", "embeddings"),
        ("/vae_approx/", "vae_approx"),
        ("/loras/", "loras"),
        ("/vae/", "vae"),
        ("/clip/", "clip"),
        ("/unet/", "unet"),
        ("/checkpoints/", "checkpoints"),
    )
    for token, directory in checks:
        if token in text:
            return directory

    if "lora" in text:
        return "loras"
    if "vae" in text:
        return "vae"
    if "controlnet" in text:
        return "controlnet"
    if "umt5" in text or "text encoder" in text or "encoder" in text:
        return "text_encoders"
    if "clip vision" in text:
        return "clip_vision"
    if "unet" in text or "diffusion" in text or "14b" in text or "5b" in text:
        return "diffusion_models"
    return None


def extract_models_from_workflow_data(workflow_data: dict[str, Any], source: str = "") -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for node in collect_nodes(workflow_data):
        properties = node.get("properties") or {}
        models = properties.get("models") or []
        for model in models:
            if not isinstance(model, dict):
                continue
            name = model.get("name")
            if not name:
                continue
            url = model.get("url") or ""
            directory = model.get("directory") or infer_directory(name, url)
            if not directory:
                continue
            entries.append(
                {
                    "name": name,
                    "directory": directory,
                    "url": url,
                    "description": f"Workflow model for {source}" if source else "Workflow model",
                    "source": source,
                }
            )
    return dedupe_model_entries(entries)


def extract_models_from_workflow_file(path: str | Path) -> list[dict[str, Any]]:
    workflow_path = workspace_path(path)
    with workflow_path.open("r", encoding="utf-8") as handle:
        workflow_data = json.load(handle)
    return extract_models_from_workflow_data(workflow_data, source=relative_to_root(workflow_path))


def get_pack_models(registry: dict[str, Any], pack_names: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for pack_name in pack_names:
        pack = registry.get("packs", {}).get(pack_name)
        if not pack:
            raise KeyError(f"Unknown model pack: {pack_name}")
        for model in pack.get("models", []):
            entry = dict(model)
            entry.setdefault("source", f"pack:{pack_name}")
            entries.append(entry)
    return dedupe_model_entries(entries)


def get_skill(registry: dict[str, Any], skill_name: str) -> dict[str, Any]:
    skill = registry.get("skills", {}).get(skill_name)
    if not skill:
        raise KeyError(f"Unknown skill: {skill_name}")
    return skill


def model_file_path(model_root: str | Path, entry: dict[str, Any]) -> Path:
    return workspace_path(model_root) / entry["directory"] / entry["name"]


def has_negative_hint(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in NEGATIVE_KEYWORDS)
