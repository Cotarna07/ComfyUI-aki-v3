import urllib.request
import urllib.parse
import json
import ssl

h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
ctx = ssl.create_default_context()
BASE = 'https://civitai.red/api/v1/models'

def api_get(url, params=None):
    if params:
        url = url + '?' + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    req = urllib.request.Request(url, headers=h)
    try:
        resp = urllib.request.urlopen(req, timeout=20, context=ctx)
        return json.loads(resp.read())
    except Exception as e:
        print(f"  [API ERROR] {e}")
        return {}

def get_model_versions(model_id):
    """获取模型所有版本详情"""
    url = f'{BASE}/{model_id}'
    req = urllib.request.Request(url, headers=h)
    try:
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        return json.loads(resp.read())
    except:
        return {}

# 1. 搜索 Wan2.2 T2V NSFW LoRA
print('=' * 70)
print('【Wan 2.2 NSFW LoRA 详细搜索】')
print()

queries = [
    ('Wan 2.2 NSFW LoRA (T2V)', {'limit': '10', 'sort': 'Most Downloaded', 'period': 'Month', 'query': 'wan 2.2 nsfw', 'type': 'Lora'}),
    ('Wan 2.2 成人/Lewd LoRA', {'limit': '10', 'sort': 'Most Downloaded', 'period': 'AllTime', 'query': 'wan 2.2 adult', 'type': 'Lora'}),
    ('Wan Video NSFW LoRA', {'limit': '10', 'sort': 'Most Downloaded', 'period': 'Month', 'query': 'wan video nsfw', 'type': 'Lora'}),
    ('Wan 2.2 I2V NSFW LoRA', {'limit': '10', 'sort': 'Most Downloaded', 'period': 'AllTime', 'query': 'wan i2v nsfw', 'type': 'Lora'}),
]

all_models = {}

for title, params in queries:
    print(f'--- {title} ---')
    data = api_get(BASE, params)
    items = data.get('items', [])
    print(f'  找到 {len(items)} 个结果')
    for i in items:
        mid = i['id']
        mtype = i.get('type', '?')
        name = i['name']
        dl = i['stats']['downloadCount']
        if mid not in all_models:
            all_models[mid] = i
            print(f'  [{mtype}] id={mid} | {name[:70]} | {dl} DL')

print()
print('=' * 70)
print('【获取 Top 15 模型详细信息（触发词、权重、描述）】')
print()

# 按下载量排序取 top 15
sorted_models = sorted(all_models.values(), key=lambda x: x['stats']['downloadCount'], reverse=True)[:15]

for idx, model in enumerate(sorted_models, 1):
    mid = model['id']
    name = model['name']
    dl = model['stats']['downloadCount']
    mtype = model.get('type', '?')
    
    print(f'--- #{idx} [{mtype}] {name[:80]} ---')
    print(f'  civitai ID: {mid} | 下载: {dl}')
    print(f'  : https://civitai.red/models/{mid}')
    
    # 获取详细版本
    detail = get_model_versions(mid)
    if detail:
        desc = detail.get('description', '')
        # 截取前 300 字符
        if desc:
            desc_short = desc[:300].replace('\n', ' ').replace('\r', '')
            print(f'  描述: {desc_short}...')
        
        versions = detail.get('modelVersions', [])
        for vi, v in enumerate(versions[:2]):  # 最多2个版本
            vname = v.get('name', '?')
            base_model = v.get('baseModel', '?')
            print(f'  v{vi+1}: {vname} | Base: {base_model}')
            
            # 触发词
            tw = v.get('trainedWords', [])
            if tw:
                print(f'  触发词: {", ".join(tw)}')
            
            # 文件
            files = v.get('files', [])
            for f in files[:2]:
                fname = f.get('name', '?')
                fsize = f.get('sizeKB', 0) / 1024
                ftype = f.get('type', '?')
                print(f'  文件: {fname} ({fsize:.1f}MB) [{ftype}]')
    print()

# 2. 搜索 Wan2.2 NSFW Checkpoint
print('=' * 70)
print('【Wan 2.2 NSFW Checkpoint / 基础模型】')
print()
cp_data = api_get(BASE, {'limit': '5', 'sort': 'Most Downloaded', 'period': 'Month', 'query': 'wan 2.2 nsfw', 'type': 'Checkpoint'})
for i in cp_data.get('items', []):
    mid = i['id']
    name = i['name']
    dl = i['stats']['downloadCount']
    versions = i.get('modelVersions', [])
    base = versions[0].get('baseModel', '?') if versions else '?'
    print(f'  [Checkpoint] id={mid} | {name[:70]} | {dl} DL | Base: {base}')
    detail = get_model_versions(mid)
    if detail:
        for v in detail.get('modelVersions', [])[:1]:
            tw = v.get('trainedWords', [])
            if tw:
                print(f'    触发词: {", ".join(tw)}')
            for f in v.get('files', [])[:1]:
                print(f'    文件: {f.get("name","?")} ({f.get("sizeKB",0)/1024:.1f}MB)')

print()
print('=' * 70)
print('【Wan 2.2 NSFW 工作流】')
print()
wf_data = api_get(BASE, {'limit': '5', 'sort': 'Most Downloaded', 'period': 'Month', 'query': 'wan 2.2 nsfw', 'types': 'Workflows'})
for i in wf_data.get('items', []):
    mid = i['id']
    name = i['name']
    dl = i.get('stats', {}).get('downloadCount', 0)
    creator = i.get('user', {}).get('username', '?')
    print(f'  [Workflow] id={mid} | {name[:70]} | {dl} DL | by {creator}')
    print(f'    : https://civitai.red/models/{mid}')

print()
print('=' * 70)
print('【高下载 NSFW/Suggestive 类 LoRA 补充搜索】')
print()
extra = api_get(BASE, {'limit': '5', 'sort': 'Most Downloaded', 'period': 'AllTime', 'nsfw': 'true', 'types': 'Lora', 'query': 'wan video'})
for i in extra.get('items', []):
    mid = i['id']
    name = i['name']
    dl = i['stats']['downloadCount']
    print(f'  [LoRA] id={mid} | {name[:70]} | {dl} DL')

print()
print('✅ 搜索完成！')