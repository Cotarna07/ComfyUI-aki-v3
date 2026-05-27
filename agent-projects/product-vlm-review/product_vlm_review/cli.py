from __future__ import annotations

import argparse
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .prompt import build_review_prompt
from .runtime import parse_json_object, write_record


DEFAULT_OLLAMA_MODEL = "huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M"
DEFAULT_INTERNVL_MODEL = "OpenGVLab/InternVL3_5-8B"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="使用本地 VLM 复核商品图事实与创意镜头建议。")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--backend", choices=("ollama", "internvl"), required=True)
    run.add_argument("--images", type=Path, nargs="+", required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--model", default="")
    run.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    run.add_argument("--timeout-seconds", type=int, default=600)
    run.add_argument("--max-tiles-per-image", type=int, default=4)
    run.add_argument("--max-new-tokens", type=int, default=1800)
    run.add_argument(
        "--per-image",
        action="store_true",
        help="逐图提取事实，防止整组上下文将某一张图的商品关系覆盖或混淆。",
    )
    return parser


def _validate_images(images: list[Path]) -> list[Path]:
    missing = [str(path) for path in images if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"图片不存在：{', '.join(missing)}")
    return [path.resolve() for path in images]


def _run(args: argparse.Namespace) -> int:
    images = _validate_images(args.images)
    prompt = build_review_prompt(images)
    prompts_and_images = [(build_review_prompt([image]), image) for image in images]
    if args.backend == "ollama":
        from .ollama_backend import review_each_with_ollama, review_with_ollama

        model = args.model or DEFAULT_OLLAMA_MODEL
        call = lambda: review_with_ollama(prompt, images, model, args.ollama_url, args.timeout_seconds)
        call_each = lambda: review_each_with_ollama(
            prompts_and_images, model, args.ollama_url, args.timeout_seconds
        )
    else:
        from .internvl_backend import review_each_with_internvl, review_with_internvl

        project_root = Path(__file__).resolve().parents[1]
        os.environ.setdefault("HF_HOME", str(project_root / "runtime" / "hf_home"))
        model = args.model or DEFAULT_INTERNVL_MODEL
        call = lambda: review_with_internvl(
            prompt, images, model, args.max_tiles_per_image, args.max_new_tokens
        )
        call_each = lambda: review_each_with_internvl(
            prompts_and_images, model, args.max_tiles_per_image, args.max_new_tokens
        )
    started = time.perf_counter()
    raw_responses = call_each() if args.per_image else [call()]
    elapsed_seconds = round(time.perf_counter() - started, 3)
    prompts = [item[0] for item in prompts_and_images] if args.per_image else [prompt]
    input_groups = [[str(item[1])] for item in prompts_and_images] if args.per_image else [[str(path) for path in images]]
    results: list[dict[str, Any]] = []
    all_valid = True
    for source_images, source_prompt, raw_response in zip(input_groups, prompts, raw_responses):
        parsed, parse_error = parse_json_object(raw_response)
        all_valid = all_valid and parsed is not None
        results.append(
            {
                "images": source_images,
                "prompt": source_prompt,
                "raw_response": raw_response,
                "parsed_response": parsed,
                "parse_error": parse_error,
            }
        )
    record: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "backend": args.backend,
        "model": model,
        "images": [str(path) for path in images],
        "mode": "per_image" if args.per_image else "combined",
        "elapsed_seconds": elapsed_seconds,
        "python": platform.python_version(),
        "hf_home": os.environ.get("HF_HOME", ""),
        "results": results,
    }
    if not args.per_image:
        record.update(results[0])
    write_record(args.output.resolve(), record)
    print(f"backend={args.backend} model={model} elapsed_seconds={elapsed_seconds}")
    print(f"output={args.output.resolve()}")
    print(f"json_valid={all_valid}")
    return 0 if all_valid else 2


def main() -> None:
    args = _parser().parse_args()
    if args.command == "run":
        raise SystemExit(_run(args))
