#!/usr/bin/env python3
"""
生成 Wan 2.2 漫剧（漫画动画）工作流 JSON。
参考原始 LTX 2.3 漫剧工作流的结构，适配 Wan 2.2 I2V 架构。

Wan 2.2 的核心差异：
- 不需要 PromptRelay，用 WanVideoTextEncode 的 | 分隔符实现分段提示词漫游
- 不需要 LTXSequencer，用 WanVideoImageToVideoEncode 直接注入首尾帧
- WanVideoSampler 替代 KSampler（内置 scheduler/shift 控制）
- 无原生音频 VAE（音频需后续合成）

用法：
  python generate_wan22_workflow.py
输出：
    ../../../../../../agent-skills/comfyui/workflows/03-source/drafts/whatdreamscost-comfyui/Wan2.2漫剧工作流.json
"""

import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).absolute().parents[5]
OUTPUT_DIR = WORKSPACE_ROOT / "agent-skills" / "comfyui" / "workflows" / "03-source" / "drafts" / "whatdreamscost-comfyui"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "Wan2.2漫剧工作流.json"

# ── 节点工厂 ────────────────────────────────────────────

_last_node_id = 0
_last_link_id = 0

def next_id():
    global _last_node_id
    _last_node_id += 1
    return _last_node_id

def next_link():
    global _last_link_id
    _last_link_id += 1
    return _last_link_id

def node(type_, pos, size=None, mode=0, inputs=None, outputs=None, properties=None, widgets_values=None, title=None, color=None, bgcolor=None, flags=None):
    nid = next_id()
    n = {
        "id": nid, "type": type_,
        "pos": list(pos),
        "size": list(size or [315, 82]),
        "flags": flags or {},
        "order": nid,
        "mode": mode,
        "inputs": inputs or [],
        "outputs": outputs or [],
        "properties": properties or {"Node name for S&R": type_},
        "widgets_values": widgets_values or [],
    }
    if title:
        n["title"] = title
    if color:
        n["color"] = color
    if bgcolor:
        n["bgcolor"] = bgcolor
    return n

def widget_input(name, wtype, widget_name=None):
    return {"label": name, "name": name, "type": wtype, "widget": {"name": widget_name or name}}

def link_input(name, wtype, link_id):
    return {"label": name, "name": name, "type": wtype, "link": link_id, "widget": {"name": name}}

def output(name, otype, links=None):
    return {"label": name, "name": name, "type": otype, "links": links or []}

def link(from_id, from_slot, to_id, to_slot, to_slot_type):
    lid = next_link()
    return {"id": lid, "origin_id": from_id, "origin_slot": from_slot,
            "target_id": to_id, "target_slot": to_slot, "type": to_slot_type}

# ── 构建工作流 ──────────────────────────────────────────

nodes = []
links = []

# === 模型加载区 ===

