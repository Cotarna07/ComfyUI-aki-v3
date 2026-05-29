import urllib.request, json, time
pid = "361b0273-15c7-420b-a25a-3c8b1512b636"
for i in range(60):
    try:
        # VRAM
        r = urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=5)
        d = json.loads(r.read())
        v = d["devices"][0]
        vram_free = v["vram_free"] / 1024**3
        vram_total = v["vram_total"] / 1024**3
        # History
        h = urllib.request.urlopen(f"http://127.0.0.1:8188/history/{pid}", timeout=5)
        hd = json.loads(h.read())
        s = hd.get(pid, {}).get("status", {})
        completed = s.get("completed")
        status_str = s.get("status_str", "")
        print(f"[{i}] VRAM: {vram_free:.1f}/{vram_total:.1f}GB | completed={completed} | {status_str}")
        if completed:
            outputs = hd[pid].get("outputs", {})
            for nid, out in outputs.items():
                for g in out.get("gifs", []):
                    print(f"  VIDEO: {g['filename']}")
                for img in out.get("images", []):
                    print(f"  IMAGE: {img['filename']}")
            break
        if status_str == "error":
            msgs = s.get("messages", [])
            for m in msgs[-5:]:
                print(f"  {m}")
            break
    except Exception as e:
        print(f"[{i}] Error: {e}")
    time.sleep(10)
