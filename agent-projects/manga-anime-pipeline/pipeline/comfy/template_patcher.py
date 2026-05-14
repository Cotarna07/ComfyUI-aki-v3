"""Patch ComfyUI API workflow templates with shot-level values.

This module is intentionally model-agnostic. It knows how to take a shot
manifest record and write values into a ComfyUI API JSON graph, but it does
not know how to run Wan, LTX, VACE, or future models. Real templates opt in
through mapping JSON files; common ComfyUI nodes also get a small auto-mapper
so simple API exports work without hand-written mappings.
"""

from __future__ import annotations

import copy
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.common.io import read_json, resolve_project_path


class TemplatePatchError(RuntimeError):
    """Raised when a workflow template cannot be patched safely."""


@dataclass(frozen=True)
class PreparedInputImage:
    """A ComfyUI LoadImage-ready asset copied into the input directory."""

    image_value: str
    source_path: str
    crop_box: list[int]
    output_path: str


@dataclass(frozen=True)
class PreparedInputAsset:
    """A ComfyUI input-directory asset prepared from a shot field."""

    field_name: str
    asset_value: str
    source_path: str
    output_path: str
    media_type: str
    crop_box: list[int] | None = None


@dataclass(frozen=True)
class PatchResult:
    workflow: dict[str, Any]
    patched_fields: list[str]
    notes: list[str]
    seed: int
    output_prefix: str
    input_image: PreparedInputImage | None = None
    input_assets: dict[str, PreparedInputAsset] | None = None


ROUTE_POSITIVE_GUIDES = {
    "establish_scene": (
        "establishing anime scene, readable environment, slow cinematic camera move, "
        "stable composition, clear spatial layout"
    ),
    "dialogue_light_motion": (
        "light dialogue motion, subtle breathing, small eye and hair movement, "
        "stable face, stable hands, calm camera drift, keep character identity consistent"
    ),
    "dialogue_heavy_expression": (
        "intense expression close-up, controlled facial acting, strong emotion, "
        "stable character identity, restrained camera movement"
    ),
    "action_performance": (
        "anime action performance, readable body mechanics, clear motion direction, "
        "stable pose silhouette, consistent costume"
    ),
    "transition_atmosphere": (
        "atmospheric transition shot, gentle environmental motion, cinematic mood, "
        "clean anime background"
    ),
    "repair_only": (
        "localized repair pass, preserve original composition, fix only visible defects, "
        "keep identity and style unchanged"
    ),
}

ROUTE_NEGATIVE_GUIDES = {
    "dialogue_light_motion": (
        "large mouth movement, extreme expression, fast action, identity drift, "
        "face melting, hand distortion, subtitles, watermark, unreadable text"
    ),
    "dialogue_heavy_expression": (
        "identity drift, off-model face, warped mouth, broken eyes, deformed hands, "
        "subtitles, watermark, unreadable text"
    ),
    "action_performance": (
        "unclear motion direction, broken limbs, extra arms, extra legs, deformed hands, "
        "identity drift, motion smear over face, watermark"
    ),
}

DEFAULT_NEGATIVE_GUIDE = (
    "worst quality, low quality, blurry, bad anatomy, deformed face, deformed hands, "
    "extra fingers, missing fingers, inconsistent costume, identity drift, watermark, text, subtitles"
)


