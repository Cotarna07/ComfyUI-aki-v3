#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


CHUNK_SIZE = 4 * 1024 * 1024
USER_AGENT = 'ComfyUI-Civitai-Downloader/2.0'
TOKEN_ENV_NAMES = ('CIVITAI_API_TOKEN', 'CIVITAI_TOKEN')
CIVITAI_API_ROOTS = (
    'https://civitai.com/api/v1',
    'https://civitai.red/api/v1',
)
CIVITAI_DOWNLOAD_ROOT = 'https://civitai.com/api/download/models'
LEGACY_TOKEN_FILE = Path.home() / '.civitai' / 'config'
USER_CONFIG_FILE = Path.home() / '.civitai' / 'downloader.json'
PROJECT_ROOT = Path(__file__).resolve().parent
PROJECT_CONFIG_FILE = PROJECT_ROOT / 'config.local.json'
PROJECT_RUNTIME_DIR = PROJECT_ROOT / 'runtime'
DEFAULT_OUTPUT_DIR = PROJECT_RUNTIME_DIR / 'downloads'
DEFAULT_LOG_DIR = PROJECT_RUNTIME_DIR / 'logs'
DEFAULT_ARIA2C_PATH = PROJECT_RUNTIME_DIR / 'tools' / 'aria2' / 'aria2c.exe'
WORKSPACE_ROOT = PROJECT_ROOT.parent.parent
DEFAULT_COMFYUI_ROOT = WORKSPACE_ROOT / 'ComfyUI' / 'models'

MODEL_TYPE_DIRS = {
    'checkpoint': 'checkpoints',
    'lora': 'loras',
    'locon': 'loras',
    'dora': 'loras',
    'vae': 'vae',
    'controlnet': 'controlnet',
    'textualinversion': 'embeddings',
    'embedding': 'embeddings',
    'hypernetwork': 'hypernetworks',
    'upscaler': 'upscale_models',
    'motionmodule': 'animatediff_models',
    'motionlora': 'animatediff_models',
    'textencoder': 'text_encoders',
    'unet': 'diffusion_models',
    'aestheticgradient': 'embeddings',
    'poses': 'poses',
    'workflows': 'workflows',
    'other': 'other',
}


class NoRedirection(urllib.request.HTTPErrorProcessor):
    def http_response(self, request, response):
        return response

    https_response = http_response


@dataclass
class Settings:
    token: str
    proxy: str | None
    output_dir: Path
    log_dir: Path
    comfyui_root: Path
    move_to_comfyui: bool
    target_subdir: str | None
    retries: int
    retry_wait: int
    timeout: int
    connections: int
    split: int
    aria2c_path: Path | None
    no_aria2: bool
    dry_run: bool
    verbose: bool


