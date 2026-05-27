from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DialogueProvider(ABC):
    provider_name: str

    @abstractmethod
    def analyze(self, window_packet: dict[str, Any], ocr_result: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError
