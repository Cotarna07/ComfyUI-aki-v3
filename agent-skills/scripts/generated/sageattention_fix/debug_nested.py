"""诊断 WAN2.2-I2V-AutoPrompt-Story.json 中 PathchSageAttentionKJ 的位置"""
import json

fp = r"D:\ComfyUI-aki-v3\agent-skills\comfyui\workflows\TEST\WAN2.2-I2V-AutoPrompt-Story.json"
with open(fp, "r", encoding="utf-8-sig") as f:
    d = json.load(f)

# 递归搜索所有嵌套结构
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
