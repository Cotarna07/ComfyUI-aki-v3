from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def write_summary(path: Path, llm_rows: list[dict[str, Any]], image_rows: list[dict[str, Any]]) -> None:
    image_by_key = {row.get("llm_key"): row for row in image_rows}
    fieldnames = [
        "llm_key",
        "model",
        "parameter_key",
        "temperature",
        "top_p",
        "max_tokens",
        "completion_tokens",
        "elapsed_sec",
        "tokens_per_sec",
        "quality_score",
        "quality_reasons",
        "image_status",
        "prompt_id",
        "positive_prompt",
        "negative_prompt",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in llm_rows:
            image = image_by_key.get(row.get("llm_key"), {})
            writer.writerow(
                {
                    "llm_key": row.get("llm_key", ""),
                    "model": row.get("model", ""),
                    "parameter_key": row.get("parameter_key", ""),
                    "temperature": row.get("temperature", ""),
                    "top_p": row.get("top_p", ""),
                    "max_tokens": row.get("max_tokens", ""),
                    "completion_tokens": row.get("completion_tokens", ""),
                    "elapsed_sec": f"{float(row.get('elapsed_sec', 0)):.3f}",
                    "tokens_per_sec": f"{float(row.get('tokens_per_sec', 0)):.3f}",
                    "quality_score": row.get("quality_score", ""),
                    "quality_reasons": "; ".join(row.get("quality_reasons", [])),
                    "image_status": image.get("status", ""),
                    "prompt_id": image.get("prompt_id", ""),
                    "positive_prompt": row.get("positive_prompt", ""),
                    "negative_prompt": row.get("negative_prompt", ""),
                }
            )
