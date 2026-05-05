"""LM Studio 模型参数调优测试（无缓冲输出版）"""
import urllib.request, urllib.error, json, time, os, sys, threading, queue
from datetime import datetime

# 无缓冲输出
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

BASE = "http://127.0.0.1:1234"
TIMEOUT_SEC = 600
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime", "lmstudio-bench-20260505")

# ============================================================
# 测试题目
# ============================================================
Q1_PROMPT = """下面是一段伪代码，功能混乱。请你重构为更清晰的 Python 结构，但不要过度设计。

代码：
def run(x):
    if x == 1:
        print("download")
    elif x == 2:
        print("analyze")
    elif x == 3:
        print("write db")
    else:
        print("unknown")

需求：
- 改成命令分发结构
- 每个任务单独函数
- 保留简单可读
- 不要引入复杂框架

请直接输出重构后的完整代码。"""

Q2_PROMPT = """下面这个 prompt 生成出来的人物手部变形、脸部飘、动作不稳定。请你优化它。

原 prompt：
beautiful woman dancing in room, cinematic, high quality, realistic, detailed

问题：
1. 手指变形
2. 脸每一帧都不一样
3. 动作太大，视频容易崩
4. 背景闪烁

要求输出格式（严格遵守）：
【优化后的 positive prompt】
（在这里写）
【优化后的 negative prompt】
（在这里写）
【修改原因】
1. （原因1）
2. （原因2）
（不超过5条）"""

# ============================================================
# 模型分类 → 参数组映射（基于 DavidAU + HuggingFace 文档）
# ============================================================

def get_param_groups(model_id):
    """根据模型 ID 返回 A/B 两组定制参数"""
    mid = model_id.lower()
    
    # --- 识别模型特征 ---
    is_thinking = any(k in mid for k in ["thinking", "savant", "freedom"])
    is_qwen3 = mid.startswith("qwen3") or "qwen3" in mid
    is_moe = any(k in mid for k in ["moe", "a3b", "a4b", "8x4b", "6x8b", "4x7b"])
    is_class3 = "darkest-universe" in mid
    is_class2 = any(k in mid for k in ["dark-reasoning", "dark-multiverse"])
    is_dark_champion = "dark-champion" in mid
    is_gemma = "gemma" in mid
    is_auto_variable = "auto-variable" in mid
    
    base = {
        "repeat_last_n": 64,
        "max_tokens": 1024,
    }
    
    if is_class3:
        # mn-darkest-universe-29b — Class 3，文档强调必须 repeat_last_n=64 + 额外惩罚
        group_a = {**base, "temperature": 0.70, "top_k": 40, "top_p": 0.95, "min_p": 0.05,
                    "repeat_penalty": 1.08, "presence_penalty": 0.05, "frequency_penalty": 0.25}
        group_b = {**base, "temperature": 0.60, "top_k": 60, "top_p": 0.90, "min_p": 0.05,
                    "repeat_penalty": 1.10, "presence_penalty": 0.10, "frequency_penalty": 0.35}
        label_a, label_b = "Class3-稳定", "Class3-收紧"
    
    elif is_auto_variable:
        # qwen3.5-9b-claude-auto-variable — 文档推荐 T=1.0
        group_a = {**base, "temperature": 1.00, "top_k": 40, "top_p": 0.95, "min_p": 0.05, "repeat_penalty": 1.05}
        group_b = {**base, "temperature": 0.70, "top_k": 20, "top_p": 0.90, "min_p": 0.05, "repeat_penalty": 1.08}
        label_a, label_b = "AutoVar-T1.0", "AutoVar-T0.7"
    
    elif is_thinking and is_qwen3:
        # Qwen3 Thinking — HuggingFace 警告：T=0 会导致死循环，推荐 T=0.6
        group_a = {**base, "temperature": 0.60, "top_k": 20, "top_p": 0.95, "min_p": 0.0, "repeat_penalty": 1.05}
        group_b = {**base, "temperature": 0.75, "top_k": 30, "top_p": 0.90, "min_p": 0.0, "repeat_penalty": 1.08}
        label_a, label_b = "Think-T0.6", "Think-T0.75"
    
    elif is_qwen3:
        # Qwen3 非 Thinking — HuggingFace 推荐 T=0.7, top_p=0.8, top_k=20
        group_a = {**base, "temperature": 0.70, "top_k": 20, "top_p": 0.80, "min_p": 0.0, "repeat_penalty": 1.05}
        group_b = {**base, "temperature": 0.85, "top_k": 40, "top_p": 0.90, "min_p": 0.05, "repeat_penalty": 1.08}
        label_a, label_b = "Qwen3-T0.7", "Qwen3-T0.85"
    
    elif is_dark_champion:
        # Dark Champion MOE — 文档推荐 T=0.8-1.2
        group_a = {**base, "temperature": 1.00, "top_k": 40, "top_p": 0.95, "min_p": 0.05, "repeat_penalty": 1.05}
        group_b = {**base, "temperature": 0.80, "top_k": 60, "top_p": 0.90, "min_p": 0.05, "repeat_penalty": 1.08}
        label_a, label_b = "Champion-T1.0", "Champion-T0.8"
    
    elif is_class2:
        # Class 2 — 稍强的参数
        group_a = {**base, "temperature": 0.80, "top_k": 40, "top_p": 0.95, "min_p": 0.05, "repeat_penalty": 1.06}
        group_b = {**base, "temperature": 1.00, "top_k": 60, "top_p": 0.90, "min_p": 0.05, "repeat_penalty": 1.08}
        label_a, label_b = "Class2-T0.8", "Class2-T1.0"
    
    elif is_gemma:
        # Gemma 4 — any-to-any 模型
        group_a = {**base, "temperature": 0.70, "top_k": 40, "top_p": 0.90, "min_p": 0.05, "repeat_penalty": 1.05}
        group_b = {**base, "temperature": 0.90, "top_k": 60, "top_p": 0.95, "min_p": 0.05, "repeat_penalty": 1.08}
        label_a, label_b = "Gemma-T0.7", "Gemma-T0.9"
    
    else:
        # Class 1 通用 — DavidAU Heretic/Deckard 标准
        group_a = {**base, "temperature": 0.80, "top_k": 40, "top_p": 0.95, "min_p": 0.05, "repeat_penalty": 1.05}
        group_b = {**base, "temperature": 0.60, "top_k": 60, "top_p": 0.90, "min_p": 0.05, "repeat_penalty": 1.08}
        label_a, label_b = "Class1-T0.8", "Class1-T0.6"
    
    return (group_a, label_a), (group_b, label_b)


