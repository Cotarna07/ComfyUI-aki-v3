import urllib.request, urllib.parse, json, ssl

h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
ctx = ssl.create_default_context()
BASE = 'https://civitai.red/api/v1/models'

def api_get(params):
    url = BASE + '?' + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    try:
        resp = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20, context=ctx)
        return json.loads(resp.read())
    except Exception as e:
        return {'items': []}

def model_detail(mid):
    try:
        resp = urllib.request.urlopen(urllib.request.Request(f'{BASE}/{mid}', headers=h), timeout=15, context=ctx)
        return json.loads(resp.read())
    except:
        return {}

SEARCHES = [
    ('Wan 成人 LoRA (AllTime)', {'limit':'10','sort':'Most Downloaded','period':'AllTime','query':'wan nsfw','type':'Lora'}),
    ('Wan NSFW LoRA (Month)', {'limit':'10','sort':'Most Downloaded','period':'Month','query':'wan nsfw','type':'Lora'}),
    ('Wan nude LoRA', {'limit':'10','sort':'Most Downloaded','period':'AllTime','query':'wan nude','type':'Lora'}),
    ('Wan adult LoRA', {'limit':'10','sort':'Most Downloaded','period':'Month','query':'wan adult','type':'Lora'}),
    ('Wan Video NSFW (全类型)', {'limit':'15','sort':'Most Downloaded','period':'Month','query':'wan video nsfw'}),
    ('Wan 2.1 NSFW LoRA', {'limit':'10','sort':'Most Downloaded','period':'AllTime','query':'wan 2.1 nsfw','type':'Lora'}),
    ('Wan I2V NSFW LoRA', {'limit':'10','sort':'Most Downloaded','period':'AllTime','query':'wan i2v nsfw','type':'Lora'}),
]

all = {}  # unified by id

for name, p in SEARCHES:
    print(f'--- {name} ---')
    data = api_get(p)
    for i in data.get('items', []):
        mid = i['id']
        if mid not in all:
            all[mid] = i
            tp = i.get('type', '?')
            print(f'  [{tp}] id={mid} | {i["name"][:70]} | {i["stats"]["downloadCount"]} DL')

print(f'\n===== 去重后共 {len(all)} 个模型 =====\n')

# 按下载量排序取 Top 20
top = sorted(all.values(), key=lambda x: x['stats']['downloadCount'], reverse=True)[:20]

for idx, m in enumerate(top, 1):
    mid = m['id']
    name = m['name']
    dl = m['stats']['downloadCount']
    tp = m.get('type', '?')
    versions = m.get('modelVersions', [])
    base = versions[0].get('baseModel', '?') if versions else '?'
    
    is_wan = any(kw in str(m).lower() for kw in ['wan', 'w-a-n'])
    
    print(f'--- #{idx} [{tp}] {name[:75]} ---')
    print(f'  id={mid} | DL={dl} | Base={base}')
    print(f'   https://civitai.red/models/{mid}')
    
    # 触发词
    for v in versions[:1]:
        tw = v.get('trainedWords', [])
        if tw:
            print(f'  触发词: {", ".join(tw)}')
        for f in v.get('files', [])[:2]:
            fname = f.get('name', '?')
            fsize = f.get('sizeKB', 0) / 1024
            print(f'  文件: {fname} ({fsize:.1f}MB)')
    print()