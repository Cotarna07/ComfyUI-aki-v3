from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


class WorkflowFormatError(Exception):
    pass


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "agent-skills").is_dir():
            return candidate
    raise RuntimeError("无法定位仓库根目录。")


REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_TARGET = REPO_ROOT / "agent-skills" / "comfyui" / "workflows" / "TEST"


def reject_nonstandard_constant(value: str) -> None:
    raise WorkflowFormatError(f"发现非标准 JSON 常量 {value!r}，为避免改坏工作流已跳过。")


def object_pairs_no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    data: dict[str, object] = {}
    duplicates: list[str] = []
    for key, value in pairs:
        if key in data:
            duplicates.append(key)
        data[key] = value
    if duplicates:
        preview = ", ".join(repr(key) for key in duplicates[:5])
        if len(duplicates) > 5:
            preview += ", ..."
        raise WorkflowFormatError(f"检测到重复键 {preview}，已跳过该文件。")
    return data


def parse_json_text(text: str) -> object:
    try:
        return json.loads(
            text,
            object_pairs_hook=object_pairs_no_duplicates,
            parse_constant=reject_nonstandard_constant,
        )
    except WorkflowFormatError:
        raise
    except json.JSONDecodeError as exc:
        raise WorkflowFormatError(
            f"JSON 解析失败: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from exc


def read_utf8_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise WorkflowFormatError(f"文件不是 UTF-8 或 UTF-8 BOM，已跳过: {exc}") from exc


def render_json_text(data: object) -> str:
    return json.dumps(
        data,
        ensure_ascii=False,
        indent="\t",
        separators=(",", ":"),
        sort_keys=False,
    ) + "\n"


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.endswith("\n"):
        normalized += "\n"
    return normalized


def build_backup_path(path: Path, backup_ext: str) -> Path:
    candidate = path.with_name(f"{path.name}{backup_ext}")
    if not candidate.exists():
        return candidate

    index = 1
    while True:
        candidate = path.with_name(f"{path.name}{backup_ext}.{index}")
        if not candidate.exists():
            return candidate
        index += 1


def write_verified_json(path: Path, formatted_text: str, original_data: object, backup_ext: str | None) -> str:
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(formatted_text, encoding="utf-8", newline="")

    try:
        rewritten_data = parse_json_text(temp_path.read_text(encoding="utf-8"))
        if rewritten_data != original_data:
            raise WorkflowFormatError("改写后的 JSON 与原始结构不一致，已中止写入。")

        backup_message = ""
        if backup_ext:
            backup_path = build_backup_path(path, backup_ext)
            shutil.copy2(path, backup_path)
            backup_message = f"，备份: {backup_path.name}"

        temp_path.replace(path)
        return f"已格式化{backup_message}"
    finally:
        if temp_path.exists():
            temp_path.unlink()


@dataclass
class FileResult:
    path: Path
    changed: bool
    written: bool
    message: str


def format_file(path: Path, write: bool, backup_ext: str | None) -> FileResult:
    original_text = read_utf8_text(path)
    original_data = parse_json_text(original_text)
    formatted_text = render_json_text(original_data)

    if normalize_text(original_text) == formatted_text:
        return FileResult(path=path, changed=False, written=False, message="已是标准格式")

    if not write:
        return FileResult(path=path, changed=True, written=False, message="需要格式化")

    message = write_verified_json(path, formatted_text, original_data, backup_ext)
    return FileResult(path=path, changed=True, written=True, message=message)


def iter_json_files(target: Path, recursive: bool) -> Iterator[Path]:
    if target.is_file():
        if not should_skip_path(target):
            yield target
        return

    walker = target.rglob("*.json") if recursive else target.glob("*.json")
    for path in sorted(walker):
        if path.is_file() and not should_skip_path(path):
            yield path


def should_skip_path(path: Path) -> bool:
    return path.name.startswith("._") or "__MACOSX" in path.parts


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量把 ComfyUI 工作流 JSON 转成可读的标准格式，并在写回前后校验结构一致。"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=str(DEFAULT_TARGET),
        help=f"要处理的 JSON 文件或目录，默认是 {DEFAULT_TARGET}",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="原地改写文件；默认只检查哪些文件需要格式化。",
    )
    parser.add_argument(
        "--top-level-only",
        action="store_true",
        help="只处理当前目录，不递归子目录。",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="原地改写时不生成 .bak 备份。",
    )
    parser.add_argument(
        "--backup-ext",
        default=".bak",
        help="备份扩展名，默认是 .bak。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = Path(args.target).expanduser().resolve()
    if not target.exists():
        print(f"[ERROR] 目标不存在: {display_path(target)}", file=sys.stderr)
        return 1

    if target.is_dir():
        files = list(iter_json_files(target, recursive=not args.top_level_only))
    elif target.suffix.lower() == ".json":
        files = [target]
    else:
        print(f"[ERROR] 只支持 .json 文件或目录: {display_path(target)}", file=sys.stderr)
        return 1

    if not files:
        print(f"[ERROR] 未找到 JSON 文件: {display_path(target)}", file=sys.stderr)
        return 1

    ok_count = 0
    needs_count = 0
    written_count = 0
    error_count = 0
    backup_ext = None if args.no_backup else args.backup_ext

    for path in files:
        try:
            result = format_file(path, write=args.write, backup_ext=backup_ext)
        except WorkflowFormatError as exc:
            error_count += 1
            print(f"[ERROR] {display_path(path)} - {exc}", file=sys.stderr)
            continue

        if result.written:
            written_count += 1
            print(f"[WRITE] {display_path(path)} - {result.message}")
        elif result.changed:
            needs_count += 1
            print(f"[NEEDS] {display_path(path)} - {result.message}")
        else:
            ok_count += 1
            print(f"[OK]    {display_path(path)} - {result.message}")

    print(
        f"\n扫描完成: 共 {len(files)} 个文件，"
        f"已标准化 {written_count} 个，"
        f"待格式化 {needs_count} 个，"
        f"已合规 {ok_count} 个，"
        f"失败 {error_count} 个。"
    )

    if error_count:
        return 1
    if needs_count and not args.write:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())