from __future__ import annotations

from dataclasses import dataclass
import json
import re

from .config import QualityConfig


@dataclass(frozen=True)
class PromptPair:
    positive_prompt: str
    negative_prompt: str
    notes: str
    parse_ok: bool


@dataclass(frozen=True)
class QualityScore:
    score: int
    reasons: list[str]


def extract_prompt_pair(text: str) -> PromptPair:
    cleaned = text.strip()
    parsed = _parse_json_object(cleaned)
    if isinstance(parsed, dict):
        return PromptPair(
            positive_prompt=str(parsed.get("positive_prompt", "")).strip(),
            negative_prompt=str(parsed.get("negative_prompt", "")).strip(),
            notes=str(parsed.get("notes", "")).strip(),
            parse_ok=True,
        )

    positive = _extract_labeled(cleaned, "positive_prompt") or _extract_labeled(cleaned, "positive")
    negative = _extract_labeled(cleaned, "negative_prompt") or _extract_labeled(cleaned, "negative")
    return PromptPair(
        positive_prompt=positive.strip(),
        negative_prompt=negative.strip(),
        notes="fallback parser",
        parse_ok=False,
    )


def score_prompt_pair(pair: PromptPair, config: QualityConfig) -> QualityScore:
    score = 0
    reasons: list[str] = []
    positive_lower = pair.positive_prompt.lower()
    negative_lower = pair.negative_prompt.lower()

    if pair.parse_ok and pair.positive_prompt and pair.negative_prompt:
        score += 20
    else:
        reasons.append("JSON 或字段解析不完整")

    if len(pair.positive_prompt) >= config.min_positive_chars:
        score += 15
    else:
        reasons.append("正面提示词偏短")

    if len(pair.negative_prompt) >= config.min_negative_chars:
        score += 10
    else:
        reasons.append("负面提示词偏短")

    positive_hits = sum(1 for term in config.required_positive_terms if term in positive_lower)
    if config.required_positive_terms:
        score += round(20 * positive_hits / len(config.required_positive_terms))
        if positive_hits < len(config.required_positive_terms):
            reasons.append("正面提示词缺少要求词")
    else:
        score += 20

    negative_hits = sum(1 for term in config.required_negative_terms if term in negative_lower)
    if config.required_negative_terms:
        score += round(15 * negative_hits / len(config.required_negative_terms))
        if negative_hits < len(config.required_negative_terms):
            reasons.append("负面提示词缺少要求词")
    else:
        score += 15

    if pair.positive_prompt.count(",") >= 6:
        score += 10
    else:
        reasons.append("正面提示词不像逗号分隔 tag")

    health = 10
    if config.penalize_non_english_prompt and _ascii_letter_ratio(pair.positive_prompt) < 0.65:
        health -= 5
        reasons.append("正面提示词英文比例偏低")
    if _has_repeated_chunks(pair.positive_prompt):
        health -= 5
        reasons.append("正面提示词重复度偏高")
    score += max(0, health)

    return QualityScore(score=min(100, score), reasons=reasons)


def _parse_json_object(text: str) -> object | None:
    # 算法与 comfyui-shared/json_utils.parse_json_object 对齐：
    # 优先代码围栏 → 首尾括号截取 → 原文兜底
    stripped = text.strip()
    candidates: list[str] = []
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.append(fenced.group(1))
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first >= 0 and last > first:
        candidates.append(stripped[first : last + 1])
    candidates.append(stripped)
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _extract_labeled(text: str, label: str) -> str:
    pattern = rf"{re.escape(label)}\s*[:：]\s*(.+?)(?:\n\w+[_\w]*\s*[:：]|\Z)"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _ascii_letter_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = sum(1 for char in text if char.isascii() and char.isalpha())
    non_space = sum(1 for char in text if not char.isspace())
    return letters / max(non_space, 1)


def _has_repeated_chunks(text: str) -> bool:
    chunks = [chunk.strip().lower() for chunk in text.split(",") if chunk.strip()]
    if len(chunks) < 4:
        return False
    return len(set(chunks)) / len(chunks) < 0.75
