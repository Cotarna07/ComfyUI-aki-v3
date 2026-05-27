from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path("D:/ComfyUI-aki-v3")
SERVER_URL = "http://127.0.0.1:8190"
INSTANCE_ROOT = PROJECT_ROOT / "agent-projects/comfyui-test-instance/runtime/instance"
OUTPUT_ROOT = INSTANCE_ROOT / "output"
RUNTIME_ROOT = PROJECT_ROOT / "agent-projects/comfyui-test-instance/runtime/audio-workflow-tests"

WORKFLOWS = {
    "nsfw-mmaudio-rife": PROJECT_ROOT / "agent-skills/comfyui/workflows/03-source/imported/nsfw-mmaudio-rife/MMAudio.json",
    "mmaudio-batch": PROJECT_ROOT / "agent-skills/comfyui/workflows/03-source/imported/mmaudio-batch/MMAudioBatchPSv1.json",
    "mmaudio-kiss-sfx-autocaption": PROJECT_ROOT
    / "agent-skills/comfyui/workflows/03-source/imported/mmaudio-kiss-sfx-autocaption/MM Audio AUTO CAPTION 2.5.json",
}

DEFAULT_VIDEOS = [
    PROJECT_ROOT / "ComfyUI/output/CMS-26-5-1_pose/ComfyUI_00089_.mp4",
    PROJECT_ROOT / "ComfyUI/output/CMS-26-5-1_pose/ComfyUI_00090_.mp4",
    PROJECT_ROOT / "ComfyUI/output/CMS-26-5-1_pose/ComfyUI_00091_.mp4",
]

NSFW_MODEL = "mmaudio_large_44k_nsfw_gold_8.5k_final_fp16.safetensors"
STANDARD_MODEL = "mmaudio_large_44k_v2_fp16.safetensors"

TEST_PROMPT = (
    "motion-synced breathing, fabric rustle, room tone, soft impacts, subtle body movement sounds, "
    "natural non-musical sound effects"
)
TEST_NEGATIVE_PROMPT = "music, singing, dialogue, narration, lyrics, distortion, static, clipping, silence"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run imported MMAudio-related workflows against three local videos.")
    parser.add_argument("--server-url", default=SERVER_URL)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--cfg", type=float, default=5.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--video-format", default="video/nvenc_h264-mp4")
    parser.add_argument("--video-bitrate", type=int, default=10)
    parser.add_argument("--skip-autocaption", action="store_true")
    return parser.parse_args()


def load_workflow(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def convert_workflow(server_url: str, workflow_path: Path) -> dict[str, Any]:
    response = requests.post(f"{server_url}/workflow/convert", json=load_workflow(workflow_path), timeout=120)
    response.raise_for_status()
    return response.json()


def submit_prompt(server_url: str, prompt_graph: dict[str, Any], *, client_id: str, workflow_name: str, notes: list[str]) -> str:
    payload = {
        "prompt": prompt_graph,
        "client_id": client_id,
        "extra_data": {
            "agent": "codex",
            "workflow_name": workflow_name,
            "source": "agent-projects/comfyui-test-instance/scripts/generated/mmaudio/test_imported_audio_workflows.py",
            "notes": "; ".join(notes),
        },
    }
    response = requests.post(f"{server_url}/prompt", json=payload, timeout=120)
    response.raise_for_status()
    result = response.json()
    prompt_id = result.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"Prompt submission did not return prompt_id: {json.dumps(result, ensure_ascii=False)}")
    return str(prompt_id)


