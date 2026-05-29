from __future__ import annotations

import json
import urllib.request
from pathlib import Path

WORKFLOW_PATHS = [
    Path(r"D:\ComfyUI-aki-v3\agent-skills\comfyui\workflows\TEST\全能图片V1+Pro+电商详情页一键生成.json"),
    Path(r"D:\ComfyUI-aki-v3\agent-skills\comfyui\workflows\TEST\电商三件套一键生成电商主图.json"),
    Path(r"D:\ComfyUI-aki-v3\agent-skills\comfyui\workflows\TEST\去水印，去字幕，去模糊，高清LTX2.3+iclora+insight工作流.json"),
]
CUSTOM_NODES_ROOT = Path(r"D:\ComfyUI-aki-v3\ComfyUI\custom_nodes")
EXTENSION_NODE_MAP = CUSTOM_NODES_ROOT / "ComfyUI-Manager" / "extension-node-map.json"
OUTPUT_PATH = Path(r"D:\ComfyUI-aki-v3\agent-skills\runtime\workflow-node-audit-20260529.json")
SEARCH_SUFFIXES = {".py", ".json", ".js", ".ts", ".md"}
MAX_SOURCE_MATCHES = 8


def fetch_registered_nodes() -> set[str]:
    with urllib.request.urlopen("http://127.0.0.1:8188/object_info", timeout=30) as response:
        object_info = json.load(response)
    return set(object_info.keys())


def load_extension_map() -> dict[str, list[str]]:
    raw = json.loads(EXTENSION_NODE_MAP.read_text(encoding="utf-8"))
    extension_map: dict[str, list[str]] = {}
    for url, payload in raw.items():
        node_names = payload[0] if payload else []
        if isinstance(node_names, list):
            extension_map[url] = [str(name) for name in node_names]
    return extension_map


def list_used_types(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return sorted(
        {
            node_type
            for node in data.get("nodes", [])
            for node_type in [node.get("type") or node.get("class_type")]
            if node_type
        }
    )


def find_source_matches(node_type: str) -> list[str]:
    matches: list[str] = []
    for file_path in CUSTOM_NODES_ROOT.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in SEARCH_SUFFIXES:
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if node_type in text:
            matches.append(str(file_path))
            if len(matches) >= MAX_SOURCE_MATCHES:
                break
    return matches


def find_manager_candidates(node_type: str, extension_map: dict[str, list[str]]) -> list[str]:
    candidates = [url for url, node_names in extension_map.items() if node_type in node_names]
    return candidates[:8]


def main() -> None:
    registered_nodes = fetch_registered_nodes()
    extension_map = load_extension_map()
    report: dict[str, object] = {
        "registered_count": len(registered_nodes),
        "workflows": [],
        "all_missing": [],
        "missing_details": {},
    }
    all_missing: set[str] = set()
    for workflow_path in WORKFLOW_PATHS:
        used_types = list_used_types(workflow_path)
        missing_types = sorted(node_type for node_type in used_types if node_type not in registered_nodes)
        all_missing.update(missing_types)
        report["workflows"].append(
            {
                "path": str(workflow_path),
                "used_count": len(used_types),
                "missing_count": len(missing_types),
                "missing_types": missing_types,
            }
        )

    missing_details: dict[str, object] = {}
    for node_type in sorted(all_missing):
        source_matches = find_source_matches(node_type)
        missing_details[node_type] = {
            "present_in_workspace": bool(source_matches),
            "source_matches": source_matches,
            "manager_candidates": find_manager_candidates(node_type, extension_map),
        }

    report["all_missing"] = sorted(all_missing)
    report["missing_details"] = missing_details
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
