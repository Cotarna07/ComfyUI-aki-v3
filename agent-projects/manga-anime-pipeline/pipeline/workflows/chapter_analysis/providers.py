from __future__ import annotations

from typing import Any

from pipeline.detection.provider_factory import create_detection_provider
from pipeline.dialogue.provider_factory import create_dialogue_provider
from pipeline.director.provider_factory import create_director_provider
from pipeline.ocr.provider_factory import create_ocr_provider


def create_analysis_providers(config: dict[str, Any]) -> dict[str, Any]:
    provider_config = config.get("providers", {})
    providers = {
        "ocr": create_ocr_provider(provider_config.get("ocr", "mock"), config),
        "dialogue": create_dialogue_provider(provider_config.get("dialogue", "mock"), config),
        "detection": create_detection_provider(provider_config.get("detection", "mock"), config),
        "director": create_director_provider(provider_config.get("director", "mock"), config),
    }
    for provider in providers.values():
        check_runtime = getattr(provider, "check_runtime", None)
        if callable(check_runtime):
            check_runtime()
    return providers


def provider_report(providers: dict[str, Any]) -> dict[str, str]:
    return {name: provider.provider_name for name, provider in providers.items()}

