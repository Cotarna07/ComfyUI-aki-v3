import json

# Genuinely-missing node types (rgthree frontend group/mute nodes & PainterFLF2V removed)
RGTHREE_FRONTEND = {
    "Fast Groups Bypasser (rgthree)", "Fast Groups Muter (rgthree)",
    "Mute / Bypass Relay (rgthree)", "Mute / Bypass Repeater (rgthree)",
}
CONFIRMED_INSTALLED = {"PainterFLF2V"}  # ComfyUI-PainterI2V

missing = [
 "CLIPLoaderMultiGPU","CM_FloatToInt","CM_IntToFloat","ColorCorrect","ColorMatchImage",
 "ColorMatchToReference","DF_Int_to_Float","EG_WXZ_QH","FL_RIFE","FastFilmGrain",
 "FramePackFindNearestBucket","Incrementer \U0001fab4","K3NKFindNearestBucket","K3NKImageGrab",
 "K3NKImageLoaderWithBlending","K3NKImageOverlay","K3NKSaveLatentPassThrought","NovaSR",
 "PauseWorkflowNode","Resolutions by Ratio (WLSH)","Sigmas Split Value",
 "UmeAiRT_BundleLoader","UmeAiRT_FilesSettings_WAN","UmeAiRT_Negative_Input","UmeAiRT_Positive_Input",
 "UmeAiRT_VideoFrameInterpolation","UmeAiRT_VideoGenerator","UmeAiRT_VideoLightningAccelerator",
 "UmeAiRT_VideoOptimization","UmeAiRT_VideoOutput","UmeAiRT_VideoSettings","UmeAiRT_VideoSmartUpscale",
 "UmeAiRT_WanLoraBlock_3","UnetLoaderGGUFDisTorchMultiGPU","VAELoaderMultiGPU",
 "WanImageToVideo_F2","WanSkipEndFrameImages_F2","ttN concat","ttN int","ttN text",
]
missing = [m for m in missing if m not in RGTHREE_FRONTEND and m not in CONFIRMED_INSTALLED]

with open(r"D:\ComfyUI-aki-v3\ComfyUI\custom_nodes\ComfyUI-Manager\extension-node-map.json","r",encoding="utf-8") as f:
    emap = json.load(f)

# emap: { repo_url: [ [node_type,...], {title/...} ] }
node_to_repos = {}
for repo, val in emap.items():
    try:
        nodelist = val[0]
    except Exception:
        continue
    for nt in nodelist:
        node_to_repos.setdefault(nt, []).append(repo)

OUT = open(r"D:\ComfyUI-aki-v3\agent-skills\scripts\generated\wan-workflow-check\missing_map.txt","w",encoding="utf-8")
def emit(s=""):
    OUT.write(s+"\n")

unresolved = []
for nt in missing:
    repos = node_to_repos.get(nt)
    if repos:
        emit("%-35s -> %s" % (nt, " | ".join(repos)))
    else:
        emit("%-35s -> ??? NOT IN MANAGER DB" % nt)
        unresolved.append(nt)

emit("\n--- UNRESOLVED (%d) ---" % len(unresolved))
for nt in unresolved:
    emit(nt)
OUT.close()
print("done", len(missing), "missing,", len(unresolved), "unresolved")
