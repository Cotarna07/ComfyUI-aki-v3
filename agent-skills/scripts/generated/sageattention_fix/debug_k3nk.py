"""诊断 K3NK 文件中 PathchSageAttentionKJ 的位置"""
import json

fp = r"D:\ComfyUI-aki-v3\agent-skills\comfyui\workflows\TEST\WAN2.2 T2V-I2V-T2I-S2V K3NK v2.5.4 SVI.json"
with open(fp, "r", encoding="utf-8-sig") as f:
    d = json.load(f)

def find_pskj(obj, path="root"):
    if isinstance(obj, dict):
        if obj.get("type") == "PathchSageAttentionKJ":
            print(f"FOUND at {path}: id={obj.get('id')}, wv={obj.get('widgets_values')}")
        for k, v in obj.items():
            find_pskj(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            find_pskj(item, f"{path}[{i}]")

find_pskj(d)
print("Done.")
