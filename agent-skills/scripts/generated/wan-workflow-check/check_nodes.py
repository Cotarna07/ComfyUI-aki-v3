import json, os, re

WF_DIR = r"D:\ComfyUI-aki-v3\agent-skills\comfyui\workflows\TEST\26-5-29"
TARGETS = [
    "Wan 2.1 - seamless loop workflow v1.2.json",
    "WAN2.2 I2V Only - K3NK v2.5.4.json",
    "WAN2.2 T2V-I2V-T2I-S2V K3NK v2.5.4 SVI.json",
    "WAN2.2_Img2video_auto.json",
    "WAN2.2_Img2video_manual.json",
    "WAN2.2_LOOP_NATIVE_UPSCALER_GGUF.json",
    "WAN2.2_LOOP_NATIVE_UPSCALER.json",
    "WAN2.2_LOOP.json",
]

# Frontend-only / structural node types that don't need a backend package
FRONTEND = {
    "Note", "MarkdownNote", "Reroute", "Bookmark (rgthree)", "Label (rgthree)",
    "PrimitiveNode", "PrimitiveInt", "PrimitiveFloat", "PrimitiveString",
    "PrimitiveStringMultiline", "Seed Everywhere",
}
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Collect node types per workflow + union
wf_types = {}
union = set()
for name in TARGETS:
    with open(os.path.join(WF_DIR, name), "r", encoding="utf-8") as f:
        data = json.load(f)
    ts = set()
    for n in data.get("nodes", []):
        t = n.get("type")
        if not t:
            continue
        if UUID_RE.match(t):
            continue  # workflow-local group/subgraph node
        ts.add(t)
    wf_types[name] = ts
    union |= ts

# Index: read all source files under custom_nodes + comfy_extras + core nodes
ROOTS = [
    r"D:\ComfyUI-aki-v3\ComfyUI\custom_nodes",
]
CORE_FILES = [r"D:\ComfyUI-aki-v3\ComfyUI\nodes.py"]
# comfy_extras holds .py files directly (not subdirs) -> treat all as core
_ce = r"D:\ComfyUI-aki-v3\ComfyUI\comfy_extras"
if os.path.isdir(_ce):
    for dp, dn, fn in os.walk(_ce):
        for f in fn:
            if f.endswith(".py"):
                CORE_FILES.append(os.path.join(dp, f))

# Map: which file blob contains the type string -> infer package
blobs = []  # (package_name, text)
for root in ROOTS:
    if not os.path.isdir(root):
        continue
    for pkg in os.listdir(root):
        pkgdir = os.path.join(root, pkg)
        if not os.path.isdir(pkgdir):
            continue
        text_parts = []
        for dp, dn, fn in os.walk(pkgdir):
            if ".git" in dp:
                continue
            for f in fn:
                if f.endswith((".py", ".js")):
                    try:
                        with open(os.path.join(dp, f), "r", encoding="utf-8", errors="ignore") as fh:
                            text_parts.append(fh.read())
                    except Exception:
                        pass
        blobs.append((pkg, "\n".join(text_parts)))

core_parts = []
for cf in CORE_FILES:
    try:
        with open(cf, "r", encoding="utf-8", errors="ignore") as fh:
            core_parts.append(fh.read())
    except Exception:
        pass
blobs.append(("[ComfyUI-core]", "\n".join(core_parts)))

def find_pkg(node_type):
    # exact quoted occurrences
    pats = ['"%s"' % node_type, "'%s'" % node_type]
    hits = []
    for pkg, text in blobs:
        for p in pats:
            if p in text:
                hits.append(pkg)
                break
    return hits

OUT = open(r"D:\ComfyUI-aki-v3\agent-skills\scripts\generated\wan-workflow-check\node_report.txt", "w", encoding="utf-8")
def emit(s=""):
    OUT.write(s + "\n")

avail = {}
missing = {}
for t in sorted(union):
    if t in FRONTEND:
        continue
    hits = find_pkg(t)
    if hits:
        avail[t] = hits
    else:
        missing[t] = []

emit("==== MISSING NODE TYPES (%d) ====" % len(missing))
for t in sorted(missing):
    # which workflows need it
    wfs = [os.path.splitext(n)[0] for n in TARGETS if t in wf_types[n]]
    emit("%s   <- %s" % (t, ", ".join(wfs)))

emit("\n==== AVAILABLE NODE TYPES (%d) ====" % len(avail))
for t in sorted(avail):
    emit("%s   [%s]" % (t, ",".join(sorted(set(avail[t])))))

# Per workflow missing summary
emit("\n==== PER-WORKFLOW MISSING ====")
for name in TARGETS:
    miss = sorted([t for t in wf_types[name] if t in missing])
    emit("\n# %s" % name)
    if miss:
        for m in miss:
            emit("   MISSING: %s" % m)
    else:
        emit("   (all node types resolved)")
OUT.close()
print("done")
