# 模型测试模块：检查模型文件存在性，在线时尝试加载
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import (
    CUSTOM_NODES_ROOT,
    MODELS_ROOT,
    NEW_CHECKPOINTS,
    NEW_DIFFUSION_MODELS,
    NEW_LORAS,
    MMAUDIO_REQUIRED_MODELS,
    MMAUDIO_OPTIONAL_MODELS,
    RIFE_VFI_REQUIRED_MODELS,
)


@dataclass
class ModelTestResult:
    name: str
    directory: str
    kind: str  # checkpoint, diffusion_model, lora, mmaudio
    on_disk: bool = False
    path: str = ""
    size_gb: float = 0.0
    can_load: bool | None = None  # None = 未测试（离线模式）
    load_error: str | None = None
    notes: str = ""


def test_new_checkpoints() -> list[ModelTestResult]:
    """测试新增的 checkpoint 模型。"""
    results = []
    for name in NEW_CHECKPOINTS:
        path = MODELS_ROOT / "checkpoints" / name
        exists = path.is_file()
        size = round(path.stat().st_size / 1024**3, 2) if exists else 0.0
        results.append(ModelTestResult(
            name=name,
            directory="checkpoints",
            kind="checkpoint",
            on_disk=exists,
            path=str(path),
            size_gb=size,
        ))
    return results


def test_new_diffusion_models() -> list[ModelTestResult]:
    """测试新增的 diffusion models。"""
    results = []
    for name in NEW_DIFFUSION_MODELS:
        path = MODELS_ROOT / "diffusion_models" / name
        exists = path.is_file()
        size = round(path.stat().st_size / 1024**3, 2) if exists else 0.0
        results.append(ModelTestResult(
            name=name,
            directory="diffusion_models",
            kind="diffusion_model",
            on_disk=exists,
            path=str(path),
            size_gb=size,
        ))
    return results


def test_new_loras() -> list[ModelTestResult]:
    """测试新增的 LoRA 模型。"""
    results = []
    for name in NEW_LORAS:
        path = MODELS_ROOT / "loras" / name
        exists = path.is_file()
        size = round(path.stat().st_size / 1024**3, 2) if exists else 0.0
        results.append(ModelTestResult(
            name=name,
            directory="loras",
            kind="lora",
            on_disk=exists,
            path=str(path),
            size_gb=size,
        ))
    return results


def test_mmaudio_models() -> list[ModelTestResult]:
    """测试 MMAudio 所需模型是否存在。"""
    results = []
    for name in MMAUDIO_REQUIRED_MODELS:
        # MMAudio 模型在 models/mmaudio/ 下
        path = MODELS_ROOT / "mmaudio" / name
        exists = path.is_file()
        size = round(path.stat().st_size / 1024**3, 2) if exists else 0.0
        results.append(ModelTestResult(
            name=name,
            directory="mmaudio",
            kind="mmaudio",
            on_disk=exists,
            path=str(path),
            size_gb=size,
            notes="MMAudio 工作流必需" if not exists else "",
        ))
    for name in MMAUDIO_OPTIONAL_MODELS:
        path = MODELS_ROOT / "mmaudio" / name
        exists = path.is_file()
        size = round(path.stat().st_size / 1024**3, 2) if exists else 0.0
        results.append(ModelTestResult(
            name=name,
            directory="mmaudio",
            kind="mmaudio_optional",
            on_disk=exists,
            path=str(path),
            size_gb=size,
            notes="MMAudioBatch/NSFW RIFE 当前引用；缺失时需在工作流里切换为标准主模型",
        ))
    # 也检查 mmaudio 目录是否存在
    if not (MODELS_ROOT / "mmaudio").is_dir():
        results.append(ModelTestResult(
            name="[目录] mmaudio/",
            directory="mmaudio",
            kind="mmaudio",
            on_disk=False,
            path=str(MODELS_ROOT / "mmaudio"),
            notes="MMAudio 模型目录不存在，需手动创建",
        ))
    return results


def _rife_vfi_paths(name: str) -> list[Path]:
    return [
        MODELS_ROOT / "rife" / name,
        CUSTOM_NODES_ROOT / "ComfyUI-VFI" / "rife" / "train_log" / name,
        CUSTOM_NODES_ROOT / "ComfyUI-VFI" / "models" / name,
    ]


def test_rife_vfi_models() -> list[ModelTestResult]:
    """测试 ComfyUI-VFI/RIFEInterpolation 节点所需 flownet.pkl。"""
    results = []
    for name in RIFE_VFI_REQUIRED_MODELS:
        candidates = _rife_vfi_paths(name)
        existing = [path for path in candidates if path.is_file()]
        path = existing[0] if existing else candidates[0]
        size = round(path.stat().st_size / 1024**3, 2) if existing else 0.0
        results.append(ModelTestResult(
            name=name,
            directory="rife / ComfyUI-VFI train_log",
            kind="rife_vfi",
            on_disk=bool(existing),
            path=str(path),
            size_gb=size,
            notes="RIFEInterpolation 节点必需；可由节点下载脚本自动下载 RIFEv4.26_0921.zip 后提取",
        ))
    return results


def test_all_new_models() -> dict[str, Any]:
    """汇总所有新增模型的测试结果。"""
    all_results = {
        "checkpoints": [r.__dict__ for r in test_new_checkpoints()],
        "diffusion_models": [r.__dict__ for r in test_new_diffusion_models()],
        "loras": [r.__dict__ for r in test_new_loras()],
        "mmaudio": [r.__dict__ for r in test_mmaudio_models()],
        "rife_vfi": [r.__dict__ for r in test_rife_vfi_models()],
    }

    # 计算统计
    total = 0
    present = 0
    for cat in all_results.values():
        for r in cat:
            total += 1
            if r.get("on_disk"):
                present += 1

    all_results["summary"] = {
        "total": total,
        "present": present,
        "missing": total - present,
    }
    return all_results