def patch_workflow_template(
    workflow_template: dict[str, Any],
    shot: dict[str, Any],
    shot_manifest: dict[str, Any],
    *,
    project_root: Path,
    mapping: dict[str, Any] | None = None,
    comfy_input_dir: Path | None = None,
    output_prefix_root: str = "manga_anime_pipeline",
    strict: bool = True,
) -> PatchResult:
    """Return a ComfyUI workflow patched for one shot.

    The mapping format supports either the README shape:

    {
      "positive_prompt": {"node_id": "93", "input": "text"}
    }

    or a versioned shape:

    {
      "version": 1,
      "fields": {
        "seed": [
          {"node_id": "86", "input": "noise_seed"},
          {"node_id": "85", "input": "noise_seed"}
        ]
      }
    }
    """

    workflow = copy.deepcopy(workflow_template)
    nodes = _node_map(workflow)
    mapping_fields = _mapping_fields(mapping)
    auto_fields = _auto_mapping_fields(nodes)
    fields = mapping_fields if mapping_fields else auto_fields
    if not fields:
        if strict:
            raise TemplatePatchError(
                f"no workflow fields were patched for shot {shot.get('shot_id')}: "
                "template has no mapping and no recognizable ComfyUI inputs"
            )
        return PatchResult(
            workflow=workflow,
            patched_fields=[],
            notes=["no mapping targets found; workflow left unchanged"],
            seed=_seed_for_shot(shot, shot_manifest),
            output_prefix=_output_prefix(shot, shot_manifest, output_prefix_root),
            input_image=None,
            input_assets={},
        )

    seed = _seed_for_shot(shot, shot_manifest)
    output_prefix = _output_prefix(shot, shot_manifest, output_prefix_root)
    input_assets = _prepare_mapped_assets(
        fields,
        shot,
        shot_manifest,
        project_root=project_root,
        comfy_input_dir=comfy_input_dir,
    )
    prepared_input = _asset_to_legacy_image(input_assets.get("input_image"))

    values: dict[str, Any] = {
        "positive_prompt": build_positive_prompt(shot),
        "negative_prompt": build_negative_prompt(shot),
        "seed": seed,
        "output_prefix": output_prefix,
        "shot_id": str(shot.get("shot_id", "")),
        "workflow_route": str(shot.get("workflow_route", "")),
    }
    for field_name, asset in input_assets.items():
        values[field_name] = asset.asset_value
    render_settings = shot.get("render_settings") if isinstance(shot.get("render_settings"), dict) else {}
    for key in ("width", "height", "length", "fps", "steps", "cfg"):
        if key in shot:
            values[key] = shot[key]
        elif key in render_settings:
            values[key] = render_settings[key]

    patched_fields: list[str] = []
    notes: list[str] = []
    for field_name, target_spec in fields.items():
        if field_name not in values or values[field_name] is None:
            continue
        targets = _normalize_targets(target_spec)
        for target in targets:
            node_id = target["node_id"]
            input_name = target["input"]
            _patch_node_input(nodes, node_id, input_name, values[field_name])
            patched_fields.append(f"{field_name}:{node_id}.{input_name}")
        notes.append(f"{field_name}={_note_value(values[field_name])}")

    if strict and not patched_fields:
        raise TemplatePatchError(
            f"no workflow fields were patched for shot {shot.get('shot_id')}: "
            "all mapped fields had missing values or unsupported inputs"
        )

    return PatchResult(
        workflow=workflow,
        patched_fields=patched_fields,
        notes=notes,
        seed=seed,
        output_prefix=output_prefix,
        input_image=prepared_input,
        input_assets=input_assets,
    )


def build_positive_prompt(shot: dict[str, Any]) -> str:
    route = str(shot.get("workflow_route") or "dialogue_light_motion")
    parts = [
        str(shot.get("positive_prompt") or "").strip(),
        ROUTE_POSITIVE_GUIDES.get(route, ""),
        f"style anchor: {shot.get('style_anchor')}" if shot.get("style_anchor") else "",
        f"emotion: {shot.get('emotion')}" if shot.get("emotion") else "",
        f"dialogue context: {shot.get('dialogue_summary')}" if shot.get("dialogue_summary") else "",
        _characters_clause(shot),
    ]
    return _join_prompt_parts(parts)


def build_negative_prompt(shot: dict[str, Any]) -> str:
    route = str(shot.get("workflow_route") or "dialogue_light_motion")
    parts = [
        str(shot.get("negative_prompt") or "").strip(),
        ROUTE_NEGATIVE_GUIDES.get(route, DEFAULT_NEGATIVE_GUIDE),
    ]
    return _join_prompt_parts(parts)


