from __future__ import annotations

from typing import Any

from pipeline.detection.base import DetectionProvider
from pipeline.detection.grounded_sam2_provider import GroundedSAM2DetectionProvider
from pipeline.detection.lightweight_provider import LightweightDetectionProvider
from pipeline.detection.mock import MockDetectionProvider


def create_detection_provider(name: str | None = None, config: dict[str, Any] | None = None) -> DetectionProvider:
    provider_name = _normalize_name(name)
    if provider_name == "mock":
        return MockDetectionProvider()
    if provider_name == "lightweight":
        return LightweightDetectionProvider(config=config)
    if provider_name == "grounded_sam2":
        return GroundedSAM2DetectionProvider(config=config)
    raise ValueError(
        f"Unknown detection provider: {name!r}. Available providers: mock, lightweight, grounded_sam2"
    )


def _normalize_name(name: str | None) -> str:
    value = (name or "mock").strip().lower()
    aliases = {
        "mock_detection": "mock",
        "light": "lightweight",
        "rule_based": "lightweight",
        "rule-based": "lightweight",
        "grounded-sam-2": "grounded_sam2",
        "grounded_sam_2": "grounded_sam2",
        "groundedsam2": "grounded_sam2",
    }
    return aliases.get(value, value)
