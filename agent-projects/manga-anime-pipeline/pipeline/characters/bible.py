from __future__ import annotations

import ast
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pipeline.common.io import as_project_path, write_json
from pipeline.common.status import utc_now_iso

GENERIC_NAMES = {
    "",
    "unknown_character",
    "黑发角色",
    "白发角色",
    "高个子角色",
    "矮个子角色",
    "角色",
    "少女",
    "女学生",
}

TRAIT_KEYS = {
    "name",
    "description",
    "hair_color",
    "hair_style",
    "eye_color",
    "attire",
    "height",
    "role",
    "action",
    "emotion",
}


def build_character_bible(
    shot_manifest: dict[str, Any],
    project_root: Path,
    runtime_root: Path,
) -> tuple[dict[str, Any], Path]:
    """Build a chapter-level character bible and annotate shots with stable ids."""

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for shot in shot_manifest.get("shots", []) or []:
        shot_character_ids: list[str] = []
        for candidate in _shot_character_candidates(shot):
            character_id = _character_id_for_candidate(candidate)
            candidate["character_id"] = character_id
            candidate["shot_id"] = shot.get("shot_id")
            candidate["source_windows"] = list(shot.get("source_windows", []) or [])
            groups[character_id].append(candidate)
            if candidate.get("role_scope") == "main" and character_id not in shot_character_ids:
                shot_character_ids.append(character_id)
        if shot_character_ids:
            shot["main_character_ids"] = shot_character_ids

    groups, merge_map = _merge_groups(groups)
    _rewrite_shot_character_ids(shot_manifest, merge_map)
    characters = [_character_entry(character_id, evidence) for character_id, evidence in sorted(groups.items())]
    bible = {
        "bible_version": "character_bible.v1",
        "series_id": shot_manifest.get("series_id"),
        "chapter_id": shot_manifest.get("chapter_id"),
        "generated_at": utc_now_iso(),
        "source": {
            "shot_manifest": "shot_manifest.json",
            "director_provider": (shot_manifest.get("director") or {}).get("provider"),
            "director_model": (shot_manifest.get("director") or {}).get("model"),
        },
        "characters": characters,
        "continuity_guidelines": _continuity_guidelines(characters),
        "open_issues": _open_issues(characters),
    }
    output_path = (
        runtime_root
        / "characters"
        / _safe_path_part(str(shot_manifest.get("series_id", "series")))
        / _safe_path_part(str(shot_manifest.get("chapter_id", "chapter")))
        / "character_bible.json"
    )
    write_json(output_path, bible)
    shot_manifest["character_bible_ref"] = as_project_path(project_root, output_path)
    return bible, output_path


