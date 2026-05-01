import urllib.request, json

print("=== Getting current ComfyUI workflow ===", flush=True)

resp = urllib.request.urlopen('http://localhost:8188/history', timeout=5)
history = json.loads(resp.read())
keys = sorted(history.keys())
last = history[keys[-1]]
wf = last['prompt'][3]['extra_pnginfo']['workflow']
nodes = wf['nodes']
links = wf.get('links', [])

# Build lookup: node_id -> node
node_by_id = {n['id']: n for n in nodes}

# Build lookup: link_id -> [from_node, from_slot, to_node, to_slot, type]
link_info = {}
for l in links:
    link_id, src_node, src_slot, dst_node, dst_slot, ltype = l
    link_info[link_id] = {'src': src_node, 'src_slot': src_slot, 'dst': dst_node, 'dst_slot': dst_slot, 'type': ltype}

print(f"=== Workflow: {len(nodes)} nodes, {len(links)} links ===", flush=True)
print(f"{'ID':>4} | {'Type':<35} | {'Widget Values'} | {'Inputs'}", flush=True)
print("=" * 140, flush=True)

for n in nodes:
    nid = n['id']
    wtype = n.get('type', '?')
    wvals = n.get('widgets_values', [])
    inputs = n.get('inputs', [])
    
    # Format widget values
    wstr = json.dumps(wvals, ensure_ascii=False) if wvals else "-"
    
    # Format inputs with connections
    in_strs = []
    for inp in inputs:
        iname = inp.get('name', '?')
        ilink = inp.get('link')
        if ilink is not None and ilink in link_info:
            li = link_info[ilink]
            src_type = node_by_id.get(li['src'], {}).get('type', f'[{li["src"]}]')
            in_strs.append(f"{iname}<-[{li['src']}]{src_type}")
        else:
            in_strs.append(f"{iname}(unconnected)")
    
    in_str = '; '.join(in_strs) if in_strs else "-"
    
    print(f"  [{nid:>3}] {wtype:<35} {wstr[:60]:<62} {in_str[:50]}", flush=True)

print()
print("=" * 140)
print("DETAILED NODE ANALYSIS", flush=True)
print()

# Detailed info for key nodes
for n in sorted(nodes, key=lambda x: x.get('order', 999)):
    nid = n['id']
    wtype = n.get('type', '?')
    title = n.get('title', '')
    wvals = n.get('widgets_values', [])
    
    if wtype in ['LoadImage', 'SaveVideo', 'CLIPLoader', 'VAELoader', 'UNETLoader', 
                  'LoraLoaderModelOnly', 'CLIPTextEncode', 'KSamplerAdvanced',
                  'ModelSamplingSD3', 'WanImageToVideo', 'CreateVideo', 'VAEDecode']:
        
        if wtype == 'KSamplerAdvanced':
            print(f"[{nid}] KSamplerAdvanced (order={n.get('order')})")
            labels = ['steps', 'cfg', 'sampler_name', 'scheduler', 'start_at_step', 'end_at_step', 'denoise', 'seed']
            for i, val in enumerate(wvals):
                lbl = labels[i] if i < len(labels) else f'arg{i}'
                print(f"    {lbl} = {val}")
                
        elif wtype == 'LoraLoaderModelOnly':
            lora_name = wvals[0] if len(wvals) > 0 else '?'
            strength = wvals[1] if len(wvals) > 1 else '?'
            print(f"[{nid}] LoraLoaderModelOnly: lora={lora_name}, strength={strength}")
            
        elif wtype == 'CLIPTextEncode':
            text = wvals[0] if wvals else ''
            print(f"[{nid}] CLIPTextEncode: text='{text[:80]}'")
            
        elif wtype == 'WanImageToVideo':
            labels = ['width', 'height', 'length', 'batch_size']
            for i, val in enumerate(wvals):
                lbl = labels[i] if i < len(labels) else f'arg{i}'
                print(f"    {lbl} = {val}")
                
        elif wtype == 'UNETLoader':
            print(f"[{nid}] UNETLoader: model={wvals[0]}, dtype={wvals[1] if len(wvals)>1 else '?'}")
            
        elif wtype == 'ModelSamplingSD3':
            print(f"[{nid}] ModelSamplingSD3: shift={wvals[0]}")
            
        elif wtype == 'LoadImage':
            print(f"[{nid}] LoadImage: image={wvals[0]}")
            
        elif wtype == 'SaveVideo':
            print(f"[{nid}] SaveVideo: prefix={wvals[0]}")

print()
print("=" * 140)
print("DATA FLOW", flush=True)

# Sort nodes by order to trace execution
sorted_nodes = sorted(nodes, key=lambda x: x.get('order', 999))
print("Execution order:", [f"{n['id']}({n['type']})" for n in sorted_nodes], flush=True)

print()
print("PIPELINE SUMMARY:", flush=True)

# Trace the chain
print("  Model chain:", flush=True)
print("    UNETLoader[95] -> LoraLoader[104] -> LoraLoader[102] -> LoraLoader[101] -> ", end="", flush=True)
print("LoraLoader[106] -> LoraLoader[103] -> LoraLoader[105] -> ModelSamplingSD3[107]", flush=True)
print("     -> KSamplerAdvanced[86] -> (latent) -> KSamplerAdvanced[85]", flush=True)

print("  VAE chain:", flush=True)
print("    VAELoader[90] -> WanImageToVideo[98] -> VAEDecode[87] -> ", end="", flush=True)
print("CreateVideo[117] -> SaveVideo[118]", flush=True)

print("  CLIP chain:", flush=True)
print("    CLIPLoader[84] -> CLIPTextEncode[89] (positive) -> WanImageToVideo[98]", flush=True)
print("    CLIPLoader[84] -> CLIPTextEncode[93] (negative) -> WanImageToVideo[98]", flush=True)

print("  Image input:", flush=True)
print("    LoadImage[1] -> WanImageToVideo[98]", flush=True)

# Save full workflow
with open('d:\\ComfyUI-aki-v3\\current_workflow.json', 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

print(f"\n{'='*80}", flush=True)
print("Full workflow JSON saved to current_workflow.json", flush=True)
print("Done!", flush=True)
