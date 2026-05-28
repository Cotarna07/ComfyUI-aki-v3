"""Build the local Wan 2.2 5B manga workflow from the installed wrapper example."""

from __future__ import annotations

import json
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[5]
PROJECT = WORKSPACE / "agent-projects" / "WhatDreamsCost-ComfyUI"
SOURCE = (
    WORKSPACE
    / "ComfyUI"
    / "custom_nodes"
    / "ComfyUI-WanVideoWrapper"
    / "example_workflows"
    / "wanvideo_2_2_5B_I2V_example_WIP.json"
)
COMPAT_OUTPUT = (
    PROJECT
    / "example_workflows"
    / "Wan2.2首尾帧漫剧完整工作流包含音频参考.json"
)
CANONICAL_OUTPUT = (
    WORKSPACE
    / "agent-skills"
    / "comfyui"
    / "workflows"
    / "02-project"
    / "whatdreamscost-comfyui"
    / "Wan2.2-5B本地漫剧工作流包含音频参考.json"
)

MODEL_NAME = r"WanVideo\2_2\wan2.2_ti2v_5B_fp16.safetensors"
VAE_NAME = r"wanvideo\Wan2_2_VAE_bf16.safetensors"
TEXT_ENCODER_NAME = "umt5-xxl-enc-bf16.safetensors"


def node(workflow: dict, node_id: int) -> dict:
    return next(item for item in workflow["nodes"] if item["id"] == node_id)


def unlink(workflow: dict, link_id: int) -> None:
    workflow["links"] = [link for link in workflow["links"] if link[0] != link_id]
    for item in workflow["nodes"]:
        for output in item.get("outputs", []):
            if output.get("links"):
                output["links"] = [
                    current for current in output["links"] if current != link_id
                ] or None
        for input_item in item.get("inputs", []):
            if input_item.get("link") == link_id:
                input_item["link"] = None


def connect(
    workflow: dict,
    source_id: int,
    source_slot: int,
    target_id: int,
    target_slot: int,
    link_type: str,
) -> int:
    link_id = max((link[0] for link in workflow["links"]), default=0) + 1
    workflow["links"].append(
        [link_id, source_id, source_slot, target_id, target_slot, link_type]
    )
    source_output = node(workflow, source_id)["outputs"][source_slot]
    source_output["links"] = (source_output.get("links") or []) + [link_id]
    node(workflow, target_id)["inputs"][target_slot]["link"] = link_id
    return link_id


def remove_nodes(workflow: dict, node_ids: set[int]) -> None:
    for link in list(workflow["links"]):
        if link[1] in node_ids or link[3] in node_ids:
            unlink(workflow, link[0])
    workflow["nodes"] = [
        item for item in workflow["nodes"] if item["id"] not in node_ids
    ]


def next_node_id(workflow: dict) -> int:
    return max(item["id"] for item in workflow["nodes"]) + 1


def make_note(note_id: int, pos: list[int], text: str, title: str) -> dict:
    return {
        "id": note_id,
        "type": "Note",
        "pos": pos,
        "size": [420, 148],
        "flags": {},
        "order": note_id,
        "mode": 0,
        "inputs": [],
        "outputs": [],
        "title": title,
        "properties": {},
        "widgets_values": [text],
        "color": "#432",
        "bgcolor": "#653",
    }


def add_audio_output(workflow: dict) -> None:
    audio_id = next_node_id(workflow)
    workflow["nodes"].append(
        {
            "id": audio_id,
            "type": "LoadAudio",
            "pos": [1850, 1120],
            "size": [320, 120],
            "flags": {},
            "order": audio_id,
            "mode": 0,
            "inputs": [],
            "outputs": [{"name": "AUDIO", "type": "AUDIO", "links": None}],
            "title": "配音或音乐音轨（仅封装入输出）",
            "properties": {"Node name for S&R": "LoadAudio"},
            "widgets_values": [""],
            "color": "#233",
            "bgcolor": "#355",
        }
    )
    output = node(workflow, 92)
    if len(output["inputs"]) < 2:
        raise ValueError("VHS_VideoCombine in the source workflow has no audio input")
    connect(workflow, audio_id, 0, 92, 1, "AUDIO")