def _merge_groups(groups: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    merge_map: dict[str, str] = {}
    alias_to_visual_id: dict[str, str] = {}
    visual_ids = [character_id for character_id, evidence in groups.items() if _group_has_visual_traits(evidence)]
    for character_id in visual_ids:
        for alias in _group_aliases(groups[character_id]):
            alias_to_visual_id.setdefault(alias, character_id)

    for character_id, evidence in groups.items():
        if character_id in visual_ids:
            continue
        for alias in _group_aliases(evidence):
            target = alias_to_visual_id.get(alias)
            if target and target != character_id:
                merge_map[character_id] = target
                break

    for character_id, evidence in groups.items():
        if character_id in merge_map or character_id in visual_ids or len(visual_ids) != 2:
            continue
        text = " ".join(_candidate_text(item) for item in evidence)
        mentioned_targets = {
            target
            for alias, target in alias_to_visual_id.items()
            if alias and alias in text
        }
        if len(mentioned_targets) == 1:
            other_targets = [target for target in visual_ids if target not in mentioned_targets]
            if other_targets:
                merge_map[character_id] = other_targets[0]

    merged: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for character_id, evidence in groups.items():
        target = merge_map.get(character_id, character_id)
        for item in evidence:
            item["character_id"] = target
            merged[target].append(item)
    return merged, merge_map


def _rewrite_shot_character_ids(shot_manifest: dict[str, Any], merge_map: dict[str, str]) -> None:
    if not merge_map:
        return
    for shot in shot_manifest.get("shots", []) or []:
        ids = []
        for character_id in shot.get("main_character_ids", []) or []:
            target = merge_map.get(character_id, character_id)
            if target not in ids:
                ids.append(target)
        if ids:
            shot["main_character_ids"] = ids


def _group_has_visual_traits(evidence: list[dict[str, Any]]) -> bool:
    return any(_infer_hair_color(item) or _infer_hair_style(item) or _infer_eye_color(item) or _infer_outfit(item) for item in evidence)


def _group_aliases(evidence: list[dict[str, Any]]) -> set[str]:
    aliases: set[str] = set()
    for item in evidence:
        name = str(item.get("name") or "").strip()
        if name and name not in GENERIC_NAMES:
            aliases.add(name.lower())
    return aliases


def _shot_character_candidates(shot: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    raw_candidates = shot.get("character_candidates")
    if isinstance(raw_candidates, list):
        for item in raw_candidates:
            candidate = _coerce_candidate(item)
            if candidate:
                candidates.append(candidate)
    for scope, field_name in (("main", "main_characters"), ("support", "support_characters")):
        for item in shot.get(field_name, []) or []:
            candidate = _coerce_candidate(item)
            if candidate:
                candidate.setdefault("role_scope", scope)
                candidates.append(candidate)
    return _dedupe_candidates(candidates)


def _coerce_candidate(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        candidate = {str(key): value for key, value in value.items() if key in TRAIT_KEYS or key == "role_scope"}
        if candidate.get("name") or candidate.get("description"):
            return candidate
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    parsed = _parse_mapping_text(text)
    if parsed is not None:
        return _coerce_candidate(parsed)
    return {"name": text, "description": text}


def _parse_mapping_text(text: str) -> dict[str, Any] | None:
    if not (text.startswith("{") and text.endswith("}")):
        return None
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    rich_names = {
        str(candidate.get("name", "")).strip()
        for candidate in candidates
        if str(candidate.get("name", "")).strip()
        and any(candidate.get(key) for key in ("description", "hair_color", "hair_style", "eye_color", "attire", "height", "role", "action", "emotion"))
        and str(candidate.get("description", "")).strip() != str(candidate.get("name", "")).strip()
    }
    for candidate in candidates:
        name = str(candidate.get("name", "")).strip()
        description = str(candidate.get("description", "")).strip()
        if name in rich_names and description == name:
            continue
        key = (str(candidate.get("name", "")), str(candidate.get("description", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _character_id_for_candidate(candidate: dict[str, Any]) -> str:
    trait_text = _candidate_text(candidate)
    if _has_any(trait_text, ["银", "白", "silver", "white"]) and _has_any(trait_text, ["长发", "long", "发箍", "headband", "绿色", "green"]):
        return "char_silver_longhair"
    if _has_any(trait_text, ["黑", "紫", "dark", "purple"]) and _has_any(trait_text, ["马尾", "ponytail", "高马尾", "金色", "yellow", "gold"]):
        return "char_dark_ponytail"
    name = str(candidate.get("name") or "").strip()
    if name and name not in GENERIC_NAMES:
        return "char_" + _safe_path_part(name.lower())
    return "char_" + _safe_path_part(_short_fingerprint(trait_text))


def _character_entry(character_id: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    aliases = _most_common_strings(item.get("name") for item in evidence if item.get("name") and item.get("name") not in GENERIC_NAMES)
    descriptions = _most_common_strings(item.get("description") for item in evidence if item.get("description"))
    heights = _most_common_strings(item.get("height") for item in evidence if item.get("height"))
    hair_colors = _most_common_strings(_infer_hair_color(item) for item in evidence)
    hair_styles = _most_common_strings(_infer_hair_style(item) for item in evidence)
    eye_colors = _most_common_strings(_infer_eye_color(item) for item in evidence)
    outfits = _most_common_strings(_infer_outfit(item) for item in evidence)
    actions = _most_common_strings(item.get("action") for item in evidence if item.get("action"))
    emotions = _most_common_strings(item.get("emotion") for item in evidence if item.get("emotion"))
    display_name = aliases[0] if aliases else _display_name_for_id(character_id)
    source_windows = sorted({window for item in evidence for window in item.get("source_windows", []) or []})
    evidence_shots = sorted({str(item.get("shot_id")) for item in evidence if item.get("shot_id")})
    return {
        "character_id": character_id,
        "display_name": display_name,
        "aliases": aliases,
        "evidence_shots": evidence_shots,
        "source_windows": source_windows,
        "visual_traits": {
            "hair_color": hair_colors[0] if hair_colors else "",
            "hair_style": hair_styles[0] if hair_styles else "",
            "eye_color": eye_colors[0] if eye_colors else "",
            "outfit": outfits[0] if outfits else "",
            "height": heights[0] if heights else "",
            "descriptions": descriptions[:4],
        },
        "performance_traits": {
            "common_actions": actions[:4],
            "common_emotions": emotions[:4],
        },
        "continuity_prompt": _continuity_prompt(character_id, display_name, hair_colors, hair_styles, eye_colors, outfits, heights),
        "negative_prompt": "identity drift, inconsistent hairstyle, inconsistent eye color, wrong school uniform, changed age, changed body proportions",
        "confidence": _confidence_for_entry(evidence, hair_colors, hair_styles, eye_colors),
    }


def _continuity_guidelines(characters: list[dict[str, Any]]) -> list[str]:
    guidelines = [
        "生成镜头时优先引用 main_character_ids，而不是重新相信单条 shot 的自然语言角色名。",
        "同一角色跨镜头必须保持发色、发型、眼睛颜色、校服款式和身高差稳定。",
        "角色参考图未人工确认前，character_bible 只能作为提示词锚点，不能替代最终角色设定图。",
    ]
    for character in characters:
        guidelines.append(f"{character['character_id']}: {character['continuity_prompt']}")
    return guidelines


def _open_issues(characters: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    if not characters:
        issues.append("未从 shot manifest 中提取到角色，需要检查 director 输出或手工标注角色。")
    for character in characters:
        traits = character["visual_traits"]
        missing = [key for key in ("hair_color", "hair_style", "outfit") if not traits.get(key)]
        if missing:
            issues.append(f"{character['character_id']} 缺少稳定外观字段：{', '.join(missing)}。")
        if character["confidence"] < 0.7:
            issues.append(f"{character['character_id']} 证据较少或外观冲突，建议人工确认。")
    return issues


def _continuity_prompt(
    character_id: str,
    display_name: str,
    hair_colors: list[str],
    hair_styles: list[str],
    eye_colors: list[str],
    outfits: list[str],
    heights: list[str],
) -> str:
    parts = [display_name or character_id]
    if hair_colors:
        parts.append(f"{hair_colors[0]} hair")
    if hair_styles:
        parts.append(hair_styles[0])
    if eye_colors:
        parts.append(f"{eye_colors[0]} eyes")
    if outfits:
        parts.append(outfits[0])
    if heights:
        parts.append(f"height {heights[0]}")
    return ", ".join(parts)


def _confidence_for_entry(
    evidence: list[dict[str, Any]],
    hair_colors: list[str],
    hair_styles: list[str],
    eye_colors: list[str],
) -> float:
    score = 0.45
    score += min(0.25, len(evidence) * 0.08)
    score += 0.1 if hair_colors else 0
    score += 0.1 if hair_styles else 0
    score += 0.1 if eye_colors else 0
    return round(min(score, 0.95), 2)


def _candidate_text(candidate: dict[str, Any]) -> str:
    return " ".join(str(value) for key, value in candidate.items() if key != "role_scope").lower()


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle.lower() in text for needle in needles)


def _infer_hair_color(candidate: dict[str, Any]) -> str:
    raw = str(candidate.get("hair_color") or "")
    text = _candidate_text(candidate)
    if raw:
        return raw
    if _has_any(text, ["黑发", "深紫", "dark purple", "purple hair"]):
        return "dark_purple"
    if _has_any(text, ["银", "白", "silver", "white"]):
        return "silver_white"
    if _has_any(text, ["黑", "dark"]):
        return "dark_purple"
    return ""


def _infer_hair_style(candidate: dict[str, Any]) -> str:
    raw = str(candidate.get("hair_style") or "")
    text = _candidate_text(candidate)
    if raw:
        return raw
    if _has_any(text, ["高马尾", "马尾", "ponytail"]):
        return "high_ponytail"
    if _has_any(text, ["长发", "long hair", "long"]):
        return "long_hair"
    return ""


def _infer_eye_color(candidate: dict[str, Any]) -> str:
    raw = str(candidate.get("eye_color") or "")
    text = _candidate_text(candidate)
    if raw:
        return raw
    if _has_any(text, ["紫瞳", "紫色眼", "purple"]):
        return "purple"
    if _has_any(text, ["金色", "黄色", "gold", "yellow"]):
        return "gold"
    if _has_any(text, ["绿色", "green"]):
        return "green"
    return ""


def _infer_outfit(candidate: dict[str, Any]) -> str:
    raw = str(candidate.get("attire") or candidate.get("outfit") or "")
    text = _candidate_text(candidate)
    if raw:
        return raw
    if _has_any(text, ["校服", "school uniform", "uniform"]):
        return "school_uniform"
    return ""


def _most_common_strings(values: Any) -> list[str]:
    cleaned = [str(value).strip() for value in values if str(value or "").strip()]
    counts = Counter(cleaned)
    return [value for value, _count in counts.most_common()]


def _display_name_for_id(character_id: str) -> str:
    if character_id == "char_silver_longhair":
        return "银白长发角色"
    if character_id == "char_dark_ponytail":
        return "深紫高马尾角色"
    return character_id


def _short_fingerprint(text: str) -> str:
    words = re.findall(r"[\w\u4e00-\u9fff]+", text)
    return "_".join(words[:3]) or "unknown_character"


def _safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"
