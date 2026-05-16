from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.request
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


MODEL_EXTENSIONS = (
    ".safetensors",
    ".ckpt",
    ".pt",
    ".pth",
    ".onnx",
    ".bin",
    ".gguf",
    ".model",
)

STORY_KEYWORDS = {
    "video": 4,
    "wan": 4,
    "wan2": 4,
    "ltx": 3,
    "framepack": 5,
    "vace": 5,
    "sonic": 4,
    "mimicmotion": 4,
    "animate": 4,
    "infinite": 4,
    "talk": 3,
    "audio": 3,
    "lip": 3,
    "pose": 3,
    "depth": 2,
    "canny": 1,
    "story": 5,
    "首尾帧": 6,
    "长视频": 6,
    "连续": 4,
    "剧情": 6,
    "分镜": 5,
    "镜头": 4,
    "续帧": 6,
    "无限循环": 5,
    "图生视频": 5,
    "文生视频": 4,
    "视频生视频": 4,
    "音生视频": 5,
    "对口型": 5,
    "数字人": 4,
    "动作": 4,
    "姿势": 4,
    "表情": 4,
    "人物迁移": 5,
    "动作迁移": 5,
    "角色替换": 4,
    "主体替换": 4,
    "视频编辑": 4,
    "视频转绘": 4,
    "修复": 1,
    "高清": 1,
}

NODE_FEATURES = {
    "LoadImage": ("image_input", 2),
    "LoadVideo": ("video_input", 4),
    "VHS_LoadVideo": ("video_input", 4),
    "LoadAudio": ("audio_input", 4),
    "VHS_LoadAudio": ("audio_input", 4),
    "CreateVideo": ("video_output", 4),
    "SaveVideo": ("video_output", 5),
    "VHS_VideoCombine": ("video_output", 5),
    "VideoCombine": ("video_output", 5),
    "WanImageToVideo": ("wan_i2v", 8),
    "WanSoundImageToVideo": ("audio_to_video", 8),
    "WanInfiniteTalkToVideo": ("talking_video", 9),
    "WanVideoSampler": ("wan_video", 8),
    "WanVideoTextEncode": ("wan_video", 6),
    "LTXVImgToVideo": ("ltx_i2v", 7),
    "LTXVConditioning": ("ltx_video", 5),
    "Sonic": ("talking_video", 8),
    "MimicMotion": ("pose_motion", 7),
    "DWPreprocessor": ("pose_control", 3),
    "OpenposePreprocessor": ("pose_control", 3),
    "DepthAnything": ("depth_control", 2),
}

TEXT_NODE_HINTS = ("CLIPTextEncode", "WanVideoTextEncode", "TextEncode", "Prompt")


@dataclass
class WorkflowRecord:
    score: int
    path: str
    name: str
    mtime: str
    size: int
    format: str
    node_count: int
    class_count: int
    unknown_class_count: int
    missing_model_count: int
    features: list[str]
    classes: list[str]
    unknown_classes: list[str]
    models: list[str]
    missing_models: list[str]
    reason: str
    suitability: str


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return None
    except Exception:
        return None


