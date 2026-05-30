from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
MODELS_ROOT = WORKSPACE_ROOT / "ComfyUI" / "models"
REPORT_ROOT = WORKSPACE_ROOT / "agent-skills" / "runtime" / "model_organize"
REFERENCE_ROOTS = [
    WORKSPACE_ROOT / "agent-skills" / "comfyui" / "workflows",
    WORKSPACE_ROOT / "ComfyUI" / "user",
    WORKSPACE_ROOT / "runtime",
]

SIDE_SUFFIXES = (".aria2",)
SKIP_FILENAMES = {
    "put_checkpoints_here",
    "put_diffusion_model_files_here",
    "put_unet_files_here",
    "put_text_encoder_files_here",
    "put_clip_or_text_encoder_models_here",
    "put_clip_vision_models_here",
    "put_loras_here",
    "put_vae_here",
    "put_controlnets_and_t2i_here",
    "lora_manager_stats.json",
}


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    target: str


RULES: dict[str, list[Rule]] = {
    "diffusion_models": [
        Rule(re.compile(r"ltx[-_. ]?2\.3|ltx23|ltx2\.3", re.I), "LTX2.3"),
        Rule(re.compile(r"wan[-_. ]?2\.2|wan22|dasiwawan22|wan_2_2|wan2_2", re.I), "WAN2.2"),
        Rule(re.compile(r"wan[-_. ]?2\.1|wan21|wan_2_1|wan2_1", re.I), "WAN2.1"),
        Rule(re.compile(r"melband", re.I), "AUDIO"),
    ],
    "checkpoints": [
        Rule(re.compile(r"wan[-_. ]?2\.2|wan22|smoothmixwan22", re.I), "WAN2.2"),
        Rule(re.compile(r"hunyuan", re.I), "HUNYUAN_VIDEO"),
        Rule(re.compile(r"cogvideo", re.I), "COGVIDEOX"),
        Rule(re.compile(r"illustrious", re.I), "ILLUSTRIOUS"),
        Rule(re.compile(r"pony", re.I), "PONY"),
        Rule(re.compile(r"anylora", re.I), "SD15"),
        Rule(re.compile(r"sdxl|sd_xl|\bxl\b|xl_|_xl|juggernautxl|animaginexl|dreamshaper xl|excelaxl|nova3dcgxl", re.I), "SDXL"),
    ],
    "unet": [
        Rule(re.compile(r"flux", re.I), "FLUX_KONTEXT"),
    ],
    "text_encoders": [
        Rule(re.compile(r"umt5", re.I), "UMT5"),
        Rule(re.compile(r"gemma", re.I), "GEMMA"),
        Rule(re.compile(r"qwen", re.I), "QWEN"),
        Rule(re.compile(r"ltx", re.I), "LTX2.3"),
    ],
    "clip": [
        Rule(re.compile(r"t5", re.I), "T5"),
        Rule(re.compile(r"open-clip|roberta", re.I), "OPENCLIP"),
        Rule(re.compile(r"clip_l", re.I), "CLIP_L"),
    ],
    "loras": [
        Rule(re.compile(r"wan[-_. ]?2\.2|wan22|\bw22\b|dasiwa_wan22|titjob_wan2\.2|nsfw-22|bouncehighwan2_2|bounce_test|dr34ml4y_i2v_14b|jfj-deepthroat-w22|svi.*wan2\.2|wananimate|360_epoch20|slop_twerk", re.I), "WAN2.2"),
        Rule(re.compile(r"wan[-_. ]?2\.1|wan21|wan_2\.1|消失wan2\.1", re.I), "WAN2.1"),
        Rule(re.compile(r"ltx[-_. ]?2\.3|ltx23|ltx2\.3|lightx2v|bouncev2_5_ltx23|dr34ml4y_ltxxx|licon-vbvr|omninft", re.I), "LTX2.3"),
        Rule(re.compile(r"kontext|f\.1|flux|fluffy-kontext|icedit", re.I), "FLUX_KONTEXT"),
        Rule(re.compile(r"ip-adapter", re.I), "IPADAPTER"),
        Rule(re.compile(r"illustrious|sdxl|\bxl\b|xl_|_xl", re.I), "ILLUSTRIOUS_SDXL"),
        Rule(re.compile(r"sd15|lcm_lora_weights_sd15", re.I), "SD15"),
    ],
    "vae": [
        Rule(re.compile(r"wan", re.I), "WAN"),
        Rule(re.compile(r"ltx|taeltx", re.I), "LTX2.3"),
        Rule(re.compile(r"qwen", re.I), "QWEN"),
        Rule(re.compile(r"^ae\.safetensors$", re.I), "FLUX"),
        Rule(re.compile(r"ema_vae_fp16|vae-ft-mse", re.I), "SD15"),
        Rule(re.compile(r"sdxl|xl_vae|\bxl\b", re.I), "SDXL"),
    ],
    "controlnet": [
        Rule(re.compile(r"depth", re.I), "DEPTH"),
        Rule(re.compile(r"line", re.I), "LINEART"),
        Rule(re.compile(r"xl", re.I), "SDXL"),
    ],
    "clip_vision": [
        Rule(re.compile(r"bigg", re.I), "VIT_BIGG"),
        Rule(re.compile(r"vit-h|vision_h", re.I), "VIT_H"),
    ],
    "ipadapter": [
        Rule(re.compile(r"sdxl", re.I), "SDXL"),
        Rule(re.compile(r"sd15", re.I), "SD15"),
        Rule(re.compile(r"^ip-adapter\.bin$", re.I), "CORE"),
    ],
}

