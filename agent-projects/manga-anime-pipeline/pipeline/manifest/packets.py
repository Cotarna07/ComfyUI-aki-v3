from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.common.io import as_project_path, resolve_project_path, write_json
from pipeline.common.schemas import OCR_RESULT_SCHEMA, STRUCTURED_PACKET_SCHEMA
from pipeline.common.status import utc_now_iso
from pipeline.common.validation import validate_json_schema
from pipeline.manifest.integrity import validate_structured_packets


def build_structured_packets(
    window_manifest: dict[str, Any],
    project_root: Path,
    runtime_root: Path,
    ocr_provider: Any,
    dialogue_provider: Any,
    detection_provider: Any,
) -> tuple[list[dict[str, Any]], list[Path], Path]:
    series_id = window_manifest["series_id"]
    chapter_id = window_manifest["chapter_id"]
    output_dir = runtime_root / "structured" / _safe_path_part(series_id) / _safe_path_part(chapter_id) / "packets"
    packet_paths: list[Path] = []
    packets: list[dict[str, Any]] = []

    for window in window_manifest["windows"]:
        window_packet = {
            **window,
            "project_root": str(project_root),
            "resolved_image_path": str(resolve_project_path(project_root, window["image_path"])),
        }
        ocr_result = ocr_provider.analyze(window_packet)
        validate_json_schema(ocr_result, OCR_RESULT_SCHEMA, "ocr_result")
        _validate_reading_order(ocr_result)
        dialogue_result = dialogue_provider.analyze(window_packet, ocr_result)
        detection_window = {**window_packet, "ocr_result": ocr_result, "dialogue_result": dialogue_result}
        detection_result = detection_provider.analyze(detection_window)
        packet = {
            "packet_version": "stage1.mock.v1",
            "series_id": series_id,
            "chapter_id": chapter_id,
            "window_id": window["window_id"],
            "page_id": window["page_id"],
            "source_page": window["source_page"],
            "window_image_path": window["image_path"],
            "source_box": window["source_box"],
            "created_at": utc_now_iso(),
            **ocr_result,
            **dialogue_result,
            **detection_result,
        }
        validate_json_schema(packet, STRUCTURED_PACKET_SCHEMA, "structured_packet")
        packet_path = output_dir / f"{window['window_id']}.json"
        write_json(packet_path, packet)
        packets.append(packet)
        packet_paths.append(packet_path)

    validate_structured_packets(window_manifest, packets)
    index_path = runtime_root / "structured" / _safe_path_part(series_id) / _safe_path_part(chapter_id) / "structured_packets.json"
    packet_refs = [as_project_path(project_root, path) for path in packet_paths]
    write_json(
        index_path,
        {
            "series_id": series_id,
            "chapter_id": chapter_id,
            "generated_at": utc_now_iso(),
            "packet_refs": packet_refs,
            "packets": [
                {"window_id": packet["window_id"], "packet_path": packet_ref}
                for packet, packet_ref in zip(packets, packet_refs)
            ],
        },
    )
    return packets, packet_paths, index_path


def _safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"


def _validate_reading_order(ocr_result: dict[str, Any]) -> None:
    block_ids = {block["block_id"] for block in ocr_result["ocr_blocks"]}
    missing = [block_id for block_id in ocr_result["reading_order"] if block_id not in block_ids]
    if missing:
        raise ValueError(f"OCR reading_order references unknown block_id values: {missing}")

