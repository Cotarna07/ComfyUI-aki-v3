"""MMAudio 调参批量测试 —— 针对同一视频测试多组 prompt / cfg / model，输出对比结果。"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path("D:/ComfyUI-aki-v3")
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
RUNNER = PROJECT_ROOT / "agent-projects/comfyui-test-instance/scripts/generated/mmaudio/run_nsfw_mmaudio_rife_demo.py"
RESULTS_DIR = PROJECT_ROOT / "agent-projects/comfyui-test-instance/runtime/tuning/mmaudio"
INPUT_VIDEO = PROJECT_ROOT / "ComfyUI/output/CMS-26-5-1_pose/ComfyUI_00089_.mp4"

# ── 测试矩阵 ──────────────────────────────────────────────
NSFW_MODEL = "mmaudio_large_44k_nsfw_gold_8.5k_final_fp16.safetensors"
STANDARD_MODEL = "mmaudio_large_44k_v2_fp16.safetensors"

PROMPTS = {
    "nsfw-direct": "intense moaning, heavy breathing, wet sounds, passionate erotic audio, sensual vocalizations",
    "nsfw-descriptive": "slow rhythmic moaning matching body movements, soft breathing between thrusts, wet intimate sounds, erotic vocal expressions synchronized with motion",
    "nsfw-short": "moaning, heavy breathing, wet sounds",
    "nsfw-whisper": "breathy whispers, soft moaning, gentle wet sounds, intimate breathing close to microphone",
}

# Phase 1: compare prompts (NSFW model, cfg=5.0, steps=25)
PHASE1 = [
    {"label": f"prompt-{key}", "prompt": text, "mmaudio_model": NSFW_MODEL, "cfg": 5.0, "steps": 25}
    for key, text in PROMPTS.items()
]

# Phase 2: compare CFG values (best prompt from phase 1, NSFW model)
PHASE2 = [
    {"label": f"cfg-{cfg}", "prompt": PROMPTS["nsfw-descriptive"], "mmaudio_model": NSFW_MODEL, "cfg": cfg, "steps": 25}
    for cfg in [3.0, 7.0, 10.0]
]

# Phase 3: compare model variants (best prompt + cfg from phase 1+2)
PHASE3 = [
    {"label": "model-standard", "prompt": PROMPTS["nsfw-descriptive"], "mmaudio_model": STANDARD_MODEL, "cfg": 5.0, "steps": 25},
    {"label": "model-nsfw", "prompt": PROMPTS["nsfw-descriptive"], "mmaudio_model": NSFW_MODEL, "cfg": 5.0, "steps": 25},
]

ALL_PHASES = [("phase1-prompts", PHASE1), ("phase2-cfg", PHASE2), ("phase3-models", PHASE3)]


def run_one(phase: str, cfg: dict, run_index: int) -> dict | None:
    label = cfg["label"]
    output_prefix = f"agent-tests/tuning/{phase}/{label}"
    cmd = [
        str(PYTHON), str(RUNNER),
        "--server-url", "http://127.0.0.1:8190",
        "--input-video", str(INPUT_VIDEO),
        "--output-prefix", output_prefix,
        "--prompt", cfg["prompt"],
        "--negative-prompt", "music, singing, speech, dialogue, silence, noise, distortion, clicks, hum, static",
        "--steps", str(cfg["steps"]),
        "--cfg", str(cfg["cfg"]),
        "--force-rate", "16.0",
        "--video-format", "video/nvenc_h264-mp4",
        "--video-bitrate", "10",
        "--mmaudio-model", cfg["mmaudio_model"],
        "--timeout", "1800",
    ]
    print(f"\n{'='*60}")
    print(f"[{run_index}] {phase}/{label}")
    print(f"  prompt: {cfg['prompt'][:80]}...")
    print(f"  cfg: {cfg['cfg']}, steps: {cfg['steps']}, model: {cfg['mmaudio_model']}")
    print(f"{'='*60}")

    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=2000)
    elapsed = time.time() - start

    record = {
        "phase": phase,
        "label": label,
        "config": cfg,
        "elapsed_sec": round(elapsed, 1),
        "returncode": result.returncode,
        "stdout": result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout,
        "stderr": result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    if result.returncode == 0:
        # Try to parse JSON summary from last line
        for line in reversed(result.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    record["summary"] = json.loads(line)
                except json.JSONDecodeError:
                    pass
                break
        print(f"  ✓ OK  ({elapsed:.0f}s)")
    else:
        print(f"  ✗ FAILED (rc={result.returncode}, {elapsed:.0f}s)")
        print(f"  stderr tail: {result.stderr[-500:]}")

    return record


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_index = 0
    all_records: list[dict] = []

    for phase_name, phase_configs in ALL_PHASES:
        for cfg in phase_configs:
            run_index += 1
            record = run_one(phase_name, cfg, run_index)
            if record:
                all_records.append(record)
            # Brief cool-down between runs
            time.sleep(3)

    # Save summary
    summary_path = RESULTS_DIR / f"tuning-summary-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    summary_path.write_text(json.dumps(all_records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSummary saved to {summary_path}")
    print(f"Total runs: {len(all_records)}, success: {sum(1 for r in all_records if r['returncode'] == 0)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
