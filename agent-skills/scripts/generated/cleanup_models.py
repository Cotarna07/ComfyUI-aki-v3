import json
import os
from pathlib import Path

def compare_models(d_json, f_json):
    with open(d_json, 'r', encoding='utf-8') as f:
        d_data = json.load(f)
    # F 盘的文件列表可能因为 PowerShell 输出的原因需要处理一下，或者直接读取
    # 这里我们直接读取第二次运行生成的 content.txt，它看起来也是 JSON 格式但外面包了一层 PowerShell 的提示
    with open(f_json, 'r', encoding='utf-8') as f:
        f_raw = f.read()
        # 尝试修剪掉 PowerShell 提示
        if '[' in f_raw:
            f_content = f_raw[f_raw.find('['):f_raw.rfind(']')+1]
            f_data = json.loads(f_content)
        else:
            print("F data format error")
            return

    d_models = {}
    for item in d_data:
        name = os.path.basename(item['FullName'])
        size = item['Length']
        if size > 0: # 忽略空文件夹标记文件
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
    d_json = r"c:\Users\Administrator\AppData\Roaming\Code\User\workspaceStorage\6ae9feee5d319aa985b135fb4a177aca\GitHub.copilot-chat\chat-session-resources\c606d51c-aa87-40b1-8883-84a49413a0d4\call_MHw5UjRDYzBiRm93ejVKZjB2QXU__vscode-1778670482992\content.json"
    f_json = r"c:\Users\Administrator\AppData\Roaming\Code\User\workspaceStorage\6ae9feee5d319aa985b135fb4a177aca\GitHub.copilot-chat\chat-session-resources\c606d51c-aa87-40b1-8883-84a49413a0d4\call_MHxxcTNlY2pIV1BUQUdVNVJzdXA__vscode-1778670482993\content.txt"
    
    dupes = compare_models(d_json, f_json)
    if dupes:
        print(f"找到 {len(dupes)} 个重复文件：")
        for d in dupes:
            print(d)
    else:
        print("未发现完全匹配的重复模型文件。")
