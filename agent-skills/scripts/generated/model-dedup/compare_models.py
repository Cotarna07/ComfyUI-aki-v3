"""对比本地 F 盘与对端网络路径的模型文件，找出重复项。"""
import os
from collections import defaultdict

local_base = r"F:\ComfyUI-aki-v3\ComfyUI\models"
peer_base = r"\\192.168.88.111\d\ComfyUI-aki-v3\ComfyUI\models"

# 收集本地文件: relpath -> size
print("扫描本地模型目录...")
local_files = {}
for root, dirs, files in os.walk(local_base):
    for f in files:
        fp = os.path.join(root, f)
        rel = os.path.relpath(fp, local_base)
        try:
            local_files[rel] = os.path.getsize(fp)
        except OSError:
            pass

print(f"本地文件总数: {len(local_files)}")

# 收集对端文件
print("扫描对端模型目录...")
peer_files = {}
for root, dirs, files in os.walk(peer_base):
    for f in files:
        fp = os.path.join(root, f)
        rel = os.path.relpath(fp, peer_base)
        try:
            peer_files[rel] = os.path.getsize(fp)
        except OSError:
            pass

print(f"对端文件总数: {len(peer_files)}")

# 找出重复: 相同相对路径 AND 相同大小
duplicates = []
for rel, size in local_files.items():
    if rel in peer_files and peer_files[rel] == size:
        duplicates.append((rel, size))

total_size = sum(s for _, s in duplicates)
print(f"\n重复文件数: {len(duplicates)}")
print(f"可释放空间: {total_size / 1024 / 1024 / 1024:.1f} GB")

# 按目录汇总
print("\n=== 按目录分类汇总 ===")
by_dir = defaultdict(lambda: {"count": 0, "size": 0})
for rel, size in duplicates:
    d = rel.split(os.sep)[0]
    by_dir[d]["count"] += 1
    by_dir[d]["size"] += size

for d in sorted(by_dir):
    info = by_dir[d]
    print(f"  {d}: {info['count']} 个文件, {info['size'] / 1024 / 1024 / 1024:.1f} GB")

# 本机独有文件
local_only = [rel for rel in local_files if rel not in peer_files]
local_only_size = sum(local_files[rel] for rel in local_only)
print(f"\n=== 仅本地存在的文件 ===")
print(f"  数量: {len(local_only)}, 大小: {local_only_size / 1024 / 1024 / 1024:.1f} GB")
for rel in sorted(local_only):
    print(f"    {rel}  ({local_files[rel] / 1024 / 1024:.1f} MB)")

# 对端独有文件
peer_only = [rel for rel in peer_files if rel not in local_files]
peer_only_size = sum(peer_files[rel] for rel in peer_only)
print(f"\n=== 仅对端存在的文件 ===")
print(f"  数量: {len(peer_only)}, 大小: {peer_only_size / 1024 / 1024 / 1024:.1f} GB")
for rel in sorted(peer_only):
    print(f"    {rel}  ({peer_files[rel] / 1024 / 1024:.1f} MB)")
