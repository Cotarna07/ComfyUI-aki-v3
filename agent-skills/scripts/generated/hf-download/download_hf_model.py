"""
HuggingFace 模型可靠下载工具
============================
解决从 HuggingFace 下载大模型时的常见问题：
- 连接不稳定 / 速度慢 → 自动使用 HF 镜像站
- 下载中断 → 支持断点续传 (resume)
- 大文件超时 → 分片下载 + 自动重试

用法:
    # 基础用法（自动使用 hf-mirror.com 镜像）
    python download_hf_model.py OpenGVLab/InternVL3_5-8B

    # 指定输出目录
    python download_hf_model.py OpenGVLab/InternVL3_5-8B --output D:/models/internvl

    # 使用 HF 官方源（不经过镜像）
    python download_hf_model.py OpenGVLab/InternVL3_5-8B --no-mirror

    # 使用自定义镜像
    python download_hf_model.py OpenGVLab/InternVL3_5-8B --mirror https://your-mirror.com

    # 需要登录的模型（gated models）
    python download_hf_model.py meta-llama/Llama-3-8B --token hf_xxxx

环境变量:
    HF_ENDPOINT: 镜像地址（等同于 --mirror）
    HF_TOKEN:    HuggingFace API token（等同于 --token）
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# ── 在导入 huggingface_hub 之前设置镜像 ──────────────────────────
# 这样可以确保 huggingface_hub 的所有内部请求都走镜像


def _parse_args_first_pass() -> argparse.Namespace:
    """第一遍解析，只拿 --no-mirror / --mirror，用于尽早设置环境变量。"""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--no-mirror", action="store_true")
    parser.add_argument("--mirror", default=None)
    args, _ = parser.parse_known_args()
    return args


_pre_args = _parse_args_first_pass()

if not _pre_args.no_mirror:
    _mirror = _pre_args.mirror or os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ["HF_ENDPOINT"] = _mirror

# ── 现在可以安全导入 ──────────────────────────────────────────────

from huggingface_hub import snapshot_download, hf_hub_download, list_repo_files  # noqa: E402
from huggingface_hub.utils import HfHubHTTPError, LocalEntryNotFoundError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="可靠下载 HuggingFace 模型（支持镜像 + 断点续传）",
    )
    parser.add_argument(
        "repo_id",
        help="HuggingFace 仓库 ID，例如 OpenGVLab/InternVL3_5-8B",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="下载目录（默认：当前目录下的 models/<repo_name>）",
    )
    parser.add_argument(
        "--mirror",
        default=None,
        help="HF 镜像地址（默认 https://hf-mirror.com）",
    )
    parser.add_argument(
        "--no-mirror",
        action="store_true",
        help="不使用镜像，直连 huggingface.co",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("HF_TOKEN", ""),
        help="HF API token（下载 gated model 时需要）",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="启用断点续传（默认开启）",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="禁用断点续传，重新下载所有文件",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="每个文件的最大重试次数（默认 5）",
    )
    parser.add_argument(
        "--retry-wait",
        type=int,
        default=10,
        help="重试等待秒数（默认 10）",
    )
    parser.add_argument(
        "--include",
        default=None,
        help="只下载匹配的文件（glob 模式），如 '*.safetensors'",
    )
    parser.add_argument(
        "--exclude",
        default=None,
        help="排除匹配的文件（glob 模式），如 '*.bin'",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅列出文件，不实际下载",
    )
    return parser


def format_size(size_bytes: int) -> str:
    """将字节数格式化为人类可读的大小。"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def download_with_retry(
    repo_id: str,
    local_dir: Path,
    token: str,
    resume: bool,
    max_retries: int,
    retry_wait: int,
    include: str | None,
    exclude: str | None,
) -> bool:
    """
    使用 snapshot_download 下载整个仓库，带自动重试。
    """
    print(f"仓库: {repo_id}")
    print(f"目标: {local_dir}")
    print(f"镜像: {os.environ.get('HF_ENDPOINT', '(直连)')}")
    print(f"断点续传: {'开启' if resume else '关闭'}")
    print()

    # 先列文件
    try:
        files = list_repo_files(repo_id, token=token or None)
    except HfHubHTTPError as e:
        print(f"❌ 无法列出仓库文件: {e}")
        return False

    # 过滤文件
    if include:
        import fnmatch
        files = [f for f in files if fnmatch.fnmatch(f, include)]
    if exclude:
        import fnmatch
        files = [f for f in files if not fnmatch.fnmatch(f, exclude)]

    safetensors_files = [f for f in files if f.endswith(".safetensors")]
    other_files = [f for f in files if not f.endswith(".safetensors")]

    print(f"共 {len(files)} 个文件")
    if safetensors_files:
        print(f"  模型权重: {len(safetensors_files)} 个 .safetensors 文件")
    print(f"  配置/代码: {len(other_files)} 个文件")
    print()

    if args.dry_run:
        print("📋 文件列表:")
        for f in files:
            print(f"  - {f}")
        print()
        print("Dry-run 模式，未实际下载。")
        return True

    # snapshot_download 是最可靠的方式，内置 resume
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"⬇️  开始下载 (第 {attempt}/{max_retries} 次尝试)...")
            local_path = snapshot_download(
                repo_id=repo_id,
                local_dir=str(local_dir),
                token=token or None,
                resume_download=resume,
                allow_patterns=include,
                ignore_patterns=[exclude] if exclude else None,
                max_workers=4,  # 4 线程并行下载
            )
            print(f"\n✅ 下载完成！")
            print(f"   路径: {local_path}")

            # 统计大小
            total_size = sum(
                (local_dir / f).stat().st_size
                for f in files
                if (local_dir / f).exists()
            )
            print(f"   总大小: {format_size(total_size)}")
            return True

        except (HfHubHTTPError, LocalEntryNotFoundError, OSError) as e:
            last_error = e
            if attempt < max_retries:
                wait = retry_wait * attempt
                print(f"⚠️  下载出错 (尝试 {attempt}/{max_retries}): {e}")
                print(f"   {wait} 秒后重试...")
                time.sleep(wait)
            else:
                print(f"❌ 下载失败（已重试 {max_retries} 次）: {e}")

        except KeyboardInterrupt:
            print("\n⚠️  用户中断。已下载的部分文件保留在目标目录中。")
            print("   下次运行相同命令可自动续传。")
            return False

    print(f"\n❌ 最终错误: {last_error}")
    return False


def main() -> int:
    global args  # noqa: PLW0602  # 方便 download_with_retry 中访问 dry_run
    parser = build_parser()
    args = parser.parse_args()

    # 确定输出目录
    if args.output:
        local_dir = Path(args.output)
    else:
        repo_name = args.repo_id.split("/")[-1]
        local_dir = Path("models") / repo_name

    local_dir.mkdir(parents=True, exist_ok=True)

    resume = not args.no_resume

    success = download_with_retry(
        repo_id=args.repo_id,
        local_dir=local_dir,
        token=args.token,
        resume=resume,
        max_retries=args.max_retries,
        retry_wait=args.retry_wait,
        include=args.include,
        exclude=args.exclude,
    )

    if success:
        print("\n💡 提示: 如需在 Python 中加载此模型，可使用:")
        print(f'   model = AutoModel.from_pretrained(r"{local_dir}", trust_remote_code=True)')
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