def prepare_shot_input_image(
    shot: dict[str, Any],
    shot_manifest: dict[str, Any],
    *,
    project_root: Path,
    comfy_input_dir: Path | None,
) -> PreparedInputImage | None:
    """Copy/crop the source window into ComfyUI input and return LoadImage value."""

    packet = _find_source_packet(shot, shot_manifest, project_root)
    source_path = _select_source_image_path(shot, packet, project_root)
    if source_path is None or not source_path.exists():
        return None
    if comfy_input_dir is None:
        comfy_input_dir = infer_comfy_input_dir(project_root)
    if comfy_input_dir is None:
        return None

    try:
        from PIL import Image
    except Exception as error:
        raise TemplatePatchError("Pillow is required to prepare ComfyUI input crops") from error

    try:
        with Image.open(source_path) as image:
            image = image.convert("RGB")
            crop_box = _resolve_crop_box(shot, packet, image.width, image.height)
            cropped = image.crop(tuple(crop_box))
            series_id = _safe_path_part(str(shot_manifest.get("series_id", "series")))
            chapter_id = _safe_path_part(str(shot_manifest.get("chapter_id", "chapter")))
            shot_id = _safe_path_part(str(shot.get("shot_id", "shot")))
            relative_path = Path("manga_anime_pipeline") / series_id / chapter_id / f"{shot_id}_crop.png"
            output_path = comfy_input_dir / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cropped.save(output_path)
    except Exception as error:
        raise TemplatePatchError(f"failed to prepare input image for shot {shot.get('shot_id')}: {error}") from error

    return PreparedInputImage(
        image_value=relative_path.as_posix(),
        source_path=str(source_path),
        crop_box=crop_box,
        output_path=str(output_path),
    )


def prepare_source_window_image(
    shot: dict[str, Any],
    shot_manifest: dict[str, Any],
    source_index: int,
    *,
    project_root: Path,
    comfy_input_dir: Path | None,
    field_name: str,
) -> PreparedInputAsset | None:
    packets = _find_source_packets(shot, shot_manifest, project_root)
    if source_index < 0 or source_index >= len(packets):
        return None
    packet = packets[source_index]
    source_path = _select_source_image_path({}, packet, project_root)
    if source_path is None or not source_path.exists():
        return None
    return _prepare_image_asset(
        source_path,
        shot,
        shot_manifest,
        project_root=project_root,
        comfy_input_dir=comfy_input_dir,
        field_name=field_name,
        crop_box=None,
    )


def prepare_path_asset(
    field_name: str,
    shot: dict[str, Any],
    shot_manifest: dict[str, Any],
    *,
    project_root: Path,
    comfy_input_dir: Path | None,
) -> PreparedInputAsset | None:
    source_path = _resolve_asset_path(field_name, shot, project_root)
    if source_path is None or not source_path.exists():
        return None
    media_type = _media_type_for_path(source_path)
    if media_type == "image":
        return _prepare_image_asset(
            source_path,
            shot,
            shot_manifest,
            project_root=project_root,
            comfy_input_dir=comfy_input_dir,
            field_name=field_name,
            crop_box=None,
        )
    return _copy_file_asset(
        source_path,
        shot,
        shot_manifest,
        project_root=project_root,
        comfy_input_dir=comfy_input_dir,
        field_name=field_name,
        media_type=media_type,
    )


