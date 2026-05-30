import json, os

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
MODEL_EXT = (".safetensors",".gguf",".pth",".ckpt",".pt",".onnx",".bin",".sft")
F_ROOT = r"F:\ComfyUI-aki-v3\ComfyUI\models"
Z_ROOT = r"Z:\ComfyUI-aki-v3\ComfyUI\models"

def walk_strings(obj):
    if isinstance(obj,str): yield obj
    elif isinstance(obj,list):
        for x in obj: yield from walk_strings(x)
    elif isinstance(obj,dict):
        for x in obj.values(): yield from walk_strings(x)

# model file -> set of workflows
model_wf = {}
for name in TARGETS:
    with open(os.path.join(WF_DIR,name),"r",encoding="utf-8") as f:
        data=json.load(f)
    for n in data.get("nodes",[]):
        for s in walk_strings(n.get("widgets_values",[])):
            if isinstance(s,str) and s.lower().endswith(MODEL_EXT):
                model_wf.setdefault(s,set()).add(os.path.splitext(name)[0])

# build basename index of F and Z
def index(root):
    idx={}
    if not os.path.isdir(root): return idx
    for dp,dn,fn in os.walk(root):
        for f in fn:
            idx.setdefault(f.lower(),[]).append(os.path.join(dp,f))
    return idx

print("indexing F ..."); fidx=index(F_ROOT)
print("indexing Z ..."); zidx=index(Z_ROOT)

def human(p):
    try:
        b=os.path.getsize(p);
        for u in ["B","KB","MB","GB"]:
            if b<1024: return f"{b:.1f}{u}"
            b/=1024
        return f"{b:.1f}TB"
    except: return "?"

OUT=open(r"D:\ComfyUI-aki-v3\agent-skills\scripts\generated\wan-workflow-check\model_report.txt","w",encoding="utf-8")
def emit(s=""): OUT.write(s+"\n")

on_f=[]; need_copy=[]; missing_both=[]
for m in sorted(model_wf):
    base=os.path.basename(m).lower()
    f_hits=fidx.get(base,[])
    z_hits=zidx.get(base,[])
    status = "F-OK" if f_hits else ("Z-AVAIL" if z_hits else "MISSING")
    if f_hits: on_f.append(m)
    elif z_hits: need_copy.append((m,z_hits[0]))
    else: missing_both.append(m)
    sz = human(z_hits[0]) if z_hits else (human(f_hits[0]) if f_hits else "")
    emit("[%s] %-60s %s" % (status, os.path.basename(m), sz))
    if z_hits:
        emit("        Z: %s" % z_hits[0])

emit("\n==== SUMMARY ====")
emit("On F (ready): %d" % len(on_f))
emit("Need copy from Z: %d" % len(need_copy))
emit("Missing on both F & Z: %d" % len(missing_both))
emit("\n-- NEED COPY (Z->F) --")
for m,z in need_copy:
    emit("%s  (%s)  [%s]" % (os.path.basename(m), human(z), z))
emit("\n-- MISSING ON BOTH --")
for m in missing_both:
    emit("%s   <- %s" % (m, ", ".join(sorted(model_wf[m]))))
OUT.close()
print("done")
