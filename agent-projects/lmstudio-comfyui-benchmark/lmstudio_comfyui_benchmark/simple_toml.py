from __future__ import annotations

import ast
from typing import Any, BinaryIO


def load(handle: BinaryIO) -> dict[str, Any]:
    text = handle.read().decode("utf-8")
    return loads(text)


def loads(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    current: Any = root
    current_path: list[str] = []
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = _strip_comment(raw_line).strip()
        index += 1
        if not line:
            continue

        if line.startswith("[[") and line.endswith("]]"):
            path = line[2:-2].strip().split(".")
            parent = _ensure_table(root, path[:-1])
            key = path[-1]
            parent.setdefault(key, [])
            item: dict[str, Any] = {}
            parent[key].append(item)
            current = item
            current_path = path
            continue

        if line.startswith("[") and line.endswith("]"):
            current_path = line[1:-1].strip().split(".")
            current = _ensure_table(root, current_path)
            continue

        if "=" not in line:
            raise ValueError(f"Invalid TOML line: {raw_line}")

        key, value = line.split("=", 1)
        raw_key = key.strip()
        quoted_key = raw_key.startswith('"') and raw_key.endswith('"')
        key = raw_key.strip('"')
        value = value.strip()

        if value.startswith('"""'):
            collected: list[str] = []
            remainder = value[3:]
            if remainder.endswith('"""') and len(remainder) >= 3:
                parsed_value = remainder[:-3]
            else:
                if remainder:
                    collected.append(remainder)
                while index < len(lines):
                    multi_line = lines[index]
                    index += 1
                    if '"""' in multi_line:
                        before, _, _after = multi_line.partition('"""')
                        collected.append(before)
                        break
                    collected.append(multi_line)
                parsed_value = "\n".join(collected)
        elif value.startswith("[") and not value.endswith("]"):
            collected = [value]
            bracket_balance = value.count("[") - value.count("]")
            while index < len(lines) and bracket_balance > 0:
                array_line = _strip_comment(lines[index]).strip()
                index += 1
                if not array_line:
                    continue
                collected.append(array_line)
                bracket_balance += array_line.count("[") - array_line.count("]")
            parsed_value = _parse_value(" ".join(collected))
        else:
            parsed_value = _parse_value(value)

        target = current
        if "." in key and not quoted_key:
            key_parts = key.split(".")
            target = _ensure_table(current, key_parts[:-1])
            key = key_parts[-1]
        target[key] = parsed_value

    return root


def _ensure_table(root: dict[str, Any], path: list[str]) -> dict[str, Any]:
    cursor = root
    for part in path:
        cursor = cursor.setdefault(part, {})
        if not isinstance(cursor, dict):
            raise ValueError(f"Path is not a table: {'.'.join(path)}")
    return cursor


def _parse_value(value: str) -> Any:
    value = _strip_comment(value).strip()
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        return ast.literal_eval(value)
    if value.startswith('"') and value.endswith('"'):
        return ast.literal_eval(value)
    try:
        if any(char in value for char in ".eE"):
            return float(value)
        return int(value)
    except ValueError:
        return value


def _strip_comment(line: str) -> str:
    in_string = False
    escaped = False
    for index, char in enumerate(line):
        if char == "\\" and in_string:
            escaped = not escaped
            continue
        if char == '"' and not escaped:
            in_string = not in_string
        if char == "#" and not in_string:
            return line[:index]
        escaped = False
    return line
