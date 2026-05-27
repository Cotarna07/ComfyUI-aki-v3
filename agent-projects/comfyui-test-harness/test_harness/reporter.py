# 报告生成模块：控制台输出 + Markdown 文件
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .config import REPORTS_DIR


CST = timezone(timedelta(hours=8))


def _icon(severity: str) -> str:
    return {"error": "❌", "warning": "⚠️", "ok": "✅", "info": "ℹ️"}.get(severity, "❓")


def print_header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_subheader(title: str) -> None:
    print(f"\n── {title} ──")


def report_preflight(server_info: dict, node_info: dict, model_census: dict) -> None:
    """输出预检报告到控制台。"""
    print_header("预检报告")

    # 服务器
    if server_info["online"]:
        print(f"  ComfyUI 服务: ✅ 在线 (v{server_info['version']})")
        print(f"  GPU: {server_info['gpu']}")
        if server_info["vram_total_gb"]:
            print(f"  VRAM: {server_info['vram_free_gb']} / {server_info['vram_total_gb']} GB 可用")
    else:
        print(f"  ComfyUI 服务: ⚠️ 离线 ({server_info.get('error', 'unknown')})")
        print(f"  → 只能执行结构校验，无法进行模型加载和实际运行测试")

    # 节点
    if node_info["online"]:
        print(f"\n  已注册节点类型: {node_info['count']}")
    else:
        print(f"\n  节点清单: ⚠️ 无法获取 ({node_info.get('error', 'unknown')})")
        print(f"  → 工作流节点类型校验将跳过")

    # 模型概况
    print(f"\n  模型目录概况:")
    total_files = 0
    total_gb = 0.0
    for dirname, info in sorted(model_census.items()):
        cnt = info["file_count"]
        gb = info["total_size_gb"]
        if cnt > 0:
            marker = "🆕" if dirname in ("mmaudio",) and cnt == 0 else ("  " if gb < 1 else "")
            print(f"    {dirname:25s}: {cnt:4d} 个文件, {gb:7.2f} GB")
            total_files += cnt
            total_gb += gb
        elif dirname in ("mmaudio", "audio_encoders", "frame_interpolation"):
            print(f"    {dirname:25s}: ⚪ 空目录（当前重点测试未必需要）")
    print(f"    {'─' * 50}")
    print(f"    {'合计':25s}: {total_files:4d} 个文件, {total_gb:7.2f} GB")


def report_workflow_validation(results: list[dict]) -> None:
    """输出工作流校验报告。"""
    print_header("工作流校验报告")

    passed = sum(1 for r in results if r["score"] == "PASS")
    warned = sum(1 for r in results if r["score"] == "WARN")
    failed = sum(1 for r in results if r["score"] == "FAIL")
    skipped = sum(1 for r in results if r["score"] == "SKIP")

    print(f"  总计: {len(results)} 个工作流")
    print(f"  ✅ PASS: {passed}  |  ⚠️ WARN: {warned}  |  ❌ FAIL: {failed}  |  ⏭️ SKIP: {skipped}")
    print()

    for r in results:
        name = Path(r["path"]).name
        score_icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭️", "unknown": "❓"}[r["score"]]
        print(f"  {score_icon} [{r['score']:5s}] {name}  (节点:{r['node_count']}, 链接:{r['link_count']}, 模型引用:{len(r['model_refs'])})")

        # 打印具体问题
        for issue in r["issues"]:
            if issue["severity"] == "ok":
                continue
            icon = _icon(issue["severity"])
            msg = issue.get("message", "?")
            # 截断过长消息
            if len(msg) > 120:
                msg = msg[:117] + "..."
            print(f"      {icon} {msg}")

    print()


def report_model_tests(results: dict) -> None:
    """输出模型测试报告。"""
    print_header("新增模型检查报告")
    s = results["summary"]
    print(f"  总计: {s['total']} 个  |  ✅ 存在: {s['present']}  |  ❌ 缺失: {s['missing']}")

    for category, items in results.items():
        if category == "summary":
            continue
        if not items:
            continue
        print_subheader(f"{category} ({len(items)} 个)")
        for item in items:
            icon = "✅" if item.get("on_disk") else "❌"
            name = item.get("name", "?")
            size = f"{item.get('size_gb', 0):.2f} GB" if item.get("on_disk") else "N/A"
            notes = item.get("notes", "")
            note_str = f" — {notes}" if notes else ""
            print(f"    {icon} {name} [{size}]{note_str}")


def write_markdown_report(
    server_info: dict,
    node_info: dict,
    model_census: dict,
    workflow_results: list[dict],
    model_results: dict,
    output_path: Path | None = None,
) -> Path:
    """生成完整的 Markdown 测试报告。"""
    if output_path is None:
        timestamp = datetime.now(CST).strftime("%Y%m%d-%H%M%S")
        output_path = REPORTS_DIR / f"test-report-{timestamp}.md"

    ts = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S CST")
    lines: list[str] = []

    lines.append(f"# ComfyUI 测试报告")
    lines.append(f"")
    lines.append(f"> 生成时间：{ts}")
    lines.append(f"> 服务器状态：{'🟢 在线' if server_info['online'] else '🔴 离线'}")
    lines.append(f"")

    # ── 预检摘要 ──
    lines.append("## 一、预检摘要")
    lines.append("")
    if server_info["online"]:
        lines.append(f"- **ComfyUI**: v{server_info['version']}")
        lines.append(f"- **GPU**: {server_info['gpu']}")
        lines.append(f"- **VRAM**: {server_info.get('vram_free_gb', '?')} / {server_info.get('vram_total_gb', '?')} GB")
        lines.append(f"- **节点类型**: {node_info['count']} 个")
    else:
        lines.append(f"- **ComfyUI**: 离线（{server_info.get('error', '未知错误')}）")
        lines.append(f"- **模式**: 仅结构校验，未执行模型加载/运行测试")
    lines.append("")

    # ── 模型概况 ──
    lines.append("## 二、模型目录概况")
    lines.append("")
    lines.append("| 目录 | 文件数 | 大小 (GB) | 状态 |")
    lines.append("|------|--------|-----------|------|")
    for dirname, info in sorted(model_census.items()):
        cnt = info["file_count"]
        gb = info["total_size_gb"]
        if cnt > 0:
            status = "✅"
        elif dirname in ("mmaudio", "audio_encoders", "frame_interpolation"):
            status = "⚪ 空（当前重点测试未必需要）"
        else:
            status = "⚪ 空"
        lines.append(f"| {dirname} | {cnt} | {gb:.2f} | {status} |")
    lines.append("")

    # ── 工作流校验 ──
    lines.append("## 三、工作流校验")
    lines.append("")
    passed = sum(1 for r in workflow_results if r["score"] == "PASS")
    warned = sum(1 for r in workflow_results if r["score"] == "WARN")
    failed = sum(1 for r in workflow_results if r["score"] == "FAIL")
    skipped = sum(1 for r in workflow_results if r["score"] == "SKIP")
    lines.append(f"| 状态 | 数量 |")
    lines.append(f"|------|------|")
    lines.append(f"| ✅ PASS | {passed} |")
    lines.append(f"| ⚠️ WARN | {warned} |")
    lines.append(f"| ❌ FAIL | {failed} |")
    lines.append(f"| ⏭️ SKIP | {skipped} |")
    lines.append(f"| **合计** | **{len(workflow_results)}** |")
    lines.append("")

    for r in workflow_results:
        name = Path(r["path"]).name
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭️"}[r["score"]]
        lines.append(f"### {icon} {name}")
        lines.append(f"- 节点: {r['node_count']}, 链接: {r['link_count']}, 模型引用: {len(r['model_refs'])}")
        lines.append(f"- 路径: `{r['path']}`")
        for issue in r["issues"]:
            if issue["severity"] == "ok":
                continue
            sev_icon = _icon(issue["severity"])
            lines.append(f"  - {sev_icon} {issue.get('message', '?')}")
        lines.append("")

    # ── 新增模型检查 ──
    lines.append("## 四、新增模型检查")
    lines.append("")
    s = model_results["summary"]
    lines.append(f"- **总计**: {s['total']} 个")
    lines.append(f"- **已存在**: {s['present']} 个")
    lines.append(f"- **缺失**: {s['missing']} 个")
    lines.append("")

    for category, items in model_results.items():
        if category == "summary" or not items:
            continue
        lines.append(f"### {category}")
        lines.append("")
        lines.append("| 状态 | 模型名 | 大小 | 备注 |")
        lines.append("|------|--------|------|------|")
        for item in items:
            icon = "✅" if item.get("on_disk") else "❌"
            name = item.get("name", "?")
            size = f"{item.get('size_gb', 0):.2f} GB" if item.get("on_disk") else "N/A"
            notes = item.get("notes", "-")
            lines.append(f"| {icon} | {name} | {size} | {notes} |")
        lines.append("")

    # ── 结论 ──
    lines.append("## 五、结论与建议")
    lines.append("")
    if failed == 0 and s["missing"] == 0:
        lines.append("✅ 所有工作流校验通过，所有新增模型就位。可以开始实际运行测试。")
    else:
        if s["missing"] > 0:
            lines.append(f"🔴 **{s['missing']} 个重点模型缺失**，会影响对应工作流的实际运行。")
            lines.append(f"   详见 `agent-skills/docs/2026-05-16_本地资源全景盘点.md` 五-B 章节获取下载链接或替代方案。")
        if failed > 0:
            lines.append(f"🔴 **{failed} 个工作流校验失败**，存在节点类型缺失或模型引用错误。")
        if warned > 0:
            lines.append(f"⚠️ **{warned} 个工作流有警告**，参数可能超出预期范围。")
        if failed == 0 and warned == 0:
            lines.append("✅ 已校验的工作流结构完整，可进入实际运行阶段。")
    lines.append("")

    # 写入文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
