from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


CHUNK_SIZE = 8 * 1024 * 1024
USER_AGENT = 'hf-mirror-resume-downloader/1.0'


def human_bytes(size: int) -> str:
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024 or unit == 'TB':
            return f'{value:.2f} {unit}'
        value /= 1024
    return f'{value:.2f} TB'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='通过 HTTP Range 持续续传大文件，适合 HuggingFace / hf-mirror 反复 EOF 场景。'
    )
    parser.add_argument('--url', required=True, help='下载地址')
    parser.add_argument('--output', required=True, type=Path, help='输出文件路径')
    parser.add_argument('--proxy', help='HTTP/HTTPS 代理，例如 http://127.0.0.1:10808')
    parser.add_argument('--expected-size', type=int, help='预期字节数；不提供时自动从响应头读取')
    parser.add_argument('--retries', type=int, default=200, help='中断后最大重连次数，默认 200')
    parser.add_argument('--retry-wait', type=int, default=8, help='重连前等待秒数，默认 8')
    parser.add_argument('--timeout', type=int, default=120, help='单次连接超时秒数，默认 120')
    return parser.parse_args()


def build_opener(proxy: str | None) -> urllib.request.OpenerDirector:
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
    opener = urllib.request.build_opener(*handlers)
    opener.addheaders = [('User-Agent', USER_AGENT)]
    return opener


def read_expected_size(opener: urllib.request.OpenerDirector, url: str, timeout: int) -> int | None:
    request = urllib.request.Request(url, method='HEAD')
    with opener.open(request, timeout=timeout) as response:
        header = response.headers.get('Content-Length')
        if header:
            return int(header)
        linked_size = response.headers.get('X-Linked-Size')
        if linked_size:
            return int(linked_size)
    return None


def download(args: argparse.Namespace) -> int:
    opener = build_opener(args.proxy)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    expected_size = args.expected_size or read_expected_size(opener, args.url, args.timeout)
    resume_from = args.output.stat().st_size if args.output.exists() else 0

    if expected_size is not None and resume_from >= expected_size:
        print(f'已完成: {args.output} ({human_bytes(resume_from)})', flush=True)
        return 0

    attempt = 0
    last_report = 0.0
    while True:
        resume_from = args.output.stat().st_size if args.output.exists() else 0
        if expected_size is not None and resume_from >= expected_size:
            print(f'下载完成: {args.output} ({human_bytes(resume_from)})', flush=True)
            return 0

        if attempt >= args.retries:
            print(
                f'下载失败，已达到最大重试次数: {attempt}，当前 {human_bytes(resume_from)}',
                file=sys.stderr,
                flush=True,
            )
            return 1

        attempt += 1
        headers = {}
        if resume_from:
            headers['Range'] = f'bytes={resume_from}-'
        request = urllib.request.Request(args.url, headers=headers)

        try:
            with opener.open(request, timeout=args.timeout) as response, args.output.open('ab' if resume_from else 'wb') as handle:
                status = getattr(response, 'status', response.getcode())
                if resume_from and status == 200:
                    handle.seek(0)
                    handle.truncate(0)
                    resume_from = 0

                print(
                    f'连接成功，第 {attempt} 次，起点 {human_bytes(resume_from)} / '
                    f'{human_bytes(expected_size) if expected_size is not None else "unknown"}',
                    flush=True,
                )
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    resume_from += len(chunk)
                    now = time.monotonic()
                    if now - last_report >= 15:
                        if expected_size is not None:
                            percent = resume_from / expected_size * 100
                            print(
                                f'进度: {percent:.1f}% ({human_bytes(resume_from)} / {human_bytes(expected_size)})',
                                flush=True,
                            )
                        else:
                            print(f'进度: {human_bytes(resume_from)}', flush=True)
                        last_report = now
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            current_size = args.output.stat().st_size if args.output.exists() else 0
            print(
                f'下载中断，第 {attempt} 次重连前等待 {args.retry_wait}s: '
                f'{type(exc).__name__}: {exc} ; 当前 {human_bytes(current_size)}',
                flush=True,
            )
            time.sleep(args.retry_wait)
            continue

        current_size = args.output.stat().st_size if args.output.exists() else 0
        if expected_size is not None and current_size >= expected_size:
            print(f'下载完成: {args.output} ({human_bytes(current_size)})', flush=True)
            return 0

        print(
            f'连接已结束但文件未满，准备继续续传: {human_bytes(current_size)} / '
            f'{human_bytes(expected_size) if expected_size is not None else "unknown"}',
            flush=True,
        )
        time.sleep(args.retry_wait)


if __name__ == '__main__':
    raise SystemExit(download(parse_args()))