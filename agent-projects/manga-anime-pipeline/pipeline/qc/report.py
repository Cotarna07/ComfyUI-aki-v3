from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.common.io import write_json


def write_acceptance_reports(project_root: Path, runtime_root: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    output_dir = runtime_root / "qc" / _safe_path_part(report["series_id"]) / _safe_path_part(report["chapter_id"])
    json_path = output_dir / "acceptance_report.json"
    md_path = output_dir / "acceptance_report.md"
    write_json(json_path, report)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_acceptance_markdown(report), encoding="utf-8", newline="\n")
    return json_path, md_path


def render_acceptance_markdown(report: dict[str, Any]) -> str:
    providers = report["provider_summary"]
    artifacts = report["artifact_summary"]
    counts = report["count_summary"]
    ocr = report["ocr_quality"]
    dialogue = report["dialogue_quality"]
    errors = report.get("errors", [])
    warnings = report.get("warnings", [])
    next_step = (
        "建议进入 Stage 4：Detection Provider。"
        if report.get("next_stage_allowed")
        else "请先修复失败项，再进入下一阶段。"
    )
    return "\n".join(
        [
            "# Stage Acceptance Report",
            "",
            "## 结论",
            f"- pipeline_status: {report['pipeline_status']}",
            f"- next_stage_allowed: {str(report['next_stage_allowed']).lower()}",
            f"- 当前建议：{next_step}",
            "",
            "## Provider 状态",
            f"- OCR: {providers.get('ocr')}",
            f"- Dialogue: {providers.get('dialogue')}",
            f"- Detection: {providers.get('detection')}",
            f"- Director: {providers.get('director')}",
            "",
            "## 产物检查",
            f"- window_manifest: {artifacts['window_manifest_exists']}",
            f"- structured_packets: {artifacts['structured_packets_exists']}",
            f"- shot_manifest: {artifacts['shot_manifest_exists']}",
            f"- status_report: {artifacts['status_report_exists']}",
            "",
            "## 数量统计",
            f"- windows: {counts['window_count']}",
            f"- structured packets: {counts['structured_packet_count']}",
            f"- shots: {counts['shot_count']}",
            f"- OCR blocks: {counts['ocr_block_count']}",
            f"- dialogue blocks: {counts['dialogue_block_count']}",
            f"- cleaned text candidates: {counts['cleaned_text_candidate_count']}",
            f"- empty OCR windows: {len(ocr['empty_ocr_windows'])}",
            f"- empty dialogue windows: {len(dialogue['empty_dialogue_windows'])}",
            "",
            "## OCR 质量",
            f"- provider: {ocr['provider']}",
            f"- is_mock_ocr: {ocr['is_mock_ocr']}",
            f"- average_confidence: {ocr['average_confidence']}",
            f"- sample_texts: {', '.join(ocr['sample_texts']) if ocr['sample_texts'] else '[]'}",
            "",
            "## Dialogue 质量",
            f"- provider: {dialogue['provider']}",
            f"- is_mock_dialogue: {dialogue['is_mock_dialogue']}",
            f"- dialogue_block_count: {dialogue['dialogue_block_count']}",
            f"- sample_dialogues: {', '.join(dialogue['sample_dialogues']) if dialogue['sample_dialogues'] else '[]'}",
            "",
            "## 失败项",
            *_items_or_empty(errors),
            "",
            "## 警告项",
            *_items_or_empty(warnings),
            "",
            "## 下一步建议",
            next_step,
            "",
        ]
    )


def _items_or_empty(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- 无"]


def _safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"
