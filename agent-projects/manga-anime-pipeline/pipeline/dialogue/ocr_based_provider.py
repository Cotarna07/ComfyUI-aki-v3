from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from pipeline.dialogue.base import DialogueProvider


@dataclass(frozen=True)
class OCRBasedDialogueConfig:
    min_confidence: float = 0.3
    max_merge_distance: int = 48
    min_text_length: int = 1


class OCRBasedDialogueProvider(DialogueProvider):
    """Rule-based dialogue extraction from OCR blocks only."""

    provider_name = "ocr_based"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        settings = ((config or {}).get("dialogue", {}) or {}).get("ocr_based", {}) or {}
        self.config = OCRBasedDialogueConfig(
            min_confidence=float(settings.get("min_confidence", 0.3)),
            max_merge_distance=int(settings.get("max_merge_distance", 48)),
            min_text_length=int(settings.get("min_text_length", 1)),
        )

    def analyze(self, window_packet: dict[str, Any], ocr_result: dict[str, Any] | None = None) -> dict[str, Any]:
        ocr_result = ocr_result or {}
        ordered_blocks = _ordered_ocr_blocks(ocr_result)
        usable_blocks = [block for block in ordered_blocks if self._is_usable(block)]
        groups = _merge_nearby_blocks(usable_blocks, self.config.max_merge_distance)

        dialogue_blocks: list[dict[str, Any]] = []
        sfx_blocks: list[dict[str, Any]] = []
        cleaned_text_candidates: list[dict[str, Any]] = []

        for index, group in enumerate(groups):
            text = _clean_text(" ".join(str(block.get("text", "")) for block in group))
            if not text:
                continue
            box = _union_box([block["box"] for block in group])
            confidence = _average_confidence(group)
            dialogue_type = _classify_dialogue(text)
            dialogue_id = f"{window_packet['window_id']}_dlg_{index:04d}"
            source_ocr_blocks = [str(block["block_id"]) for block in group]
            dialogue = {
                "dialogue_id": dialogue_id,
                "text": text,
                "source_ocr_blocks": source_ocr_blocks,
                "box": box,
                "confidence": confidence,
                "dialogue_type": dialogue_type,
                "speaker": None,
                "provider": self.provider_name,
            }
            dialogue_blocks.append(dialogue)
            if dialogue_type == "sfx":
                sfx_blocks.append(
                    {
                        "sfx_id": f"{window_packet['window_id']}_sfx_{len(sfx_blocks):04d}",
                        "text": text,
                        "source_ocr_blocks": source_ocr_blocks,
                        "box": box,
                        "confidence": confidence,
                        "provider": self.provider_name,
                    }
                )
            cleaned_text_candidates.append(
                {
                    "candidate_id": f"{window_packet['window_id']}_txt_{len(cleaned_text_candidates):04d}",
                    "text": text,
                    "source_dialogue_id": dialogue_id,
                    "confidence": confidence,
                    "provider": self.provider_name,
                }
            )

        return {
            "dialogue_blocks": dialogue_blocks,
            "bubble_boxes": [],
            "sfx_blocks": sfx_blocks,
            "cleaned_text_candidates": cleaned_text_candidates,
            "provider": self.provider_name,
        }

    def _is_usable(self, block: dict[str, Any]) -> bool:
        text = _clean_text(str(block.get("text", "")))
        if len(text) < self.config.min_text_length:
            return False
        if _is_pure_symbol(text):
            return False
        if float(block.get("confidence", 0.0)) < self.config.min_confidence:
            return False
        return isinstance(block.get("box"), list) and len(block["box"]) == 4


def _ordered_ocr_blocks(ocr_result: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = [block for block in ocr_result.get("ocr_blocks", []) if isinstance(block, dict)]
    by_id = {block.get("block_id"): block for block in blocks}
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for block_id in ocr_result.get("reading_order", []):
        if block_id in by_id:
            ordered.append(by_id[block_id])
            seen.add(block_id)
    ordered.extend(block for block in blocks if block.get("block_id") not in seen)
    return ordered


def _merge_nearby_blocks(blocks: list[dict[str, Any]], max_distance: int) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for block in blocks:
        if not groups:
            groups.append([block])
            continue
        current_box = _union_box([item["box"] for item in groups[-1]])
        if _box_distance(current_box, block["box"]) <= max_distance:
            groups[-1].append(block)
        else:
            groups.append([block])
    return groups


def _box_distance(box_a: list[int], box_b: list[int]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    horizontal_gap = max(0, max(ax1, bx1) - min(ax2, bx2))
    vertical_gap = max(0, max(ay1, by1) - min(ay2, by2))
    return math.hypot(horizontal_gap, vertical_gap)


def _union_box(boxes: list[list[int]]) -> list[int]:
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def _average_confidence(blocks: list[dict[str, Any]]) -> float:
    if not blocks:
        return 0.0
    return float(sum(float(block.get("confidence", 0.0)) for block in blocks) / len(blocks))


def _classify_dialogue(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
    if _looks_like_sfx(compact):
        return "sfx"
    if len(compact) >= 40 or compact.startswith(("旁白", "此时", "那天", "后来")):
        return "narration"
    return "speech"


def _looks_like_sfx(text: str) -> bool:
    if re.search(r"(.)\1{2,}", text):
        return True
    if len(re.findall(r"[!！?？]", text)) >= 2:
        return True
    if len(text) <= 6 and re.search(r"[~～ー—-]", text):
        return True
    return False


def _is_pure_symbol(text: str) -> bool:
    return not re.search(r"[A-Za-z0-9\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
