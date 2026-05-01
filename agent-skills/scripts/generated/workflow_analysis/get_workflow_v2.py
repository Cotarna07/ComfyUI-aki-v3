import urllib.request, json

resp = urllib.request.urlopen('http://localhost:8188/history', timeout=5)
history = json.loads(resp.read())
keys = sorted(history.keys())
last = history[keys[-1]]
wf = last['prompt'][3]['extra_pnginfo']['workflow']
nodes = wf['nodes']
links = wf.get('links', [])

print(f"=== Links ({len(links)}) ===")
for l in links:
    print(f'  [{l[0]}] {l[3]}[{l[1]}].{l[6]} -> {l[5]}[{l[2]}].{l[7]}')

print()
print("=== Key node widget values ===")
for n in nodes:
    if n['type'] in ['KSamplerAdvanced', 'WanImageToVideo', 'CLIPTextEncode', 'LoraLoaderModelOnly', 'UNETLoader', 'ModelSamplingSD3']:
        print(f'Node {n["id"]} ({n["type"]}): {json.dumps(n["widgets_values"], ensure_ascii=False)}')

print()
print("=== All nodes with inputs ===")
for n in nodes:
    inputs = n.get('inputs', [])
    if inputs:
        for inp in inputs:
            if inp.get('link') is not None:
                print(f'  Node {n["id"]} ({n["type"]}) input "{inp["name"]}" <- link {inp["link"]}')