def iter_values(obj: Any):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from iter_values(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from iter_values(value)
    else:
        yield obj


def walk_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_dicts(value)


def workflow_format(obj: Any) -> str:
    if isinstance(obj, dict) and obj and all(isinstance(v, dict) and "class_type" in v for v in obj.values()):
        return "api"
    if isinstance(obj, dict) and "nodes" in obj and isinstance(obj["nodes"], list):
        return "ui"
    return "unknown"


def collect_classes(obj: Any) -> list[str]:
    classes: list[str] = []
    for item in walk_dicts(obj):
        if isinstance(item.get("class_type"), str):
            classes.append(item["class_type"])
        elif isinstance(item.get("type"), str) and ("inputs" in item or "outputs" in item or "widgets_values" in item):
            classes.append(item["type"])
    # UI subgraph wrapper nodes sometimes use UUIDs; keep them for unknown-class checks,
    # but de-duplicate while preserving order.
    seen: set[str] = set()
    result: list[str] = []
    for cls in classes:
        if cls not in seen:
            result.append(cls)
            seen.add(cls)
    return result


def collect_model_refs(obj: Any) -> list[str]:
    refs: list[str] = []
    for value in iter_values(obj):
        if not isinstance(value, str):
            continue
        text = value.replace("\\", "/")
        for token in re.split(r"[\n\r\t\"'<>|]", text):
            token = token.strip().strip(",;")
            lowered = token.lower()
            if any(lowered.endswith(ext) for ext in MODEL_EXTENSIONS):
                refs.append(Path(token).name)
    seen: set[str] = set()
    result: list[str] = []
    for ref in refs:
        if ref not in seen:
            result.append(ref)
            seen.add(ref)
    return result


def build_model_index(model_root: Path) -> set[str]:
    names: set[str] = set()
    if not model_root.exists():
        return names
    for ext in MODEL_EXTENSIONS:
        for path in model_root.rglob(f"*{ext}"):
            names.add(path.name)
    return names


def get_object_classes(server: str) -> set[str]:
    try:
        with urllib.request.urlopen(f"{server.rstrip('/')}/object_info", timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        return set(data.keys())
    except Exception:
        return set()


def classify_unknown(classes: list[str], object_classes: set[str]) -> list[str]:
    if not object_classes:
        return []
    unknown = []
    for cls in classes:
        if cls in object_classes:
            continue
        if re.fullmatch(r"[0-9a-fA-F-]{20,}", cls):
            continue
        if cls in {"Note", "Reroute", "PrimitiveNode"}:
            continue
        unknown.append(cls)
    return sorted(set(unknown))


def score_workflow(path: Path, obj: Any, classes: list[str], missing_models: list[str], unknown_classes: list[str]) -> tuple[int, list[str], str, str]:
    text = (str(path) + " " + " ".join(classes) + " " + " ".join(str(v) for v in iter_values(obj) if isinstance(v, str))).lower()
    score = 0
    reasons: list[str] = []
    features: list[str] = []

    for keyword, value in STORY_KEYWORDS.items():
        if keyword.lower() in text:
            score += value
            reasons.append(keyword)

    class_set = set(classes)
    for cls in classes:
        if cls in NODE_FEATURES:
            feature, value = NODE_FEATURES[cls]
            score += value
            features.append(feature)

    if any(hint.lower() in " ".join(classes).lower() for hint in TEXT_NODE_HINTS):
        score += 2
        features.append("prompt")
    if any("video" in cls.lower() for cls in classes):
        score += 3
        features.append("video_nodes")
    if any("audio" in cls.lower() or "sound" in cls.lower() or "sonic" in cls.lower() for cls in classes):
        score += 4
        features.append("audio_or_lipsync")
    if {"LoadImage", "LoadVideo"} & class_set:
        score += 2
    if "SaveVideo" in class_set or "VHS_VideoCombine" in class_set or "CreateVideo" in class_set:
        score += 4

    if "nsfw" in text or "色情" in text or "涩涩" in text:
        score -= 4
        reasons.append("NSFW/需安全改写")

    if unknown_classes:
        score -= min(10, len(unknown_classes) * 2)
    if missing_models:
        score -= min(8, len(missing_models) * 1)

    if score >= 28 and len(unknown_classes) <= 8:
        suitability = "优先测试"
    elif score >= 18 and len(unknown_classes) <= 15:
        suitability = "候选"
    elif score >= 12:
        suitability = "辅助/后期"
    else:
        suitability = "不推荐"

    return score, sorted(set(features)), "、".join(dict.fromkeys(reasons[:12])), suitability


def analyze(root: Path, model_root: Path, server: str) -> list[WorkflowRecord]:
    object_classes = get_object_classes(server)
    model_index = build_model_index(model_root)
    records: list[WorkflowRecord] = []

    for path in root.rglob("*.json"):
        obj = load_json(path)
        if obj is None:
            continue
        classes = collect_classes(obj)
        models = collect_model_refs(obj)
        missing_models = [model for model in models if model not in model_index]
        unknown_classes = classify_unknown(classes, object_classes)
        score, features, reason, suitability = score_workflow(path, obj, classes, missing_models, unknown_classes)
        stat = path.stat()
        records.append(
            WorkflowRecord(
                score=score,
                path=str(path),
                name=path.name,
                mtime=stat.st_mtime_ns.__str__(),
                size=stat.st_size,
                format=workflow_format(obj),
                node_count=sum(1 for _ in walk_dicts(obj) if isinstance(_, dict) and ("class_type" in _ or "type" in _)),
                class_count=len(classes),
                unknown_class_count=len(unknown_classes),
                missing_model_count=len(missing_models),
                features=features,
                classes=classes[:80],
                unknown_classes=unknown_classes[:50],
                models=models[:80],
                missing_models=missing_models[:50],
                reason=reason,
                suitability=suitability,
            )
        )

    records.sort(key=lambda item: (item.suitability != "优先测试", -item.score, item.unknown_class_count, item.missing_model_count, item.path))
    return records


def write_outputs(records: list[WorkflowRecord], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "story_workflow_scan.json"
    json_path.write_text(json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = out_dir / "story_workflow_scan.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "score",
                "suitability",
                "format",
                "unknown_class_count",
                "missing_model_count",
                "name",
                "path",
                "features",
                "reason",
                "unknown_classes",
                "missing_models",
            ]
        )
        for record in records:
            writer.writerow(
                [
                    record.score,
                    record.suitability,
                    record.format,
                    record.unknown_class_count,
                    record.missing_model_count,
                    record.name,
                    record.path,
                    ";".join(record.features),
                    record.reason,
                    ";".join(record.unknown_classes[:15]),
                    ";".join(record.missing_models[:15]),
                ]
            )

    top = [r for r in records if r.suitability in {"优先测试", "候选", "辅助/后期"}][:40]
    md_lines = [
        "# 剧情向工作流扫描结果",
        "",
        f"- 扫描工作流数量：{len(records)}",
        f"- 优先测试：{sum(1 for r in records if r.suitability == '优先测试')}",
        f"- 候选：{sum(1 for r in records if r.suitability == '候选')}",
        f"- 辅助/后期：{sum(1 for r in records if r.suitability == '辅助/后期')}",
        "",
        "| 分级 | 分数 | 缺节点 | 缺模型 | 文件 | 关键能力 |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for record in top:
        rel = record.path.replace("\\", "/")
        md_lines.append(
            f"| {record.suitability} | {record.score} | {record.unknown_class_count} | {record.missing_model_count} | `{rel}` | {', '.join(record.features[:8])} |"
        )
    (out_dir / "story_workflow_shortlist.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default="D:/ComfyUI-aki-v3/agent-skills/comfyui/userdata/default/workflows/comfyui_workflow",
    )
    parser.add_argument("--model-root", default="D:/ComfyUI-aki-v3/ComfyUI/models")
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--out-dir", default="D:/ComfyUI-aki-v3/agent-skills/runtime/workflow_story_filter")
    args = parser.parse_args()


    root = Path(args.root)
    if not root.exists():
        print(f"Missing root: {root}", file=sys.stderr)
        return 2

    records = analyze(root, Path(args.model_root), args.server)
    write_outputs(records, Path(args.out_dir))

    counts = Counter(r.suitability for r in records)
    print(json.dumps({"total": len(records), "counts": counts}, ensure_ascii=False, indent=2))
    for record in records[:20]:
        print(f"{record.suitability}\t{record.score}\tmissing_nodes={record.unknown_class_count}\tmissing_models={record.missing_model_count}\t{record.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
