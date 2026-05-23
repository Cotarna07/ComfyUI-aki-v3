"""删除本地 F 盘中与对端完全重复的模型文件，释放约 556 GB 空间。"""
import os
import time
from datetime import datetime

local_base = r"F:\ComfyUI-aki-v3\ComfyUI\models"
peer_base = r"\\192.168.88.111\d\ComfyUI-aki-v3\ComfyUI\models"
log_dir = r"d:\ComfyUI-aki-v3\agent-skills\scripts\generated\model-dedup\runtime"
os.makedirs(log_dir, exist_ok=True)

log_path = os.path.join(log_dir, f"delete_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

log("=" * 60)
log("开始扫描对比...")

# 收集本地文件
local_files = {}
for root, dirs, files in os.walk(local_base):
    for f in files:
        fp = os.path.join(root, f)
        rel = os.path.relpath(fp, local_base)
        try:
            local_files[rel] = (fp, os.path.getsize(fp))
        except OSError as e:
            log(f"  [SKIP 本地] {rel}: {e}")

# 收集对端文件
peer_files = {}
for root, dirs, files in os.walk(peer_base):
    for f in files:
        fp = os.path.join(root, f)
        rel = os.path.relpath(fp, peer_base)
        try:
            peer_files[rel] = os.path.getsize(fp)
        except OSError as e:
            log(f"  [SKIP 对端] {rel}: {e}")

# 找出可安全删除的文件
to_delete = []
for rel, (fp, size) in local_files.items():
    if rel in peer_files and peer_files[rel] == size:
        to_delete.append((rel, fp, size))

total_size = sum(s for _, _, s in to_delete)
log(f"本地文件: {len(local_files)}, 对端文件: {len(peer_files)}")
log(f"可安全删除: {len(to_delete)} 个文件, 共 {total_size / 1024 / 1024 / 1024:.1f} GB")
log("")

# 确认
log("将在 5 秒后开始删除，按 Ctrl+C 可取消...")
time.sleep(5)

# 执行删除
deleted_count = 0
deleted_size = 0
failed = []

for i, (rel, fp, size) in enumerate(to_delete, 1):
    try:
        os.remove(fp)
        deleted_count += 1
        deleted_size += size
        if i % 20 == 0 or i == len(to_delete):
            log(f"  进度: {i}/{len(to_delete)}  ({deleted_size / 1024 / 1024 / 1024:.1f} GB 已释放)")
    except OSError as e:
        failed.append((rel, str(e)))
        log(f"  [失败] {rel}: {e}")

log("")
log("=" * 60)
log(f"删除完成!")
log(f"  成功: {deleted_count} 个文件")
log(f"  失败: {len(failed)} 个文件")
log(f"  释放空间: {deleted_size / 1024 / 1024 / 1024:.1f} GB")
if failed:
    log("  失败列表:")
    for rel, err in failed:
        log(f"    {rel}: {err}")

# 清理空目录
log("")
log("清理空目录...")
empty_dirs_removed = 0
for root, dirs, files in os.walk(local_base, topdown=False):
    if root == local_base:
        continue
    try:
        if not os.listdir(root):
            os.rmdir(root)
            empty_dirs_removed += 1
    except OSError:
        pass
log(f"  清理空目录: {empty_dirs_removed} 个")

log(f"\n日志已保存到: {log_path}")