def build_workflow() -> dict:
    with SOURCE.open("r", encoding="utf-8") as handle:
        workflow = json.load(handle)

    workflow["version"] = 0.4
    workflow["last_node_id"] = max(item["id"] for item in workflow["nodes"])
    workflow["last_link_id"] = max(link[0] for link in workflow["links"])

    model = node(workflow, 22)
    model["title"] = "Wan 2.2 TI2V 5B（16 GB 本地预览）"
    model["widgets_values"] = [
        MODEL_NAME,
        "fp16_fast",
        "disabled",
        "offload_device",
        "sdpa",
    ]

    t5 = node(workflow, 11)
    t5["title"] = "UMT5 文本编码器（本机已有）"
    t5["widgets_values"] = [
        TEXT_ENCODER_NAME,
        "bf16",
        "offload_device",
        "disabled",
    ]

    vae = node(workflow, 38)
    vae["title"] = "Wan 2.2 VAE（按插件示例路径安装）"
    vae["widgets_values"] = [VAE_NAME, "bf16"]

    start_image = node(workflow, 58)
    start_image["title"] = "起始分镜图（5B 有效条件输入）"
    start_image["widgets_values"] = ["", "image"]

    resize = node(workflow, 71)
    resize["title"] = "输入图缩放到 832 x 480"
    resize["widgets_values"][0:2] = [832, 480]

    latent = node(workflow, 78)
    latent["title"] = "本地预览尺寸：832 x 480 / 81 帧"
    latent["widgets_values"] = [832, 480, 81]

    prompt = node(workflow, 16)
    prompt["title"] = "漫剧镜头提示词"
    prompt["widgets_values"][0] = (
        "anime cinematic scene, clean lineart, expressive character acting, "
        "consistent costume and face, natural blinking and breathing, subtle hair "
        "and cloth motion, smooth camera movement, preserve the composition and "
        "character identity of the starting storyboard frame"
    )
    prompt["widgets_values"][1] = (
        "text, subtitles, watermark, logo, extra people, malformed hands, deformed "
        "face, duplicated limbs, flicker, jitter, frame tearing, heavy blur, low "
        "quality, static image, abrupt camera jump"
    )

    sampler = node(workflow, 27)
    sampler["title"] = "Wan 5B 采样（质量预览）"

    output = node(workflow, 92)
    output["title"] = "输出 MP4（合并配音或音乐）"
    output["widgets_values"].update(
        {
            "frame_rate": 16,
            "filename_prefix": "Wan2.2_5B_Manga_Local_Audio",
            "save_output": True,
            "trim_to_audio": False,
        }
    )
    output["widgets_values"].pop("videopreview", None)

    # Remove vendor demonstration branches and optional compile wiring from the
    # deliverable canvas so every executable node belongs to the default route.
    remove_nodes(workflow, {35, 46, 48, 49, 50, 51})

    add_audio_output(workflow)
    note_texts = [
        (
            "本地验证版：RTX 5070 Ti 16 GB\n"
            "- Wan 2.2 TI2V 5B 单模型路线\n"
            "- 默认 832 x 480 / 81 帧 / 16 fps\n"
            "- 起始分镜会参与当前镜头生成",
            "本地版说明",
            [80, 1200],
        ),
        (
            "重要限制：5B 路线不等同于旧版 14B 首尾帧引导。\n"
            "本画布只保留可执行的起始图入口；请将上一镜头\n"
            "末帧作为下一镜头的起始图来保持衔接。",
            "首尾帧差异",
            [520, 1200],
        ),
        (
            "音轨仅在 VHS 输出节点中封装进 MP4，\n"
            "不会驱动口型或动作。口型同步需要另接流程。",
            "音频说明",
            [960, 1200],
        ),
        (
            "首次运行需安装插件示例对应权重：\n"
            "diffusion_models/WanVideo/2_2/wan2.2_ti2v_5B_fp16.safetensors\n"
            "vae/wanvideo/Wan2_2_VAE_bf16.safetensors\n"
            "UMT5 文本编码器本机已有。",
            "模型依赖",
            [1400, 1280],
        ),
    ]
    for text, title, pos in note_texts:
        note_id = next_node_id(workflow)
        workflow["nodes"].append(make_note(note_id, pos, text, title))

    workflow["last_node_id"] = max(item["id"] for item in workflow["nodes"])
    workflow["last_link_id"] = max(link[0] for link in workflow["links"])
    workflow.setdefault("extra", {})["wan_manga_notes"] = {
        "route": "Wan 2.2 TI2V 5B local preview, single starting-frame conditioning",
        "device_target": "NVIDIA GeForce RTX 5070 Ti 16 GB",
        "effective_inputs": ["start_image", "prompt", "optional_audio_mux"],
        "reference_only_inputs": ["end_frame_storyboard_outside_execution_graph"],
        "audio_drives_motion": False,
        "defaults": {"width": 832, "height": 480, "frames": 81, "fps": 16},
        "required_models": {
            "diffusion_model": MODEL_NAME,
            "vae": VAE_NAME,
            "text_encoder": TEXT_ENCODER_NAME,
        },
        "upgrade_path": "Move back to the Wan 2.2 A14B first/last-frame workflow on rented GPU for final-quality evaluation.",
    }
    return workflow


def write_workflow(path: Path, workflow: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(workflow, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    workflow = build_workflow()
    for output in (COMPAT_OUTPUT, CANONICAL_OUTPUT):
        write_workflow(output, workflow)
        print(output)


if __name__ == "__main__":
    main()
