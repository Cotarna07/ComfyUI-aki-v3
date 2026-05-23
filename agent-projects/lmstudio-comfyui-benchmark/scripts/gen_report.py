import json, os
from collections import defaultdict

INFILE = r"d:\ComfyUI-aki-v3\agent-projects\lmstudio-comfyui-benchmark\runtime\lmstudio-bench-20260505\raw_results.jsonl"
OUTFILE = r"d:\ComfyUI-aki-v3\agent-projects\lmstudio-comfyui-benchmark\runtime\lmstudio-bench-20260505\comparison_report.md"

with open(INFILE,encoding="utf-8") as f:
    results = [json.loads(line) for line in f if line.strip()]

# Group by model+question
groups = defaultdict(list)
for r in results:
    key = (r["model"][:60], r["question"])
    groups[key].append(r)

def score(r):
    if r["dead"]: return -1
    if r["err"]: return 0
    if not r["ok"]: return 0
    out = r["output"].strip()
    if not out and r["tok"] > 100: return -2  # dead loop
    if not out: return 0
    if r["stop"] == "stop" and len(out) > 30: return 2
    if r["stop"] == "length" and len(out) > 30: return 1
    if len(out) > 0: return 1
    return 0

def icon(score):
    if score == 2: return ":white_check_mark:"
    if score == 1: return ":large_orange_diamond:"
    if score == 0: return ":x:"
    if score == -1: return ":clock2: **TIMEOUT**"
    if score == -2: return ":skull: **DEAD LOOP**"

def short_model(mid):
    parts = mid.split("-")
    if len(parts) > 3:
        arch = "Thinking" if "think" in mid.lower() else ("MoE" if any(k in mid.lower() for k in ["moe","a3b","a4b","8x"]) else "Dense")
        size = "?"
        for p in parts:
            if p.endswith("b") and p[:-1].replace(".","").isdigit():
                size = p.upper()
                break
        return f"{parts[0][:8]}-{size} ({arch})"
    return mid[:30]

lines = []
lines.append("# LM Studio 模型参数调优评测报告")
lines.append(f"> 日期: 2026-05-05 | 测试数: {len(results)} | 模型数: 13")
lines.append("")
lines.append("## 评分说明\n")
lines.append("| 标记 | 含义 |")
lines.append("|------|------|")
lines.append("| :white_check_mark: | 正常输出，stop=stop，输出完整 |")
lines.append("| :large_orange_diamond: | 输出被截断 (stop=length) 但内容有 |")
lines.append("| :x: | 失败（HTTP 400 / timeout / 空输出） |")
lines.append("| :skull: DEAD LOOP | 消耗全部 token 但输出为空 |")
lines.append("| :clock2: TIMEOUT | 超时 600s 未响应 |")
lines.append("")

for qname in ["Q1-重构", "Q2-优化"]:
    lines.append(f"## {qname}\n")
    lines.append("| # | 模型 | 组A 参数 | A得分 | A输出 | 组B 参数 | B得分 | B输出 | 推荐 |")
    lines.append("|---|------|---------|-------|-------|---------|-------|-------|------|")
    
    for i, ((mid, qn), entries) in enumerate(sorted(groups.items())):
        if qname not in qn: continue
        entries_sorted = sorted(entries, key=lambda r: r["label"])
        if len(entries_sorted) < 2: continue
        a, b = entries_sorted[0], entries_sorted[1]
        sa, sb = score(a), score(b)
        out_a = a["output"][:60].replace("\n"," ").replace("|","/") if a["output"] else ("TIMEOUT" if a["dead"] else ("DEAD" if a["tok"]>100 and not a["output"] else a["err"][:40]))
        out_b = b["output"][:60].replace("\n"," ").replace("|","/") if b["output"] else ("TIMEOUT" if b["dead"] else ("DEAD" if b["tok"]>100 and not b["output"] else b["err"][:40]))
        rec = "A" if sa > sb else ("B" if sb > sa else "=")
        lines.append(f"| {i+1} | {short_model(mid)} | {a['label']} | {icon(sa)} | {out_a[:40]} | {b['label']} | {icon(sb)} | {out_b[:40]} | **{rec}** |")
    lines.append("")

# Summary
lines.append("## 总结\n")
lines.append("| 模型 | Q1-A | Q1-B | Q2-A | Q2-B | 最佳组 |")
lines.append("|------|------|------|------|------|--------|")

model_summary = defaultdict(lambda: {"Q1-重构":(0,0),"Q2-优化":(0,0)})
for (mid, qn), entries in groups.items():
    entries_sorted = sorted(entries, key=lambda r: r["label"])
    if len(entries_sorted) < 2: continue
    a, b = entries_sorted[0], entries_sorted[1]
    model_summary[mid]["Q1-重构" if "Q1" in qn else "Q2-优化"] = (score(a), score(b))

for mid in sorted(set(m[0] for m in groups)):
    s = model_summary[mid]
    best = "A" if sum(s["Q1-重构"])+sum(s["Q2-优化"]) > 0 else "B" if sum(s["Q2-优化"]) > sum(s["Q1-重构"]) else "A"
    lines.append(f"| {short_model(mid)} | {icon(s['Q1-重构'][0])} | {icon(s['Q1-重构'][1])} | {icon(s['Q2-优化'][0])} | {icon(s['Q2-优化'][1])} | **{best}** |")

with open(OUTFILE,"w",encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Report: {OUTFILE}")
