import urllib.request, json

resp = urllib.request.urlopen('http://localhost:8188/history', timeout=5)
history = json.loads(resp.read())
keys = sorted(history.keys())
last = history[keys[-1]]
prompt = last.get('prompt', [])
exec_config = prompt[2]  # dict: node_id -> {class_type, inputs_dict}

print("=" * 100)
print("## Actual Execution Graph (from prompt[2])")
print("=" * 100)

for nid in sorted(exec_config.keys(), key=int):
    n = exec_config[nid]
    ctype = n['class_type']
    inp = n.get('inputs', {})
    print(f"\n[{nid}] {ctype}")
    for iname, ival in inp.items():
        if isinstance(ival, list):
            print(f"    {iname} = <- Node[{ival[0]}].output[{ival[1]}]")
        else:
            s = str(ival)
            if len(s) > 120:
                s = s[:120] + "..."
            print(f"    {iname} = {s}")

print("\n\n" + "=" * 100)
print("## KEY FLOW ANALYSIS")
print("=" * 100)

# Trace model chain
print("\n=== Model Chain (UNET -> LoRAs -> Sampler) ===")
for nid in sorted(exec_config.keys(), key=int):
    n = exec_config[nid]
    ctype = n['class_type']
    inp = n.get('inputs', {})
    
    if ctype in ['UNETLoader', 'LoraLoaderModelOnly', 'ModelSamplingSD3']:
        model_input = inp.get('model', None)
        if isinstance(model_input, list):
            print(f"  [{nid}] {ctype}  model <- [{model_input[0]}]")
        else:
            print(f"  [{nid}] {ctype}  (source / no model input)")

print("\n\n=== Conditioning Flow ===")
for nid in sorted(exec_config.keys(), key=int):
    n = exec_config[nid]
    ctype = n['class_type']
    inp = n.get('inputs', {})
    
    if ctype == 'WanImageToVideo':
        for k in ['positive', 'negative', 'vae', 'images']:
            val = inp.get(k, None)
            if isinstance(val, list):
                print(f"  WanImageToVideo[{nid}].{k} <- Node[{val[0]}].output[{val[1]}]")
        # Show other params
        for k in ['width', 'height', 'length', 'batch_size']:
            if k in inp:
                print(f"  WanImageToVideo[{nid}].{k} = {inp[k]}")

print("\n\n=== KSampler Analysis ===")
for nid in sorted(exec_config.keys(), key=int):
    n = exec_config[nid]
    ctype = n['class_type']
    inp = n.get('inputs', {})
    
    if ctype == 'KSamplerAdvanced':
        print(f"\n  KSampler[{nid}]:")
        for k, val in inp.items():
            if isinstance(val, list):
                print(f"    {k} <- Node[{val[0]}].output[{val[1]}]")
            else:
                print(f"    {k} = {val}")
        
        # What consumes this KSampler's output?
        print(f"    -> FOLLOWERS:", end="")
        followers = []
        for nid2 in sorted(exec_config.keys(), key=int):
            inp2 = exec_config[nid2].get('inputs', {})
            for k2, v2 in inp2.items():
                if isinstance(v2, list) and v2[0] == nid:
                    followers.append(f"[{nid2}]{exec_config[nid2]['class_type']}.{k2}")
        if followers:
            for f in followers:
                print(f" {f}", end="")
        else:
            print(" (none)", end="")
        print()

print("\n\n" + "=" * 100)
print("## POSITIVE vs NEGATIVE mapping check")
print("=" * 100)
for nid in sorted(exec_config.keys(), key=int):
    n = exec_config[nid]
    inp = n.get('inputs', {})
    if n['class_type'] == 'WanImageToVideo':
        pos = inp.get('positive', [])
        neg = inp.get('negative', [])
        if isinstance(pos, list):
            from_node = exec_config.get(str(pos[0]), {})
            text = from_node.get('inputs', {}).get('text', '?') if from_node else '?'
            print(f"  POSITIVE <- Node[{pos[0]}] = '{str(text)[:60]}'")
        if isinstance(neg, list):
            from_node = exec_config.get(str(neg[0]), {})
            text = from_node.get('inputs', {}).get('text', '?') if from_node else '?'
            print(f"  NEGATIVE <- Node[{neg[0]}] = '{str(text)[:60]}'")
