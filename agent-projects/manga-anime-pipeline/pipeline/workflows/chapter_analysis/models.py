from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StageResult:
    value: Any
    reused: bool = False


class OutputExistsError(RuntimeError):
    pass

