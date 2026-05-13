from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DirectorProvider(ABC):
    provider_name: str
    model_name: str

    @abstractmethod
    def create_shots(self, structured_packet: dict[str, Any], context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError
