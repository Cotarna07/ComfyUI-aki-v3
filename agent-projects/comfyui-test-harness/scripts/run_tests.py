# ComfyUI 测试框架 — CLI 入口
"""用法: python scripts/run_tests.py [--quick] [--output PATH]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from test_harness.runner import run_all_tests


def main() -> None:
    parser = argparse.ArgumentParser(description="ComfyUI 资源测试框架")
    parser.add_argument("--all", action="store_true", help="全库巡检模式：会包含大量历史工作流，默认不启用")
    parser.add_argument("--output", type=Path, default=None, help="指定报告输出路径")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════╗")
    print("║     ComfyUI 资源测试框架 v1.0                    ║")
    print("║     工作流校验 · 模型检查 · 参数审计              ║")
    print("╚══════════════════════════════════════════════════╝")

    scope = "all" if args.all else "focus"
    results = run_all_tests(scope=scope)

    # 输出最终结论
    print("\n" + "=" * 60)
    failed_wf = sum(1 for r in results["workflow_results"] if r["score"] == "FAIL")
    model_missing = results["model_results"]["summary"]["missing"]

    if failed_wf == 0 and model_missing == 0:
        print("  🎉 全部通过！所有工作流和模型就绪。")
        print("  → 可以开始实际运行测试。")
    else:
        print(f"  📊 测试结果: {failed_wf} 个重点工作流失败, {model_missing} 个重点模型缺失")
        if results["server"]["online"]:
            print(f"  → 修复上述问题后可重新运行本测试。")
        else:
            print(f"  → 请启动 ComfyUI 后重新运行以获取完整报告。")

    print(f"  📄 完整报告: {results['report_path']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
