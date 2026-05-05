import json, os
from collections import defaultdict

INFILE = r"d:\ComfyUI-aki-v3\agent-projects\lmstudio-comfyui-benchmark\runtime\lmstudio-bench-20260505\raw_results.jsonl"
OUTFILE = r"d:\ComfyUI-aki-v3\agent-projects\lmstudio-comfyui-benchmark\runtime\lmstudio-bench-20260505\comparison_full.md"

with open(INFILE,encoding="utf-8") as f:
    results = [json.loads(line) for line in f if line.strip()]

groups = defaultdict(list)
for r in results:
    key = (r["model"], r["question"])
    groups[key].append(r)

def render_output(r):
    if r.get("dead"): return "**TIMEOUT**"
    out = r.get("output","")
    if not out and r.get("tok",0) > 100: return "**DEAD LOOP (1024 tokens, empty output)**"
    if r.get("err") and not out: return f"*{r['err'][:60]}*"
    if not out: return "*empty*"
    return out

lines = []
lines.append("# LM Studio 全模型输出对照")
lines.append(f"> 52 tests | 13 models | 2026-05-05")
lines.append("")

# By question
for qn in ["Q1-重构", "Q2-优化"]:
    lines.append(f"---")
    lines.append(f"## {qn}")
    lines.append("")
    for (mid, question), entries in sorted(groups.items()):
        if qn not in question: continue
        short = mid[:70]
        lines.append(f"### {short}")
        lines.append("")
        entries_sorted = sorted(entries, key=lambda r: r["label"])
        for r in entries_sorted:
            lines.append(f"**{r['label']}** | {r['sec']}s | tok={r['tok']} | stop={r['stop']}")
            lines.append("")
            out_text = render_output(r)
            # If it's code, wrap in code block
            if "```" in out_text or "def " in out_text[:10] or "class " in out_text[:10]:
                lines.append("```")
                lines.append(out_text.replace("```",""))
                lines.append("```")
            else:
                lines.append(out_text)
            lines.append("")
        lines.append("")

with open(OUTFILE,"w",encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Full report: {OUTFILE}")
