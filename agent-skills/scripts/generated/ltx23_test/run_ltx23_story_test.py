from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path("D:/ComfyUI-aki-v3")
DEFAULT_SERVER = "http://127.0.0.1:8188"
DEFAULT_WORKFLOW = PROJECT_ROOT / "agent-skills/comfyui/workflows/TEST/LTX2.3最强漫剧工作流包含音频参考 (1).json"
DEFAULT_PROMPT_PACK = PROJECT_ROOT / "agent-projects/manga-anime-pipeline/runtime/2026-05-15_test_projects_short_manga/review/optimized_prompt_pack.json"
DEFAULT_RUNTIME_ROOT = PROJECT_ROOT / "agent-skills/comfyui/runtime/ltx23_story_test"
DEFAULT_SEGMENT_LENGTHS = [39, 39, 39, 38, 38]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LTX 2.3 story workflow with prompts derived from the short manga materials.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--prompt-pack", type=Path, default=DEFAULT_PROMPT_PACK)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    parser.add_argument("--seed", type=int, default=608936875)
    parser.add_argument("--prompt-mode", choices=["story", "original"], default="story")
    parser.add_argument("--timeout", type=int, default=3600)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_prompt_fragments(values: list[str]) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in value.split(","):
            fragment = part.strip()
            if not fragment:
                continue
            lowered = fragment.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            merged.append(fragment)
    return ", ".join(merged)


def resolve_material_path(prompt_pack_path: Path, raw_path: str) -> str:
    normalized = Path(raw_path.replace("\\", "/"))
    if normalized.is_absolute() and normalized.exists():
        return str(normalized)

    workspace_candidate = PROJECT_ROOT / normalized
    if workspace_candidate.exists():
        return str(workspace_candidate)

    runtime_anchor = next((parent for parent in prompt_pack_path.parents if parent.name.lower() == "runtime"), None)
    if runtime_anchor is not None:
        project_candidate = runtime_anchor.parent / normalized
        if project_candidate.exists():
            return str(project_candidate)

    raise FileNotFoundError(f"素材文件不存在: {raw_path}")


def build_story_materials(prompt_pack_path: Path, prompt_pack: dict[str, Any]) -> dict[str, Any]:
    shots = prompt_pack["shots"]
    characters = prompt_pack["characters"]
    character_bits = "; ".join(str(item["continuity_prompt"]) for item in characters)
    global_prompt = (
        "High quality anime short film, Japanese school slice of life romance, strong character consistency across all shots, "
        "expressive but restrained facial acting, clean line art, soft cel shading, cinematic continuity, subtle motion, "
        "stable anatomy, no readable generated text, character continuity: "
        f"{character_bits}"
    )

    segment_prompts = [
        str(shots[0]["optimized_positive_prompt"]),
        str(shots[0]["optimized_positive_prompt"]) + ", closer emotional beat, sustained eye contact, gentle continuation, no scene cut",
        str(shots[1]["optimized_positive_prompt"]),
        str(shots[1]["optimized_positive_prompt"]) + ", maintain the lifting pose, restrained movement, gentle emotional transition, no scene cut",
        str(shots[2]["optimized_positive_prompt"]),
    ]

    negative_prompt = merge_prompt_fragments(
        [str(shot["optimized_negative_prompt"]) for shot in shots]
        + [str(character["negative_prompt"]) for character in characters]
    )

    image_paths = [
        resolve_material_path(prompt_pack_path, str(shots[0]["input_image_path"])),
        resolve_material_path(prompt_pack_path, str(shots[0]["input_image_path"])),
        resolve_material_path(prompt_pack_path, str(shots[1]["input_image_path"])),
        resolve_material_path(prompt_pack_path, str(shots[1]["input_image_path"])),
        resolve_material_path(prompt_pack_path, str(shots[2]["input_image_path"])),
    ]

    return {
        "global_prompt": global_prompt,
        "segment_prompts": segment_prompts,
        "segment_lengths": list(DEFAULT_SEGMENT_LENGTHS),
        "negative_prompt": negative_prompt,
        "image_paths": image_paths,
        "shot_ids": [str(shot["shot_id"]) for shot in shots],
    }


