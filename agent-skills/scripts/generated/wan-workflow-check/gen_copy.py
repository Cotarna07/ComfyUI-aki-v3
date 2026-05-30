import json, os

WF_DIR = r"D:\ComfyUI-aki-v3\agent-skills\comfyui\workflows\TEST\26-5-29"
TARGETS = [
    "Wan 2.1 - seamless loop workflow v1.2.json","WAN2.2 I2V Only - K3NK v2.5.4.json",
    "WAN2.2 T2V-I2V-T2I-S2V K3NK v2.5.4 SVI.json","WAN2.2_Img2video_auto.json",
    "WAN2.2_Img2video_manual.json","WAN2.2_LOOP_NATIVE_UPSCALER_GGUF.json",
    "WAN2.2_LOOP_NATIVE_UPSCALER.json","WAN2.2_LOOP.json",
]
MODEL_EXT=(".safetensors",".gguf",".pth",".ckpt",".pt",".onnx",".bin",".sft")
F_ROOT=r"F:\ComfyUI-aki-v3\ComfyUI\models"; Z_ROOT=r"Z:\ComfyUI-aki-v3\ComfyUI\models"

def ws(o):
    if isinstance(o,str): yield o
    elif isinstance(o,list):
        for x in o: yield from ws(x)
    elif isinstance(o,dict):
        for x in o.values(): yield from ws(x)

models=set()
for n in TARGETS:
    d=json.load(open(os.path.join(WF_DIR,n),encoding="utf-8"))
    for node in d.get("nodes",[]):
        for s in ws(node.get("widgets_values",[])):
            if isinstance(s,str) and s.lower().endswith(MODEL_EXT):
                models.add(s)

def index(root):
    idx={}
    for dp,dn,fn in os.walk(root):
        for f in fn: idx.setdefault(f.lower(),[]).append(os.path.join(dp,f))
    return idx
fidx=index(F_ROOT); zidx=index(Z_ROOT)

pairs=[]  # (src, dst)
for m in sorted(models):
    base=os.path.basename(m).lower()
    if fidx.get(base): continue          # already on F
    z=zidx.get(base)
    if not z: continue                   # missing on both
    src=z[0]
    rel=os.path.relpath(src, Z_ROOT)     # preserve category/subdir
    dst=os.path.join(F_ROOT, rel)
    pairs.append((src,dst))

# Emit robocopy ps1 (robocopy works on dir+file)
lines=["$ErrorActionPreference='Continue'"]
groups={}
for src,dst in pairs:
    sdir=os.path.dirname(src); ddir=os.path.dirname(dst); fn=os.path.basename(src)
    groups.setdefault((sdir,ddir),[]).append(fn)
for (sdir,ddir),fns in groups.items():
    flist=" ".join('"%s"'%f for f in fns)
    lines.append('robocopy "%s" "%s" %s /J /R:1 /W:3 /NFL /NDL /NP /NJH'%(sdir,ddir,flist))
lines.append("Write-Output 'COPY_DONE'")
open(r"D:\ComfyUI-aki-v3\agent-skills\scripts\generated\wan-workflow-check\do_copy.ps1","w",encoding="utf-8").write("\n".join(lines))
print("pairs:",len(pairs))
for s,d in pairs: print(os.path.basename(s))