def wait_for_history(server_url: str, prompt_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_snapshot = ""
    while time.time() < deadline:
        response = requests.get(f"{server_url}/history/{prompt_id}", timeout=60)
        response.raise_for_status()
        history = response.json()
        entry = history.get(prompt_id)
        if entry:
            return entry

        queue_response = requests.get(f"{server_url}/queue", timeout=60)
        queue_response.raise_for_status()
        last_snapshot = json.dumps(queue_response.json(), ensure_ascii=False)
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for prompt {prompt_id}; last queue snapshot={last_snapshot}")


def extract_output_files(history_entry: dict[str, Any]) -> list[Path]:
    found: list[Path] = []
    for node_output in history_entry.get("outputs", {}).values():
        if not isinstance(node_output, dict):
            continue
        for items in node_output.values():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                fullpath = item.get("fullpath")
                if fullpath:
                    found.append(Path(fullpath))
                    continue
                filename = item.get("filename")
                if not filename:
                    continue
                subfolder = item.get("subfolder") or ""
                found.append(OUTPUT_ROOT / subfolder / filename)

    deduped: list[Path] = []
    seen: set[str] = set()
    for path in found:
        key = str(path)
        if key not in seen:
            deduped.append(path)
            seen.add(key)
    return deduped


def unload_models(server_url: str) -> None:
    try:
        response = requests.post(f"{server_url}/free", json={"unload_models": True}, timeout=30)
        response.raise_for_status()
    except Exception as exc:
        print(f"Model unload failed (non-fatal): {exc}", file=sys.stderr)


def ensure_inputs() -> tuple[list[Path], Path, dict[Path, str]]:
    copied_for_batch = RUNTIME_ROOT / "input-batch"
    copied_for_batch.mkdir(parents=True, exist_ok=True)
    input_subfolder = INSTANCE_ROOT / "input/agent-tests/audio-workflow-tests"
    input_subfolder.mkdir(parents=True, exist_ok=True)

    relative_loadvideo_files: dict[Path, str] = {}
    copied_batch_paths: list[Path] = []
    for source in DEFAULT_VIDEOS:
        if not source.is_file():
            raise FileNotFoundError(source)
        batch_target = copied_for_batch / source.name
        loadvideo_target = input_subfolder / source.name
        shutil.copy2(source, batch_target)
        shutil.copy2(source, loadvideo_target)
        copied_batch_paths.append(batch_target)
        relative_loadvideo_files[source] = f"agent-tests/audio-workflow-tests/{source.name}"
    return copied_batch_paths, copied_for_batch, relative_loadvideo_files


def apply_video_combine_settings(inputs: dict[str, Any], *, output_prefix: str, video_format: str, video_bitrate: int) -> None:
    inputs["filename_prefix"] = output_prefix
    inputs["format"] = video_format
    inputs["save_output"] = True
    inputs["pix_fmt"] = "yuv420p"
    if "nvenc" in video_format:
        inputs["bitrate"] = video_bitrate
        inputs["megabit"] = True
        inputs.pop("crf", None)


def apply_mmaudio_sampler_settings(inputs: dict[str, Any], *, seed: int, steps: int, cfg: float) -> None:
    inputs["steps"] = steps
    inputs["cfg"] = cfg
    inputs["seed"] = seed
    inputs["negative_prompt"] = TEST_NEGATIVE_PROMPT
    inputs["mask_away_clip"] = False
    inputs["force_offload"] = False


def run_graph(
    args: argparse.Namespace,
    *,
    workflow_name: str,
    graph: dict[str, Any],
    seed: int,
    notes: list[str],
) -> dict[str, Any]:
    client_id = f"agent:codex|workflow:{workflow_name}|run:{seed % 1000000:06d}"
    start = time.time()
    prompt_id = submit_prompt(
        args.server_url,
        graph,
        client_id=client_id,
        workflow_name=workflow_name,
        notes=notes,
    )
    print(f"[{workflow_name}] submitted prompt_id={prompt_id}")
    try:
        history_entry = wait_for_history(args.server_url, prompt_id, args.timeout)
    finally:
        unload_models(args.server_url)
    elapsed = round(time.time() - start, 1)
    outputs = extract_output_files(history_entry)
    return {
        "workflow": workflow_name,
        "prompt_id": prompt_id,
        "client_id": client_id,
        "elapsed_sec": elapsed,
        "status": history_entry.get("status", {}),
        "outputs": [str(path) for path in outputs],
        "notes": notes,
    }


def build_nsfw_rife_graph(args: argparse.Namespace, *, input_video: Path, seed: int, output_prefix: str) -> tuple[dict[str, Any], list[str]]:
    graph = convert_workflow(args.server_url, WORKFLOWS["nsfw-mmaudio-rife"])
    remove_nodes: list[str] = []
    for node_id, node in graph.items():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.setdefault("inputs", {})
        if class_type == "VHS_LoadVideoFFmpegPath":
            inputs["video"] = str(input_video)
            inputs["force_rate"] = 16.0
        elif class_type == "MMAudioModelLoader":
            inputs["mmaudio_model"] = NSFW_MODEL
        elif class_type == "MMAudioSampler":
            apply_mmaudio_sampler_settings(inputs, seed=seed, steps=args.steps, cfg=args.cfg)
            inputs["prompt"] = TEST_PROMPT
        elif class_type == "VHS_VideoCombine":
            if "audio" in inputs:
                apply_video_combine_settings(
                    inputs,
                    output_prefix=output_prefix,
                    video_format=args.video_format,
                    video_bitrate=args.video_bitrate,
                )
            else:
                remove_nodes.append(str(node_id))
    for node_id in remove_nodes:
        graph.pop(node_id, None)
    notes = [
        f"input_video={input_video}",
        f"output_prefix={output_prefix}",
        f"prompt={TEST_PROMPT}",
        f"negative_prompt={TEST_NEGATIVE_PROMPT}",
        f"steps={args.steps}",
        f"cfg={args.cfg}",
        f"seed={seed}",
        f"mmaudio_model={NSFW_MODEL}",
        "force_rate=16.0",
        f"video_format={args.video_format}",
    ]
    if remove_nodes:
        notes.append(f"removed_nodes={','.join(remove_nodes)}")
    return graph, notes


def build_batch_graph(
    args: argparse.Namespace,
    *,
    input_directory: Path,
    seed: int,
    output_prefix_root: str,
    batch_id: str = "apple",
) -> tuple[dict[str, Any], list[str]]:
    graph = convert_workflow(args.server_url, WORKFLOWS["mmaudio-batch"])
    removable_nodes: list[str] = []
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.setdefault("inputs", {})
        if class_type in {
            "CR Integer To String",
            "ShowText|pysssss",
            "CR Float Input Switch JK",
            "PrimitiveString",
            "Text Concatenate",
            "PrimitiveFloat",
            "SimpleToggleNode",
        }:
            removable_nodes.append(next(node_id for node_id, candidate in graph.items() if candidate is node))
            continue
        if class_type == "For Each Filename [DVB]":
            inputs["id"] = batch_id
            inputs["directory"] = str(input_directory)
            inputs["pattern"] = "*.mp4"
        elif class_type == "VHS_LoadVideoPath":
            inputs["force_rate"] = 16.0
        elif class_type == "MMAudioModelLoader":
            inputs["mmaudio_model"] = STANDARD_MODEL
        elif class_type == "MMAudioSampler":
            apply_mmaudio_sampler_settings(inputs, seed=seed, steps=args.steps, cfg=args.cfg)
            inputs["prompt"] = TEST_PROMPT
        elif class_type == "VHS_VideoCombine":
            inputs["filename_prefix"] = f"{output_prefix_root}/batch"
            inputs["format"] = args.video_format
            inputs["save_output"] = True
            inputs["pix_fmt"] = "yuv420p"
            if "nvenc" in args.video_format:
                inputs["bitrate"] = args.video_bitrate
                inputs["megabit"] = True
                inputs.pop("crf", None)
    for node_id in removable_nodes:
        graph.pop(node_id, None)
    notes = [
        f"input_directory={input_directory}",
        f"batch_id={batch_id}",
        "pattern=*.mp4",
        f"output_prefix={output_prefix_root}/batch",
        f"prompt={TEST_PROMPT}",
        f"negative_prompt={TEST_NEGATIVE_PROMPT}",
        f"steps={args.steps}",
        f"cfg={args.cfg}",
        f"seed={seed}",
        f"mmaudio_model={STANDARD_MODEL}",
        "force_rate=16.0",
        f"video_format={args.video_format}",
        f"removed_nodes={','.join(removable_nodes)}",
    ]
    return graph, notes


def build_autocaption_graph(
    args: argparse.Namespace,
    *,
    loadvideo_file: str,
    seed: int,
    output_prefix: str,
) -> tuple[dict[str, Any], list[str]]:
    graph = convert_workflow(args.server_url, WORKFLOWS["mmaudio-kiss-sfx-autocaption"])
    removable_nodes: list[str] = []
    for node_id, node in graph.items():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.setdefault("inputs", {})
        if class_type in {"PreviewAny", "PreviewImage"}:
            removable_nodes.append(str(node_id))
            continue
        if class_type == "easy cleanGpuUsed" and inputs.get("anything") == ["133", 0]:
            removable_nodes.append(str(node_id))
            continue
        if class_type == "LoadVideo":
            inputs["file"] = loadvideo_file
        elif class_type == "MMAudioModelLoader":
            inputs["mmaudio_model"] = STANDARD_MODEL
        elif class_type == "MMAudioSampler":
            apply_mmaudio_sampler_settings(inputs, seed=seed, steps=args.steps, cfg=args.cfg)
        elif class_type == "Florence2Run":
            inputs["seed"] = seed
        elif class_type == "OllamaChat":
            inputs["system"] = (
                "Convert scene descriptions into concise sound-effect cues only. "
                "Describe plausible audible motion, breathing, fabric, impacts, and room tone. "
                "Avoid dialogue, lyrics, music, and explicit wording. Output short comma-separated tags."
            )
        elif class_type == "StringConcatenate":
            inputs["string_a"] = "natural motion sound effects, room tone, "
        elif class_type == "VHS_VideoCombine":
            apply_video_combine_settings(
                inputs,
                output_prefix=output_prefix,
                video_format=args.video_format,
                video_bitrate=args.video_bitrate,
            )
    for node_id in removable_nodes:
        graph.pop(node_id, None)
    notes = [
        f"loadvideo_file={loadvideo_file}",
        f"output_prefix={output_prefix}",
        f"negative_prompt={TEST_NEGATIVE_PROMPT}",
        f"steps={args.steps}",
        f"cfg={args.cfg}",
        f"seed={seed}",
        f"mmaudio_model={STANDARD_MODEL}",
        "ollama_system=neutral_sfx_tags",
        "manual_prompt_prefix=natural motion sound effects, room tone",
        f"video_format={args.video_format}",
        f"removed_nodes={','.join(removable_nodes)}",
    ]
    return graph, notes


def probe_media(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,duration,sample_rate,channels",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {"exists": True, "probe_error": result.stderr[-1000:]}
    data = json.loads(result.stdout)
    data["exists"] = True
    return data


def main() -> int:
    args = parse_args()
    copied_batch_paths, batch_dir, loadvideo_files = ensure_inputs()
    print(f"Prepared {len(copied_batch_paths)} input files in {batch_dir}")

    base_seed = args.seed if args.seed is not None else random.randrange(1, 2**63 - 1)
    started_at = datetime.now().strftime("%Y%m%d-%H%M%S")
    results: list[dict[str, Any]] = []

    for index, input_video in enumerate(DEFAULT_VIDEOS):
        seed = base_seed + index
        output_prefix = f"agent-tests/audio-workflow-tests/nsfw-mmaudio-rife/{input_video.stem.lower()}"
        graph, notes = build_nsfw_rife_graph(args, input_video=input_video, seed=seed, output_prefix=output_prefix)
        results.append(run_graph(args, workflow_name="nsfw-mmaudio-rife", graph=graph, seed=seed, notes=notes))

    batch_seed = base_seed + 100
    graph, notes = build_batch_graph(
        args,
        input_directory=batch_dir,
        seed=batch_seed,
        output_prefix_root="agent-tests/audio-workflow-tests/mmaudio-batch",
    )
    results.append(run_graph(args, workflow_name="mmaudio-batch", graph=graph, seed=batch_seed, notes=notes))

    if not args.skip_autocaption:
        for index, input_video in enumerate(DEFAULT_VIDEOS):
            seed = base_seed + 200 + index
            output_prefix = f"agent-tests/audio-workflow-tests/mmaudio-kiss-sfx-autocaption/{input_video.stem.lower()}"
            graph, notes = build_autocaption_graph(
                args,
                loadvideo_file=loadvideo_files[input_video],
                seed=seed,
                output_prefix=output_prefix,
            )
            results.append(
                run_graph(args, workflow_name="mmaudio-kiss-sfx-autocaption", graph=graph, seed=seed, notes=notes)
            )

    for result in results:
        result["media_probe"] = {path: probe_media(Path(path)) for path in result.get("outputs", [])}

    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    summary_path = RUNTIME_ROOT / f"summary-{started_at}.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary_path": str(summary_path), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
