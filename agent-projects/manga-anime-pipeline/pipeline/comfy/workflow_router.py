"""Workflow template router for ComfyUI submissions."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class TemplateMissing(RuntimeError):
    """Raised when a referenced workflow template file does not exist."""


class WorkflowRouter:
    def __init__(self, templates: dict[str, str | None], project_root: Path) -> None:
        self._templates = templates
        self._project_root = project_root

    def resolve(self, workflow_route: str) -> Path | None:
        if workflow_route not in self._templates:
            raise TemplateMissing(
                f"workflow_route {workflow_route!r} has no template entry in comfy config workflow_templates"
            )
        raw = self._templates[workflow_route]
        if raw is None or raw == "":
            return None
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self._project_root / candidate
        if not candidate.exists():
            raise TemplateMissing(
                f"workflow template file not found: {candidate} (route={workflow_route})"
            )
        return candidate

    def all_routes(self) -> list[str]:
        return list(self._templates.keys())

    def validate_all(self) -> dict[str, Any]:
        findings: dict[str, Any] = {"missing": [], "valid": [], "skipped": []}
        for route, raw in self._templates.items():
            if raw is None or raw == "":
                findings["skipped"].append(route)
                continue
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = self._project_root / candidate
            if candidate.exists():
                findings["valid"].append(route)
            else:
                findings["missing"].append({"route": route, "path": str(candidate)})
        return findings
