"""
LM Studio 模型参数调优测试 v2
- 每次测试完立即写入 raw_results.jsonl
- 每个模型开始前先 ping 暖场
- 按文档逐模型定制参数
"""
import urllib.request, urllib.error, json, time, os, sys
from datetime import datetime

BASE = "http://127.0.0.1:1234"
HTTP_TO = 120
THREAD_TO = 600
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime", "lmstudio-bench-20260505")
os.makedirs(OUT_DIR, exist_ok=True)

RESULTS_FILE = os.path.join(OUT_DIR, "raw_results.jsonl")

Q1 = """请重构以下伪代码为 Python 命令分发结构，每个任务独立函数，不过度设计：

def run(x):
    if x == 1: print("download")
    elif x == 2: print("analyze")
    elif x == 3: print("write db")
    else: print("unknown")

直接输出重构后的 Python 代码。"""

Q2 = """你是视频 prompt 优化专家。优化以下 prompt，输出格式为：
[POSITIVE]
(优化后)
[NEGATIVE]
(优化后)
[REASONS]
1.
2.
(<=5条)

原 prompt: beautiful woman dancing in room, cinematic, high quality, realistic, detailed
问题: 手指变形、脸不稳定、动作太大、背景闪烁"""

# ============ 参数矩阵 ============
def get_params(model_id):
    m = model_id.lower()
    is_thinking = any(k in m for k in ["thinking","savant","freedom"])
    is_qwen = m.startswith("qwen") or "/qwen" in m
    base = {"repeat_last_n":64,"max_tokens":1024}
    
    if "darkest-universe" in m:  # Class 3
        a = {**base,"temperature":0.70,"top_k":40,"top_p":0.95,"min_p":0.05,"repeat_penalty":1.08,"presence_penalty":0.05,"frequency_penalty":0.25}
        b = {**base,"temperature":0.60,"top_k":60,"top_p":0.90,"min_p":0.05,"repeat_penalty":1.10,"presence_penalty":0.10,"frequency_penalty":0.35}
        return ("Class3-T0.7",a),("Class3-T0.6",b)
    if "auto-variable" in m:
        a = {**base,"temperature":1.00,"top_k":40,"top_p":0.95,"min_p":0.05,"repeat_penalty":1.05}
        b = {**base,"temperature":0.70,"top_k":20,"top_p":0.90,"min_p":0.05,"repeat_penalty":1.08}
        return ("Auto-T1.0",a),("Auto-T0.7",b)
    if is_thinking and is_qwen:
        a = {**base,"temperature":0.60,"top_k":20,"top_p":0.95,"min_p":0.0,"repeat_penalty":1.05}
        b = {**base,"temperature":0.75,"top_k":30,"top_p":0.90,"min_p":0.0,"repeat_penalty":1.08}
        return ("Think-T0.6",a),("Think-T0.75",b)
    if is_qwen:
        a = {**base,"temperature":0.70,"top_k":20,"top_p":0.80,"min_p":0.0,"repeat_penalty":1.05}
        b = {**base,"temperature":0.85,"top_k":40,"top_p":0.90,"min_p":0.05,"repeat_penalty":1.08}
        return ("Qwen-T0.7",a),("Qwen-T0.85",b)
    if "dark-reasoning" in m or "dark-multiverse" in m:
        a = {**base,"temperature":0.80,"top_k":40,"top_p":0.95,"min_p":0.05,"repeat_penalty":1.06}
        b = {**base,"temperature":1.00,"top_k":60,"top_p":0.90,"min_p":0.05,"repeat_penalty":1.08}
        return ("Cls2-T0.8",a),("Cls2-T1.0",b)
    if "dark-champion" in m:
        a = {**base,"temperature":1.00,"top_k":40,"top_p":0.95,"min_p":0.05,"repeat_penalty":1.05}
        b = {**base,"temperature":0.80,"top_k":60,"top_p":0.90,"min_p":0.05,"repeat_penalty":1.08}
        return ("Champ-T1.0",a),("Champ-T0.8",b)
    if "gemma" in m:
        a = {**base,"temperature":0.70,"top_k":40,"top_p":0.90,"min_p":0.05,"repeat_penalty":1.05}
        b = {**base,"temperature":0.90,"top_k":60,"top_p":0.95,"min_p":0.05,"repeat_penalty":1.08}
        return ("Gemma-T0.7",a),("Gemma-T0.9",b)
    # Class 1 default
    a = {**base,"temperature":0.80,"top_k":40,"top_p":0.95,"min_p":0.05,"repeat_penalty":1.05}
    b = {**base,"temperature":0.60,"top_k":60,"top_p":0.90,"min_p":0.05,"repeat_penalty":1.08}
    return ("Cls1-T0.8",a),("Cls1-T0.6",b)