def _prepare_mapped_assets(
    fields: dict[str, Any],
    shot: dict[str, Any],
    shot_manifest: dict[str, Any],
    *,
    project_root: Path,
    comfy_input_dir: Path | None,
) -> dict[str, PreparedInputAsset]:
    assets: dict[str, PreparedInputAsset] = {}
    for field_name in fields:
        if field_name == "input_image":
            legacy = prepare_shot_input_image(
                shot,
                shot_manifest,
                project_root=project_root,
                comfy_input_dir=comfy_input_dir,
            )
            if legacy is None:
                raise TemplatePatchError(
                    f"workflow mapping for shot {shot.get('shot_id')} requires input_image, "
                    "but no source image could be prepared"
                )
            assets[field_name] = PreparedInputAsset(
                field_name=field_name,
                asset_value=legacy.image_value,
                source_path=legacy.source_path,
                output_path=legacy.output_path,
                media_type="image",
                crop_box=legacy.crop_box,
            )
            continue
        source_index = _source_image_index(field_name)
        if source_index is not None:
            asset = prepare_source_window_image(
                shot,
                shot_manifest,
                source_index,
                project_root=project_root,
                comfy_input_dir=comfy_input_dir,
                field_name=field_name,
            )
            if asset is None:
                raise TemplatePatchError(
                    f"workflow mapping for shot {shot.get('shot_id')} requires {field_name}, "
                    "but that source window image could not be prepared"
                )
            assets[field_name] = asset
            continue
        if _is_path_asset_field(field_name):
            asset = prepare_path_asset(
                field_name,
                shot,
                shot_manifest,
                project_root=project_root,
                comfy_input_dir=comfy_input_dir,
            )
            if asset is None:
                raise TemplatePatchError(
                    f"workflow mapping for shot {shot.get('shot_id')} requires {field_name}, "
                    "but no matching path field was found"
                )
            assets[field_name] = asset
    return assets


def _asset_to_legacy_image(asset: PreparedInputAsset | None) -> PreparedInputImage | None:
    if asset is None:
        return None
    return PreparedInputImage(
        image_value=asset.asset_value,
        source_path=asset.source_path,
        crop_box=asset.crop_box or [0, 0, 0, 0],
        output_path=asset.output_path,
    )


def _prepare_image_asset(
    source_path: Path,
    shot: dict[str, Any],
    shot_manifest: dict[str, Any],
    *,
    project_root: Path,
    comfy_input_dir: Path | None,
    field_name: str,
    crop_box: list[int] | None,
) -> PreparedInputAsset | None:
    if comfy_input_dir is None:
        comfy_input_dir = infer_comfy_input_dir(project_root)
    if comfy_input_dir is None:
        return None
    try:
        from PIL import Image
    except Exception as error:
        raise TemplatePatchError("Pillow is required to prepare ComfyUI input images") from error
    try:
        with Image.open(source_path) as image:
            image = image.convert("RGB")
            box = crop_box or [0, 0, image.width, image.height]
            box = _clamp_box(box, image.width, image.height)
            prepared = image.crop(tuple(box))
            relative_path = _asset_relative_path(shot, shot_manifest, field_name, ".png")
            output_path = comfy_input_dir / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            prepared.save(output_path)
    except Exception as error:
        raise TemplatePatchError(f"failed to prepare {field_name} for shot {shot.get('shot_id')}: {error}") from error
    return PreparedInputAsset(
        field_name=field_name,
        asset_value=relative_path.as_posix(),
        source_path=str(source_path),
        output_path=str(output_path),
        media_type="image",
        crop_box=box,
    )


def _copy_file_asset(
    source_path: Path,
    shot: dict[str, Any],
    shot_manifest: dict[str, Any],
    *,
    project_root: Path,
    comfy_input_dir: Path | None,
    field_name: str,
    media_type: str,
) -> PreparedInputAsset | None:
    if comfy_input_dir is None:
        comfy_input_dir = infer_comfy_input_dir(project_root)
    if comfy_input_dir is None:
        return None
    suffix = source_path.suffix or _default_suffix_for_media(media_type)
    relative_path = _asset_relative_path(shot, shot_manifest, field_name, suffix)
    output_path = comfy_input_dir / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source_path, output_path)
    except Exception as error:
        raise TemplatePatchError(f"failed to copy {field_name} for shot {shot.get('shot_id')}: {error}") from error
    return PreparedInputAsset(
        field_name=field_name,
        asset_value=relative_path.as_posix(),
        source_path=str(source_path),
        output_path=str(output_path),
        media_type=media_type,
        crop_box=None,
    )


