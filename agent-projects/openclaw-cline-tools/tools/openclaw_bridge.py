from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parents[1]
LOCAL_VENDOR_ROOT = PROJECT_ROOT / "vendor"
CONFIG_PATH = PROJECT_ROOT / "config" / "toolchain.json"
DEFAULT_CONFIG = {
    "openclaw_root": str(PROJECT_ROOT),
    "scrapling_root": str(LOCAL_VENDOR_ROOT / "Scrapling"),
    "scrapling_python": str(WORKSPACE_ROOT / ".venv" / "Scripts" / "python.exe"),
    "scrapling_exe": str(WORKSPACE_ROOT / ".venv" / "Scripts" / "scrapling.exe"),
    "opencli_root": str(LOCAL_VENDOR_ROOT / "opencli"),
    "opencli_main": str(LOCAL_VENDOR_ROOT / "opencli" / "dist" / "main.js"),
    "node_command": "node",
    "bitbrowser_api": "http://127.0.0.1:54345",
}
ENV_OVERRIDES = {
    "openclaw_root": "OPENCLAW_TOOLS_ROOT",
    "scrapling_root": "OPENCLAW_SCRAPLING_ROOT",
    "scrapling_python": "OPENCLAW_SCRAPLING_PYTHON",
    "scrapling_exe": "OPENCLAW_SCRAPLING_EXE",
    "opencli_root": "OPENCLAW_OPENCLI_ROOT",
    "opencli_main": "OPENCLAW_OPENCLI_MAIN",
    "node_command": "OPENCLAW_NODE_COMMAND",
    "bitbrowser_api": "OPENCLAW_BITBROWSER_API",
}


def load_json_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return dict(DEFAULT_CONFIG)
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        user_config = json.load(handle)
    merged = dict(DEFAULT_CONFIG)
    merged.update(user_config)
    for key, env_name in ENV_OVERRIDES.items():
        env_value = os.getenv(env_name)
        if env_value:
            merged[key] = env_value
    return merged


def normalized_config() -> dict[str, Any]:
    raw = load_json_config()
    return {
        "openclaw_root": Path(raw["openclaw_root"]),
        "scrapling_root": Path(raw["scrapling_root"]),
        "scrapling_python": Path(raw["scrapling_python"]),
        "scrapling_exe": Path(raw["scrapling_exe"]),
        "opencli_root": Path(raw["opencli_root"]),
        "opencli_main": Path(raw["opencli_main"]),
        "node_command": str(raw["node_command"]),
        "bitbrowser_api": str(raw["bitbrowser_api"]).rstrip("/"),
    }


def node_available(command: str) -> bool:
    command_path = Path(command)
    if command_path.is_absolute():
        return command_path.exists()
    return shutil.which(command) is not None


def passthrough_args(values: list[str]) -> list[str]:
    if values and values[0] == "--":
        return values[1:]
    return values


