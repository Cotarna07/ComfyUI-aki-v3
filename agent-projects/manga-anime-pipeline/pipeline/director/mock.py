from __future__ import annotations

from typing import Any

from pipeline.common.schemas import WORKFLOW_ROUTES
from pipeline.director.base import DirectorProvider
from pipeline.director.context import dialogue_summary


class MockDirector(DirectorProvider):
    """Qwen3-VL stand-in that creates deterministic, schema-valid shot drafts."""

    provider_name = "mock_director"

    model_name = "mock-qwen3-vl-compatible"

    def create_shots(self, structured_packet: dict[str, Any], context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        context_summary = context or {}
        shot_index = int(context_summary.get("shot_index", 0))
        return [self.draft_shot(structured_packet, context_summary, shot_index)]

    def draft_shot(self, packet: dict[str, Any], context_summary: dict[str, Any], shot_index: int) -> dict[str, Any]:
        route, shot_type, story_role, action_level = _route_for_packet(packet, shot_index)
        crop = _first_crop(packet)
        text = dialogue_summary(packet)
        focus_subjects = packet.get("focus_subjects", [])
        main_characters = [subject.get("label", "unknown_character") for subject in focus_subjects[:1]] or ["unknown_character"]
        confidence = 0.62 if route == "skip" else 0.76
        anime_fit_score = 0.35 if route == "skip" else 0.74
        return {
            "shot_id": f"{_safe_id(packet['chapter_id'])}_s{shot_index:04d}",
            "source_pages": [packet["page_id"]],
            "source_windows": [packet["window_id"]],
            "source_ranges": [{"page_id": packet["page_id"], "box": packet["source_box"]}],
            "merge_with_prev": False,
            "merge_with_next": False,
            "story_role": story_role,
            "shot_type": shot_type,
            "anime_fit_score": anime_fit_score,
            "main_characters": main_characters,
            "support_characters": [],
            "emotion": "neutral_tension",
            "action_level": action_level,
            "dialogue_summary": text,
            "continuity_notes": [
                f"保持来源窗口 {packet['window_id']} 的角色服装和画风一致",
                _context_note(context_summary),
            ],
            "crop_recommendation": crop,
            "positive_prompt": _positive_prompt(route, shot_type, text),
            "negative_prompt": "extra fingers, inconsistent costume, warped face, deformed anatomy, unreadable text",
            "style_anchor": "stage1_mock_series_style",
            "workflow_route": route,
            "confidence": confidence,
        }


def _route_for_packet(packet: dict[str, Any], shot_index: int) -> tuple[str, str, str, str]:
    if _scene_density_value(packet) < 0.15:
        return "skip", "skip", "low_visual_information", "low"
    if shot_index == 0:
        return "establish_scene", "establishing", "scene_setup", "low"
    if shot_index % 5 == 0:
        return "transition_atmosphere", "transition", "atmosphere_transition", "low"
    if shot_index % 4 == 0:
        return "dialogue_heavy_expression", "dialogue_closeup", "dialogue_emotion_peak", "medium"
    if shot_index % 3 == 0:
        return "action_performance", "action", "character_action", "high"
    return "dialogue_light_motion", "dialogue", "dialogue_progression", "low"


def _first_crop(packet: dict[str, Any]) -> dict[str, Any]:
    candidates = packet.get("crop_candidates", [])
    if candidates:
        candidate = candidates[0]
        return {"type": candidate.get("type", "medium_shot"), "box": candidate.get("box", packet["source_box"])}
    return {"type": "full_window", "box": packet["source_box"]}


def _context_note(context_summary: dict[str, Any]) -> str:
    previous_id = context_summary.get("previous_window_id") or "无"
    next_id = context_summary.get("next_window_id") or "无"
    return f"上下文窗口 previous={previous_id}, next={next_id}"


def _positive_prompt(route: str, shot_type: str, text: str) -> str:
    if route not in WORKFLOW_ROUTES:
        raise ValueError(f"Unsupported workflow_route: {route}")
    return (
        "anime cinematic shot, clean line art, consistent character design, "
        f"{shot_type}, {route}, subtle motion, dialogue context: {text}"
    )


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"


def _scene_density_value(packet: dict[str, Any]) -> float:
    value = packet.get("scene_density")
    if isinstance(value, dict):
        raw = value.get("value", 0)
    else:
        raw = value if value is not None else 0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0
