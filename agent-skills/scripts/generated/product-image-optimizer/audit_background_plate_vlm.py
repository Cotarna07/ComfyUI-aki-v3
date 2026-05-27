# -*- coding: utf-8 -*-
"""Audit a generated background plate for product-like forbidden objects.

This is a diagnostic gate for factual product workflows. It does not approve
publication by itself; it can reject an unsafe plate before foreground
compositing and preserve evidence for later review.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


DEFAULT_MODEL = "huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M"
DEFAULT_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_FORBIDDEN = (
    "product, duplicate product, toy, model, package, printed text, logo, watermark"
)
POSITIVE_MARKERS = (
    "features",
    "contains",
    "shows",
    "visible",
    "present",
    "positioned",
    "parked",
    "detected",
    "appears",
    "there is",
    "there are",
)
NEGATIVE_MARKERS = ("no ", "not ", "without ", "none", "absent")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True, help="Generated background plate.")
    parser.add_argument(
        "--product",
        required=True,
        help="Product to be composited later, for example 'red brick-built Formula 1 toy car'.",
    )
    parser.add_argument(
        "--forbidden",
        default=DEFAULT_FORBIDDEN,
        help="Comma-separated objects forbidden in the plate.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def encode_image(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    return base64.b64encode(path.read_bytes()).decode("ascii")


def make_prompt(product: str, forbidden: str) -> str:
    return (
        "You are a strict safety checker for factual e-commerce product images. "
        f"This image must be an empty background plate before compositing a {product}. "
        "Studio walls, floors, lights and a plain support surface are allowed. "
        f"Forbidden objects are: {forbidden}. "
        "Inspect only whether forbidden objects are visibly present in the background plate. "
        "Return strict JSON with keys: has_forbidden_object (boolean), "
        "detected_forbidden_objects (array of strings, empty when none), "
        "locations (array of strings), evidence (array of short strings), action (string). "
        "If any forbidden object or similar silhouette is visible, has_forbidden_object must be true."
    )


def request_audit(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        "model": args.model,
        "messages": [
            {
                "role": "user",
                "content": make_prompt(args.product, args.forbidden),
                "images": [encode_image(args.image)],
            }
        ],
        "stream": False,
        "format": "json",
        "keep_alive": 0,
        "options": {"temperature": 0, "num_predict": 500, "num_ctx": 4096},
    }
    response = requests.post(args.url, json=payload, timeout=900)
    response.raise_for_status()
    message = response.json()["message"]["content"]
    parsed = json.loads(message)
    return {"raw_content": message, "parsed": parsed}


def contradiction_evidence(parsed: dict[str, Any], forbidden: str) -> list[str]:
    terms = [term.strip().lower() for term in forbidden.split(",") if term.strip()]
    evidence = parsed.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    warnings: list[str] = []
    for text in evidence:
        lowered = str(text).lower()
        if any(marker in lowered for marker in NEGATIVE_MARKERS):
            continue
        if any(term in lowered for term in terms) and any(
            marker in lowered for marker in POSITIVE_MARKERS
        ):
            warnings.append(str(text))
    return warnings


def make_result(args: argparse.Namespace, response: dict[str, Any]) -> dict[str, Any]:
    parsed = response["parsed"]
    detected = parsed.get("detected_forbidden_objects", [])
    if isinstance(detected, str):
        detected = [detected] if detected.strip() else []
    warnings = contradiction_evidence(parsed, args.forbidden)
    model_failed = bool(parsed.get("has_forbidden_object")) or bool(detected)
    gate_pass = not model_failed and not warnings
    return {
        "image": str(args.image),
        "product": args.product,
        "forbidden": args.forbidden,
        "model": args.model,
        "diagnostic_only": True,
        "gate_pass": gate_pass,
        "model_failed": model_failed,
        "contradiction_warnings": warnings,
        "vlm_response": parsed,
        "raw_content": response["raw_content"],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> int:
    args = parse_args()
    result = make_result(args, request_audit(args))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0 if result["gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
