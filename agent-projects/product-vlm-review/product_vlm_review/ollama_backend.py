from __future__ import annotations

import base64
import json
from pathlib import Path
from urllib.request import Request, urlopen


def review_with_ollama(
    prompt: str,
    images: list[Path],
    model: str,
    base_url: str,
    timeout_seconds: int,
) -> str:
    encoded_images = [base64.b64encode(path.read_bytes()).decode("ascii") for path in images]
    payload = {
        "model": model,
        "stream": False,
        "messages": [{"role": "user", "content": prompt, "images": encoded_images}],
        "options": {"temperature": 0, "num_predict": 1800},
    }
    request = Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        value = json.loads(response.read().decode("utf-8"))
    result = str((value.get("message") or {}).get("content") or "")
    if not result:
        raise RuntimeError(
            "Ollama 未返回 message.content；"
            f"done_reason={value.get('done_reason')!r}, error={value.get('error')!r}"
        )
    return result


def review_each_with_ollama(
    prompts_and_images: list[tuple[str, Path]],
    model: str,
    base_url: str,
    timeout_seconds: int,
) -> list[str]:
    return [
        review_with_ollama(prompt, [image], model, base_url, timeout_seconds)
        for prompt, image in prompts_and_images
    ]
