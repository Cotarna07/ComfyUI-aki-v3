"""ComfyUI HTTP 客户端（纯 stdlib，无第三方依赖）。

合并自三个独立实现：
- manga-anime-pipeline/pipeline/comfy/client.py  —— 基础请求层
- lmstudio-comfyui-benchmark/comfyui.py          —— 轮询 + 工作流节点路径补丁
- comfyui-test-harness/preflight.py              —— 服务器状态 + 节点清单查询
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


class ServerUnreachable(RuntimeError):
    """ComfyUI 服务不可达。"""


@dataclass(frozen=True)
class ComfyClientConfig:
    server: str = "http://127.0.0.1:8188"
    timeout_seconds: float = 60.0
    poll_interval_seconds: float = 2.0
    prompt_timeout_seconds: float = 600.0
    client_id: str = "agent:comfyui-shared"


@dataclass
class ServerStats:
    online: bool
    version: str | None = None
    gpu: str | None = None
    vram_free_gb: float | None = None
    vram_total_gb: float | None = None
    error: str | None = None


@dataclass
class NodeInventory:
    online: bool
    node_types: dict[str, dict[str, str]] = field(default_factory=dict)
    count: int = 0
    error: str | None = None


@dataclass(frozen=True)
class PromptResult:
    prompt_id: str
    status: str          # "completed" | "timeout" | "error"
    history: dict[str, Any]


class ComfyClient:
    """ComfyUI HTTP 客户端，纯 stdlib urllib 实现。

    用法::

        client = ComfyClient()
        stats = client.check_server()          # → ServerStats
        nodes = client.get_node_inventory()    # → NodeInventory
        pid = client.submit_prompt(payload)    # → str  prompt_id
        result = client.wait_for_result(pid)   # → PromptResult
    """

    def __init__(self, config: ComfyClientConfig | None = None) -> None:
        self.config = config or ComfyClientConfig()

    # ── 服务器状态 ───────────────────────────────────────────────────────────

    def check_server(self) -> ServerStats:
        """查询 /system_stats，返回在线状态、GPU 型号与显存信息。"""
        try:
            data = self._request("GET", "/system_stats", timeout=5)
        except Exception as exc:
            return ServerStats(online=False, error=str(exc))

        stats = ServerStats(
            online=True,
            version=data.get("system", {}).get("comfyui_version"),
        )
        devices = data.get("devices") or []
        if devices:
            dev = devices[0]
            stats.gpu = dev.get("name")
            vram_total = dev.get("vram_total")
            if vram_total:
                stats.vram_total_gb = round(vram_total / 1024**3, 2)
                stats.vram_free_gb = round(dev.get("vram_free", 0) / 1024**3, 2)
        return stats

    # ── 节点清单 ─────────────────────────────────────────────────────────────

    def get_node_inventory(self) -> NodeInventory:
        """查询 /object_info，返回所有已注册节点类型。"""
        try:
            data = self._request("GET", "/object_info", timeout=10)
        except Exception as exc:
            return NodeInventory(online=False, error=str(exc))

        node_types = {k: {"category": v.get("category", "")} for k, v in data.items()}
        return NodeInventory(online=True, node_types=node_types, count=len(node_types))

    # ── 提交与查询 ───────────────────────────────────────────────────────────

    def submit_prompt(self, prompt_payload: dict[str, Any]) -> str:
        """向 /prompt 提交工作流，返回 prompt_id。"""
        payload = {
            "prompt": prompt_payload,
            "client_id": self.config.client_id,
        }
        response = self._request("POST", "/prompt", body=payload)
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI 未返回 prompt_id: {response}")
        return str(prompt_id)

    def get_history(self, prompt_id: str) -> dict[str, Any]:
        """查询 /history/{prompt_id}，返回原始历史记录 dict。"""
        return self._request("GET", f"/history/{prompt_id}")

    def wait_for_result(self, prompt_id: str) -> PromptResult:
        """轮询直到任务完成或超时，返回 PromptResult。"""
        deadline = time.monotonic() + self.config.prompt_timeout_seconds
        while time.monotonic() < deadline:
            history = self.get_history(prompt_id)
            item = history.get(prompt_id)
            if item:
                status = item.get("status", {}).get("status_str", "completed")
                return PromptResult(prompt_id=prompt_id, status=str(status), history=item)
            time.sleep(self.config.poll_interval_seconds)
        return PromptResult(prompt_id=prompt_id, status="timeout", history={})

    # ── 内部 HTTP ────────────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        url = self.config.server.rstrip("/") + path
        data: bytes | None = None
        headers: dict[str, str] = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
        effective_timeout = timeout if timeout is not None else self.config.timeout_seconds
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                raw = resp.read().decode("utf-8") or "{}"
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ComfyUI {method} {path} HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ServerUnreachable(f"ComfyUI {method} {path} 无法连接: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"ComfyUI {method} {path} 返回非 JSON: {exc}") from exc