@dataclass
class ResolvedEndpoint:
    url: str
    needs_auth_header: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='稳定下载 Civitai 模型，支持断点续传、自动重试、代理、日志和批量下载。',
    )
    parser.add_argument(
        'model_ref',
        nargs='?',
        help='单个模型引用，支持版本 ID、模型页 URL、下载 URL',
    )
    parser.add_argument(
        'legacy_output_path',
        nargs='?',
        help='兼容旧版脚本的输出目录参数',
    )
    parser.add_argument(
        '--model-ref',
        dest='model_refs',
        action='append',
        default=[],
        help='额外模型引用，可重复传入实现批量下载',
    )
    parser.add_argument(
        '--input-file',
        type=Path,
        help='批量输入文件，每行一个版本 ID 或 URL，支持 # 注释',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        help='下载目录；未指定时默认使用项目 runtime/downloads',
    )
    parser.add_argument(
        '--log-dir',
        type=Path,
        help='日志目录；未指定时默认使用项目 runtime/logs',
    )
    parser.add_argument(
        '--manifest-out',
        type=Path,
        help='本次任务汇总 JSON 输出路径',
    )
    parser.add_argument(
        '--comfyui-root',
        type=Path,
        help='ComfyUI models 根目录，默认自动定位为当前工作区下的 ComfyUI/models',
    )
    parser.add_argument(
        '--move-to-comfyui',
        action='store_true',
        help='下载完成后自动移动到 ComfyUI 对应模型目录',
    )
    parser.add_argument(
        '--target-subdir',
        help='覆盖自动类型映射，直接指定 ComfyUI 子目录，例如 loras 或 checkpoints',
    )
    parser.add_argument(
        '--token',
        help='Civitai API Token；未指定时会依次读取环境变量、config.local.json、~/.civitai/downloader.json、~/.civitai/config',
    )
    parser.add_argument(
        '--proxy',
        help='代理地址，例如 http://127.0.0.1:7890；未指定时自动读取 HTTP_PROXY/HTTPS_PROXY',
    )
    parser.add_argument(
        '--config',
        type=Path,
        help='显式指定 JSON 配置文件',
    )
    parser.add_argument(
        '--aria2c-path',
        type=Path,
        help='aria2c 可执行文件路径；未指定时自动探测 aria2c 或项目 runtime/tools/aria2/aria2c.exe',
    )
    parser.add_argument(
        '--no-aria2',
        action='store_true',
        help='禁用 aria2c，强制使用内置续传下载器',
    )
    parser.add_argument(
        '--retries',
        type=int,
        default=5,
        help='失败重试次数，默认 5',
    )
    parser.add_argument(
        '--retry-wait',
        type=int,
        default=10,
        help='每次重试前等待秒数，默认 10',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=60,
        help='单次网络超时时间（秒），默认 60',
    )
    parser.add_argument(
        '--connections',
        type=int,
        default=8,
        help='aria2 单文件最大并发连接数，默认 8',
    )
    parser.add_argument(
        '--split',
        type=int,
        default=8,
        help='aria2 分片数，默认 8',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='只解析元数据和目标路径，不实际下载',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='输出更多调试信息',
    )
    return parser


def load_json_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f'配置文件必须是 JSON 对象: {path}')
    return data


def collect_config(args: argparse.Namespace) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if args.config:
        config.update(load_json_config(args.config))
        return config

    for candidate in (PROJECT_CONFIG_FILE, USER_CONFIG_FILE):
        if candidate.exists():
            config.update(load_json_config(candidate))
    return config


def resolve_token(args: argparse.Namespace, config: dict[str, Any]) -> str:
    if args.token:
        return args.token.strip()

    for env_name in TOKEN_ENV_NAMES:
        value = os.getenv(env_name)
        if value:
            return value.strip()

    config_token = config.get('token')
    if isinstance(config_token, str) and config_token.strip():
        return config_token.strip()

    if LEGACY_TOKEN_FILE.exists():
        value = LEGACY_TOKEN_FILE.read_text(encoding='utf-8').strip()
        if value:
            return value

    raise SystemExit(
        '缺少 Civitai API Token。请使用 --token、设置 CIVITAI_API_TOKEN 环境变量，'
        '或在 ~/.civitai/downloader.json / config.local.json 中提供 token。'
    )


def resolve_proxy(args: argparse.Namespace, config: dict[str, Any]) -> str | None:
    if args.proxy:
        return args.proxy.strip()
    for env_name in ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy'):
        value = os.getenv(env_name)
        if value:
            return value.strip()
    config_proxy = config.get('proxy')
    if isinstance(config_proxy, str) and config_proxy.strip():
        return config_proxy.strip()
    return None


def parse_args() -> tuple[argparse.Namespace, list[str], dict[str, Any]]:
    parser = build_parser()
    args = parser.parse_args()
    config = collect_config(args)

    if args.legacy_output_path:
        if args.output_dir is not None:
            parser.error('兼容旧参数 output_path 不能与 --output-dir 同时使用')
        if args.model_refs or args.input_file:
            parser.error('兼容旧参数 output_path 只能用于单个位置参数下载')
        args.output_dir = Path(args.legacy_output_path)

    refs: list[str] = []
    if args.model_ref:
        refs.append(args.model_ref)
    refs.extend(args.model_refs)
    if args.input_file:
        refs.extend(load_refs_from_file(args.input_file))

    if not refs:
        parser.error('至少需要提供一个模型引用，可用位置参数、--model-ref 或 --input-file')

    return args, refs, config


