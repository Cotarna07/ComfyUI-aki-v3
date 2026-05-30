import json, os, re, glob, sys, io

OUT = open(r"D:\ComfyUI-aki-v3\agent-skills\scripts\generated\wan-workflow-check\result.txt", "w", encoding="utf-8")
def emit(s=""):
    OUT.write(s + "\n")

WF_DIR = r"D:\ComfyUI-aki-v3\agent-skills\comfyui\workflows\TEST\26-5-29"
TARGETS = [
    "Wan 2.1 - seamless loop workflow v1.2.json",
    "WAN2.2 I2V Only - K3NK v2.5.4.json",
    "WAN2.2 T2V-I2V-T2I-S2V K3NK v2.5.4 SVI.json",
    "WAN2.2_Img2video_auto.json",
    "WAN2.2_Img2video_manual.json",
    "WAN2.2_LOOP_NATIVE_UPSCALER_GGUF.json",
    "WAN2.2_LOOP_NATIVE_UPSCALER.json",
    "WAN2.2_LOOP.json",
]

MODEL_EXT = (".safetensors", ".gguf", ".pth", ".ckpt", ".pt", ".onnx", ".bin", ".sft")

def walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for x in obj:
            yield from walk_strings(x)
    elif isinstance(obj, dict):
        for x in obj.values():
            yield from walk_strings(x)

for name in TARGETS:
    path = os.path.join(WF_DIR, name)
    if not os.path.exists(path):
        emit(str(f"### MISSING FILE: {name}"))
        continue
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    nodes = data.get("nodes", [])
    types = set()
    models = set()
    for n in nodes:
        t = n.get("type")
        if t:
            types.add(t)
        for s in walk_strings(n.get("widgets_values", [])):
            if isinstance(s, str) and s.lower().endswith(MODEL_EXT):
                models.add(s)
    emit(str(f"\n===== {name} ====="))
    emit(str(f"-- NODE TYPES ({len(types)}) --"))
    for t in sorted(types):
        emit(str(t))
    emit(str(f"-- MODEL FILES ({len(models)}) --"))
    for m in sorted(models):
        emit(str(m))
