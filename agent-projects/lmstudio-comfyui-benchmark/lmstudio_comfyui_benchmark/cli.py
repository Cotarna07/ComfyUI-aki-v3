from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .runner import BenchmarkRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark LM Studio models and submit prompts to ComfyUI.")
    parser.add_argument("--config", required=True, help="Path to benchmark TOML config.")
    parser.add_argument("--run-id", default=None, help="Optional fixed run id for resumable overnight runs.")
    args = parser.parse_args(argv)

    config = load_config(Path(args.config).resolve())
    runner = BenchmarkRunner(config, run_id=args.run_id)
    run_dir = runner.run()
    print(f"测评完成，结果目录：{run_dir}")
    return 0
