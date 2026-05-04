import urllib.request, urllib.parse, json, ssl, time, os

h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
ctx = ssl.create_default_context()
BASE = 'https://civitai.red/api/v1/models'

def api(params):
    url = BASE + '?' + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    try:
        resp = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20, context=ctx)
        return json.loads(resp.read())
    except Exception as e:
        return {'items': []}

# 本地模型
LOCAL = set()
for d in [r'ComfyUI\models\loras', r'ComfyUI\models\checkpoints', r'ComfyUI\models\diffusion_models']:
    if os.path.isdir(d):
        for f in os.listdir(d):
            name = f.lower().replace('.safetensors','').replace('.ckpt','').replace('.pt','').replace('.gguf','')
            LOCAL.add(name)

# 搜索集合
SEARCHES = [
    # === Wan 视频 NSFW ===
    ('Wan-LoRA-NSFW', {'limit':10,'sort':'Most Downloaded','period':'AllTime','query':'wan nsfw','type':'Lora'}),
    ('Wan-LoRA-nude', {'limit':10,'sort':'Most Downloaded','period':'AllTime','query':'wan nude','type':'Lora'}),
    ('Wan-LoRA-sexy', {'limit':10,'sort':'Most Downloaded','period':'AllTime','query':'wan sexy','type':'Lora'}),
    ('Wan-Checkpoint-NSFW', {'limit':10,'sort':'Most Downloaded','period':'AllTime','query':'wan nsfw','type':'Checkpoint'}),
    ('Wan-Workflow', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'wan video'}),
    
    # === 图片模型 NSFW LoRA ===
    ('SDXL-NSFW-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','nsfw':'true','type':'Lora','query':'sdxl nsfw'}),
    ('Illustrious-NSFW-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'illustrious nsfw','type':'Lora'}),
    ('Pony-NSFW-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'pony nsfw','type':'Lora'}),
    ('Flux-NSFW-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'flux nsfw','type':'Lora'}),
    ('NoobAI-NSFW-LoRA', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'noobai nsfw','type':'Lora'}),
    
    # === 视频模型 NSFW ===
    ('LTX-Video-NSFW', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'ltx video nsfw','type':'Lora'}),
    ('Hunyuan-NSFW', {'limit':10,'sort':'Most Downloaded','period':'Month','query':'hunyuan nsfw','type':'Lora'}),
]

all_m = {}
for name, p in SEARCHES:
    data = api(p)
    for i in data.get('items', []):
        mid = i['id']
        if mid not in all_m:
            all_m[mid] = i
    print(f'[{name}] items={len(data.get("items",[]))} total_unique={len(all_m)}')
    time.sleep(0.2)

# 按下载量排序，过滤本地
sorted_m = sorted(all_m.values(), key=lambda x: x['stats']['downloadCount'], reverse=True)

def is_local(m):
    name = m['name'].lower().replace('_',' ').replace('-',' ')
    for l in LOCAL:
        l2 = l.replace('_',' ').replace('-',' ')
        if len(name) > 10 and len(l2) > 10:
            # 重叠系数
            ws = set(name.split())
            ls = set(l2.split())
            overlap = ws & ls
            if len(overlap) >= 2 and len(overlap) / max(len(ws),1) > 0.35:
                return True
    return False

new_m = [m for m in sorted_m if not is_local(m)]
skipped = [m for m in sorted_m if is_local(m)]

print(f'\n新模型: {len(new_m)}, 跳过本地: {len(skipped)}')

# 写 markdown 文档
md = f'''# ComfyUI NSFW 模型 & 工作流 审核清单

> 生成时间: {time.strftime("%Y-%m-%d %H:%M")}  
> 数据来源: Civitai API  
> 搜索范围: NSFW 相关, 近半年热门, 多生态覆盖  
> 状态: **待审核**

---

## 📋 本地已有模型 (无需重复下载)

'''

for s in skipped:
    base = s.get('modelVersions', [{}])[0].get('baseModel', '?') if s.get('modelVersions') else '?'
    md += f'- ~~{s["name"][:85]}~~ (id={s["id"]}, {base})\n'

md += f'''

---

## 🆕 推荐下载模型 ({len(new_m)} 个)

### 📹 视频模型 (Wan / LTX / Hunyuan)

'''

for i, m in enumerate(new_m):
    tp = m.get('type','?')
    versions = m.get('modelVersions', [])
    base = versions[0].get('baseModel','?') if versions else '?'
    dl = m['stats']['downloadCount']
    mid = m['id']
    name = m['name']
    tw = versions[0].get('trainedWords',[]) if versions else []
    files = []
    if versions:
        for f in versions[0].get('files',[])[:2]:
            files.append(f'{f.get("name","?")} ({f.get("sizeKB",0)/1024:.0f}MB)')
    
    # 分类
    cat = '🖼️ 图片' 
    if any(k in base.lower()+name.lower() for k in ['wan','ltx','hunyuan']):
        cat = '📹 视频'
    
    md += f'''### {i+1}. {name}

| 属性 | 值 |
|---|---|
| **类型** | {tp} |
| **Civitai ID** | {mid} |
| **链接** | https://civitai.red/models/{mid} |
| **下载量** | {dl:,} |
| **基础模型** | {base} |
| **触发词** | {", ".join(tw) if tw else "无"} |
| **文件** | {"; ".join(files) if files else "见详情页"} |

---
'''
    if (i+1) % 8 == 0:
        md += '\n'

md += f'''
---

## 📊 统计概览

- 搜索接口: {len(SEARCHES)} 个查询
- 去重后: {len(all_m)} 个唯一模型
- 本地已有: {len(skipped)} 个 (已过滤)
- **新增推荐: {len(new_m)} 个**

## 📝 使用说明

1. 访问链接查看样图和用户反馈
2. 下载 `.safetensors` 文件放入对应目录:
   - LoRA → `ComfyUI/models/loras/`
   - Checkpoint → `ComfyUI/models/checkpoints/`
   - Diffusion Model → `ComfyUI/models/diffusion_models/`
3. 工作流 `.zip` 文件导入 ComfyUI 后需调整路径

---

> ⚠️ 本清单仅供审核参考，实际效果以测试为准
'''

with open(r'agent-skills\docs\NSFW_model_review_2026-05-02.md', 'w', encoding='utf-8') as f:
    f.write(md)

print(f'\n✅ 文档已生成: agent-skills/docs/NSFW_model_review_2026-05-02.md')