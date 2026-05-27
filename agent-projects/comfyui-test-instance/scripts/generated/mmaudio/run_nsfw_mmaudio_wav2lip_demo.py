from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

from run_nsfw_mmaudio_rife_demo import (
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_SERVER_URL,
    DEFAULT_WORKFLOW,
    apply_overrides,
    convert_workflow,
    extract_output_files,
    load_json,
    submit_prompt,
    unload_all_models,
    wait_for_history,
)


PROJECT_ROOT = Path("D:/ComfyUI-aki-v3")
DEFAULT_WAV_DIR = PROJECT_ROOT / "agent-projects/comfyui-test-instance/runtime/wav2lip"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MMAudio first, then use Wav2Lip to align the mouth with the generated audio.")
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL)
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--input-video", type=Path, required=True)
    parser.add_argument("--mmaudio-output-prefix", default="agent-tests/mmaudio-wav2lip/mmaudio")
    parser.add_argument("--lipsync-output-prefix", default="agent-tests/mmaudio-wav2lip/final")
    parser.add_argument("--prompt", default="slow rhythmic moaning matching body movements, soft breathing between thrusts, wet intimate sounds, erotic vocal expressions synchronized with motion")
    parser.add_argument("--negative-prompt", default="music, singing, speech, dialogue, silence, noise, distortion, clicks, hum, static")
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--cfg", type=float, default=7.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--force-rate", type=float, default=16.0)
    parser.add_argument("--video-format", default="video/nvenc_h264-mp4")
    parser.add_argument("--video-bitrate", type=int, default=10)
    parser.add_argument("--mmaudio-model", default="mmaudio_large_44k_nsfw_gold_8.5k_final_fp16.safetensors")
    parser.add_argument("--lipsync-mode", choices=["sequential", "repetitive"], default="sequential")
    parser.add_argument("--face-detect-batch", type=int, default=4)
    parser.add_argument("--lipsync-frame-rate", type=float, default=30.0)
    parser.add_argument("--wav-dir", type=Path, default=DEFAULT_WAV_DIR)
    parser.add_argument("--timeout", type=int, default=1800)
    return parser.parse_args()


def ensure_success(history_entry: dict, stage_name: str) -> None:
    status = history_entry.get("status", {})
    if status.get("status_str") != "success":
        raise RuntimeError(f"{stage_name} failed: {json.dumps(status, ensure_ascii=False)}")


def choose_primary_mp4(paths: list[Path]) -> Path:
    for path in paths:
        if path.suffix.lower() == ".mp4":
            return path
    raise FileNotFoundError(f"No mp4 output found in: {[str(path) for path in paths]}")


def extract_audio_to_wav(source_video: Path, output_wav: Path) -> None:
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_video),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_wav),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = result.stderr[-2000:] if result.stderr else ""
        raise RuntimeError(f"ffmpeg audio extraction failed: {tail}")


def run_mmaudio_stage(args: argparse.Namespace, seed: int, stage_output_prefix: str) -> Path:
    workflow = load_json(args.workflow)
    prompt_graph = convert_workflow(args.server_url, workflow)
    notes = apply_overrides(
        prompt_graph,
        input_video=args.input_video,
        output_prefix=stage_output_prefix,
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
    notes.append("post_process=wav2lip")

    client_id = f"agent:copilot|workflow:nsfw-mmaudio-rife|run:{seed % 1000000:06d}|stage:mmaudio"
    try:
        submit_result = submit_prompt(
            args.server_url,
            prompt_graph,
            client_id=client_id,
            workflow_name=args.workflow.stem,
            notes=notes,
        )
        prompt_id = submit_result.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"MMAudio prompt submission did not return prompt_id: {json.dumps(submit_result, ensure_ascii=False)}")

        print(f"MMAudio prompt_id: {prompt_id}")
        history_entry = wait_for_history(args.server_url, prompt_id, args.timeout)
        ensure_success(history_entry, "mmaudio")
        return choose_primary_mp4(extract_output_files(history_entry, DEFAULT_OUTPUT_ROOT))
    finally:
        unload_all_models(args.server_url)


