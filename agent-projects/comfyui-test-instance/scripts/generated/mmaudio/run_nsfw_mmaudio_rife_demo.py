from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import requests


DEFAULT_SERVER_URL = "http://127.0.0.1:8190"
DEFAULT_WORKFLOW = Path("D:/ComfyUI-aki-v3/agent-skills/comfyui/workflows/03-source/imported/nsfw-mmaudio-rife/MMAudio.json")
DEFAULT_OUTPUT_ROOT = Path("D:/ComfyUI-aki-v3/agent-projects/comfyui-test-instance/runtime/instance/output")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the imported MMAudio RIFE workflow against a local test video.")
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL)
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--input-video", type=Path, required=True)
    parser.add_argument("--output-prefix", default="agent-tests/mmaudio-rife-demo")
    parser.add_argument("--prompt", default="soft synthetic ambience, gentle electronic beeps, subtle whooshes following the motion, no voices")
    parser.add_argument("--negative-prompt", default="voice, speech, dialogue, lyrics, moaning, sexual sounds, explicit sounds, screaming")
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--cfg", type=float, default=5.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--force-rate", type=float, default=16.0)
    parser.add_argument("--video-format", default="video/nvenc_h264-mp4")
    parser.add_argument("--video-bitrate", type=int, default=10)
    parser.add_argument("--mmaudio-model", default=None, help="Override MMAudio model filename (e.g. mmaudio_large_44k_nsfw_gold_8.5k_final_fp16.safetensors)")
    parser.add_argument("--client-id", default=None)
    parser.add_argument("--timeout", type=int, default=1800)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def convert_workflow(server_url: str, workflow: dict) -> dict:
    response = requests.post(f"{server_url}/workflow/convert", json=workflow, timeout=120)
    response.raise_for_status()
    return response.json()


def apply_overrides(prompt_graph: dict, *, input_video: Path, output_prefix: str, prompt_text: str, negative_prompt: str, steps: int, cfg: float, seed: int, force_rate: float, video_format: str, video_bitrate: int, mmaudio_model: str | None = None) -> list[str]:
    notes: list[str] = []
    nodes_to_remove: list[str] = []
    for node_id, node in prompt_graph.items():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.setdefault("inputs", {})

        if class_type in {"VHS_LoadVideoFFmpegPath", "VHS_LoadVideoPath"}:
            inputs["video"] = str(input_video)
            inputs["force_rate"] = force_rate

        if class_type == "MMAudioModelLoader":
            if mmaudio_model:
                inputs["mmaudio_model"] = mmaudio_model

        if class_type == "MMAudioSampler":
            inputs["steps"] = steps
            inputs["cfg"] = cfg
            inputs["seed"] = seed
            inputs["prompt"] = prompt_text
            inputs["negative_prompt"] = negative_prompt
            inputs["mask_away_clip"] = False
            inputs["force_offload"] = False

        if class_type == "VHS_VideoCombine":
            if "audio" in inputs:
                inputs["filename_prefix"] = output_prefix
                inputs["save_output"] = True
                inputs["format"] = video_format
                inputs["pix_fmt"] = "yuv420p"
                if "nvenc" in video_format:
                    inputs["bitrate"] = video_bitrate
                    inputs["megabit"] = True
                    inputs.pop("crf", None)
            else:
                nodes_to_remove.append(str(node_id))

    for node_id in nodes_to_remove:
        prompt_graph.pop(node_id, None)

    notes.append(f"input_video={input_video}")
    notes.append(f"prompt={prompt_text}")
    notes.append(f"negative_prompt={negative_prompt}")
    notes.append(f"steps={steps}")
    notes.append(f"cfg={cfg}")
    notes.append(f"seed={seed}")
    notes.append(f"force_rate={force_rate}")
    notes.append(f"output_prefix={output_prefix}")
    notes.append(f"video_format={video_format}")
    if mmaudio_model:
        notes.append(f"mmaudio_model={mmaudio_model}")
    if "nvenc" in video_format:
        notes.append(f"video_bitrate={video_bitrate}M")
    if nodes_to_remove:
        notes.append(f"removed_nodes={','.join(nodes_to_remove)}")
    return notes


