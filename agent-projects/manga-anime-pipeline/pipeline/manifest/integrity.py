from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from pipeline.common.io import resolve_project_path
from pipeline.common.schemas import SHOT_MANIFEST_SCHEMA, STRUCTURED_PACKET_SCHEMA, WINDOW_MANIFEST_SCHEMA
from pipeline.common.validation import validate_json_schema


class ManifestIntegrityError(ValueError):
    pass


def validate_window_manifest(
    chapter: dict[str, Any],
    window_manifest: dict[str, Any],
    project_root: Path | None = None,
    require_images: bool = True,
) -> None:
    validate_json_schema(window_manifest, WINDOW_MANIFEST_SCHEMA, "window_manifest")
    page_map = {page["page_id"]: page for page in chapter["pages"]}
    windows = window_manifest.get("windows", [])
    if not windows:
        raise ManifestIntegrityError("window_manifest must contain at least one window")

    windows_by_page: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_ids: set[str] = set()
    for window in windows:
        window_id = window["window_id"]
        if window_id in seen_ids:
            raise ManifestIntegrityError(f"duplicate window_id: {window_id}")
        seen_ids.add(window_id)
        source_page = window["source_page"]
        if source_page != window["page_id"]:
            raise ManifestIntegrityError(f"window {window_id} has mismatched page_id/source_page")
        if source_page not in page_map:
            raise ManifestIntegrityError(f"window {window_id} references unknown source_page: {source_page}")
        page = page_map[source_page]
        _validate_source_box(window_id, window["source_box"], page["width"], page["height"])
        left, top, right, bottom = window["source_box"]
        if window["width"] != right - left or window["height"] != bottom - top:
            raise ManifestIntegrityError(f"window {window_id} width/height does not match source_box")
        if require_images and project_root is not None:
            image_path = resolve_project_path(project_root, window["image_path"])
            if not image_path.exists():
                raise ManifestIntegrityError(f"window image does not exist for {window_id}: {image_path}")
        windows_by_page[source_page].append(window)

    for source_page, page_windows in windows_by_page.items():
        page_windows.sort(key=lambda item: (item["source_box"][1], item.get("index", 0)))
        _validate_page_overlap(source_page, page_windows)


def validate_structured_packets(window_manifest: dict[str, Any], packets: list[dict[str, Any]]) -> None:
    window_ids = {window["window_id"] for window in window_manifest["windows"]}
    packet_ids = {packet.get("window_id") for packet in packets}
    if window_ids != packet_ids:
        missing = sorted(window_ids - packet_ids)
        extra = sorted(packet_ids - window_ids)
        raise ManifestIntegrityError(f"structured packet/window mismatch; missing={missing}, extra={extra}")
    window_by_id = {window["window_id"]: window for window in window_manifest["windows"]}
    for packet in packets:
        validate_json_schema(packet, STRUCTURED_PACKET_SCHEMA, "structured_packet")
        window = window_by_id[packet["window_id"]]
        if packet["source_box"] != window["source_box"]:
            raise ManifestIntegrityError(f"structured packet {packet['window_id']} source_box mismatch")
        if packet["page_id"] != window["source_page"]:
            raise ManifestIntegrityError(f"structured packet {packet['window_id']} page_id mismatch")


def validate_shot_manifest_links(packets: list[dict[str, Any]], shot_manifest: dict[str, Any]) -> None:
    validate_json_schema(shot_manifest, SHOT_MANIFEST_SCHEMA, "shot_manifest")
    packet_by_window = {packet["window_id"]: packet for packet in packets}
    seen_shot_ids: set[str] = set()
    for shot in shot_manifest["shots"]:
        shot_id = shot["shot_id"]
        if shot_id in seen_shot_ids:
            raise ManifestIntegrityError(f"duplicate shot_id: {shot_id}")
        seen_shot_ids.add(shot_id)
        for window_id in shot["source_windows"]:
            if window_id not in packet_by_window:
                raise ManifestIntegrityError(f"shot {shot_id} references unknown source_window: {window_id}")
        source_pages = set(shot["source_pages"])
        for source_range in shot["source_ranges"]:
            if source_range["page_id"] not in source_pages:
                raise ManifestIntegrityError(f"shot {shot_id} source_range page_id is not listed in source_pages")


def _validate_source_box(window_id: str, box: list[int], page_width: int, page_height: int) -> None:
    left, top, right, bottom = box
    if left < 0 or top < 0 or right > page_width or bottom > page_height:
        raise ManifestIntegrityError(f"window {window_id} source_box is outside original image bounds")
    if left >= right or top >= bottom:
        raise ManifestIntegrityError(f"window {window_id} source_box must have positive area")


def _validate_page_overlap(source_page: str, windows: list[dict[str, Any]]) -> None:
    for index, window in enumerate(windows):
        previous_window = windows[index - 1] if index > 0 else None
        next_window = windows[index + 1] if index < len(windows) - 1 else None
        expected_prev = 0 if previous_window is None else max(0, previous_window["source_box"][3] - window["source_box"][1])
        expected_next = 0 if next_window is None else max(0, window["source_box"][3] - next_window["source_box"][1])
        if window["overlap_prev"] != expected_prev:
            raise ManifestIntegrityError(
                f"window {window['window_id']} overlap_prev={window['overlap_prev']} but expected {expected_prev} on {source_page}"
            )
        if window["overlap_next"] != expected_next:
            raise ManifestIntegrityError(
                f"window {window['window_id']} overlap_next={window['overlap_next']} but expected {expected_next} on {source_page}"
            )