from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.common.io import read_json, write_json
from pipeline.prompting import create_prompt_optimizer


RUNTIME_ROOT = PROJECT_ROOT / "runtime" / "2026-05-15_test_projects_short_manga"
REVIEW_DIR = RUNTIME_ROOT / "review"
DEFAULT_INPUT = REVIEW_DIR / "video_prompt_pack.json"
DEFAULT_JSON = REVIEW_DIR / "optimized_prompt_pack.json"
DEFAULT_MD = REVIEW_DIR / "optimized_prompt_pack.md"


def main() -> int:
    args = _parse_args()
    prompt_pack = read_json(args.input)
    optimizer = create_prompt_optimizer(
        {
            "provider": args.provider,
            "model": args.model,
            "base_url": args.base_url,
            "api_key_env": args.api_key_env,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "timeout_seconds": args.timeout_seconds,
        }
    )
    raw_optimized = optimizer.optimize(prompt_pack)
    merged = merge_optimized_prompt_pack(prompt_pack, raw_optimized)
    write_json(args.output_json, merged)
    write_markdown(merged, args.output_md)
    print(
        json.dumps(
            {
                "provider": merged.get("optimizer", {}).get("provider"),
                "model": merged.get("optimizer", {}).get("model"),
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
                "characters": len(merged.get("characters", [])),
                "shots": len(merged.get("shots", [])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def merge_optimized_prompt_pack(prompt_pack: dict[str, Any], optimized: dict[str, Any]) -> dict[str, Any]:
    character_updates = _items_by_id(optimized.get("characters", []), "character_id")
    shot_updates = _items_by_id(optimized.get("shots", []), "shot_id")
    merged_characters = []
    for character in prompt_pack.get("characters", []):
        update = character_updates.get(str(character.get("character_id", "")), {})
        merged = dict(character)
        if update:
            merged["optimized_design_prompt"] = enrich_character_design_prompt(
                str(update.get("design_prompt") or update.get("positive_prompt") or "").strip(),
                character,
            )
            merged["optimized_negative_prompt"] = enrich_negative_prompt(
                str(update.get("negative_prompt") or character.get("negative_prompt") or "").strip(),
                character_scope=True,
            )
            merged["reference_notes"] = str(update.get("reference_notes") or "").strip()
        merged_characters.append(merged)

    merged_shots = []
    for shot in prompt_pack.get("shots", []):
        update = shot_updates.get(str(shot.get("shot_id", "")), {})
        merged = dict(shot)
        if update:
            merged["optimized_positive_prompt"] = enrich_shot_positive_prompt(
                str(update.get("positive_prompt") or "").strip(),
                shot,
            )
            merged["optimized_negative_prompt"] = enrich_negative_prompt(str(update.get("negative_prompt") or "").strip())
            merged["motion_prompt"] = str(update.get("motion_prompt") or "").strip()
            merged["camera_prompt"] = str(update.get("camera_prompt") or "").strip()
            merged["quality_notes"] = str(update.get("quality_notes") or "").strip()
        merged_shots.append(merged)

    result = dict(prompt_pack)
    result["optimizer"] = optimized.get("optimizer", {})
    result["characters"] = merged_characters
    result["shots"] = merged_shots
    result["raw_optimizer_response"] = optimized
    return result


def enrich_character_design_prompt(prompt: str, character: dict[str, Any]) -> str:
    traits = character.get("visual_traits") or {}
    anchors = [
        str(character.get("continuity_prompt") or ""),
        "anime production character reference sheet",
        "solo full-body design, front view plus small expression callouts",
        "clear silhouette, accurate age impression, consistent body proportions",
        "clean school uniform design with readable collar, bow, sleeves and skirt details",
        "soft studio lighting, crisp line art, delicate cel shading, polished key visual quality",
        "plain neutral background, no typography, no speech bubble, no logo",
        "ready as a stable reference image for image-to-video and later character LoRA training",
    ]
    if traits.get("descriptions"):
        descriptions = traits.get("descriptions")
        if isinstance(descriptions, list) and descriptions:
            anchors.insert(1, str(descriptions[0]))
    return _join_unique([prompt, *anchors])


def enrich_shot_positive_prompt(prompt: str, shot: dict[str, Any]) -> str:
    anchors = [
        "use the source manga panel as storyboard composition guide",
        "retain original character placement and height difference",
        "preserve source speech bubble layout only if already present, do not generate new readable text",
        "light dialogue animation, subtle breathing, tiny eye blink, slight hair sway",
        "stable face, stable hands, consistent school uniform colors, no identity drift",
        "gentle parallax, calm camera drift, anime keyframe quality, clean line art, soft cel shading",
    ]
    if shot.get("dialogue_summary"):
        anchors.insert(0, f"story beat: {shot.get('dialogue_summary')}")
    return _join_unique([prompt, *anchors])


def enrich_negative_prompt(prompt: str, *, character_scope: bool = False) -> str:
    common = [
        "worst quality",
        "low quality",
        "lowres",
        "blurry",
        "jpeg artifacts",
        "bad anatomy",
        "bad hands",
        "extra fingers",
        "missing fingers",
        "fused fingers",
        "deformed face",
        "asymmetrical eyes",
        "identity drift",
        "inconsistent hairstyle",
        "inconsistent eye color",
        "wrong school uniform",
        "watermark",
        "logo",
        "signature",
        "new subtitles",
        "random text",
        "unreadable generated text",
        "cropped head",
        "out of frame",
        "photorealistic",
        "3D render",
    ]
    if character_scope:
        common.extend(["multiple people", "duplicate character", "busy background", "speech bubble"])
    else:
        common.extend(["large mouth movement", "extreme expression", "fast action", "heavy body motion"])
    return _join_unique([prompt, *common])


def write_markdown(prompt_pack: dict[str, Any], output_path: Path) -> None:
    optimizer = prompt_pack.get("optimizer", {})
    lines = [
        "# LLM 优化提示词包",
        "",
        f"- provider：`{optimizer.get('provider', '')}`",
        f"- model：`{optimizer.get('model', '')}`",
        f"- base_url：`{optimizer.get('base_url', '')}`",
        "",
        "## 角色设定图 Prompt",
        "",
    ]
    for character in prompt_pack.get("characters", []):
        lines.extend(
            [
                f"### {character.get('display_name')} / `{character.get('character_id')}`",
                "",
                "正向：",
                "",
                f"```text\n{character.get('optimized_design_prompt') or character.get('continuity_prompt') or ''}\n```",
                "",
                "负向：",
                "",
                f"```text\n{character.get('optimized_negative_prompt') or character.get('negative_prompt') or ''}\n```",
                "",
                f"参考备注：{character.get('reference_notes') or ''}",
                "",
            ]
        )
    lines.extend(["## 视频镜头 Prompt", ""])
    for shot in prompt_pack.get("shots", []):
        positive = shot.get("optimized_positive_prompt") or shot.get("final_positive_prompt") or ""
        negative = shot.get("optimized_negative_prompt") or shot.get("final_negative_prompt") or ""
        lines.extend(
            [
                f"### {shot.get('shot_id')} / `{shot.get('workflow_route')}`",
                "",
                f"- 角色：`{', '.join(shot.get('main_character_ids', []))}`",
                f"- motion：{shot.get('motion_prompt') or ''}",
                f"- camera：{shot.get('camera_prompt') or ''}",
                f"- quality_notes：{shot.get('quality_notes') or ''}",
                "",
                "正向：",
                "",
                f"```text\n{positive}\n```",
                "",
                "负向：",
                "",
                f"```text\n{negative}\n```",
                "",
            ]
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _items_by_id(items: Any, id_field: str) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    if not isinstance(items, list):
        return by_id
    for item in items:
        if isinstance(item, dict):
            item_id = str(item.get(id_field) or "").strip()
            if item_id:
                by_id[item_id] = item
    return by_id


def _join_unique(parts: list[str]) -> str:
    clauses: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for clause in str(part or "").replace("，", ",").split(","):
            text = clause.strip()
            if not text:
                continue
            key = text.lower()
            if key in {"multiple views", "multiple views optional"}:
                continue
            if key not in seen:
                clauses.append(text)
                seen.add(key)
    return ", ".join(clauses)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimize the test-project prompt pack with an LLM provider")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--temperature", type=float, default=0.25)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