def probe_process(command: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return False, str(exc)

    message = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode == 0:
        return True, message
    return False, message or f"process exited with code {completed.returncode}"


def run_process(command: list[str], cwd: Path | None = None) -> int:
    completed = subprocess.run(command, cwd=str(cwd) if cwd else None, check=False)
    return int(completed.returncode)


def ensure_scrapling_runtime(config: dict[str, Any]) -> tuple[bool, str]:
    ok, message = probe_process([str(config["scrapling_python"]), "-V"], cwd=config["scrapling_root"])
    if ok:
        return True, message or "Scrapling Python runtime is available"
    detail = message or "unknown error"
    return False, (
        "当前配置的 Scrapling 运行时不可执行。"
        f" 详细信息: {detail}。"
        " 请检查 config/toolchain.json 中的 scrapling_python 和 scrapling_exe，"
        "或重新在当前工作区的 .venv 中安装 Scrapling。"
    )


def print_config(config: dict[str, Any]) -> None:
    display = {
        "openclaw_root": str(config["openclaw_root"]),
        "scrapling_root": str(config["scrapling_root"]),
        "scrapling_python": str(config["scrapling_python"]),
        "scrapling_exe": str(config["scrapling_exe"]),
        "opencli_root": str(config["opencli_root"]),
        "opencli_main": str(config["opencli_main"]),
        "node_command": config["node_command"],
        "bitbrowser_api": config["bitbrowser_api"],
    }
    print(json.dumps(display, ensure_ascii=False, indent=2))


def check_command(_: argparse.Namespace, config: dict[str, Any]) -> int:
    scrapling_runtime_ok, scrapling_runtime_message = ensure_scrapling_runtime(config)
    checks = [
        ("openclaw_root", config["openclaw_root"].exists()),
        ("scrapling_root", config["scrapling_root"].exists()),
        ("scrapling_python", config["scrapling_python"].exists() and scrapling_runtime_ok),
        ("scrapling_exe", config["scrapling_exe"].exists() and scrapling_runtime_ok),
        ("opencli_root", config["opencli_root"].exists()),
        ("opencli_main", config["opencli_main"].exists()),
        ("node_command", node_available(config["node_command"])),
    ]
    has_error = False
    for name, ok in checks:
        status = "OK" if ok else "MISSING"
        print(f"[{status:7}] {name}")
        if name == "node_command":
            print(f"          {config['node_command']}")
        elif name in {"scrapling_python", "scrapling_exe"} and not scrapling_runtime_ok:
            print(f"          {config[name]}")
            print(f"          {scrapling_runtime_message}")
        else:
            print(f"          {config[name]}")
        has_error = has_error or not ok

    try:
        response = bitbrowser_request(config, "/health", {})
        print("[OK     ] bitbrowser_api")
        print(f"          {config['bitbrowser_api']} -> {json.dumps(response, ensure_ascii=False)}")
    except RuntimeError as exc:
        print("[WARN   ] bitbrowser_api")
        print(f"          {config['bitbrowser_api']} -> {exc}")

    return 1 if has_error else 0


def scrapling_command(args: argparse.Namespace, config: dict[str, Any]) -> int:
    extra = passthrough_args(args.args)
    if not extra:
        print("scrapling 子命令不能为空，例如: scrapling extract get https://example.com output.md", file=sys.stderr)
        return 2
    ok, message = ensure_scrapling_runtime(config)
    if not ok:
        print(message, file=sys.stderr)
        return 1
    return run_process([str(config["scrapling_exe"]), *extra], cwd=config["scrapling_root"])


def scrapling_python_command(args: argparse.Namespace, config: dict[str, Any]) -> int:
    extra = passthrough_args(args.args)
    if not extra:
        print("scrapling-python 子命令不能为空，例如: scrapling-python -c \"import scrapling\"", file=sys.stderr)
        return 2
    ok, message = ensure_scrapling_runtime(config)
    if not ok:
        print(message, file=sys.stderr)
        return 1
    return run_process([str(config["scrapling_python"]), *extra], cwd=config["scrapling_root"])


def opencli_command(args: argparse.Namespace, config: dict[str, Any]) -> int:
    extra = passthrough_args(args.args)
    if not extra:
        print("opencli 子命令不能为空，例如: opencli list", file=sys.stderr)
        return 2
    if not node_available(config["node_command"]):
        print(f"node 不可用: {config['node_command']}", file=sys.stderr)
        return 1
    return run_process([config["node_command"], str(config["opencli_main"]), *extra], cwd=config["opencli_root"])


def bitbrowser_request(config: dict[str, Any], endpoint: str, payload: dict[str, Any]) -> Any:
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{config['bitbrowser_api']}{endpoint}",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read()
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def bitbrowser_health_command(_: argparse.Namespace, config: dict[str, Any]) -> int:
    print(json.dumps(bitbrowser_request(config, "/health", {}), ensure_ascii=False, indent=2))
    return 0


def bitbrowser_list_command(args: argparse.Namespace, config: dict[str, Any]) -> int:
    payload = {"page": args.page, "pageSize": args.page_size}
    print(json.dumps(bitbrowser_request(config, "/browser/list", payload), ensure_ascii=False, indent=2))
    return 0


def bitbrowser_open_command(args: argparse.Namespace, config: dict[str, Any]) -> int:
    print(json.dumps(bitbrowser_request(config, "/browser/open", {"id": args.window_id}), ensure_ascii=False, indent=2))
    return 0


def bitbrowser_close_command(args: argparse.Namespace, config: dict[str, Any]) -> int:
    print(json.dumps(bitbrowser_request(config, "/browser/close", {"id": args.window_id}), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bridge to external openclaw_tools components from this workspace")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check", help="Check configured external tool paths and BitBrowser health")
    subparsers.add_parser("print-config", help="Print resolved configuration")

    scrapling_parser = subparsers.add_parser("scrapling", help="Forward arguments to scrapling.exe")
    scrapling_parser.add_argument("args", nargs=argparse.REMAINDER)

    scrapling_python_parser = subparsers.add_parser("scrapling-python", help="Run Python inside Scrapling's venv")
    scrapling_python_parser.add_argument("args", nargs=argparse.REMAINDER)

    opencli_parser = subparsers.add_parser("opencli", help="Forward arguments to external opencli")
    opencli_parser.add_argument("args", nargs=argparse.REMAINDER)

    subparsers.add_parser("bitbrowser-health", help="Call BitBrowser /health")

    bitbrowser_list_parser = subparsers.add_parser("bitbrowser-list", help="Call BitBrowser /browser/list")
    bitbrowser_list_parser.add_argument("--page", type=int, default=0)
    bitbrowser_list_parser.add_argument("--page-size", type=int, default=20, dest="page_size")

    bitbrowser_open_parser = subparsers.add_parser("bitbrowser-open", help="Call BitBrowser /browser/open")
    bitbrowser_open_parser.add_argument("window_id")

    bitbrowser_close_parser = subparsers.add_parser("bitbrowser-close", help="Call BitBrowser /browser/close")
    bitbrowser_close_parser.add_argument("window_id")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = normalized_config()

    command_map = {
        "check": check_command,
        "print-config": lambda _args, _config: (print_config(_config) or 0),
        "scrapling": scrapling_command,
        "scrapling-python": scrapling_python_command,
        "opencli": opencli_command,
        "bitbrowser-health": bitbrowser_health_command,
        "bitbrowser-list": bitbrowser_list_command,
        "bitbrowser-open": bitbrowser_open_command,
        "bitbrowser-close": bitbrowser_close_command,
    }
    return command_map[args.command](args, config)


if __name__ == "__main__":
    raise SystemExit(main())