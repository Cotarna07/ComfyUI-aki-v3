import urllib.request
import urllib.parse
import json
import ssl

h = {'User-Agent': 'Mozilla/5.0'}
b = 'https://civitai.red/api/v1/models'
ctx = ssl.create_default_context()

def q(params):
    encoded = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    url = b + '?' + encoded
    req = urllib.request.Request(url, headers=h)
    resp = urllib.request.urlopen(req, timeout=15, context=ctx)
    return json.loads(resp.read())

# NSFW Checkpoint 全时段最热
print('=== NSFW Checkpoint (AllTime) ===')
try:
    for i in q({'limit':'8','sort':'Most Downloaded','period':'AllTime','nsfw':'true','type':'Checkpoint'}).get('items', []):
        base = i.get('modelVersions', [{}])[0].get('baseModel', '?')
        dl = i['stats']['downloadCount']
        print(f"  [{i['type']}] id={i['id']} | {i['name'][:60]} | {dl} DL | Base: {base}")
except Exception as e:
    print(f"  Error: {e}")

print()
print('=== NSFW Lora (AllTime) ===')
try:
    for i in q({'limit':'5','sort':'Most Downloaded','period':'AllTime','nsfw':'true','type':'Lora'}).get('items', []):
        base = i.get('modelVersions', [{}])[0].get('baseModel', '?')
        dl = i['stats']['downloadCount']
        print(f"  [{i['type']}] id={i['id']} | {i['name'][:60]} | {dl} DL | Base: {base}")
except Exception as e:
    print(f"  Error: {e}")

print()
print('=== NSFW Lora (Month, 近一月) ===')
try:
    for i in q({'limit':'5','sort':'Most Downloaded','period':'Month','tag':'NSFW','type':'Lora'}).get('items', []):
        base = i.get('modelVersions', [{}])[0].get('baseModel', '?')
        dl = i['stats']['downloadCount']
        print(f"  [{i['type']}] id={i['id']} | {i['name'][:60]} | {dl} DL | Base: {base}")
except Exception as e:
    print(f"  Error: {e}")

# 用 Month 因为 SixMonths 不被支持
print()
print('=== NSFW Checkpoint (Month) ===')
result = q({'limit':'5','sort':'Most Downloaded','period':'Month','tag':'NSFW','type':'Checkpoint'})
for i in result.get('items', []):
    base = i.get('modelVersions', [{}])[0].get('baseModel', '?')
    dl = i['stats']['downloadCount']
    print(f"  [{i['type']}] id={i['id']} | {i['name'][:60]} | {dl} DL | Base: {base}")

print()
print('=== wan+nsfw 搜索 (Month, Checkpoint) ===')
result = q({'limit':'5','sort':'Most Downloaded','period':'Month','query':'wan nsfw','type':'Checkpoint'})
for i in result.get('items', []):
    dl = i['stats']['downloadCount']
    base = i.get('modelVersions', [{}])[0].get('baseModel', '?')
    print(f"  [{i['type']}] id={i['id']} | {i['name'][:60]} | {dl} DL | Base: {base}")

print()
print('=== wan+nsfw 搜索 (Month, Lora) ===')
result = q({'limit':'5','sort':'Most Downloaded','period':'Month','query':'wan nsfw','type':'Lora'})
for i in result.get('items', []):
    dl = i['stats']['downloadCount']
    base = i.get('modelVersions', [{}])[0].get('baseModel', '?')
    print(f"  [{i['type']}] id={i['id']} | {i['name'][:60]} | {dl} DL | Base: {base}")

print()
print('=== wan video nsfw 搜索 (Month, Lora) ===')
result = q({'limit':'5','sort':'Most Downloaded','period':'Month','query':'wan video nsfw','type':'Lora'})
for i in result.get('items', []):
    dl = i['stats']['downloadCount']
    base = i.get('modelVersions', [{}])[0].get('baseModel', '?')
    print(f"  [{i['type']}] id={i['id']} | {i['name'][:60]} | {dl} DL | Base: {base}")

# 工作流
wf_url = 'https://civitai.red/api/v1/workflows'

print()
print('=== WAN Video 工作流 (Month) ===')
enc = urllib.parse.urlencode({'limit':'5','sort':'Most Downloaded','period':'Month','query':'wan video nsfw'}, quote_via=urllib.parse.quote)
req = urllib.request.Request(wf_url + '?' + enc, headers=h)
try:
    resp = urllib.request.urlopen(req, timeout=15, context=ctx)
    data = json.loads(resp.read())
    for i in data.get('items', []):
        creator = i.get('user', {}).get('username', '?')
        dl = i.get('stats', {}).get('downloadCount', 0)
        print(f"  [Workflow] id={i['id']} | {i['name'][:60]} (by {creator}) | {dl} DL")
except Exception as e:
    print(f"  Error: {e}")

print()
print('=== NSFW 工作流 AllTime ===')
enc = urllib.parse.urlencode({'limit':'5','sort':'Most Downloaded','period':'AllTime','nsfw':'true'}, quote_via=urllib.parse.quote)
req = urllib.request.Request(wf_url + '?' + enc, headers=h)
try:
    resp = urllib.request.urlopen(req, timeout=15, context=ctx)
    data = json.loads(resp.read())
    for i in data.get('items', []):
        creator = i.get('user', {}).get('username', '?')
        dl = i.get('stats', {}).get('downloadCount', 0)
        print(f"  [Workflow] id={i['id']} | {i['name'][:60]} (by {creator}) | {dl} DL")
except Exception as e:
    print(f"  Error: {e}")