def build_wav2lip_graph(*, video_path: Path, audio_path: Path, output_prefix: str, face_detect_batch: int, lipsync_mode: str, lipsync_frame_rate: float, video_format: str, video_bitrate: int) -> dict:
    return {
        "1": {
            "class_type": "VHS_LoadVideoFFmpegPath",
            "inputs": {
                "video": str(video_path),
                "force_rate": 0,
                "custom_width": 0,
                "custom_height": 0,
                "frame_load_cap": 0,
                "start_time": 0,
            },
        },
        "2": {
            "class_type": "VHS_LoadAudio",
            "inputs": {
                "audio_file": str(audio_path),
                "seek_seconds": 0,
                "duration": 0,
            },
        },
        "3": {
            "class_type": "Wav2Lip",
            "inputs": {
                "images": ["1", 0],
                "mode": lipsync_mode,
                "face_detect_batch": face_detect_batch,
                "audio": ["2", 0],
            },
        },
        "4": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["3", 0],
                "frame_rate": lipsync_frame_rate,
                "loop_count": 0,
                "filename_prefix": output_prefix,
                "format": video_format,
                "pingpong": False,
                "save_output": True,
                "audio": ["3", 1],
                "pix_fmt": "yuv420p",
                "bitrate": video_bitrate,
                "megabit": True,
            },
        },
    }


def run_wav2lip_stage(args: argparse.Namespace, *, seed: int, video_path: Path, audio_path: Path, stage_output_prefix: str) -> Path:
    prompt_graph = build_wav2lip_graph(
        video_path=video_path,
        audio_path=audio_path,
        output_prefix=stage_output_prefix,
        face_detect_batch=args.face_detect_batch,
        lipsync_mode=args.lipsync_mode,
        lipsync_frame_rate=args.lipsync_frame_rate,
        video_format=args.video_format,
        video_bitrate=args.video_bitrate,
    )
    notes = [
        f"source_video={video_path}",
        f"audio_path={audio_path}",
        f"output_prefix={stage_output_prefix}",
        f"lipsync_mode={args.lipsync_mode}",
        f"face_detect_batch={args.face_detect_batch}",
        f"frame_rate={args.lipsync_frame_rate}",
    ]
    client_id = f"agent:copilot|workflow:nsfw-mmaudio-wav2lip|run:{seed % 1000000:06d}|stage:wav2lip"

    try:
        submit_result = submit_prompt(
            args.server_url,
            prompt_graph,
            client_id=client_id,
            workflow_name="nsfw-mmaudio-wav2lip",
            notes=notes,
        )
        prompt_id = submit_result.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"Wav2Lip prompt submission did not return prompt_id: {json.dumps(submit_result, ensure_ascii=False)}")

        print(f"Wav2Lip prompt_id: {prompt_id}")
        history_entry = wait_for_history(args.server_url, prompt_id, args.timeout)
        ensure_success(history_entry, "wav2lip")
        return choose_primary_mp4(extract_output_files(history_entry, DEFAULT_OUTPUT_ROOT))
    finally:
        unload_all_models(args.server_url)


def main() -> int:
    args = parse_args()
    args.input_video = args.input_video.resolve()
    if not args.input_video.is_file():
        print(f"Input video not found: {args.input_video}", file=sys.stderr)
        return 1

    seed = args.seed if args.seed is not None else random.randrange(1, 2**63 - 1)
    stem = args.input_video.stem.lower()
    mmaudio_prefix = f"{args.mmaudio_output_prefix}/{stem}"
    lipsync_prefix = f"{args.lipsync_output_prefix}/{stem}"

    mmaudio_video = run_mmaudio_stage(args, seed, mmaudio_prefix)
    wav_path = args.wav_dir / f"{stem}-mmaudio.wav"
    extract_audio_to_wav(mmaudio_video, wav_path)
    lipsync_video = run_wav2lip_stage(
        args,
        seed=seed,
        video_path=mmaudio_video,
        audio_path=wav_path,
        stage_output_prefix=lipsync_prefix,
    )

    summary = {
        "seed": seed,
        "input_video": str(args.input_video),
        "mmaudio_video": str(mmaudio_video),
        "wav_audio": str(wav_path),
        "lipsync_video": str(lipsync_video),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())