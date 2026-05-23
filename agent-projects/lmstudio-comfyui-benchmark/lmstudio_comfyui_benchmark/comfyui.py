from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any

from .config import ComfyUiConfig
from .http_json import request_json


@dataclass(frozen=True)
class ComfyJobResult:
    prompt_id: str
    status: str
    history: dict[str, Any]


class ComfyUiClient:
    def __init__(self, config: ComfyUiConfig) -> None:
        self.config = config

    def check(self) -> dict[str, Any]:
        return request_json("GET", f"{self.config.base_url}/system_stats", timeout=30)

    def load_workflow(self) -> dict[str, Any]:
        with self.config.workflow_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def build_prompt(self, workflow: dict[str, Any], positive_prompt: str, negative_prompt: str) -> dict[str, Any]:
        prompt = deepcopy(workflow)
        set_path_value(prompt, self.config.positive_prompt_path, positive_prompt)
        set_path_value(prompt, self.config.negative_prompt_path, negative_prompt)
        for path, value in self.config.overrides.items():
            set_path_value(prompt, path, value)
        return prompt

    def enqueue(self, prompt: dict[str, Any]) -> str:
        data = request_json(
            "POST",
            f"{self.config.base_url}/prompt",
            payload={"prompt": prompt, "client_id": self.config.client_id},
            timeout=60,
        )
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI did not return prompt_id: {data}")
        return str(prompt_id)

    def wait_for_history(self, prompt_id: str) -> ComfyJobResult:
        deadline = time.monotonic() + self.config.prompt_timeout_sec
        while time.monotonic() < deadline:
            history = request_json("GET", f"{self.config.base_url}/history/{prompt_id}", timeout=60)
            item = history.get(prompt_id)
            if item:
                status = item.get("status", {}).get("status_str", "completed")
                return ComfyJobResult(prompt_id=prompt_id, status=str(status), history=item)
            time.sleep(self.config.poll_interval_sec)
        return ComfyJobResult(prompt_id=prompt_id, status="timeout", history={})


def set_path_value(payload: dict[str, Any], dotted_path: str, value: Any) -> None:
    if not dotted_path:
        raise ValueError("Dotted path is required.")
    parts = dotted_path.split(".")
    cursor: Any = payload
    for part in parts[:-1]:
        if isinstance(cursor, dict):
            if part not in cursor:
                raise KeyError(f"Path segment not found: {dotted_path}")
            cursor = cursor[part]
        elif isinstance(cursor, list):
            cursor = cursor[int(part)]
        else:
            raise TypeError(f"Cannot walk through {type(cursor).__name__} at {part}")
    leaf = parts[-1]
    if isinstance(cursor, dict):
        if leaf not in cursor:
            raise KeyError(f"Path segment not found: {dotted_path}")
        cursor[leaf] = value
    elif isinstance(cursor, list):
        cursor[int(leaf)] = value
    else:
        raise TypeError(f"Cannot set value on {type(cursor).__name__}")


def workflow_exists(config: ComfyUiConfig) -> bool:
    return bool(config.workflow_path) and Path(config.workflow_path).is_file()
