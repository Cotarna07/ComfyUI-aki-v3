#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


REQUESTED_MODELS = {
    'dessert': {
        'label': 'Dessert Models / Gelato',
        'url': 'https://civitai.com/models/1884582/dessert-models?modelVersionId=2756641',
    },
    'smooth': {
        'label': 'Smooth Mix Wan 2.2 14B (I2V/T2V) / I2V v2.0 High',
        'url': 'https://civitai.com/models/1995784/smooth-mix-wan-22-14b-i2vt2v?modelVersionId=2513182',
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='交互式 Civitai 下载入口，启动后可直接在终端粘贴链接或版本 ID。',
    )
    parser.add_argument(
        '--only',
        choices=sorted(REQUESTED_MODELS.keys()),
        action='append',
        help='下载内置预设模型，可重复传入；未传时默认进入交互式粘贴模式。',
    )
    parser.add_argument('--model-ref', dest='model_refs', action='append', default=[], help='直接传入模型页面链接、下载链接或版本 ID，可重复使用。')
    parser.add_argument('--token', help='显式传入 Civitai API Token。')
    parser.add_argument('--python', type=Path, default=Path(sys.executable), help='用于执行下载器的 Python 路径。')
    parser.add_argument('--output-dir', type=Path, help='下载暂存目录，默认沿用主下载器配置。')
    parser.add_argument('--log-dir', type=Path, help='日志目录，默认沿用主下载器配置。')
    parser.add_argument('--comfyui-root', type=Path, help='ComfyUI models 根目录，默认沿用主下载器配置。')
    parser.add_argument('--no-move-to-comfyui', action='store_true', help='下载后不自动移动到 ComfyUI 模型目录。')
    parser.add_argument('--use-aria2', action='store_true', help='改用 aria2c 后端；默认使用 Python 内置下载器以显示进度条。')
    parser.add_argument('--interactive', action='store_true', help='即使传入了其他参数，也强制进入交互式粘贴模式。')
    parser.add_argument('--dry-run', action='store_true', help='只解析下载任务，不实际下载。')
    parser.add_argument('--verbose', action='store_true', help='透传调试输出到主下载器。')
    return parser


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def prompt_for_refs() -> list[str]:
    print('请在下面逐行粘贴 Civitai 链接、下载链接或 modelVersionId。')
    print('输入完成后，直接回车一次开始下载。')
    refs: list[str] = []
    while True:
        try:
            line = input('链接/ID> ').strip()
        except EOFError:
            print()
            break

        if not line:
            if refs:
                break
            print('至少需要输入一个链接或版本 ID。')
            continue

        refs.append(line)

    return refs


def collect_refs(args: argparse.Namespace) -> list[str]:
    refs: list[str] = []

    selected_keys = args.only or []
    for key in selected_keys:
        refs.append(REQUESTED_MODELS[key]['url'])

    refs.extend(args.model_refs)

    if args.interactive or not refs:
        refs = prompt_for_refs()

    return refs


def build_command(args: argparse.Namespace, refs: list[str]) -> list[str]:
    downloader_script = project_root() / 'download.py'

    command = [str(args.python), str(downloader_script)]
    for ref in refs:
        command.extend(['--model-ref', ref])

    if args.token:
        command.extend(['--token', args.token])
    if args.output_dir:
        command.extend(['--output-dir', str(args.output_dir)])
    if args.log_dir:
        command.extend(['--log-dir', str(args.log_dir)])
    if args.comfyui_root:
        command.extend(['--comfyui-root', str(args.comfyui_root)])
    if not args.no_move_to_comfyui:
        command.append('--move-to-comfyui')
    if not args.use_aria2:
        command.append('--no-aria2')
    if args.dry_run:
        command.append('--dry-run')
    if args.verbose:
        command.append('--verbose')
    return command


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    refs = collect_refs(args)

    if not refs:
        parser.error('未提供任何有效的下载链接或版本 ID。')

    print('本次下载目标:')
    for ref in refs:
        print(f'- {ref}')

    command = build_command(args, refs)
    print('\n执行命令:')
    print(shlex.join(command))
    print()

    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main())