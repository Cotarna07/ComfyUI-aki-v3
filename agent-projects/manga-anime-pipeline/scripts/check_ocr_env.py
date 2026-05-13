"""Inspect the OCR runtime environment.

Reports python version, virtualenv, optional paddleocr/paddle imports and
whether the PaddleOCR provider can be instantiated. Does not raise on
missing optional dependencies; returns structured findings instead.
"""

from __future__ import annotations

import importlib
import os
import platform
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def check_ocr_environment() -> dict[str, Any]:
    findings: dict[str, Any] = {
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "virtual_env": os.environ.get("VIRTUAL_ENV"),
        "paddleocr_import_ok": False,
        "paddle_import_ok": False,
        "paddleocr_version": None,
        "paddle_version": None,
        "provider_ready": False,
        "errors": [],
        "warnings": [],
        "install_command": "python -m pip install -r requirements-ocr.txt",
    }
    findings["paddleocr_import_ok"], findings["paddleocr_version"], paddle_error = _try_import("paddleocr")
    if paddle_error:
        findings["errors"].append(f"paddleocr import failed: {paddle_error}")
    findings["paddle_import_ok"], findings["paddle_version"], paddle_core_error = _try_import("paddle")
    if paddle_core_error:
        findings["errors"].append(f"paddle import failed: {paddle_core_error}")
    findings["provider_ready"], provider_error = _try_instantiate_provider()
    if provider_error:
        findings["errors"].append(f"PaddleOCR provider check failed: {provider_error}")
    findings["ocr_env_ready"] = bool(
        findings["paddleocr_import_ok"] and findings["paddle_import_ok"] and findings["provider_ready"]
    )
    return findings


def _try_import(module_name: str) -> tuple[bool, str | None, str | None]:
    try:
        module = importlib.import_module(module_name)
    except Exception as error:
        return False, None, str(error)
    version = getattr(module, "__version__", None)
    return True, version, None


def _try_instantiate_provider() -> tuple[bool, str | None]:
    try:
        from pipeline.ocr.paddle_provider import PaddleOCRProvider

        provider = PaddleOCRProvider()
        provider.check_runtime()
        return True, None
    except Exception as error:
        return False, str(error)


def main() -> int:
    import json

    findings = check_ocr_environment()
    print(json.dumps(findings, ensure_ascii=False, indent=2))
    return 0 if findings["ocr_env_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
