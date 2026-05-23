"""
VPS 环境检查 + 模型下载脚本
SSH 到 175.24.132.54，检查磁盘空间，下载模型
"""
import paramiko
import sys
import time

HOST = "175.24.132.54"
USER = "ubuntu"
PASS = "happy365@"
PORT = 22

def ssh_exec(ssh, cmd, timeout=60):
    """执行命令并返回输出"""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out.strip(), err.strip()

def main():
    print(f"[INFO] 连接 {USER}@{HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
        print("[OK] SSH 已连接")
    except Exception as e:
        print(f"[FAIL] SSH 连接失败: {e}")
        return

    # 1. 检查磁盘
    print("\n=== VPS 磁盘空间 ===")
    out, err = ssh_exec(ssh, "df -h / && df -h /home 2>/dev/null; echo '---'; free -h | head -2")
    print(out)

    # 2. 检查工具
    print("\n=== 可用工具 ===")
    for tool in ["python3", "pip3", "aria2c", "wget", "curl", "rsync"]:
        out, _ = ssh_exec(ssh, f"which {tool} 2>/dev/null && {tool} --version 2>/dev/null | head -1 || echo 'NOT FOUND'")
        print(f"  {tool}: {out.split(chr(10))[0] if out else 'NOT FOUND'}")

    # 3. 测试到 CivitAI 和 HF 的连接速度
    print("\n=== 网络测试 ===")
    out, _ = ssh_exec(ssh, "curl -s -o /dev/null -w 'CivitAI: %{http_code} %{time_total}s\n' --connect-timeout 10 'https://civitai.com/api/v1/models/2604673' 2>&1")
    print(f"  {out}")
    out, _ = ssh_exec(ssh, "curl -s -o /dev/null -w 'HuggingFace: %{http_code} %{time_total}s\n' --connect-timeout 10 'https://huggingface.co' 2>&1")
    print(f"  {out}")

    ssh.close()
    print("\n[INFO] 完成")

if __name__ == "__main__":
    main()
