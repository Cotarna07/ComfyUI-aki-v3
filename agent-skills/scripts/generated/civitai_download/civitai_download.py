from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests


MODEL_ROOT = Path("D:/ComfyUI-Models")
TYPE_DIRS = {
    "Checkpoint": "checkpoints",
    "LORA": "loras",
    "LoCon": "loras",
    "DoRA": "loras",
    "VAE": "vae",
    "TextEncoder": "text_encoders",
    "UNet": "diffusion_models",
}


def civitai_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Codex ComfyUI model downloader",
        }
    )
    return session


def api_get(session: requests.Session, url: str) -> dict[str, Any]:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def find_version(session: requests.Session, version_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
    # The model-version endpoint is compact, but the model endpoint gives model type
    # and useful model-level metadata. Search is stable enough for a generated helper.
    data = api_get(
        session,
        f"https://civitai.com/api/v1/model-versions/{version_id}",
    )
    model_id = data["modelId"]
    model = api_get(session, f"https://civitai.com/api/v1/models/{model_id}")
    return model, data


def primary_file(version: dict[str, Any]) -> dict[str, Any]:
    files = version.get("files") or []
    if not files:
        raise RuntimeError(f"version {version.get('id')} has no files")
    primary = [file for file in files if file.get("primary")]
    return primary[0] if primary else files[0]


def destination_for(model: dict[str, Any], file: dict[str, Any]) -> Path:
    directory = TYPE_DIRS.get(model.get("type"), "other")
    target_dir = MODEL_ROOT / directory
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / file["name"]


def expected_bytes(file: dict[str, Any]) -> int | None:
    size_kb = file.get("sizeKB")
    if size_kb is None:
        return None
    return int(float(size_kb) * 1024)


def download_url(session: requests.Session, url: str) -> str:
    response = session.get(url, allow_redirects=False, stream=True, timeout=30)
    response.close()
    if response.status_code not in {302, 303, 307, 308}:
        raise RuntimeError(f"download endpoint returned HTTP {response.status_code}")
    location = response.headers.get("location")
    if not location:
        raise RuntimeError("download endpoint did not return a redirect location")
    return location


def human_bytes(size: int | None) -> str:
    if size is None:
        return "unknown"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def stream_download(
    session: requests.Session,
    signed_url: str,
    target: Path,
    expected_size: int | None,
    label: str,
) -> str:
    if target.exists() and expected_size and target.stat().st_size == expected_size:
        print(f"[skip] {label}: exists ({human_bytes(expected_size)})", flush=True)
        return "skipped"

    part = target.with_name(target.name + ".part")
    offset = part.stat().st_size if part.exists() else 0
    headers = {}
    if offset:
        headers["Range"] = f"bytes={offset}-"
        print(f"[resume] {label}: from {human_bytes(offset)}", flush=True)
    else:
        print(f"[download] {label}: {human_bytes(expected_size)} -> {target}", flush=True)

    storage_headers = {
        "User-Agent": session.headers.get("User-Agent", "Codex ComfyUI model downloader")
    }
    storage_headers.update(headers)
    with requests.get(signed_url, headers=storage_headers, stream=True, timeout=60) as response:
        if offset and response.status_code == 200:
            offset = 0
            mode = "wb"
        else:
            mode = "ab" if offset else "wb"
        response.raise_for_status()
        downloaded = offset
        last_report = time.monotonic()
        with part.open(mode + "") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if now - last_report >= 30:
                    if expected_size:
                        pct = downloaded / expected_size * 100
                        print(f"[progress] {label}: {pct:.1f}% ({human_bytes(downloaded)})", flush=True)
                    else:
                        print(f"[progress] {label}: {human_bytes(downloaded)}", flush=True)
                    last_report = now

    if expected_size and part.stat().st_size != expected_size:
        raise RuntimeError(
            f"{label} size mismatch: got {part.stat().st_size}, expected {expected_size}"
        )
    part.replace(target)
    print(f"[done] {label}: {human_bytes(target.stat().st_size)}", flush=True)
    return "downloaded"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-id", type=int, action="append", default=[])
    parser.add_argument("--version-id-file", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--retries", type=int, default=5)
    args = parser.parse_args()

    version_ids = list(args.version_id)
    if args.version_id_file:
        version_ids.extend(
            int(line.strip())
            for line in args.version_id_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    if not version_ids:
        parser.error("at least one --version-id or --version-id-file entry is required")

    token = os.environ.get("CIVITAI_API_TOKEN")
    if not token:
        print("CIVITAI_API_TOKEN is required", file=sys.stderr)
        return 2

    session = civitai_session(token)
    manifest: list[dict[str, Any]] = []
    for version_id in version_ids:
        model, version = find_version(session, version_id)
        file = primary_file(version)
        target = destination_for(model, file)
        label = f"{model.get('name')} / {version.get('name')}"
        scan_ok = (
            file.get("pickleScanResult") == "Success"
            and file.get("virusScanResult") == "Success"
        )
        if not scan_ok:
            raise RuntimeError(f"{label} failed scan gate: {file.get('name')}")
        last_error: str | None = None
        for attempt in range(1, args.retries + 1):
            try:
                signed_url = download_url(session, version["downloadUrl"])
                status = stream_download(
                    session,
                    signed_url,
                    target,
                    expected_bytes(file),
                    label,
                )
                last_error = None
                break
            except (requests.RequestException, OSError, RuntimeError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                print(
                    f"[retry] {label}: attempt {attempt}/{args.retries} failed: {last_error}",
                    flush=True,
                )
                if attempt == args.retries:
                    status = "failed"
                else:
                    time.sleep(min(60, attempt * 5))
        manifest.append(
            {
                "model_id": model.get("id"),
                "version_id": version.get("id"),
                "model_name": model.get("name"),
                "version_name": version.get("name"),
                "model_type": model.get("type"),
                "base_model": version.get("baseModel"),
                "file_name": file.get("name"),
                "target": str(target),
                "size_bytes": target.stat().st_size if target.exists() else None,
                "status": status,
                "error": last_error,
            }
        )

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
