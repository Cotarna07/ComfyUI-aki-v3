# 预检模块：服务器连接、节点清单、模型文件存在性
# 原实现依赖 requests 库；已重构为 stdlib urllib，与 comfyui-shared 客户端对齐。
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import MODELS_ROOT, SERVER_URL


# ── 内部 HTTP 工具 ────────────────────────────────────────────────────────────

def _get_json(path: str, timeout: float) -> dict[str, Any]:
    """向 ComfyUI 发 GET 请求，返回 JSON dict；失败抛 RuntimeError。"""
    url = SERVER_URL.rstrip("/") + path
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {path} HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET {path} 连接失败: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GET {path} 返回非 JSON: {exc}") from exc


# ── 服务器检查 ────────────────────────────────────────────────────────────────

def check_server() -> dict[str, Any]:
    """检查 ComfyUI 服务是否可达，返回系统信息。"""
    result: dict[str, Any] = {
        "online": False,
        "version": None,
        "gpu": None,
        "vram_free_gb": None,
        "vram_total_gb": None,
        "error": None,
    }
    try:
        stats = _get_json("/system_stats", timeout=5)
        result["online"] = True
        result["version"] = stats.get("system", {}).get("comfyui_version", "unknown")
        devices = stats.get("devices") or []
        if devices:
            dev = devices[0]
            result["gpu"] = dev.get("name", "unknown")
            vram_total = dev.get("vram_total")
            if vram_total:
                result["vram_free_gb"] = round(dev.get("vram_free", 0) / 1024**3, 2)
                result["vram_total_gb"] = round(vram_total / 1024**3, 2)
    except Exception as exc:
        result["error"] = str(exc)
    return result


# ── 节点清单 ──────────────────────────────────────────────────────────────────

def get_node_inventory() -> dict[str, Any]:
    """从 /object_info 获取所有已注册节点类型。"""
    result: dict[str, Any] = {
        "online": False,
        "node_types": {},
        "count": 0,
        "error": None,
    }
    try:
        data = _get_json("/object_info", timeout=10)
        result["online"] = True
        result["node_types"] = {k: {"category": v.get("category", "")} for k, v in data.items()}
        result["count"] = len(result["node_types"])
    except Exception as exc:
        result["error"] = str(exc)
    return result


# ── 模型文件检查 ──────────────────────────────────────────────────────────────

def model_exists(directory: str, filename: str) -> bool:
    """检查指定模型文件是否存在。"""
    return (MODELS_ROOT / directory / filename).is_file()


def check_model_list(models: list[dict[str, str]]) -> list[dict[str, Any]]:
    """批量检查模型存在性。models: [{"directory": "checkpoints", "name": "xxx.safetensors"}]"""
    results = []
    for m in models:
        d = m.get("directory", "")
        n = m.get("name", "")
        exists = model_exists(d, n) if d and n else False
        results.append({**m, "exists": exists, "full_path": str(MODELS_ROOT / d / n) if d and n else ""})
    return results


def check_models_by_dir(directory: str, names: list[str]) -> list[dict[str, Any]]:
    """检查某个目录下的一批模型文件是否存在。"""
    return [
        {
            "directory": directory,
            "name": name,
            "exists": model_exists(directory, name),
            "full_path": str(MODELS_ROOT / directory / name),
        }
        for name in names
    ]


def full_model_census() -> dict[str, Any]:
    """遍历 models/ 下所有子目录，统计文件数和总大小。"""
    if not MODELS_ROOT.is_dir():
        return {"error": f"Models root not found: {MODELS_ROOT}"}

    census: dict[str, dict[str, Any]] = {}
    for subdir in sorted(MODELS_ROOT.iterdir()):
        if not subdir.is_dir():
            continue
        files = [f for f in subdir.rglob("*") if f.is_file() and not f.name.startswith("put_")]
        total_size = sum(f.stat().st_size for f in files)
        census[subdir.name] = {
            "file_count": len(files),
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / 1024**3, 2),
        }
    return census