def _asset_relative_path(shot: dict[str, Any], shot_manifest: dict[str, Any], field_name: str, suffix: str) -> Path:
    series_id = _safe_path_part(str(shot_manifest.get("series_id", "series")))
    chapter_id = _safe_path_part(str(shot_manifest.get("chapter_id", "chapter")))
    shot_id = _safe_path_part(str(shot.get("shot_id", "shot")))
    safe_field = _safe_path_part(field_name)
    if not suffix.startswith("."):
        suffix = "." + suffix
    return Path("manga_anime_pipeline") / series_id / chapter_id / f"{shot_id}_{safe_field}{suffix}"


def infer_comfy_input_dir(project_root: Path) -> Path | None:
    """Infer this workspace's ComfyUI/input directory if present."""

    for candidate_root in [project_root, *project_root.parents]:
        candidate = candidate_root / "ComfyUI" / "input"
        if candidate.exists():
            return candidate
    return None


def load_mapping(mapping_path: Path | None) -> dict[str, Any] | None:
    if mapping_path is None:
        return None
    if not mapping_path.exists():
        return None
    return read_json(mapping_path)


def _node_map(workflow: dict[str, Any]) -> dict[str, Any]:
    if isinstance(workflow.get("nodes"), dict):
        return workflow["nodes"]
    return workflow


def _mapping_fields(mapping: dict[str, Any] | None) -> dict[str, Any]:
    if not mapping:
        return {}
    raw = mapping.get("fields") if isinstance(mapping.get("fields"), dict) else mapping
    ignored = {"version", "description", "notes", "route"}
    return {str(key): value for key, value in raw.items() if key not in ignored}


def _auto_mapping_fields(nodes: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, list[dict[str, str]]] = {}
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        class_type = str(node.get("class_type", "")).lower()
        title = str((node.get("_meta") or {}).get("title", "")).lower()
        if "cliptextencode" in class_type and "text" in inputs:
            if "positive" in title:
                fields.setdefault("positive_prompt", []).append({"node_id": str(node_id), "input": "text"})
            elif "negative" in title:
                fields.setdefault("negative_prompt", []).append({"node_id": str(node_id), "input": "text"})
        if "loadimage" in class_type and "image" in inputs:
            fields.setdefault("input_image", []).append({"node_id": str(node_id), "input": "image"})
        for input_name in ("seed", "noise_seed"):
            if input_name in inputs and ("sampler" in class_type or "seed" in input_name):
                fields.setdefault("seed", []).append({"node_id": str(node_id), "input": input_name})
        if "filename_prefix" in inputs:
            fields.setdefault("output_prefix", []).append({"node_id": str(node_id), "input": "filename_prefix"})
        for field_name in ("width", "height", "length", "fps", "steps", "cfg"):
            if field_name in inputs:
                fields.setdefault(field_name, []).append({"node_id": str(node_id), "input": field_name})
    return fields


def _normalize_targets(target_spec: Any) -> list[dict[str, str]]:
    specs = target_spec if isinstance(target_spec, list) else [target_spec]
    targets: list[dict[str, str]] = []
    for spec in specs:
        if not isinstance(spec, dict):
            raise TemplatePatchError(f"invalid mapping target: {spec!r}")
        node_id = spec.get("node_id") or spec.get("node")
        input_name = spec.get("input") or spec.get("input_name")
        if not node_id or not input_name:
            raise TemplatePatchError(f"mapping target requires node_id and input: {spec!r}")
        targets.append({"node_id": str(node_id), "input": str(input_name)})
    return targets


