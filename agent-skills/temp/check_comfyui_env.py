# -*- coding: utf-8 -*-
"""Check ComfyUI available nodes and models for NSFW video workflow."""
import urllib.request
import json
import re

# 1. Get object_info and find Wan/LTX related nodes
print("=== Fetching object_info ===")
resp = urllib.request.urlopen('http://127.0.0.1:8188/object_info')
text = resp.read().decode('utf-8')

matches = re.findall(r'"([^"]*(?:WanVideo|LTX|PowerLora|GGUF|UNET|CLIP|VAE|KSampler|EmptyLatent|LoadImage|Save|Video|TextEncode|Conditioning)[^"]*)"', text)
print("\n=== Wan/LTX/Video Nodes ===")
for m in sorted(set(matches)):
    print(f"  {m}")

# 2. Check available LoRA models
print("\n=== Checking LoRA models ===")
import os
lora_dir = r"D:\ComfyUI-aki-v3\ComfyUI\models\loras"
if os.path.isdir(lora_dir):
    for f in sorted(os.listdir(lora_dir)):
        fn = f.lower()
        if any(t in fn for t in ['nsfw', 'wan', 'ltx', 'bounce', 'titjob', 'pose', 'dream', 'girl']):
            print(f"  {f}")

# 3. Check Wan diffusion models
print("\n=== Checking Wan diffusion_models ===")
diff_dir = r"D:\ComfyUI-aki-v3\ComfyUI\models\diffusion_models"
if os.path.isdir(diff_dir):
    for f in sorted(os.listdir(diff_dir)):
        fn = f.lower()
        if any(t in fn for t in ['wan', 'nsfw', 'smooth', 'dasiwa']):
            print(f"  {f}")

# 4. Check text_encoders
print("\n=== Checking text_encoders ===")
te_dir = r"D:\ComfyUI-aki-v3\ComfyUI\models\text_encoders"
if os.path.isdir(te_dir):
    for f in sorted(os.listdir(te_dir)):
        fn = f.lower()
        if any(t in fn for t in ['umt5', 't5', 'clip', 'wan']):
            print(f"  {f}")

# 5. Check VAE
print("\n=== Checking VAE ===")
vae_dir = r"D:\ComfyUI-aki-v3\ComfyUI\models\vae"
if os.path.isdir(vae_dir):
    for f in sorted(os.listdir(vae_dir)):
        fn = f.lower()
        if any(t in fn for t in ['wan', 'nsfw']):
            print(f"  {f}")

print("\n=== Done ===")
