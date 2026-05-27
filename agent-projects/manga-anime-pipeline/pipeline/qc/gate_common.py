"""Common helpers for stage gate scripts.

Each gate produces:
- a JSON report at runtime/qc/<series>/<chapter>/<gate>_report.json
- a Markdown report at runtime/qc/<series>/<chapter>/<gate>_report.md
- a stable shape with gate_name, gate_status, next_stage_allowed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from pipeline.common.io import read_json, write_json


def safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"


def gate_output_dir(runtime_root: Path, series_id: str, chapter_id: str) -> Path:
    return runtime_root / "qc" / safe_path_part(series_id) / safe_path_part(chapter_id)


def project_ref(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def write_gate_reports(
    project_root: Path,
    runtime_root: Path,
    gate_name: str,
    report: dict[str, Any],
    markdown: str,
) -> tuple[Path, Path]:
    series_id = report.get("series_id", "unknown_series")
    chapter_id = report.get("chapter_id", "unknown_chapter")
    output_dir = gate_output_dir(runtime_root, series_id, chapter_id)
    json_path = output_dir / f"{gate_name}_report.json"
    md_path = output_dir / f"{gate_name}_report.md"
    write_json(json_path, report)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown, encoding="utf-8", newline="\n")
    return json_path, md_path


def load_input_metadata(input_path: Path) -> tuple[str, str]:
    if not input_path.exists():
        return "unknown_series", "unknown_chapter"
    chapter = read_json(input_path)
    return str(chapter.get("series_id", "unknown_series")), str(chapter.get("chapter_id", "unknown_chapter"))


def render_simple_markdown(title: str, report: dict[str, Any], extra_sections: dict[str, Iterable[str]] | None = None) -> str:
    lines = [
        f"# {title}",
        "",
        "## 结论",
        f"- gate_name: {report.get('gate_name')}",
        f"- gate_status: {report.get('gate_status')}",
        f"- next_stage_allowed: {str(report.get('next_stage_allowed', False)).lower()}",
        f"- next_action: {report.get('next_action', '')}",
        "",
        "## 检查项",
    ]
    for key, value in (report.get("checks") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## 命令建议")
    for key, value in (report.get("commands") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## 失败项")
    errors = report.get("errors") or []
    lines.extend([f"- {item}" for item in errors] if errors else ["- 无"])
    lines.append("")
    lines.append("## 警告项")
    warnings = report.get("warnings") or []
    lines.extend([f"- {item}" for item in warnings] if warnings else ["- 无"])
    if extra_sections:
        for heading, items in extra_sections.items():
            lines.append("")
            lines.append(f"## {heading}")
            items_list = list(items)
            lines.extend([f"- {item}" for item in items_list] if items_list else ["- 无"])
    lines.append("")
    return "\n".join(lines)