# ============================================================
# API 调用（带超时）
# ============================================================

def api_call(method, path, body=None, timeout=120):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)[:300]}


def run_one_test(model_id, question, params, label, q_name, timeout=TIMEOUT_SEC):
    """单个测试：发送 prompt，等待结果，返回字典"""
    print(f"    [{label}] 开始 @ {datetime.now().strftime('%H:%M:%S')}", flush=True)
    start = time.time()
    
    result = {
        "model": model_id,
        "question": q_name,
        "param_label": label,
        "params": params.copy(),
        "started": datetime.now().isoformat(),
        "ok": False,
        "dead_loop": False,
        "output": "",
        "stop_reason": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "elapsed_sec": 0,
        "error": "",
    }
    
    # 构建请求体 — HTTP 层 timeout 120s，线程等待 timeout（600s）
    HTTP_TIMEOUT = 120
    body = {
        "model": model_id,
        "messages": [{"role": "user", "content": question}],
        "max_tokens": params["max_tokens"],
        "temperature": params["temperature"],
        "top_p": params["top_p"],
        "stream": False,
        "extra_body": {},
    }
    for k in ["top_k", "min_p", "repeat_penalty", "repeat_last_n",
              "presence_penalty", "frequency_penalty"]:
        if k in params:
            body["extra_body"][k] = params[k]
    
    response_queue = queue.Queue()
    
    def _call():
        try:
            resp = api_call("POST", "/v1/chat/completions", body, timeout=HTTP_TIMEOUT)
            response_queue.put(resp)
        except Exception as e:
            response_queue.put({"error": str(e)})
    
    thread = threading.Thread(target=_call, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    elapsed = time.time() - start
    result["elapsed_sec"] = round(elapsed, 1)
    
    if thread.is_alive():
        # 超时 → 死循环
        result["dead_loop"] = True
        result["error"] = f"超时 {timeout}s，判定为死循环"
        print(f"    [{label}] !! 超时 {elapsed:.0f}s -> 死循环")
        return result
    
    try:
        resp = response_queue.get(timeout=2)
    except queue.Empty:
        result["error"] = "响应队列为空"
        return result
    
    if "error" in resp and "choices" not in resp:
        result["error"] = str(resp["error"])[:300]
        print(f"    [{label}] XX {result['error'][:80]}")
        return result
    
    if "choices" not in resp or len(resp["choices"]) == 0:
        result["error"] = f"no choices: {str(resp)[:200]}"
        print(f"    [{label}] XX 无有效输出")
        return result
    
    choice = resp["choices"][0]
    result["ok"] = True
    result["output"] = choice["message"]["content"]
    result["stop_reason"] = choice.get("finish_reason", "unknown")
    usage = resp.get("usage", {})
    result["prompt_tokens"] = usage.get("prompt_tokens", 0)
    result["completion_tokens"] = usage.get("completion_tokens", 0)
    
    out_len = len(result["output"])
    tok_s = result["completion_tokens"] / max(elapsed, 0.1)
    status = "OK" if result["stop_reason"] == "stop" else "??"
    print(f"    [{label}] {status} stop={result['stop_reason']} len={out_len} "
          f"tok={result['completion_tokens']} {tok_s:.1f}t/s {elapsed:.0f}s")
    
    return result


# ============================================================
# 主流程
# ============================================================

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    
    # 获取模型列表
    print("正在获取模型列表...")
    models_resp = api_call("GET", "/v1/models")
    all_models = models_resp.get("data", [])
    chat_models = [m for m in all_models if "embed" not in m["id"].lower()]
    print(f"共 {len(chat_models)} 个对话模型\n")
    
    all_results = []
    questions = [("Q1-代码重构", Q1_PROMPT), ("Q2-Prompt优化", Q2_PROMPT)]
    
    for i, m in enumerate(chat_models):
        mid = m["id"]
        short = mid[:65]
        print(f"\n{'='*70}")
        print(f"[{i+1}/{len(chat_models)}] {short}")
        print(f"{'='*70}")
        
        # 获取该模型的参数组
        (ga, la), (gb, lb) = get_param_groups(mid)
        
        for q_name, q_text in questions:
            print(f"  >> {q_name}")
            
            # 组 A
            r1 = run_one_test(mid, q_text, ga, la, q_name)
            all_results.append(r1)
            
            # 组 B
            r2 = run_one_test(mid, q_text, gb, lb, q_name)
            all_results.append(r2)
    
    # ========================================
    # 生成汇总
    # ========================================
    summary_path = os.path.join(OUT_DIR, "summary.csv")
    raw_path = os.path.join(OUT_DIR, "raw_results.json")
    
    # 保存原始结果
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    # 生成 CSV
    with open(summary_path, "w", encoding="utf-8-sig") as f:
        f.write("模型,题目,参数组,成功,stop_reason,输出长度,耗时秒,Token数,死循环,错误\n")
        for r in all_results:
            f.write(f'{r["model"][:60]},{r["question"]},{r["param_label"]},'
                    f'{r["ok"]},{r["stop_reason"]},{len(r["output"])},'
                    f'{r["elapsed_sec"]},{r["completion_tokens"]},'
                    f'{r["dead_loop"]},"{r["error"][:80]}"\n')
    
    # 控制台汇总
    print("\n\n" + "=" * 70)
    print("==== 评测汇总 ====")
    print("=" * 70)
    
    ok_count = sum(1 for r in all_results if r["ok"])
    dead_count = sum(1 for r in all_results if r["dead_loop"])
    total = len(all_results)
    print(f"总测试: {total} | 成功: {ok_count} | 死循环: {dead_count} | 其他失败: {total - ok_count - dead_count}")
    
    print(f"\n原始结果: {raw_path}")
    print(f"CSV 汇总: {summary_path}")
    
    return all_results


if __name__ == "__main__":
    main()
