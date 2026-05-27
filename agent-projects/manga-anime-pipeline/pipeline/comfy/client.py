"""Lightweight ComfyUI HTTP client using stdlib urllib."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class ServerUnreachable(RuntimeError):
    """Raised when ComfyUI server cannot be reached."""


@dataclass(frozen=True)
class ComfyClientConfig:
    server: str = "http://127.0.0.1:8188"
    timeout_seconds: float = 60.0


class ComfyClient:
    def __init__(self, config: ComfyClientConfig | None = None) -> None:
        self.config = config or ComfyClientConfig()

    def check_server(self) -> dict[str, Any]:
        try:
            return self._request("GET", "/system_stats")
        except Exception as error:
            raise ServerUnreachable(f"ComfyUI server unreachable at {self.config.server}: {error}") from error

    def submit_prompt(self, prompt_payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/prompt", body=prompt_payload)

    def get_history(self, prompt_id: str) -> dict[str, Any]:
        return self._request("GET", f"/history/{prompt_id}")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self.config.server.rstrip("/") + path
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = response.read().decode("utf-8") or "{}"
                return json.loads(payload)
        except urllib.error.URLError as error:
            raise RuntimeError(f"ComfyUI {method} {path} failed: {error}") from error
        except json.JSONDecodeError as error:
            raise RuntimeError(f"ComfyUI {method} {path} returned non-JSON body: {error}") from error
