from __future__ import annotations

import json
from pathlib import Path


WORKFLOW_PATH = Path(
    r"D:\ComfyUI-aki-v3\agent-skills\comfyui\workflows\TEST\去水印，去字幕，去模糊，高清LTX2.3+iclora+insight工作流.json"
)

UNET_NODE_ID = 3940
AUDIO_VAE_NODE_ID = 4010
DISTILL_LORA_NODE_ID = 4922
CLIP_NODE_ID = 5023
VIDEO_VAE_NODE_ID = 990001
VIDEO_VAE_LINK_IDS = [13279, 13405, 13658, 13683]


def _find_node(nodes: list[dict], node_id: int) -> tuple[int, dict]:
    for index, node in enumerate(nodes):
        if node.get("id") == node_id:
            return index, node
    raise ValueError(f"Node {node_id} not found")


def main() -> None:
    data = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    nodes: list[dict] = data["nodes"]
    links: list[list] = data["links"]

    unet_index, unet_node = _find_node(nodes, UNET_NODE_ID)
    audio_vae_index, audio_vae_node = _find_node(nodes, AUDIO_VAE_NODE_ID)
    distill_lora_index, distill_lora_node = _find_node(nodes, DISTILL_LORA_NODE_ID)
    clip_index, clip_node = _find_node(nodes, CLIP_NODE_ID)

    nodes[unet_index] = {
        "outputs": [
            {
                "name": "MODEL",
                "links": [13217],
                "label": "MODEL",
                "type": "MODEL",
                "localized_name": "MODEL",
            }
        ],
        "color": "#223",
        "widgets_values": [
            "ltx-2.3-22b-dev_transformer_only_fp8_scaled.safetensors",
            "default",
        ],
        "inputs": [
            {
                "widget": {"name": "unet_name"},
                "name": "unet_name",
                "label": "unet_name",
                "type": "COMBO",
                "localized_name": "unet_name",
            },
            {
                "widget": {"name": "weight_dtype"},
                "name": "weight_dtype",
                "label": "weight_dtype",
                "type": "COMBO",
                "localized_name": "weight_dtype",
            },
        ],
        "flags": unet_node.get("flags", {}),
        "type": "UNETLoader",
        "mode": unet_node.get("mode", 0),
        "bgcolor": "#335",
        "size": [592.15625, 110],
        "pos": unet_node["pos"],
        "id": UNET_NODE_ID,
        "properties": {
            "Node name for S&R": "UNETLoader",
            "widget_ue_connectable": {
                "weight_dtype": True,
                "unet_name": True,
            },
        },
        "order": unet_node.get("order", 0),
    }

    nodes[audio_vae_index] = {
        "outputs": [
            {
                "label": "VAE",
                "name": "VAE",
                "type": "VAE",
                "links": [13274],
            }
        ],
        "color": "#322",
        "widgets_values": [
            "LTX23_audio_vae_bf16.safetensors",
            "main_device",
            "bf16",
        ],
        "inputs": [
            {
                "label": "vae_name",
                "name": "vae_name",
                "type": "COMBO",
                "widget": {"name": "vae_name"},
            },
            {
                "label": "device",
                "name": "device",
                "type": "COMBO",
                "widget": {"name": "device"},
            },
            {
                "label": "weight_dtype",
                "name": "weight_dtype",
                "type": "COMBO",
                "widget": {"name": "weight_dtype"},
            },
        ],
        "flags": audio_vae_node.get("flags", {}),
        "order": audio_vae_node.get("order", 0),
        "mode": audio_vae_node.get("mode", 0),
        "size": [482.9375, 175.328125],
        "pos": audio_vae_node["pos"],
        "id": AUDIO_VAE_NODE_ID,
        "type": "VAELoaderKJ",
        "properties": {
            "Node name for S&R": "VAELoaderKJ",
            "cnr_id": "comfyui-kjnodes",
            "ver": "01d9fa9c983273532cacdf9532c74a93c7dc86d2",
            "ue_properties": {
                "widget_ue_connectable": {},
                "input_ue_unconnectable": {},
                "version": "7.8",
            },
            "widget_ue_connectable": {
                "weight_dtype": True,
                "device": True,
                "vae_name": True,
            },
        },
        "color": "#322",
        "bgcolor": "#533",
    }

    distill_lora_node["widgets_values"][0] = "ltx-2.3-22b-distilled-lora-384-1.1.safetensors"
    nodes[distill_lora_index] = distill_lora_node

    nodes[clip_index] = {
        "outputs": [
            {
                "label": "CLIP",
                "name": "CLIP",
                "type": "CLIP",
                "links": [13459, 13460],
            }
        ],
        "color": "#223",
        "widgets_values": [
            "gemma_3_12B_it_fp8_e4m3fn.safetensors",
            "ltx-2.3_text_projection_bf16.safetensors",
            "ltxv",
            "default",
        ],
        "inputs": [
            {
                "label": "clip_name1",
                "name": "clip_name1",
                "type": "COMBO",
                "widget": {"name": "clip_name1"},
            },
            {
                "label": "clip_name2",
                "name": "clip_name2",
                "type": "COMBO",
                "widget": {"name": "clip_name2"},
            },
            {
                "label": "type",
                "name": "type",
                "type": "COMBO",
                "widget": {"name": "type"},
            },
            {
                "label": "device",
                "name": "device",
                "type": "COMBO",
                "widget": {"name": "device"},
            },
        ],
        "flags": clip_node.get("flags", {}),
        "order": clip_node.get("order", 0),
        "mode": clip_node.get("mode", 0),
        "size": [420, 126],
        "pos": clip_node["pos"],
        "id": CLIP_NODE_ID,
        "type": "DualCLIPLoader",
        "properties": {
            "Node name for S&R": "DualCLIPLoader",
            "widget_ue_connectable": {
                "clip_name1": True,
                "clip_name2": True,
                "type": True,
                "device": True,
            },
        },
        "bgcolor": "#335",
    }

    video_vae_node = {
        "id": VIDEO_VAE_NODE_ID,
        "type": "VAELoaderKJ",
        "pos": [102.51716613769531, 680.4957885742188],
        "size": [482.9375, 175.328125],
        "flags": {},
        "order": 8,
        "mode": 0,
        "inputs": [
            {
                "label": "vae_name",
                "name": "vae_name",
                "type": "COMBO",
                "widget": {"name": "vae_name"},
            },
            {
                "label": "device",
                "name": "device",
                "type": "COMBO",
                "widget": {"name": "device"},
            },
            {
                "label": "weight_dtype",
                "name": "weight_dtype",
                "type": "COMBO",
                "widget": {"name": "weight_dtype"},
            },
        ],
        "outputs": [
            {
                "label": "VAE",
                "name": "VAE",
                "type": "VAE",
                "links": VIDEO_VAE_LINK_IDS,
            }
        ],
        "properties": {
            "Node name for S&R": "VAELoaderKJ",
            "cnr_id": "comfyui-kjnodes",
            "ver": "01d9fa9c983273532cacdf9532c74a93c7dc86d2",
            "ue_properties": {
                "widget_ue_connectable": {},
                "input_ue_unconnectable": {},
                "version": "7.8",
            },
            "widget_ue_connectable": {
                "weight_dtype": True,
                "device": True,
                "vae_name": True,
            },
        },
        "widgets_values": [
            "LTX23_video_vae_bf16.safetensors",
            "main_device",
            "bf16",
        ],
        "color": "#322",
        "bgcolor": "#533",
    }

    try:
        existing_video_vae_index, _ = _find_node(nodes, VIDEO_VAE_NODE_ID)
    except ValueError:
        nodes.insert(audio_vae_index, video_vae_node)
    else:
        nodes[existing_video_vae_index] = video_vae_node

    for link in links:
        if link[0] in VIDEO_VAE_LINK_IDS:
            link[1] = VIDEO_VAE_NODE_ID
            link[2] = 0

    data["last_node_id"] = max(data.get("last_node_id", 0), VIDEO_VAE_NODE_ID)

    WORKFLOW_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent="\t") + "\n",
        encoding="utf-8",
    )
    print(WORKFLOW_PATH)


if __name__ == "__main__":
    main()