DEFAULT_TARGETS = tuple(RULES)


def iter_reference_files() -> list[Path]:
    files: list[Path] = []
    for root in REFERENCE_ROOTS:
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*.json") if path.is_file())
    return files


def load_reference_blob() -> str:
    parts: list[str] = []
    for path in iter_reference_files():
        try:
            parts.append(path.read_text(encoding="utf-8", errors="ignore").lower())
        except OSError:
            continue
    return "\n".join(parts)


def target_subdir(root_name: str, file_name: str) -> str:
    rules = RULES.get(root_name, [])
    for rule in rules:
        if rule.pattern.search(file_name):
            return rule.target
    return "MISC"


def file_group(root_dir: Path, file_name: str) -> list[Path]:
    paths = [root_dir / file_name]
    primary = root_dir / file_name
    metadata = root_dir / f"{primary.stem}.metadata.json"
    if metadata.exists():
        paths.append(metadata)
    for suffix in SIDE_SUFFIXES:
        sidecar = root_dir / f"{file_name}{suffix}"
        if sidecar.exists():
            paths.append(sidecar)
    return [path for path in paths if path.exists()]


def top_level_primary_files(root_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        if path.name in SKIP_FILENAMES:
            continue
        if path.name.endswith(".metadata.json"):
            continue
        if path.name.endswith(SIDE_SUFFIXES):
            continue
        files.append(path)
    return files


def orphan_sidecars(root_dir: Path) -> list[Path]:
    results: list[Path] = []
    for path in sorted(root_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        if path.name in SKIP_FILENAMES:
            continue
        is_metadata = path.name.endswith(".metadata.json")
        is_aria2 = path.name.endswith(".aria2")
        if not (is_metadata or is_aria2):
            continue
        if is_aria2:
            primary_name = path.name[:-6]
        else:
            primary_name = path.name[:-14]
        if (root_dir / primary_name).exists():
            continue
        results.append(path)
    return results


def classify_orphan_sidecar(root_name: str, sidecar_path: Path) -> str:
    if sidecar_path.name.endswith(".aria2"):
        primary_name = sidecar_path.name[:-6]
    else:
        primary_name = sidecar_path.name[:-14]
    return target_subdir(root_name, primary_name)


def format_path(path: Path) -> str:
    return path.as_posix().replace(str(WORKSPACE_ROOT).replace("\\", "/") + "/", "")


def collect_plan(target_roots: tuple[str, ...], include_referenced: bool) -> dict[str, object]:
    reference_blob = load_reference_blob() if not include_referenced else ""
    plan_moves: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    summary = Counter()
    planned_sources: set[str] = set()

    for root_name in target_roots:
        root_dir = MODELS_ROOT / root_name
        if not root_dir.exists():
            continue

        for primary in top_level_primary_files(root_dir):
            ref_hit = (primary.name.lower() in reference_blob) if reference_blob else False
            subdir = target_subdir(root_name, primary.name)
            group = file_group(root_dir, primary.name)
            group_size = sum(path.stat().st_size for path in group)
            destination_dir = root_dir / subdir

            if ref_hit:
                skipped.append(
                    {
                        "source": format_path(primary),
                        "reason": "referenced_in_workflows",
                        "suggested_target": format_path(destination_dir / primary.name),
                        "size_bytes": group_size,
                    }
                )
                continue

            for path in group:
                relative_dest = destination_dir / path.name
                formatted_source = format_path(path)
                if formatted_source in planned_sources:
                    continue
                plan_moves.append(
                    {
                        "source": formatted_source,
                        "destination": format_path(relative_dest),
                        "root": root_name,
                        "subdir": subdir,
                        "size_bytes": path.stat().st_size,
                    }
                )
                planned_sources.add(formatted_source)
            summary[f"{root_name}/{subdir}"] += 1

        for sidecar in orphan_sidecars(root_dir):
            subdir = classify_orphan_sidecar(root_name, sidecar)
            destination_dir = root_dir / subdir
            formatted_source = format_path(sidecar)
            if formatted_source in planned_sources:
                continue
            plan_moves.append(
                {
                    "source": formatted_source,
                    "destination": format_path(destination_dir / sidecar.name),
                    "root": root_name,
                    "subdir": subdir,
                    "size_bytes": sidecar.stat().st_size,
                }
            )
            planned_sources.add(formatted_source)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "models_root": format_path(MODELS_ROOT),
        "include_referenced": include_referenced,
        "planned_groups": sum(summary.values()),
        "planned_files": len(plan_moves),
        "planned_bytes": sum(item["size_bytes"] for item in plan_moves),
        "planned_by_target": dict(sorted(summary.items())),
        "moves": plan_moves,
        "skipped": skipped,
    }


def execute_plan(plan: dict[str, object]) -> dict[str, object]:
    completed: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    for item in plan["moves"]:
        source = WORKSPACE_ROOT / Path(item["source"])
        destination = WORKSPACE_ROOT / Path(item["destination"])

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                source_name = source.name.lower()
                is_sidecar = source_name.endswith(".aria2") or source_name.endswith(".metadata.json")
                if is_sidecar and source.stat().st_size == destination.stat().st_size:
                    source.unlink()
                    completed.append(
                        {
                            "source": item["source"],
                            "destination": item["destination"],
                        }
                    )
                    continue
                errors.append(
                    {
                        "source": item["source"],
                        "destination": item["destination"],
                        "error": "destination_exists",
                    }
                )
                continue
            source.rename(destination)
            completed.append(
                {
                    "source": item["source"],
                    "destination": item["destination"],
                }
            )
        except OSError as exc:
            errors.append(
                {
                    "source": item["source"],
                    "destination": item["destination"],
                    "error": str(exc),
                }
            )

    return {
        "completed": completed,
        "errors": errors,
    }


def write_report(report_name: str, payload: dict[str, object]) -> Path:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_ROOT / report_name
    report_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report_path


def human_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standardize ComfyUI model storage into second-level family folders.")
    parser.add_argument("--execute", action="store_true", help="Apply planned moves.")
    parser.add_argument("--include-referenced", action="store_true", help="Also move filenames referenced in known workflow JSON files.")
    parser.add_argument(
        "--roots",
        nargs="+",
        default=list(DEFAULT_TARGETS),
        choices=list(DEFAULT_TARGETS),
        help="Model roots to organize.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_roots = tuple(args.roots)
    plan = collect_plan(target_roots=target_roots, include_referenced=args.include_referenced)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    if not args.execute:
        report_path = write_report(f"{timestamp}_dry_run.json", plan)
        print(f"planned_groups={plan['planned_groups']}")
        print(f"planned_files={plan['planned_files']}")
        print(f"planned_size={human_size(int(plan['planned_bytes']))}")
        print(f"skipped={len(plan['skipped'])}")
        print(f"report={report_path}")
        return 0

    execution = execute_plan(plan)
    result = {
        **plan,
        "executed_at": datetime.now().isoformat(timespec="seconds"),
        "completed": execution["completed"],
        "errors": execution["errors"],
    }
    report_path = write_report(f"{timestamp}_executed.json", result)
    print(f"completed={len(execution['completed'])}")
    print(f"errors={len(execution['errors'])}")
    print(f"report={report_path}")
    return 0 if not execution["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())