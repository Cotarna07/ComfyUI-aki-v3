from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

from comfyui_skill_utils import (
    extract_models_from_workflow_file,
    get_pack_models,
    get_skill,
    load_registry,
    model_file_path,
    workspace_path,
)


DEFAULT_TIMEOUT = 60
CHUNK_SIZE = 8 * 1024 * 1024


def format_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def resolve_requested_models(args: argparse.Namespace, registry: dict) -> list[dict]:
    entries: list[dict] = []
    requested_any = False

    if args.all_packs:
        requested_any = True
        entries.extend(get_pack_models(registry, list(registry.get("packs", {}).keys())))

    for pack_name in args.pack:
        requested_any = True
        entries.extend(get_pack_models(registry, [pack_name]))

    for skill_name in args.skill:
        requested_any = True
        skill = get_skill(registry, skill_name)
        pack_name = skill.get("model_pack")
        if pack_name:
            entries.extend(get_pack_models(registry, [pack_name]))
            continue

        source_workflow = skill.get("source_workflow")
        if source_workflow:
            try:
                entries.extend(extract_models_from_workflow_file(source_workflow))
            except FileNotFoundError:
                pass

    for workflow_path in args.workflow:
        requested_any = True
        entries.extend(extract_models_from_workflow_file(workflow_path))

    if not requested_any:
        entries.extend(get_pack_models(registry, ["wan22_t2v_fast"]))

    deduped: dict[tuple[str, str], dict] = {}
    for entry in entries:
        deduped[(entry["directory"], entry["name"])] = entry
    return sorted(deduped.values(), key=lambda item: (item["directory"], item["name"]))


def print_model_status(entries: list[dict], model_root: Path) -> list[dict]:
    missing: list[dict] = []
    print("=" * 72)
    print(f"Model root: {model_root}")
    print("=" * 72)
    for entry in entries:
        target = model_file_path(model_root, entry)
        if target.exists():
            status = "READY"
            size_text = format_size(target.stat().st_size)
        else:
            status = "MISSING"
            size_text = "unknown"
            missing.append(entry)
        print(f"[{status:7}] {entry['directory']}/{entry['name']}")
        if entry.get("description"):
            print(f"          {entry['description']}")
        if target.exists():
            print(f"          {size_text}")
    print()
    return missing


def apply_mirror(url: str, mirror: str) -> str:
    if not mirror:
        return url
    return url.replace("https://huggingface.co", mirror.rstrip("/"))


def download_entry(entry: dict, model_root: Path, mirror: str, hf_token: str, overwrite: bool) -> bool:
    url = entry.get("url") or ""
    if not url:
        print(f"SKIP    {entry['name']} (no download URL in registry or workflow metadata)")
        return False

    target = model_file_path(model_root, entry)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and not overwrite:
        print(f"SKIP    {target} already exists")
        return True

    tmp_path = target.with_suffix(target.suffix + ".part")
    existing_size = tmp_path.stat().st_size if tmp_path.exists() else 0

    headers = {"User-Agent": "ComfyUI-Agent-Skill/1.0"}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"
    if existing_size and not overwrite:
        headers["Range"] = f"bytes={existing_size}-"

    final_url = apply_mirror(url, mirror)
    print(f"DOWNLOAD {entry['directory']}/{entry['name']}")
    print(f"         {final_url}")

    response = requests.get(final_url, headers=headers, stream=True, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()

    append_mode = response.status_code == 206 and existing_size > 0 and not overwrite
    if overwrite and tmp_path.exists():
        tmp_path.unlink()
        existing_size = 0

    content_length = int(response.headers.get("Content-Length", "0"))
    total_size = existing_size + content_length if append_mode else content_length
    bytes_written = existing_size if append_mode else 0

    with tmp_path.open("ab" if append_mode else "wb") as handle:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue
            handle.write(chunk)
            bytes_written += len(chunk)
            if total_size:
                percent = min(100.0, bytes_written / total_size * 100)
                print(
                    f"\r         {percent:6.2f}% {format_size(bytes_written)} / {format_size(total_size)}",
                    end="",
                    flush=True,
                )
            else:
                print(f"\r         {format_size(bytes_written)}", end="", flush=True)

    print()
    tmp_path.replace(target)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download ComfyUI model packs or workflow models")
    parser.add_argument("--registry", default=None, help="Path to agent-skills/comfyui/registry.json")
    parser.add_argument("--model-root", default=None, help="Override model root directory")
    parser.add_argument("--pack", action="append", default=[], help="Download a named model pack")
    parser.add_argument("--skill", action="append", default=[], help="Download the model pack behind a named skill")
    parser.add_argument("--workflow", action="append", default=[], help="Analyze and download models referenced by a workflow JSON file")
    parser.add_argument("--all-packs", action="store_true", help="Download every pack declared in the registry")
    parser.add_argument("--list-packs", action="store_true", help="List named packs and exit")
    parser.add_argument("--check", action="store_true", help="Only check whether files exist")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    parser.add_argument("--mirror", default=os.environ.get("HF_ENDPOINT", ""), help="Mirror for huggingface.co URLs")
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""), help="Optional Hugging Face token")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry = load_registry(args.registry)

    if args.list_packs:
        for name, pack in registry.get("packs", {}).items():
            print(f"{name}: {pack.get('description', '')}")
        return 0

    model_root = workspace_path(args.model_root or registry.get("model_root", "D:/ComfyUI-Models"))
    entries = resolve_requested_models(args, registry)
    if not entries:
        print("No model entries were resolved.")
        return 1

    missing = print_model_status(entries, model_root)
    if args.check:
        return 0 if not missing else 2

    if not missing and not args.overwrite:
        print("Everything requested is already present.")
        return 0

    to_download = entries if args.overwrite else missing
    success = 0
    for entry in to_download:
        try:
            if download_entry(entry, model_root, args.mirror, args.hf_token, args.overwrite):
                success += 1
        except requests.HTTPError as error:
            print(f"ERROR   {entry['name']}: {error}")
        except KeyboardInterrupt:
            print("Interrupted by user.")
            return 130
        except Exception as error:
            print(f"ERROR   {entry['name']}: {error}")

    print()
    print(f"Completed {success}/{len(to_download)} downloads.")
    print("If ComfyUI is already running, restart it after downloads finish so new model lists refresh cleanly.")
    return 0 if success == len(to_download) else 1


if __name__ == "__main__":
    sys.exit(main())