# 1. WanVideoModelLoader — 加载 Wan 2.2 I2V 模型
mloader = node(
    "WanVideoModelLoader",
    pos=[-600, -200],
    size=[400, 120],
    inputs=[
        widget_input("model", "COMBO"),
        widget_input("base_precision", "COMBO"),
        widget_input("quantization", "COMBO"),
        widget_input("load_device", "COMBO"),
    ],
    outputs=[output("model", "WANVIDEOMODEL")],
    widgets_values=["wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "bf16", "fp8_e4m3fn_scaled_fast", "offload_device"],
)
nodes.append(mloader)

# 2. LoadWanVideoT5TextEncoder — 加载 T5 文本编码器
t5loader = node(
    "LoadWanVideoT5TextEncoder",
    pos=[-600, 0],
    size=[400, 100],
    inputs=[
        widget_input("t5_model", "COMBO"),
        widget_input("device", "COMBO"),
    ],
    outputs=[output("text_encoder", "WANTEXTENCODER")],
    widgets_values=["t5xxl_fp8_e4m3fn_scaled.safetensors", "offload_device"],
)
nodes.append(t5loader)

# 3. WanVideoVAELoader — 加载 VAE
vaeloader = node(
    "WanVideoVAELoader",
    pos=[-600, 160],
    size=[400, 100],
    inputs=[widget_input("vae", "COMBO")],
    outputs=[output("vae", "WANVAE")],
    widgets_values=["Wan2_1_VAE_bf16.safetensors"],
)
nodes.append(vaeloader)

# === 输入区 ===

# 4. MultiImageLoader — 加载漫剧图片
miloader = node(
    "MultiImageLoader",
    pos=[-100, -200],
    size=[860, 550],
    inputs=[
        widget_input("image_paths", "STRING"),
        link_input("width", "INT", 0),
        link_input("height", "INT", 0),
        widget_input("interpolation", "COMBO"),
        widget_input("resize_method", "COMBO"),
        widget_input("multiple_of", "INT"),
        widget_input("img_compression", "INT"),
    ],
    outputs=[output("multi_output", "IMAGE"), output("image_1", "IMAGE"),
             output("image_2", "IMAGE"), output("image_3", "IMAGE")],
    widgets_values=["", 1280, 720, "bilinear", "stretch", 8, 0],
    title="📥 拖入漫剧图片 (第1张=首帧, 第2张=末帧, 可选中间帧)",
)
nodes.append(miloader)

# 5. INTConstant — 宽度
w_const = node(
    "INTConstant", pos=[-400, 50], size=[200, 60],
    inputs=[widget_input("value", "INT")],
    outputs=[output("value", "INT")],
    widgets_values=[1280],
)
nodes.append(w_const)

# 6. INTConstant — 高度
h_const = node(
    "INTConstant", pos=[-400, 130], size=[200, 60],
    inputs=[widget_input("value", "INT")],
    outputs=[output("value", "INT")],
    widgets_values=[720],
)
nodes.append(h_const)

# INTConstant → MultiImageLoader (width, height)
links.append(link(w_const["id"], 0, miloader["id"], 1, "INT"))
links.append(link(h_const["id"], 0, miloader["id"], 2, "INT"))

# === 提示词区 ===

# 7. WanVideoTextEncode
textenc = node(
    "WanVideoTextEncode",
    pos=[-100, 430],
    size=[800, 250],
    inputs=[
        widget_input("positive_prompt", "STRING"),
        widget_input("negative_prompt", "STRING"),
    ],
    outputs=[output("text_embeds", "WANVIDEOTEXTEMBEDS")],
    widgets_values=[
        "|".join([
            "anime style, manga animation, the character is performing with natural movements, smooth motion, high quality 2D animation, vibrant colors, detailed background, cinematic lighting, professional anime production quality",
            "anime style, manga animation, the character transitions to next scene, dynamic camera movement, expressive character animation, detailed facial expressions, fluid motion, professional anime quality",
            "anime style, manga animation, dramatic action sequence, fast paced movement, dynamic angles, impact frames, speed lines, professional animation studio quality",
            "anime style, manga animation, emotional close-up scene, detailed facial expression, subtle movement, atmospheric lighting, cinematic depth of field, high quality 2D animation",
            "anime style, manga animation, final scene climax, epic composition, dramatic lighting, smooth character animation, satisfying conclusion, professional anime production",
        ]),
        "subtitles, text, watermark, logo, signature, blurry, distorted, low quality, jpeg artifacts, oversaturated, pixelated, ugly, deformed, extra limbs, bad anatomy, disfigured",
    ],
    title="📝 提示词 (用 | 分隔5段，自动漫游)",
)
nodes.append(textenc)

# T5 → TextEncode
links.append(link(t5loader["id"], 0, textenc["id"], 0, "WANTEXTENCODER"))

# === I2V 编码区 ===

# 8. WanVideoImageToVideoEncode
i2venc = node(
    "WanVideoImageToVideoEncode",
    pos=[850, -200],
    size=[400, 280],
    inputs=[
        widget_input("width", "INT"),
        widget_input("height", "INT"),
        widget_input("num_frames", "INT"),
        widget_input("noise_aug_strength", "FLOAT"),
        widget_input("start_latent_strength", "FLOAT"),
        widget_input("end_latent_strength", "FLOAT"),
        widget_input("force_offload", "BOOLEAN"),
    ],
    outputs=[output("image_embeds", "WANVIDIMAGE_EMBEDS")],
    widgets_values=[1280, 720, 121, 0.02, 1.0, 1.0, True],
    title="🎬 I2V 编码 (首帧→末帧)",
)
nodes.append(i2venc)

# MultiImageLoader.image_1 (首帧) → I2VEncode.start_image
i2venc["inputs"].append(link_input("start_image", "IMAGE", 0))
# MultiImageLoader.image_2 (末帧) → I2VEncode.end_image
i2venc["inputs"].append(link_input("end_image", "IMAGE", 0))
links.append(link(miloader["id"], 1, i2venc["id"], 7, "IMAGE"))
links.append(link(miloader["id"], 2, i2venc["id"], 8, "IMAGE"))

# VAE → I2VEncode
i2venc["inputs"].append(link_input("vae", "WANVAE", 0))
links.append(link(vaeloader["id"], 0, i2venc["id"], 9, "WANVAE"))

# === 采样配置区 ===

# 9. WanVideoContextOptions
ctxopt = node(
    "WanVideoContextOptions",
    pos=[850, 150],
    size=[400, 120],
    inputs=[
        widget_input("start_index", "INT"),
        widget_input("context_window", "INT"),
        widget_input("overlap", "INT"),
        widget_input("synch_mode", "COMBO"),
    ],
    outputs=[output("context_options", "WANVIDCONTEXT")],
    widgets_values=[5, 4, 1, "offload"],
    title="⚙️ 上下文窗口",
)
nodes.append(ctxopt)

# 10. WanVideoSampler
sampler = node(
    "WanVideoSampler",
    pos=[850, 350],
    size=[450, 320],
    inputs=[
        link_input("model", "WANVIDEOMODEL", 0),
        link_input("image_embeds", "WANVIDIMAGE_EMBEDS", 0),
        widget_input("steps", "INT"),
        widget_input("cfg", "FLOAT"),
        widget_input("shift", "FLOAT"),
        widget_input("seed", "INT"),
        widget_input("force_offload", "BOOLEAN"),
        widget_input("scheduler", "COMBO"),
        widget_input("riflex_freq_index", "INT"),
    ],
    outputs=[output("samples", "LATENT"), output("denoised_samples", "LATENT")],
    widgets_values=[30, 6.0, 5.0, 0, True, "unipc", 0],
    title="🎲 WanVideo Sampler",
)
nodes.append(sampler)

# ModelLoader → Sampler (model)
links.append(link(mloader["id"], 0, sampler["id"], 0, "WANVIDEOMODEL"))
# I2VEncode → Sampler (image_embeds)
links.append(link(i2venc["id"], 0, sampler["id"], 1, "WANVIDIMAGE_EMBEDS"))

# 文本嵌入和上下文到 sampler
sampler["inputs"].append(link_input("text_embeds", "WANVIDEOTEXTEMBEDS", 0))
sampler["inputs"].append(link_input("context_options", "WANVIDCONTEXT", 0))
links.append(link(textenc["id"], 0, sampler["id"], 9, "WANVIDEOTEXTEMBEDS"))
links.append(link(ctxopt["id"], 0, sampler["id"], 10, "WANVIDCONTEXT"))

# === 输出区 ===

# 11. WanVideoDecode — VAE 解码
decoder = node(
    "WanVideoDecode",
    pos=[850, 750],
    size=[400, 120],
    inputs=[
        link_input("vae", "WANVAE", 0),
        link_input("samples", "LATENT", 0),
        widget_input("enable_vae_tiling", "BOOLEAN"),
        widget_input("tile_x", "INT"),
        widget_input("tile_y", "INT"),
        widget_input("tile_stride_x", "INT"),
        widget_input("tile_stride_y", "INT"),
    ],
    outputs=[output("images", "IMAGE")],
    widgets_values=[True, 256, 256, 128, 128],
    title="📤 VAE 解码",
)
nodes.append(decoder)
links.append(link(vaeloader["id"], 0, decoder["id"], 0, "WANVAE"))
links.append(link(sampler["id"], 0, decoder["id"], 1, "LATENT"))

# 12. VHS_VideoCombine — 合并为视频
vhs = node(
    "VHS_VideoCombine",
    pos=[1350, 750],
    size=[500, 300],
    inputs=[
        link_input("images", "IMAGE", 0),
        widget_input("frame_rate", "FLOAT"),
        widget_input("loop_count", "INT"),
        widget_input("filename_prefix", "STRING"),
        widget_input("format", "COMBO"),
        widget_input("pix_fmt", "COMBO"),
        widget_input("crf", "INT"),
        widget_input("save_metadata", "BOOLEAN"),
        widget_input("pingpong", "BOOLEAN"),
        widget_input("save_output", "BOOLEAN"),
    ],
    outputs=[],
    widgets_values=[24, 0, "Wan22_Manga", "video/h264-mp4", "yuv420p", 19, True, False, True],
    title="💾 输出视频",
)
nodes.append(vhs)
links.append(link(decoder["id"], 0, vhs["id"], 0, "IMAGE"))

# ── 组装工作流 JSON ─────────────────────────────────────

workflow = {
    "last_node_id": _last_node_id,
    "last_link_id": _last_link_id,
    "nodes": nodes,
    "links": links,
    "groups": [],
    "config": {},
    "extra": {
        "title": "Wan 2.2 漫剧工作流 (含音频参考)",
        "description": (
            "基于 Wan 2.2 I2V 的漫剧/漫画动画生成工作流。\n"
            "使用 MultiImageLoader 加载分镜图，WanVideoTextEncode 的 | 分隔符实现分段提示词漫游。\n"
            "需要模型: wan2.2_i2v_high_noise_14B_fp8_scaled + T5 + Wan VAE\n"
            "生成日期: 2026-05-27"
        ),
    },
    "version": 0.4,
}

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(workflow, f, ensure_ascii=False, indent=2)

print(f"✅ 工作流已生成: {OUTPUT_PATH}")
print(f"   节点数: {_last_node_id}, 链接数: {_last_link_id}")
