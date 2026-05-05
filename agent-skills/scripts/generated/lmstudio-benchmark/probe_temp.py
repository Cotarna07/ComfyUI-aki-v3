"""第二轮：测试不同 temperature 下模型的输出行为"""
import urllib.request, urllib.error, json

BASE = "http://127.0.0.1:1234"

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())

models = [m for m in api("GET","/v1/models")["data"] if "embed" not in m["id"].lower()]

prompt = "Count from 1 to 5. Output ONLY the numbers separated by commas. Do not explain."

for i, m in enumerate(models):
    mid = m["id"]
    short = mid[:60]
    print(f"\n{'='*60}")
    print(f"[{i+1}/13] {short}")
    
    for temp in [0.0, 0.5, 0.7, 1.0]:
        r = api("POST", "/v1/chat/completions", {
            "model": mid,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 50,
            "temperature": temp,
            "stream": False
        })
        if "choices" in r:
            c = r["choices"][0]
            txt = c["message"]["content"].strip()[:80]
            stop = c.get("finish_reason", "?")
            u = r.get("usage", {})
            print(f"  T={temp:.1f} stop={stop} tok={u.get('completion_tokens','?')} => [{txt}]")
        else:
            err = r.get("error",{}).get("message",str(r))[:100]
            print(f"  T={temp:.1f} ERR: {err}")