def load_refs_from_file(path: Path) -> list[str]:
    refs: list[str] = []
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        refs.append(line)
    return refs


def resolve_settings(args: argparse.Namespace, config: dict[str, Any]) -> Settings:
    output_dir = Path(args.output_dir or config.get('output_dir') or DEFAULT_OUTPUT_DIR).expanduser()
    log_dir = Path(args.log_dir or config.get('log_dir') or DEFAULT_LOG_DIR).expanduser()
    comfyui_root = Path(args.comfyui_root or config.get('comfyui_root') or DEFAULT_COMFYUI_ROOT).expanduser()

    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        token=resolve_token(args, config),
        proxy=resolve_proxy(args, config),
        output_dir=output_dir,
        log_dir=log_dir,
        comfyui_root=comfyui_root,
        move_to_comfyui=args.move_to_comfyui or bool(config.get('move_to_comfyui', False)),
        target_subdir=args.target_subdir or config.get('target_subdir'),
        retries=args.retries,
        retry_wait=args.retry_wait,
        timeout=args.timeout,
        connections=args.connections,
        split=args.split,
        aria2c_path=find_aria2c(args.aria2c_path, config.get('aria2c_path')),
        no_aria2=args.no_aria2 or bool(config.get('no_aria2', False)),
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


def find_aria2c(cli_path: Path | None, config_value: Any) -> Path | None:
    candidates: list[Path] = []
    if cli_path:
        candidates.append(cli_path)
    if isinstance(config_value, str) and config_value.strip():
        candidates.append(Path(config_value.strip()).expanduser())

    env_path = os.getenv('ARIA2C_PATH')
    if env_path:
        candidates.append(Path(env_path).expanduser())

    if DEFAULT_ARIA2C_PATH.exists():
        candidates.append(DEFAULT_ARIA2C_PATH)

    which_result = shutil.which('aria2c')
    if which_result:
        candidates.append(Path(which_result))

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def build_opener(proxy: str | None = None, disable_redirects: bool = False):
    handlers: list[Any] = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
    if disable_redirects:
        handlers.append(NoRedirection())
    opener = urllib.request.build_opener(*handlers)
    opener.addheaders = [('User-Agent', USER_AGENT)]
    return opener


def request_json(url: str, settings: Settings) -> dict[str, Any]:
    payload = request_bytes(url, settings, expect_json=True)
    return json.loads(payload.decode('utf-8'))


def preferred_api_root_for_ref(ref: str) -> str | None:
    parsed = urlparse(ref.strip())
    if not parsed.scheme or not parsed.netloc:
        return None
    host = parsed.netloc.lower()
    if 'civitai.red' in host:
        return CIVITAI_API_ROOTS[1]
    if 'civitai.com' in host:
        return CIVITAI_API_ROOTS[0]
    return None


def request_api_json(path: str, settings: Settings, preferred_root: str | None = None) -> dict[str, Any]:
    candidate_roots: list[str] = []
    if preferred_root:
        candidate_roots.append(preferred_root)
    for root in CIVITAI_API_ROOTS:
        if root not in candidate_roots:
            candidate_roots.append(root)

    last_error: Exception | None = None
    for root in candidate_roots:
        try:
            return request_json(f'{root}{path}', settings)
        except Exception as exc:
            last_error = exc
            if settings.verbose:
                print(f'API 根地址失败，准备回退: {root}{path} -> {exc}', flush=True)

    raise RuntimeError(f'请求失败: {path} -> {last_error}') from last_error