def _patch_node_input(nodes: dict[str, Any], node_id: str, input_name: str, value: Any) -> None:
    node = nodes.get(node_id)
    if not isinstance(node, dict):
        raise TemplatePatchError(f"mapping references missing node_id={node_id}")
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        raise TemplatePatchError(f"node_id={node_id} has no inputs dict")
    if input_name not in inputs:
        raise TemplatePatchError(f"node_id={node_id} has no input {input_name!r}")
    inputs[input_name] = value


def _seed_for_shot(shot: dict[str, Any], shot_manifest: dict[str, Any]) -> int:
    raw = shot.get("seed")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    identity = "|".join(
        [
            str(shot_manifest.get("series_id", "")),
            str(shot_manifest.get("chapter_id", "")),
            str(shot.get("shot_id", "")),
            str(shot.get("workflow_route", "")),
        ]
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % 2_147_483_647


def _output_prefix(shot: dict[str, Any], shot_manifest: dict[str, Any], root: str) -> str:
    return "/".join(
        [
            _safe_path_part(root),
            _safe_path_part(str(shot_manifest.get("series_id", "series"))),
            _safe_path_part(str(shot_manifest.get("chapter_id", "chapter"))),
            _safe_path_part(str(shot.get("workflow_route", "route"))),
            _safe_path_part(str(shot.get("shot_id", "shot"))),
        ]
    )


def _source_image_index(field_name: str) -> int | None:
    prefix = "source_image_"
    if not field_name.startswith(prefix):
        return None
    raw = field_name[len(prefix) :]
    if not raw.isdigit():
        return None
    return int(raw)


def _is_path_asset_field(field_name: str) -> bool:
    return field_name in {
        "reference_image",
        "character_reference_image",
        "style_reference_image",
        "pose_image",
        "control_image",
        "mask_image",
        "source_video",
        "repair_video",
        "mask_video",
        "audio",
    }


def _resolve_asset_path(field_name: str, shot: dict[str, Any], project_root: Path) -> Path | None:
    assets = shot.get("assets") if isinstance(shot.get("assets"), dict) else {}
    references = shot.get("references") if isinstance(shot.get("references"), dict) else {}
    crop = shot.get("crop_recommendation") if isinstance(shot.get("crop_recommendation"), dict) else {}
    candidates = [
        shot.get(f"{field_name}_path"),
        shot.get(field_name),
        assets.get(f"{field_name}_path"),
        assets.get(field_name),
        references.get(f"{field_name}_path"),
        references.get(field_name),
    ]
    if field_name == "mask_image":
        candidates.extend([shot.get("mask_path"), crop.get("mask_path")])
    for raw in candidates:
        if isinstance(raw, dict):
            raw = raw.get("path") or raw.get("image_path") or raw.get("file_path")
        if not raw:
            continue
        path = Path(str(raw))
        if not path.is_absolute():
            path = resolve_project_path(project_root, path)
        if path.exists():
            return path
    return None


def _media_type_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".avif"}:
        return "image"
    if suffix in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
        return "video"
    if suffix in {".wav", ".mp3", ".flac", ".ogg", ".m4a"}:
        return "audio"
    return "file"


def _default_suffix_for_media(media_type: str) -> str:
    if media_type == "video":
        return ".mp4"
    if media_type == "audio":
        return ".wav"
    return ".bin"


def _find_source_packet(shot: dict[str, Any], shot_manifest: dict[str, Any], project_root: Path) -> dict[str, Any] | None:
    packets = _find_source_packets(shot, shot_manifest, project_root)
    return packets[0] if packets else None