def submit_prompt(server_url: str, prompt_graph: dict, *, client_id: str, workflow_name: str, notes: list[str]) -> dict:
    payload = {
        "prompt": prompt_graph,
        "client_id": client_id,
        "extra_data": {
            "agent": "copilot",
            "workflow_name": workflow_name,
            "source": "agent-projects/comfyui-test-instance/scripts/generated/mmaudio/run_nsfw_mmaudio_rife_demo.py",
            "notes": "; ".join(notes),
        },
    }
    response = requests.post(f"{server_url}/prompt", json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


def wait_for_history(server_url: str, prompt_id: str, timeout_seconds: int) -> dict:
    deadline = time.time() + timeout_seconds
    last_error: str | None = None
    while time.time() < deadline:
        response = requests.get(f"{server_url}/history/{prompt_id}", timeout=60)
        response.raise_for_status()
        history = response.json()
        if history:
            entry = history.get(prompt_id)
            if entry is None and len(history) == 1:
                entry = next(iter(history.values()))
            if entry:
                return entry

        queue_response = requests.get(f"{server_url}/queue", timeout=60)
        queue_response.raise_for_status()
        queue_data = queue_response.json()
        running = queue_data.get("queue_running") or []
        pending = queue_data.get("queue_pending") or []
        prompt_ids = json.dumps({"running": running, "pending": pending}, ensure_ascii=False)
        last_error = f"prompt_id={prompt_id} still not in history; queue snapshot={prompt_ids}"
        time.sleep(5)

    raise TimeoutError(last_error or f"Timed out waiting for prompt {prompt_id}")


def extract_output_files(history_entry: dict, output_root: Path) -> list[Path]:
    found: list[Path] = []
    outputs = history_entry.get("outputs", {})
    for _, node_output in outputs.items():
        if not isinstance(node_output, dict):
            continue
        for _, items in node_output.items():
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
                found.append(output_root / subfolder / filename)
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in found:
        key = str(path)
        if key not in seen:
            deduped.append(path)
            seen.add(key)
    return deduped


def unload_all_models(server_url: str) -> None:
    """释放 ComfyUI 中所有已加载模型，避免长时间占用显存。"""
    try:
        resp = requests.post(f"{server_url}/free", json={"unload_models": True}, timeout=30)
        resp.raise_for_status()
        print("All models unloaded.")
    except Exception as exc:
        print(f"Model unload failed (non-fatal): {exc}")


def main() -> int:
    args = parse_args()
    input_video = args.input_video.resolve()
    if not input_video.is_file():
        print(f"Input video not found: {input_video}", file=sys.stderr)
        return 1

    workflow = load_json(args.workflow)
    prompt_graph = convert_workflow(args.server_url, workflow)
    seed = args.seed if args.seed is not None else random.randrange(1, 2**63 - 1)
    notes = apply_overrides(
        prompt_graph,
        input_video=input_video,
        output_prefix=args.output_prefix,
        prompt_text=args.prompt,
        negative_prompt=args.negative_prompt,
        steps=args.steps,
        cfg=args.cfg,
        seed=seed,
        force_rate=args.force_rate,
        video_format=args.video_format,
        video_bitrate=args.video_bitrate,
        mmaudio_model=args.mmaudio_model,
    )

    client_id = args.client_id or f"agent:copilot|workflow:nsfw-mmaudio-rife|run:{seed % 1000000:06d}"
    submit_result = submit_prompt(
        args.server_url,
        prompt_graph,
        client_id=client_id,
        workflow_name=args.workflow.stem,
        notes=notes,
    )
    prompt_id = submit_result.get("prompt_id")
    if not prompt_id:
        print(json.dumps(submit_result, ensure_ascii=False, indent=2))
        raise RuntimeError("Prompt submission did not return prompt_id")

    print(f"Submitted prompt_id: {prompt_id}")
    history_entry = wait_for_history(args.server_url, prompt_id, args.timeout)
    output_files = extract_output_files(history_entry, DEFAULT_OUTPUT_ROOT)

    summary = {
        "prompt_id": prompt_id,
        "client_id": client_id,
        "status": history_entry.get("status", {}),
        "outputs": [str(path) for path in output_files],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    unload_all_models(args.server_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())