def build_timeline_data(prompts: list[str], lengths: list[int]) -> str:
    colors = [
        "hsl(295, 55%, 55%)",
        "hsl(73, 55%, 55%)",
        "hsl(210, 55%, 55%)",
        "hsl(348, 55%, 55%)",
        "hsl(125, 55%, 55%)",
    ]
    payload = {
        "segments": [
            {
                "prompt": prompt,
                "length": length,
                "color": colors[index % len(colors)],
            }
            for index, (prompt, length) in enumerate(zip(prompts, lengths, strict=True))
        ]
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def convert_workflow(server: str, workflow_path: Path) -> dict[str, Any]:
    response = requests.post(f"{server}/workflow/convert", json=read_json(workflow_path), timeout=180)
    response.raise_for_status()
    return response.json()


def patch_workflow(
    workflow: dict[str, Any],
    *,
    prompt_mode: str,
    global_prompt: str,
    segment_prompts: list[str],
    segment_lengths: list[int],
    negative_prompt: str,
    image_paths: list[str],
    seed: int,
    output_prefix: str,
) -> dict[str, Any]:
    promptrelay_patched = False
    negative_patched = False
    multiimage_patched = False
    sampler_patched = False
    savevideo_patched = False

    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.setdefault("inputs", {})

        if class_type == "PromptRelayEncodeTimeline" and prompt_mode == "story":
            inputs["global_prompt"] = global_prompt
            inputs["max_frames"] = sum(segment_lengths)
            inputs["timeline_data"] = build_timeline_data(segment_prompts, segment_lengths)
            inputs["local_prompts"] = " | ".join(segment_prompts)
            inputs["segment_lengths"] = ", ".join(str(length) for length in segment_lengths)
            promptrelay_patched = True
            continue

        if class_type == "CLIPTextEncode" and prompt_mode == "story":
            text_value = str(inputs.get("text", ""))
            if "subtitles" in text_value.lower() or "watermark" in text_value.lower():
                inputs["text"] = negative_prompt
                negative_patched = True
            continue

        if class_type == "MultiImageLoader" and "image_paths" in inputs:
            inputs["image_paths"] = "\n".join(image_paths)
            multiimage_patched = True
            continue

        if class_type == "SamplerCustom" and "noise_seed" in inputs:
            inputs["noise_seed"] = seed
            sampler_patched = True
            continue

        if class_type == "SaveVideo" and "filename_prefix" in inputs:
            inputs["filename_prefix"] = output_prefix
            savevideo_patched = True

    if prompt_mode == "story" and not promptrelay_patched:
        raise RuntimeError("PromptRelayEncodeTimeline 节点未找到，无法注入剧情时间线。")
    if prompt_mode == "story" and not negative_patched:
        raise RuntimeError("负向 CLIPTextEncode 节点未找到，无法注入负向提示词。")
    if not multiimage_patched:
        raise RuntimeError("MultiImageLoader 节点未找到，无法注入素材关键帧。")
    if not sampler_patched:
        raise RuntimeError("SamplerCustom 节点未找到，无法注入 seed。")
    if not savevideo_patched:
        raise RuntimeError("SaveVideo 节点未找到，无法改写输出前缀。")

    return workflow


def submit_prompt(server: str, workflow: dict[str, Any], *, client_id: str, notes: str) -> str:
    payload = {
        "prompt": workflow,
        "client_id": client_id,
        "extra_data": {
            "agent": "copilot",
            "workflow_name": "ltx23_story_test",
            "source": "agent-skills/scripts/generated/ltx23_test/run_ltx23_story_test.py",
            "notes": notes,
        },
    }
    response = requests.post(f"{server}/prompt", json=payload, timeout=180)
    response.raise_for_status()
    data = response.json()
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"/prompt 未返回 prompt_id: {json.dumps(data, ensure_ascii=False)}")
    return str(prompt_id)