def request_bytes(
    url: str,
    settings: Settings,
    *,
    expect_json: bool = False,
    disable_redirects: bool = False,
    extra_headers: dict[str, str] | None = None,
) -> bytes:
    last_error: Exception | None = None
    opener = build_opener(settings.proxy, disable_redirects=disable_redirects)
    headers = {'Authorization': f'Bearer {settings.token}'}
    if extra_headers:
        headers.update(extra_headers)

    for attempt in range(1, settings.retries + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with opener.open(request, timeout=settings.timeout) as response:
                status = getattr(response, 'status', response.getcode())
                if expect_json and status >= 400:
                    raise urllib.error.HTTPError(url, status, response.reason, response.headers, None)
                return response.read()
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in {400, 401, 403, 404}:
                break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc

        if attempt < settings.retries:
            time.sleep(min(120, settings.retry_wait * attempt))

    raise RuntimeError(f'请求失败: {url} -> {last_error}') from last_error


def normalize_key(value: str | None) -> str:
    if not value:
        return 'other'
    return re.sub(r'[^a-z0-9]+', '', value.lower())


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name).strip().rstrip('.')
    return sanitized or 'downloaded_file'


def human_bytes(size: int | None) -> str:
    if size is None:
        return 'unknown'
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024 or unit == 'TB':
            return f'{value:.2f} {unit}'
        value /= 1024
    return f'{value:.2f} TB'


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0 or seconds == float('inf'):
        return '--:--'
    total_seconds = int(seconds)
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f'{hours:d}:{minutes:02d}:{secs:02d}'
    return f'{minutes:02d}:{secs:02d}'


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def expected_bytes(file_info: dict[str, Any]) -> int | None:
    size_kb = file_info.get('sizeKB')
    if size_kb is None:
        return None
    return int(float(size_kb) * 1024)


def extract_version_id(ref: str) -> int:
    value = ref.strip()
    if value.isdigit():
        return int(value)

    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f'无法识别模型引用: {ref}')

    query = parsed.query or ''
    query_match = re.search(r'(?:^|&)modelVersionId=(\d+)(?:&|$)', query)
    if query_match:
        return int(query_match.group(1))

    path_match = re.search(r'/api/download/models/(\d+)', parsed.path)
    if path_match:
        return int(path_match.group(1))

    path_match = re.search(r'/api/v1/model-versions/(\d+)', parsed.path)
    if path_match:
        return int(path_match.group(1))

    raise ValueError(f'无法从引用中提取 modelVersionId: {ref}')


def fetch_version(version_id: int, settings: Settings, ref: str | None = None) -> dict[str, Any]:
    return request_api_json(
        f'/model-versions/{version_id}',
        settings,
        preferred_root=preferred_api_root_for_ref(ref or ''),
    )


def fetch_model(model_id: int, settings: Settings, ref: str | None = None) -> dict[str, Any]:
    return request_api_json(
        f'/models/{model_id}',
        settings,
        preferred_root=preferred_api_root_for_ref(ref or ''),
    )


def select_primary_file(version_data: dict[str, Any]) -> dict[str, Any]:
    files = version_data.get('files') or []
    if not files:
        raise RuntimeError(f"版本 {version_data.get('id')} 没有可下载文件")
    primary_files = [file_info for file_info in files if file_info.get('primary')]
    return primary_files[0] if primary_files else files[0]


def resolve_subdir(model_type: str | None, override: str | None) -> str:
    if override:
        return override.strip().strip('/\\')
    key = normalize_key(model_type)
    return MODEL_TYPE_DIRS.get(key, 'other')


def build_target_paths(filename: str, model_type: str | None, settings: Settings) -> tuple[Path, Path, str | None]:
    stage_path = settings.output_dir / filename
    if settings.move_to_comfyui:
        subdir = resolve_subdir(model_type, settings.target_subdir)
        final_path = settings.comfyui_root / subdir / filename
        return stage_path, final_path, subdir
    return stage_path, stage_path, None


def is_complete_file(path: Path, expected_size: int | None) -> bool:
    if not path.exists() or not path.is_file():
        return False
    if expected_size is None:
        return path.stat().st_size > 0
    return path.stat().st_size == expected_size


def part_path_for(target_path: Path) -> Path:
    return target_path.with_name(target_path.name + '.part')


def incomplete_file_size(path: Path, expected_size: int | None) -> int:
    if not path.exists() or not path.is_file():
        return 0
    if is_complete_file(path, expected_size):
        return 0
    return path.stat().st_size


