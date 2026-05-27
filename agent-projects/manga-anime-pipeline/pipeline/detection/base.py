from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DetectionProvider(ABC):
    provider_name: str

    @abstractmethod
    def analyze(self, window_packet: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
