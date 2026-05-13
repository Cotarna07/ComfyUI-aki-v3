from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class OCRProvider(ABC):
    provider_name: str

    def check_runtime(self) -> None:
        return None

    @abstractmethod
    def analyze(self, window_packet: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
