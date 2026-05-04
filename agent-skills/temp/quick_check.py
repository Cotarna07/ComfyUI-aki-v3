import urllib.request, json, os, time

pid = "361b0273-15c7-420b-a25a-3c8b1512b636"

# Check history
h = urllib.request.urlopen(f"http://127.0.0.1:8188/history/{pid}", timeout=10)
d = json.loads(h.read())
s = d.get(pid, {}).get("status", {})
print(f"completed: {s.get('completed')}")
print(f"status_str: {s.get('status_str', '')}")

msgs = s.get("messages", [])
for m in msgs[-3:]:
    print(f"  [{m[0]}] {str(m[1])[:300]}")

# Check VRAM
r = urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=10)
d2 = json.loads(r.read())
v = d2["devices"][0]
print(f"VRAM: {v['vram_free']/1024**3:.1f}GB free / {v['vram_total']/1024**3:.1f}GB total")

# Check output
outdir = r"D:\ComfyUI-aki-v3\ComfyUI\output"
files = [f for f in os.listdir(outdir) if "NSFW_TEST" in f]
print(f"NSFW_TEST files in output: {files}")
