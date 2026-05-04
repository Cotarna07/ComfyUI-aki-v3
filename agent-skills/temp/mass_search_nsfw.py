import urllib.request, urllib.parse, json, ssl, time, os, re

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

# ======= 本地已有模型 =======
LOCAL_LORAS = set()
loras_dir = r'ComfyUI\models\loras'
if os.path.isdir(loras_dir):
    for f in os.listdir(loras_dir):
        LOCAL_LORAS.add(f.lower().replace('.safetensors','').replace('.ckpt','').replace('.pt','').replace('_',' ').replace('-',' '))

ckpt_dir = r'ComfyUI\models\checkpoints'
if os.path.isdir(ckpt_dir):
    for f in os.listdir(ckpt_dir):
        LOCAL_LORAS.add(f.lower().replace('.safetensors','').replace('.ckpt','').replace('.pt','').replace('.gguf','').replace('_',' ').replace('-',' '))

dm_dir = r'ComfyUI\models\diffusion_models'
if os.path.isdir(dm_dir):
    for f in os.listdir(dm_dir):
        LOCAL_LORAS.add(f.lower().replace('.safetensors','').replace('.ckpt','').replace('.pt','').replace('.gguf','').replace('_',' ').replace('-',' '))

print(f'本地已有 {len(LOCAL_LORAS)} 个模型文件')
for l in sorted(LOCAL_LORAS):
    print(f'  - {l[:80]}')

# ======= 全面搜索 NSFW 模型 =======
SEARCHES = [
    # Wan 视频 NSFW
    ('Wan-成人-LoRA', {'limit':15,'sort':'Most Downloaded','period':'Month','query':'wan nsfw','type':'Lora'}),
    ('Wan-裸体-LoRA', {'limit':10,'sort':'Most Downloaded','period':'AllTime','query':'wan nude','type':'Lora'}),
    ('Wan-T2V-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'wan t2v nsfw','type':'Lora'}),
    ('Wan-I2V-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'wan i2v nsfw','type':'Lora'}),
    ('Wan-erotic-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'wan erotic','type':'Lora'}),
    ('Wan-性感-LoRA', {'limit':10,'sort':'Most Downloaded','period':'AllTime','query':'wan sexy','type':'Lora'}),
    
    # Wan 视频 NSFW Checkpoint
    ('Wan-NSFW-Checkpoint', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'wan nsfw','type':'Checkpoint'}),
    
    # Wan video 工作流
    ('Wan-Video-工作流', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'wan video'}),
    
    # SDXL NSFW LoRA
    ('SDXL-NSFW-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','nsfw':'true','type':'Lora'}),
    ('SDXL-nude-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'nude sdxl','type':'Lora'}),
    
    # Illustrious NSFW (当前最热生态)
    ('Illustrious-NSFW-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'illustrious nsfw','type':'Lora'}),
    ('Illustrious-nude-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'illustrious nude','type':'Lora'}),
    
    # Pony NSFW
    ('Pony-NSFW-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'pony nsfw','type':'Lora'}),
    
    # Flux NSFW
    ('Flux-NSFW-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'flux nsfw','type':'Lora'}),
    
    # LTX Video NSFW
    ('LTX-NSFW-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'ltx nsfw','type':'Lora'}),
    ('LTX-Video-NSFW', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'ltx video nsfw'}),
    
    # SD1.5 经典 NSFW
    ('SD15-NSFW-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','nsfw':'true','type':'Lora'}),
    
    # Hunyuan Video NSFW
    ('Hunyuan-NSFW', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'hunyuan nsfw'}),
]

print(f'\n{"="*70}')
print(f'开始大规模搜索...')
print(f'{"="*70}\n')

all_models = {}
total_items = 0

for name, params in SEARCHES:
    data = api_get(params)
    items = data.get('items', [])
    new = 0
    for i in items:
        mid = i['id']
        if mid not in all_models:
            all_models[mid] = i
            new += 1
    total_items += new
    print(f'[{name}] 找到 {len(items)} 个, 新增 {new} 个')
    time.sleep(0.3)  # 避免请求过快

print(f'\n去重后共 {len(all_models)} 个模型')

# 获取详细信息并过滤本地已有的
print(f'\n{"="*70}')
print(f'获取 Top 30 模型详细信息（过滤本地已有）...')
print(f'{"="*70}\n')

# 按下载量排序
sorted_models = sorted(all_models.values(), key=lambda x: x['stats']['downloadCount'], reverse=True)

new_models = []
skipped = []
for m in sorted_models:
    name_lower = m['name'].lower().replace('_',' ').replace('-',' ')
    # 模糊匹配
    is_local = False
    for local in LOCAL_LORAS:
        # 核心词匹配
        core_words = [w for w in name_lower.split() if len(w) > 3]
        local_words = local.split()
        common = set(core_words) & set(local_words)
        if len(common) >= 2 and len(common) >= len(core_words) * 0.4:
            is_local = True
            break
    
    if is_local:
        skipped.append(m['name'][:60])
        continue
    new_models.append(m)
    if len(new_models) >= 30:
        break

print(f'过滤掉 {len(skipped)} 个本地已有模型')
print(f'筛选出 {len(new_models)} 个新模型\n')

# 输出详细信息
out = []
for idx, m in enumerate(new_models, 1):
    mid = m['id']
    name = m['name']
    dl = m['stats']['downloadCount']
    tp = m.get('type', '?')
    versions = m.get('modelVersions', [])
    base = versions[0].get('baseModel', '?') if versions else '?'
    rating = m.get('stats', {}).get('rating', 0)
    thumbs_up = m.get('stats', {}).get('thumbsUpCount', 0)
    
    # 获取详情
    detail = model_detail(mid)
    desc = ''
    trigger_words = []
    file_info = []
    if detail:
        desc_raw = detail.get('description', '')
        desc = ' '.join(desc_raw[:200].replace('<p>','').replace('</p>','').replace('<br>','').replace('\n',' ').split())
        for v in detail.get('modelVersions', [])[:2]:
            tw = v.get('trainedWords', [])
            if tw:
                trigger_words.extend(tw)
            for f in v.get('files', [])[:2]:
                fname = f.get('name', '?')
                fsize = f.get('sizeKB', 0) / 1024
                file_info.append(f'{fname} ({fsize:.1f}MB)')
    
    # 打印
    print(f'--- #{idx} [{tp}] {name[:75]} ---')
    print(f'  : https://civitai.red/models/{mid}')
    print(f'  下载: {dl} | 赞: {thumbs_up} | 评分: {rating:.1f} | Base: {base}')
    if trigger_words:
        print(f'  触发词: {", ".join(set(trigger_words))}')
    if file_info:
        print(f'  文件: {"; ".join(file_info)}')
    if desc:
        print(f'  描述: {desc[:200]}')
    print()
    
    time.sleep(0.2)

print(f'过滤掉的本地模型 ({len(skipped)}):')
for s in skipped:
    print(f'  ~ {s}')

print(f'\n✅ 共推荐 {len(new_models)} 个新模型供审核')