def current_partial_size(target_path: Path, expected_size: int | None) -> int:
    return max(
        incomplete_file_size(target_path, expected_size),
        incomplete_file_size(part_path_for(target_path), expected_size),
    )


def normalize_partial_files(target_path: Path, expected_size: int | None) -> Path:
    part_path = part_path_for(target_path)
    target_size = incomplete_file_size(target_path, expected_size)
    part_size = incomplete_file_size(part_path, expected_size)

    if target_size and not part_size:
        target_path.replace(part_path)
        print(
            f'发现历史残片，已转为续传文件: {target_path.name} ({human_bytes(target_size)})',
            flush=True,
        )
        return part_path

    if target_size and part_size:
        if target_size > part_size:
            part_path.unlink(missing_ok=True)
            target_path.replace(part_path)
            print(
                f'发现更大的历史残片，已切换为续传源: {target_path.name} '
                f'({human_bytes(target_size)}，原 .part 为 {human_bytes(part_size)})',
                flush=True,
            )
        else:
            target_path.unlink(missing_ok=True)
            print(
                f'发现较小的历史残片，已忽略: {target_path.name} '
                f'({human_bytes(target_size)}，当前 .part 为 {human_bytes(part_size)})',
                flush=True,
            )

    return part_path


def resolve_endpoint(download_url: str, settings: Settings) -> ResolvedEndpoint:
    opener = build_opener(settings.proxy, disable_redirects=True)
    request = urllib.request.Request(
        download_url,
        headers={
            'Authorization': f'Bearer {settings.token}',
            'User-Agent': USER_AGENT,
        },
    )

    last_error: Exception | None = None
    for attempt in range(1, settings.retries + 1):
        try:
            with opener.open(request, timeout=settings.timeout) as response:
                status = getattr(response, 'status', response.getcode())
                if status in {301, 302, 303, 307, 308}:
                    location = response.getheader('Location')
                    if not location:
                        raise RuntimeError('下载接口返回了重定向，但缺少 Location')
                    parsed = urlparse(location)
                    if not parsed.scheme:
                        base = urlparse(download_url)
                        location = f'{base.scheme}://{base.netloc}{location}'
                    return ResolvedEndpoint(url=location, needs_auth_header=False)
                if status == 200:
                    return ResolvedEndpoint(url=download_url, needs_auth_header=True)
                if status in {401, 403, 404}:
                    raise RuntimeError(f'下载接口返回 HTTP {status}')
                raise RuntimeError(f'无法处理下载接口响应 HTTP {status}')
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code in {401, 403, 404}:
                break
            if attempt < settings.retries:
                time.sleep(min(120, settings.retry_wait * attempt))

    raise RuntimeError(f'解析下载地址失败: {last_error}') from last_error


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + '\n')


def print_progress(
    prefix: str,
    downloaded: int,
    expected_size: int | None,
    *,
    start_time: float | None = None,
    initial_downloaded: int = 0,
    final: bool = False,
) -> None:
    line = ''
    if expected_size:
        percent = downloaded / expected_size * 100
        bar_width = 24
        filled = min(bar_width, int(bar_width * min(downloaded, expected_size) / expected_size))
        bar = '#' * filled + '-' * (bar_width - filled)
        line = (
            f'\r{prefix} [{bar}] {percent:5.1f}% '
            f'({human_bytes(downloaded)} / {human_bytes(expected_size)})'
        )
    else:
        line = f'\r{prefix} {human_bytes(downloaded)}'

    if start_time is not None:
        elapsed = max(time.monotonic() - start_time, 1e-6)
        session_downloaded = max(0, downloaded - initial_downloaded)
        speed = session_downloaded / elapsed
        line += f' {human_bytes(int(speed))}/s'
        if expected_size and speed > 0:
            remaining = max(expected_size - downloaded, 0)
            line += f' ETA {format_duration(remaining / speed)}'

    line = line.ljust(140)
    print(line, end='\n' if final else '', flush=True)