def wait_for_history(server: str, prompt_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = requests.get(f"{server}/history/{prompt_id}", timeout=60)
        response.raise_for_status()
        history = response.json()
        entry = history.get(prompt_id)
        if entry:
            return entry
        time.sleep(5)
    raise TimeoutError(f"等待 prompt_id={prompt_id} 完成超时。")


def extract_output_paths(history_entry: dict[str, Any]) -> list[str]:
    results: list[str] = []
    outputs = history_entry.get("outputs") or {}
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        for items in node_output.values():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                filename = item.get("filename")
                if not filename:
                    continue
                subfolder = str(item.get("subfolder") or "")
                output_path = PROJECT_ROOT / "ComfyUI/output" / subfolder / str(filename)
                results.append(str(output_path))
    deduped: list[str] = []
    seen: set[str] = set()
    for item in results:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def main() -> int:
    args = parse_args()
    prompt_pack = read_json(args.prompt_pack)
    story_materials = build_story_materials(args.prompt_pack, prompt_pack)

    run_id = uuid.uuid4().hex[:8]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    runtime_dir = args.runtime_root / f"{stamp}_{run_id}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    output_prefix = f"agent_skills/ltx23_story_test/{stamp}_{run_id}/ltx23_story_ep001"

    workflow = convert_workflow(args.server, args.workflow)
    patched_workflow = patch_workflow(
        workflow,
        prompt_mode=args.prompt_mode,
        global_prompt=story_materials["global_prompt"],
        segment_prompts=story_materials["segment_prompts"],
        segment_lengths=story_materials["segment_lengths"],
        negative_prompt=story_materials["negative_prompt"],
        image_paths=story_materials["image_paths"],
        seed=args.seed,
        output_prefix=output_prefix,
    )

    patched_workflow_path = runtime_dir / "patched_api_workflow.json"
    patched_workflow_path.write_text(json.dumps(patched_workflow, ensure_ascii=False, indent=2), encoding="utf-8")

    client_id = f"agent:copilot|workflow:ltx23_story_test|run:{run_id}"
    notes = "; ".join(
        [
            f"workflow={args.workflow}",
            f"prompt_pack={args.prompt_pack}",
            f"prompt_mode={args.prompt_mode}",
            f"shot_ids={','.join(story_materials['shot_ids'])}",
            f"segment_lengths={story_materials['segment_lengths']}",
            f"seed={args.seed}",
            f"output_prefix={output_prefix}",
            f"image_paths={story_materials['image_paths']}",
            (
                "patched=PromptRelayEncodeTimeline.global_prompt/local_prompts/timeline_data, CLIPTextEncode.text, "
                "MultiImageLoader.image_paths, SamplerCustom.noise_seed, SaveVideo.filename_prefix"
                if args.prompt_mode == "story"
                else "patched=MultiImageLoader.image_paths, SamplerCustom.noise_seed, SaveVideo.filename_prefix"
            ),
        ]
    )

    prompt_id = submit_prompt(args.server, patched_workflow, client_id=client_id, notes=notes)
    history_entry = wait_for_history(args.server, prompt_id, args.timeout)
    output_files = extract_output_paths(history_entry)

    record = {
        "server": args.server,
        "workflow_path": str(args.workflow),
        "prompt_pack_path": str(args.prompt_pack),
        "runtime_dir": str(runtime_dir),
        "client_id": client_id,
        "prompt_id": prompt_id,
        "seed": args.seed,
        "prompt_mode": args.prompt_mode,
        "segment_lengths": story_materials["segment_lengths"],
        "shot_ids": story_materials["shot_ids"],
        "image_paths": story_materials["image_paths"],
        "output_prefix": output_prefix,
        "output_files": output_files,
        "status": history_entry.get("status", {}),
        "patched_api_workflow": str(patched_workflow_path),
        "global_prompt": story_materials["global_prompt"] if args.prompt_mode == "story" else None,
        "segment_prompts": story_materials["segment_prompts"] if args.prompt_mode == "story" else None,
        "negative_prompt": story_materials["negative_prompt"] if args.prompt_mode == "story" else None,
    }
    record_path = runtime_dir / "run_record.json"
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())