def _find_source_packets(shot: dict[str, Any], shot_manifest: dict[str, Any], project_root: Path) -> list[dict[str, Any]]:
    wanted = {str(item) for item in shot.get("source_windows", []) or []}
    refs = shot_manifest.get("source_packet_refs", []) or []
    matched: dict[str, dict[str, Any]] = {}
    fallback: list[dict[str, Any]] = []
    for ref in refs:
        try:
            path = resolve_project_path(project_root, str(ref))
            packet = read_json(path)
        except Exception:
            continue
        window_id = str(packet.get("window_id"))
        if not wanted:
            fallback.append(packet)
        elif window_id in wanted:
            matched[window_id] = packet
    if wanted:
        return [matched[window_id] for window_id in shot.get("source_windows", []) or [] if str(window_id) in matched]
    return fallback


def _select_source_image_path(shot: dict[str, Any], packet: dict[str, Any] | None, project_root: Path) -> Path | None:
    crop = shot.get("crop_recommendation") if isinstance(shot.get("crop_recommendation"), dict) else {}
    candidates = [
        shot.get("input_image_path"),
        crop.get("image_path"),
        shot.get("window_image_path"),
        packet.get("window_image_path") if packet else None,
        packet.get("image_path") if packet else None,
    ]
    for raw in candidates:
        if not raw:
            continue
        path = Path(str(raw))
        if not path.is_absolute():
            path = resolve_project_path(project_root, path)
        if path.exists():
            return path
    return None


def _resolve_crop_box(
    shot: dict[str, Any],
    packet: dict[str, Any] | None,
    image_width: int,
    image_height: int,
) -> list[int]:
    crop = shot.get("crop_recommendation") if isinstance(shot.get("crop_recommendation"), dict) else {}
    box = _coerce_box(crop.get("box"))
    if box and _box_within(box, image_width, image_height):
        return box
    if box and packet and _coerce_box(packet.get("source_box")):
        source_box = _coerce_box(packet.get("source_box")) or [0, 0, image_width, image_height]
        relative = [box[0] - source_box[0], box[1] - source_box[1], box[2] - source_box[0], box[3] - source_box[1]]
        if _box_intersects(relative, image_width, image_height):
            return _clamp_box(relative, image_width, image_height)
    source_ranges = shot.get("source_ranges") or []
    if source_ranges and isinstance(source_ranges[0], dict):
        range_box = _coerce_box(source_ranges[0].get("box"))
        if range_box and packet and _coerce_box(packet.get("source_box")):
            source_box = _coerce_box(packet.get("source_box")) or [0, 0, image_width, image_height]
            relative = [
                range_box[0] - source_box[0],
                range_box[1] - source_box[1],
                range_box[2] - source_box[0],
                range_box[3] - source_box[1],
            ]
            if _box_intersects(relative, image_width, image_height):
                return _clamp_box(relative, image_width, image_height)
    return [0, 0, image_width, image_height]


def _coerce_box(value: Any) -> list[int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x1, y1, x2, y2 = [int(round(float(item))) for item in value]
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]


def _box_within(box: list[int], width: int, height: int) -> bool:
    return 0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height


def _box_intersects(box: list[int], width: int, height: int) -> bool:
    return box[0] < width and box[2] > 0 and box[1] < height and box[3] > 0


def _clamp_box(box: list[int], width: int, height: int) -> list[int]:
    x1 = max(0, min(width - 1, box[0]))
    y1 = max(0, min(height - 1, box[1]))
    x2 = max(x1 + 1, min(width, box[2]))
    y2 = max(y1 + 1, min(height, box[3]))
    return [x1, y1, x2, y2]


def _characters_clause(shot: dict[str, Any]) -> str:
    names = [str(item) for item in shot.get("main_characters", []) or [] if str(item).strip()]
    if not names:
        return ""
    return "main characters: " + ", ".join(names[:3])


def _join_prompt_parts(parts: list[str]) -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for clause in str(part or "").split(","):
            text = clause.strip()
            key = text.lower()
            if text and key not in seen:
                cleaned.append(text)
                seen.add(key)
    return ", ".join(cleaned)


def _safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"


def _note_value(value: Any) -> str:
    text = str(value)
    if len(text) > 160:
        return text[:157] + "..."
    return text