def download_with_builtin(
    endpoint: ResolvedEndpoint,
    target_path: Path,
    expected_size: int | None,
    settings: Settings,
) -> None:
    part_path = normalize_partial_files(target_path, expected_size)
    opener = build_opener(settings.proxy)
    last_error: Exception | None = None
    for attempt in range(1, settings.retries + 1):
        offset = part_path.stat().st_size if part_path.exists() else 0
        headers = {'User-Agent': USER_AGENT}
        if endpoint.needs_auth_header:
            headers['Authorization'] = f'Bearer {settings.token}'
        if offset:
            headers['Range'] = f'bytes={offset}-'

        progress_prefix = f'内置下载 {target_path.name}'
        progress_rendered = False
        start_time = time.monotonic()
        request = urllib.request.Request(endpoint.url, headers=headers)
        try:
            with opener.open(request, timeout=settings.timeout) as response:
                status = getattr(response, 'status', response.getcode())
                if offset and status == 200:
                    raise RuntimeError('服务端未返回 206 续传响应，已保留残片，准备刷新签名后重试')
                else:
                    mode = 'ab' if offset else 'wb'

                ensure_parent(part_path)
                if offset:
                    print(
                        f'检测到残片，准备续传: {target_path.name} ({human_bytes(offset)} 已下载)',
                        flush=True,
                    )
                downloaded = offset
                last_report = start_time
                with part_path.open(mode) as handle:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        handle.write(chunk)
                        downloaded += len(chunk)
                        now = time.monotonic()
                        if now - last_report >= 0.2:
                            print_progress(
                                progress_prefix,
                                downloaded,
                                expected_size,
                                start_time=start_time,
                                initial_downloaded=offset,
                            )
                            progress_rendered = True
                            last_report = now

            if expected_size is not None and part_path.stat().st_size != expected_size:
                raise RuntimeError(
                    f'文件大小校验失败，当前 {part_path.stat().st_size}，预期 {expected_size}'
                )
            print_progress(
                progress_prefix,
                part_path.stat().st_size,
                expected_size,
                start_time=start_time,
                initial_downloaded=offset,
                final=True,
            )
            part_path.replace(target_path)
            return
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = exc
            if progress_rendered:
                print('', flush=True)
            if attempt < settings.retries:
                current_size = part_path.stat().st_size if part_path.exists() else 0
                print(
                    f'内置下载失败，准备重试 {attempt}/{settings.retries}: '
                    f'{target_path.name} {human_bytes(current_size)} / {human_bytes(expected_size)} ; {exc}',
                    flush=True,
                )
                time.sleep(min(120, settings.retry_wait * attempt))

    raise RuntimeError(f'内置下载最终失败: {last_error}') from last_error


def download_with_aria2(
    endpoint: ResolvedEndpoint,
    target_path: Path,
    settings: Settings,
    raw_log_path: Path,
) -> None:
    if settings.aria2c_path is None:
        raise RuntimeError('aria2c 不可用')

    ensure_parent(target_path)
    ensure_parent(raw_log_path)
    command = [
        str(settings.aria2c_path),
        endpoint.url,
        '--continue=true',
        '--allow-overwrite=false',
        '--auto-file-renaming=false',
        '--file-allocation=none',
        '--summary-interval=30',
        f'--max-tries={settings.retries}',
        f'--retry-wait={settings.retry_wait}',
        f'--timeout={settings.timeout}',
        f'--connect-timeout={settings.timeout}',
        f'--max-connection-per-server={settings.connections}',
        f'--split={settings.split}',
        f'--dir={target_path.parent}',
        f'--out={target_path.name}',
        f'--log={raw_log_path}',
        '--log-level=notice',
        '--console-log-level=warn',
        f'--user-agent={USER_AGENT}',
    ]
    if settings.proxy:
        command.append(f'--all-proxy={settings.proxy}')
    if endpoint.needs_auth_header:
        command.append(f'--header=Authorization: Bearer {settings.token}')

    if settings.verbose:
        print('aria2 命令:', shlex.join(command), flush=True)

    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f'aria2c 退出码 {completed.returncode}，详情见 {raw_log_path}')