# ============ API ============
def api(path, body=None, timeout=HTTP_TO):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(BASE+path, data=data, method="POST" if body else "GET")
    req.add_header("Content-Type","application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error":str(e)[:200]}

def save_result(r):
    with open(RESULTS_FILE,"a",encoding="utf-8") as f:
        f.write(json.dumps(r,ensure_ascii=False)+"\n")

def ping(model_id):
    """暖场：发极简请求清缓存"""
    body = {"model":model_id,"messages":[{"role":"user","content":"Hi"}],"max_tokens":5,"temperature":0.6,"stream":False}
    try:
        api("/v1/chat/completions", body, timeout=10)
    except:
        pass

def run_one(model_id, question, params, label, qname):
    t0 = time.time()
    r = {"model":model_id[:80],"question":qname,"label":label,"params":params,
         "ok":False,"dead":False,"output":"","stop":"","tok":0,"sec":0,"err":""}
    
    body = {"model":model_id,"messages":[{"role":"user","content":question}],
            "max_tokens":params["max_tokens"],"temperature":params["temperature"],
            "top_p":params["top_p"],"stream":False,"extra_body":{}}
    for k in ["top_k","min_p","repeat_penalty","repeat_last_n","presence_penalty","frequency_penalty"]:
        if k in params: body["extra_body"][k] = params[k]
    
    import threading, queue
    q = queue.Queue()
    def call():
        try:
            q.put(api("/v1/chat/completions", body, timeout=HTTP_TO))
        except Exception as e:
            q.put({"error":str(e)})
    
    t = threading.Thread(target=call, daemon=True)
    t.start()
    t.join(timeout=THREAD_TO)
    r["sec"] = round(time.time()-t0, 1)
    
    if t.is_alive():
        r["dead"] = True; r["err"] = f"timeout {THREAD_TO}s"
        print(f"  [{label}] DEAD {r['sec']}s", flush=True)
        save_result(r); return r
    
    try:
        resp = q.get(timeout=2)
    except:
        r["err"] = "queue empty"; save_result(r); return r
    
    if "error" in resp and "choices" not in resp:
        r["err"] = str(resp["error"])[:150]
        print(f"  [{label}] ERR {r['err'][:60]}", flush=True)
        save_result(r); return r
    
    if "choices" not in resp or not resp["choices"]:
        r["err"] = "no choices"; save_result(r); return r
    
    c = resp["choices"][0]
    r["ok"] = True
    r["output"] = c["message"]["content"]
    r["stop"] = c.get("finish_reason","?")
    r["tok"] = resp.get("usage",{}).get("completion_tokens",0)
    
    out_short = r["output"][:50].replace("\n"," ").replace("\r","")
    print(f"  [{label}] stop={r['stop']} len={len(r['output'])} tok={r['tok']} {r['sec']}s [{out_short}]", flush=True)
    save_result(r)
    return r

# ============ MAIN ============
def main():
    print("Fetching models...", flush=True)
    models = [m for m in api("/v1/models").get("data",[]) if "embed" not in m["id"].lower()]
    print(f"{len(models)} models\n", flush=True)
    
    questions = [("Q1-重构",Q1),("Q2-优化",Q2)]
    total = 0
    
    for i,m in enumerate(models):
        mid = m["id"]
        print(f"\n[{i+1}/{len(models)}] {mid[:70]}", flush=True)
        print("-"*60, flush=True)
        
        # 暖场 ping
        ping(mid)
        
        (la,ga),(lb,gb) = get_params(mid)
        
        for qn,qt in questions:
            run_one(mid, qt, ga, la, qn)
            run_one(mid, qt, gb, lb, qn)
            total += 2
    
    print(f"\nDone. {total} tests. Results: {RESULTS_FILE}", flush=True)

if __name__ == "__main__":
    main()
