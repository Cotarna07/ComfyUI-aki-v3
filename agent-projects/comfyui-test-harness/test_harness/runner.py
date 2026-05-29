# 测试编排器：协调预检、校验、模型测试、报告生成
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import (
    USER_WORKFLOWS_ROOT,
    API_WORKFLOWS_ROOT,
    IMPORTED_WORKFLOWS_ROOT,
    FOCUS_WORKFLOWS,
    NEW_WORKFLOWS,
)
from .preflight import check_server, get_node_inventory, full_model_census
from .workflow_validator import validate_workflow
from .model_tester import test_all_new_models
from .reporter import (
    report_preflight,
    report_workflow_validation,
    report_model_tests,
    write_markdown_report,
)


def _is_probable_workflow(path: Path) -> bool:
    if path.suffix.lower() != ".json":
        return False
    name = path.name.lower()
    if name in {"config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"}:
        return False
    if name.endswith("_config.json") or name.endswith(".index.json"):
        return False
    return True


def _collect_from_explicit_path(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if _is_probable_workflow(path) else []
    if path.is_dir():
        return [item for item in sorted(path.rglob("*.json")) if _is_probable_workflow(item)]
    return []


def collect_workflow_paths(scope: str = "focus", explicit_paths: list[Path] | None = None) -> list[Path]:
    """收集需要校验的工作流路径。focus 只测近期重点；all 才做全库巡检。"""
    paths: list[Path] = []

    if explicit_paths:
        for explicit_path in explicit_paths:
            paths.extend(_collect_from_explicit_path(explicit_path))
        return list(dict.fromkeys(paths))

    if scope == "focus":
        for path in FOCUS_WORKFLOWS:
            if path.is_file() and _is_probable_workflow(path):
                paths.append(path)
        return list(dict.fromkeys(paths))

    # 1. 新增导入工作流（优先级最高）
    for p in NEW_WORKFLOWS:
        if p.is_file():
            if _is_probable_workflow(p):
                paths.append(p)

    # 2. 技能包 API 工作流
    if API_WORKFLOWS_ROOT.is_dir():
        for f in sorted(API_WORKFLOWS_ROOT.glob("*.json")):
            if _is_probable_workflow(f):
                paths.append(f)

    # 3. 技能包导入工作流子目录
    if IMPORTED_WORKFLOWS_ROOT.is_dir():
        for f in sorted(IMPORTED_WORKFLOWS_ROOT.rglob("*.json")):
            if f not in paths:
                if _is_probable_workflow(f):
                    paths.append(f)

    # 4. 用户工作流（只取优先级目录中的几个代表）
    if USER_WORKFLOWS_ROOT.is_dir():
        # 只取根目录下的 JSON 文件和一级子目录下的前几个 JSON
        for f in sorted(USER_WORKFLOWS_ROOT.glob("*.json")):
            if _is_probable_workflow(f):
                paths.append(f)
        # 只采样部分子目录
        for sub in sorted(USER_WORKFLOWS_ROOT.rglob("*.json")):
            if sub.parent != USER_WORKFLOWS_ROOT:
                if len([p for p in paths if p.parent == sub.parent]) < 5:
                    if _is_probable_workflow(sub):
                        paths.append(sub)

    return list(dict.fromkeys(paths))


def run_all_tests(scope: str = "focus", explicit_paths: list[Path] | None = None) -> dict[str, Any]:
    """执行完整测试流程，返回结果字典。"""
    results: dict[str, Any] = {
        "timestamp": "",
        "server": {},
        "node_inventory": {},
        "model_census": {},
        "workflow_results": [],
        "model_results": {},
        "report_path": "",
    }

    # ── 1. 预检 ──
    print("🔍 正在执行预检...")
    results["server"] = check_server()
    results["model_census"] = full_model_census()

    # 节点清单（仅在线时）
    if results["server"]["online"]:
        results["node_inventory"] = get_node_inventory()
    else:
        results["node_inventory"] = {"online": False, "node_types": {}, "count": 0}

    report_preflight(
        results["server"],
        results["node_inventory"],
        results["model_census"],
    )

    # ── 2. 工作流校验 ──
    print("📋 正在校验工作流...")
    node_types = results["node_inventory"].get("node_types", {})
    workflow_paths = collect_workflow_paths(scope=scope, explicit_paths=explicit_paths)

    for wf_path in workflow_paths:
        result = validate_workflow(wf_path, node_types if node_types else None)
        results["workflow_results"].append(result)

    # 按分数排序（FAIL 排最前）
    score_order = {"FAIL": 0, "WARN": 1, "PASS": 2, "unknown": 3}
    results["workflow_results"].sort(key=lambda r: score_order.get(r["score"], 99))

    report_workflow_validation(results["workflow_results"])

    # ── 3. 模型测试 ──
    print("🧪 正在检查新增模型...")
    results["model_results"] = test_all_new_models()
    report_model_tests(results["model_results"])

    # ── 4. 生成报告 ──
    print("\n📝 正在生成 Markdown 报告...")
    report_path = write_markdown_report(
        server_info=results["server"],
        node_info=results["node_inventory"],
        model_census=results["model_census"],
        workflow_results=results["workflow_results"],
        model_results=results["model_results"],
    )
    results["report_path"] = str(report_path)
    print(f"   报告已保存: {report_path}")

    return results