def download_with_refreshable_endpoint(
    download_url: str,
    target_path: Path,
    expected_size: int | None,
    settings: Settings,
    raw_log_path: Path,
) -> str:
    backend = 'builtin'
    last_error: Exception | None = None

    for attempt in range(1, settings.retries + 1):
        if is_complete_file(target_path, expected_size):
            return backend

        endpoint = resolve_endpoint(download_url, settings)
        try:
            if not settings.no_aria2 and settings.aria2c_path is not None:
                backend = 'aria2c'
                if attempt > 1:
                    current_size = target_path.stat().st_size if target_path.exists() else 0
                    print(
                        f'续传重试 {attempt}/{settings.retries}，已保留 {human_bytes(current_size)}: {target_path.name}',
                        flush=True,
                    )
                download_with_aria2(endpoint, target_path, settings, raw_log_path)
            else:
                backend = 'builtin'
                download_with_builtin(endpoint, target_path, expected_size, settings)

            if is_complete_file(target_path, expected_size):
                return backend

            raise RuntimeError(
                f'下载进程已结束，但文件仍未完整: {target_path.stat().st_size if target_path.exists() else 0}'
            )
        except Exception as exc:
            last_error = exc
            if is_complete_file(target_path, expected_size):
                return backend
            if attempt < settings.retries:
                current_size = current_partial_size(target_path, expected_size)
                print(
                    f'下载中断，准备刷新签名后续传 {attempt}/{settings.retries}: '
                    f'{human_bytes(current_size)} / {human_bytes(expected_size)} ; {exc}',
                    flush=True,
                )
                time.sleep(min(120, settings.retry_wait * attempt))

    raise RuntimeError(f'下载最终失败: {last_error}') from last_error


def move_into_place(stage_path: Path, final_path: Path, expected_size: int | None) -> None:
    if stage_path == final_path:
        return
    if not stage_path.exists():
        raise RuntimeError(f'下载完成后未找到暂存文件: {stage_path}')
    if expected_size is not None and stage_path.stat().st_size != expected_size:
        raise RuntimeError(
            f'暂存文件大小不匹配，无法移动: {stage_path.stat().st_size} != {expected_size}'
        )
    ensure_parent(final_path)
    if final_path.exists() and not is_complete_file(final_path, expected_size):
        raise RuntimeError(f'目标文件已存在但大小不匹配，请先检查: {final_path}')
    if final_path.exists() and is_complete_file(final_path, expected_size):
        stage_path.unlink(missing_ok=True)
        return
    shutil.move(str(stage_path), str(final_path))


def describe_ref(version_id: int, model_name: str, version_name: str, filename: str) -> str:
    return f'[{version_id}] {model_name} / {version_name} -> {filename}'


