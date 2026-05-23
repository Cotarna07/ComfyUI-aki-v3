import json
import os
from pathlib import Path

def compare_models(d_json, f_json):
    try:
        with open(d_json, 'r', encoding='utf-8-sig') as f:
            d_data = json.load(f)
        with open(f_json, 'r', encoding='utf-8-sig') as f:
            f_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return []

    d_models = {}
    for item in d_data:
        name = os.path.basename(item['FullName'])
        size = item['Length']
        if size > 0:
            d_models[name] = {'path': item['FullName'], 'size': size}

    f_models = {}
    for item in f_data:
        name = os.path.basename(item['FullName'])
        size = item['Length']
        if size > 0:
            f_models[name] = {'path': item['FullName'], 'size': size}

    duplicates = []
    for name, info in d_models.items():
        if name in f_models:
            if info['size'] == f_models[name]['size']:
                duplicates.append(info['path'])
    
    return duplicates

if __name__ == "__main__":
    d_json = r"D:\ComfyUI-aki-v3\agent-skills\runtime\d_models.json"
    f_json = r"D:\ComfyUI-aki-v3\agent-skills\runtime\f_models.json"
    
    dupes = compare_models(d_json, f_json)
    if dupes:
        print(f"FOUND {len(dupes)} DUPLICATES")
        for d in dupes:
            print(d)
    else:
        print("NO DUPLICATES FOUND")
