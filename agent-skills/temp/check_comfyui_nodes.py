# -*- coding: utf-8 -*-
"""Check ComfyUI available nodes for NSFW video workflow."""
import urllib.request, json, re, sys, os
sys.stdout.reconfigure(encoding='utf-8')

print("Fetching object_info...", flush=True)
resp = urllib.request.urlopen('http://127.0.0.1:8188/object_info', timeout=30)
text = resp.read().decode('utf-8')
print(f"Got {len(text)} bytes", flush=True)

# Find all unique top-level keys (node class names)
pattern = r'"([A-Z][^"]{2,80})"\s*:\s*\{'
matches = list(set(re.findall(pattern, text)))
print(f"Total unique node classes: {len(matches)}", flush=True)

# Filter for relevant ones
relevant = []
for m in sorted(matches):
    ml = m.lower()
    if any(t in ml for t in ['wan', 'ltx', 'ksampler', 'lora', 'gguf', 'unet',
                              'clip', 'vae', 'model', 'latent', 'encode', 'decode',
                              'condition', 'image', 'save', 'preview', 'load',
                              'empty', 'batch', 'prompt']):
        relevant.append(m)

print(f"Relevant nodes: {len(relevant)}", flush=True)
for m in relevant:
    print(f"  {m}", flush=True)
