"""Workflow template router for ComfyUI submissions."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class TemplateMissing(RuntimeError):
    """Raised when a referenced workflow template file does not exist."""


class WorkflowRouter:
    def __init__(
        self,
        templates: dict[str, str | None],
        project_root: Path,
        mappings: dict[str, str | None] | None = None,
    ) -> None:
        self._templates = templates
        self._project_root = project_root
        self._mappings = mappings or {}

    @property
    def project_root(self) -> Path:
        return self._project_root

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

    def resolve_mapping(self, workflow_route: str, template_path: Path) -> Path | None:
        raw = self._mappings.get(workflow_route)
        if raw:
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = self._project_root / candidate
            if not candidate.exists():
                raise TemplateMissing(
                    f"workflow mapping file not found: {candidate} (route={workflow_route})"
                )
            return candidate
        sibling = template_path.with_name(f"{template_path.stem}.mapping.json")
        return sibling if sibling.exists() else None

    def validate_all(self) -> dict[str, Any]:
        findings: dict[str, Any] = {"missing": [], "valid": [], "skipped": [], "mappings_valid": [], "mappings_missing": []}
        for route, raw in self._templates.items():
            if raw is None or raw == "":
                findings["skipped"].append(route)
                continue
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = self._project_root / candidate
            if candidate.exists():
                findings["valid"].append(route)
                mapping_raw = self._mappings.get(route)
                if mapping_raw:
                    mapping_path = Path(mapping_raw)
                    if not mapping_path.is_absolute():
                        mapping_path = self._project_root / mapping_path
                    if mapping_path.exists():
                        findings["mappings_valid"].append(route)
                    else:
                        findings["mappings_missing"].append({"route": route, "path": str(mapping_path)})
            else:
                findings["missing"].append({"route": route, "path": str(candidate)})
        return findings

    def validate_routes(self, workflow_routes: list[str]) -> dict[str, Any]:
        findings: dict[str, Any] = {"missing": [], "valid": [], "skipped": [], "mappings_valid": [], "mappings_missing": []}
        seen: set[str] = set()
        for route in workflow_routes:
            if route in seen:
                continue
            seen.add(route)
            if route not in self._templates:
                findings["missing"].append(
                    {
                        "route": route,
                        "path": "<no template entry in comfy config workflow_templates>",
                    }
                )
                continue
            raw = self._templates[route]
            if raw is None or raw == "":
                if route == "skip":
                    findings["skipped"].append(route)
                else:
                    findings["missing"].append(
                        {
                            "route": route,
                            "path": "<route disabled in comfy config workflow_templates>",
                        }
                    )
                continue
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = self._project_root / candidate
            if not candidate.exists():
                findings["missing"].append({"route": route, "path": str(candidate)})
                continue
            findings["valid"].append(route)
            mapping_raw = self._mappings.get(route)
            if not mapping_raw:
                continue
            mapping_path = Path(mapping_raw)
            if not mapping_path.is_absolute():
                mapping_path = self._project_root / mapping_path
            if mapping_path.exists():
                findings["mappings_valid"].append(route)
            else:
                findings["mappings_missing"].append({"route": route, "path": str(mapping_path)})
        return findings
