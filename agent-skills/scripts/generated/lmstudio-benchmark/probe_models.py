"""探测 LM Studio 中每个模型的基础响应能力和参数支持"""
import urllib.request, urllib.error, json, sys

BASE = "http://127.0.0.1:1234"

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())

models = [m for m in api("GET","/v1/models")["data"] if "embed" not in m["id"].lower()]
print(f"{len(models)} chat models\n")
results = []
for i,m in enumerate(models):
    mid = m["id"]
    print(f"[{i+1}/{len(models)}] {mid[:80]}")
    r = api("POST","/v1/chat/completions",{"model":mid,"messages":[{"role":"user","content":'Say "OK".'}],"max_tokens":25,"temperature":0,"stream":False})
    if "choices" in r:
        c = r["choices"][0]
        u = r.get("usage",{})
        ok = True
        out = c["message"]["content"][:120]
        print(f"  OK stop={c.get('finish_reason')} tok={u.get('prompt_tokens')}/{u.get('completion_tokens')} => {out[:80]}")
    else:
        ok = False; out = r.get("error",{}).get("message",str(r))[:120]
        print(f"  FAIL {out[:100]}")
    results.append({"model":mid,"ok":ok,"out":out})
    print()

print("="*60); print("SUMMARY:")
for r in results:
    s = "OK" if r["ok"] else "!!"
    print(f"  [{s}] {r['model'][:70]}")
