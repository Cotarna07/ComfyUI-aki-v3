from __future__ import annotations

from typing import Any


def build_context_summary(packets: list[dict[str, Any]], index: int) -> dict[str, Any]:
    previous_packet = packets[index - 1] if index > 0 else None
    next_packet = packets[index + 1] if index < len(packets) - 1 else None
    return {
        "shot_index": index,
        "previous_window_id": previous_packet["window_id"] if previous_packet else None,
        "next_window_id": next_packet["window_id"] if next_packet else None,
        "previous_dialogue_summary": dialogue_summary(previous_packet) if previous_packet else "",
        "next_dialogue_summary": dialogue_summary(next_packet) if next_packet else "",
        "chapter_position": index / max(len(packets) - 1, 1),
    }


def dialogue_summary(packet: dict[str, Any] | None) -> str:
    if not packet:
        return ""
    candidates = packet.get("cleaned_text_candidates", [])
    if candidates:
        candidate = candidates[0]
        if isinstance(candidate, dict):
            return str(candidate.get("text", ""))[:240]
        return str(candidate)[:240]
    return f"Window {packet['window_id']} has no detected dialogue."