def process_ref(
    ref: str,
    settings: Settings,
    run_id: str,
    jsonl_path: Path,
) -> dict[str, Any]:
    started_at = time.time()
    version_id = extract_version_id(ref)
    version_data = fetch_version(version_id, settings, ref=ref)
    model_id = int(version_data['modelId'])
    model_data = version_data.get('model') or fetch_model(model_id, settings, ref=ref)
    file_info = select_primary_file(version_data)

    filename = sanitize_filename(file_info.get('name') or f'{version_id}.bin')
    expected_size = expected_bytes(file_info)
    model_type = model_data.get('type')
    stage_path, final_path, target_subdir = build_target_paths(filename, model_type, settings)
    label = describe_ref(version_id, model_data.get('name', 'unknown'), version_data.get('name', 'unknown'), filename)
    raw_log_path = settings.log_dir / f'{run_id}-{version_id}.aria2.log'
    backend = 'builtin'
    status = 'planned'

    if is_complete_file(final_path, expected_size):
        status = 'skipped'
        print(f'已跳过，目标文件已存在: {label}', flush=True)
    else:
        if is_complete_file(stage_path, expected_size):
            print(f'复用已完成的暂存文件: {label}', flush=True)
            status = 'ready'
        else:
            if settings.dry_run:
                print(f'演练模式，不执行下载: {label}', flush=True)
            else:
                preferred_backend = 'aria2' if not settings.no_aria2 and settings.aria2c_path is not None else '内置下载器'
                print(f'开始 {preferred_backend} 下载: {label}', flush=True)
                backend = download_with_refreshable_endpoint(
                    file_info['downloadUrl'],
                    stage_path,
                    expected_size,
                    settings,
                    raw_log_path,
                )
                print(f'下载完成: {label}', flush=True)
            status = 'downloaded'

        if not settings.dry_run:
            move_into_place(stage_path, final_path, expected_size)
            if stage_path != final_path:
                print(f'已移动到: {final_path}', flush=True)
                status = 'moved'

    record = {
        'timestamp': iso_now(),
        'run_id': run_id,
        'ref': ref,
        'version_id': version_id,
        'model_id': model_id,
        'model_name': model_data.get('name'),
        'version_name': version_data.get('name'),
        'model_type': model_type,
        'file_name': filename,
        'expected_size': expected_size,
        'download_url': file_info.get('downloadUrl'),
        'stage_path': str(stage_path),
        'final_path': str(final_path),
        'target_subdir': target_subdir,
        'backend': backend,
        'status': status,
        'duration_seconds': round(time.time() - started_at, 2),
        'pickle_scan_result': file_info.get('pickleScanResult'),
        'virus_scan_result': file_info.get('virusScanResult'),
    }
    append_jsonl(jsonl_path, record)
    return record


def write_summary(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open('w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def main() -> int:
    args, refs, config = parse_args()
    settings = resolve_settings(args, config)
    run_id = datetime.now().strftime('%Y%m%d-%H%M%S')
    jsonl_path = settings.log_dir / f'{run_id}.jsonl'
    summary_path = args.manifest_out or (settings.log_dir / f'{run_id}.summary.json')

    if settings.verbose:
        visible_settings = asdict(settings)
        visible_settings['token'] = '***'
        visible_settings['aria2c_path'] = str(settings.aria2c_path) if settings.aria2c_path else None
        visible_settings['output_dir'] = str(settings.output_dir)
        visible_settings['log_dir'] = str(settings.log_dir)
        visible_settings['comfyui_root'] = str(settings.comfyui_root)
        print(json.dumps(visible_settings, ensure_ascii=False, indent=2), flush=True)

    if settings.no_aria2:
        print('已禁用 aria2c，将使用内置续传下载器。', flush=True)
    elif settings.aria2c_path is None:
        print('未找到 aria2c，将自动回退到内置续传下载器。建议先运行 scripts/install_aria2.ps1。', flush=True)
    else:
        print(f'检测到 aria2c: {settings.aria2c_path}', flush=True)

    results: list[dict[str, Any]] = []
    exit_code = 0
    for ref in refs:
        try:
            results.append(process_ref(ref, settings, run_id, jsonl_path))
        except Exception as exc:
            exit_code = 1
            failure_record = {
                'timestamp': iso_now(),
                'run_id': run_id,
                'ref': ref,
                'status': 'failed',
                'error': f'{type(exc).__name__}: {exc}',
            }
            append_jsonl(jsonl_path, failure_record)
            results.append(failure_record)
            print(f'下载失败: {ref} -> {exc}', file=sys.stderr, flush=True)

    summary = {
        'timestamp': iso_now(),
        'run_id': run_id,
        'results': results,
        'log_file': str(jsonl_path),
        'settings': {
            'output_dir': str(settings.output_dir),
            'log_dir': str(settings.log_dir),
            'comfyui_root': str(settings.comfyui_root),
            'move_to_comfyui': settings.move_to_comfyui,
            'target_subdir': settings.target_subdir,
            'proxy': settings.proxy,
            'backend': 'builtin' if settings.no_aria2 or settings.aria2c_path is None else 'aria2c',
        },
    }
    write_summary(summary_path, summary)
    print(f'运行日志: {jsonl_path}', flush=True)
    print(f'汇总清单: {summary_path}', flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
