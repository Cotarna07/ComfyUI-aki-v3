import json
import os
from pathlib import Path

def delete_duplicates(d_json, f_json):
    try:
        with open(d_json, 'r', encoding='utf-8-sig') as f:
            d_data = json.load(f)
        with open(f_json, 'r', encoding='utf-8-sig') as f:
            f_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

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

    deleted_count = 0
    freed_space = 0
    for name, info in d_models.items():
        if name in f_models:
            if info['size'] == f_models[name]['size']:
                try:
                    path_to_del = info['path']
                    size = info['size']
                    if os.path.exists(path_to_del):
                        os.remove(path_to_del)
                        print(f"DELETED: {path_to_del} ({size / 1024**3:.2f} GB)")
                        deleted_count += 1
                        freed_space += size
                except Exception as e:
                    print(f"FAILED TO DELETE {info['path']}: {e}")
    
    print(f"\nFINISH: Deleted {deleted_count} files, freed {freed_space / 1024**3:.2f} GB space.")

if __name__ == "__main__":
    # 使用之前保存的干净 JSON
    d_json = r"D:\ComfyUI-aki-v3\agent-skills\runtime\d_models.json"
    f_json = r"D:\ComfyUI-aki-v3\agent-skills\runtime\f_models.json"
    delete_duplicates(d_json, f_json)
