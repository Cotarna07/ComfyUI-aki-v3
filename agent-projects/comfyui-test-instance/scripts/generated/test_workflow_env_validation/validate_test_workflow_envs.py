from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


UUID_LIKE_NODE_TYPE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
SECTION_HEADER = re.compile(r"^[一二三四五六七八九十]+、")

IGNORED_NODE_TYPES = {
    "Note",
    "MarkdownNote",
    "PrimitiveNode",
    "Reroute",
    "SetNode",
    "GetNode",
    "SamplerSelector",
    "SchedulerSelector",
    "Label (rgthree)",
    "Fast Groups Bypasser (rgthree)",
}

NODE_TYPE_ALIASES = {
    "Text Concatenate": "CR Text Concatenate",
}


@dataclass
class SectionSpec:
    title: str
    env_names: list[str]
    patterns: list[str] = field(default_factory=list)


@dataclass
class EnvironmentInventory:
    name: str
    url: str
    online: bool
    node_types: set[str]
    error: str | None = None


@dataclass
class WorkflowRecord:
    source: str
    source_kind: str
    class_types: list[str]
    missing_class_types: list[str]
    error: str | None = None


@dataclass
class SectionReport:
    title: str
    env_names: list[str]
    env_urls: list[str]
    offline_envs: list[str] = field(default_factory=list)
    unmatched_patterns: list[str] = field(default_factory=list)
    archive_without_json: list[str] = field(default_factory=list)
    invalid_sources: list[dict[str, str]] = field(default_factory=list)
    workflow_records: list[WorkflowRecord] = field(default_factory=list)


def discover_workspace_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "AGENTS.md").is_file():
            return candidate
    raise RuntimeError("未找到工作区根目录（缺少 AGENTS.md）。")


SCRIPT_PATH = Path(__file__).resolve()
WORKSPACE_ROOT = discover_workspace_root(SCRIPT_PATH.parent)
PROJECT_ROOT = WORKSPACE_ROOT / "agent-projects" / "comfyui-test-instance"
DEFAULT_DOC_PATH = WORKSPACE_ROOT / "agent-skills" / "docs" / "2026-05-30_TEST工作流环境安装提示词.md"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "environments.json"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "runtime" / "test_workflow_env_validation"


def read_json_text(raw: bytes) -> Any:
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            return json.loads(raw.decode(encoding))
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON 解析失败: {exc}") from exc
    raise ValueError("无法按 UTF-8/UTF-8-SIG 解码 JSON。")


def load_environment_config(config_path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    default_listen = data.get("default_listen", "127.0.0.1")
    result: dict[str, dict[str, Any]] = {}
    for env in data.get("environments", []):
        name = env.get("name")
        port = env.get("port")
        if not name or not port:
            continue
        result[str(name)] = {
            "port": int(port),
            "url": f"http://{default_listen}:{int(port)}",
            "config": env,
        }
    return result


def parse_doc_sections(doc_path: Path, env_names: list[str]) -> list[SectionSpec]:
    sections: list[SectionSpec] = []
    current: SectionSpec | None = None

    for raw_line in doc_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if SECTION_HEADER.match(line):
            matched_envs = [name for name in env_names if name in line]
            current = SectionSpec(title=line, env_names=matched_envs)
            if matched_envs:
                sections.append(current)
            else:
                current = None
            continue

        if current and line.startswith("- "):
            current.patterns.append(line[2:].strip())

    return sections


def expand_pattern(workspace_root: Path, pattern: str) -> list[Path]:
    absolute_pattern = str(workspace_root / pattern.replace("/", str(Path("/")).replace("\\", "/")))
    matches = sorted({Path(path) for path in glob.glob(absolute_pattern, recursive=True)})
    if matches:
        return matches

    exact_path = workspace_root / Path(pattern)
    if exact_path.exists():
        return [exact_path]
    return []


def fetch_inventory(url: str) -> EnvironmentInventory:
    request = urllib.request.Request(f"{url.rstrip('/')}/object_info", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        return EnvironmentInventory(name="", url=url, online=True, node_types=set(data.keys()))
    except urllib.error.URLError as exc:
        return EnvironmentInventory(name="", url=url, online=False, node_types=set(), error=str(exc.reason))
    except Exception as exc:
        return EnvironmentInventory(name="", url=url, online=False, node_types=set(), error=str(exc))


def walk_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_dicts(value)


def collect_class_types(obj: Any) -> list[str]:
    classes: list[str] = []
    seen: set[str] = set()
    for item in walk_dicts(obj):
        node_type: str | None = None
        if isinstance(item.get("class_type"), str):
            node_type = item["class_type"]
        elif isinstance(item.get("type"), str) and any(key in item for key in ("inputs", "outputs", "widgets_values")):
            node_type = item["type"]
        if node_type and node_type not in seen:
            classes.append(node_type)
            seen.add(node_type)
    return classes


def normalize_missing_classes(class_types: list[str], available: set[str]) -> list[str]:
    missing: list[str] = []
    seen: set[str] = set()
    for class_type in class_types:
        if class_type in IGNORED_NODE_TYPES:
            continue
        if UUID_LIKE_NODE_TYPE.fullmatch(class_type):
            continue
        effective = NODE_TYPE_ALIASES.get(class_type, class_type)
        if effective in available:
            continue
        if class_type not in seen:
            missing.append(class_type)
            seen.add(class_type)
    return missing


def load_json_workflow(path: Path) -> tuple[Any | None, str | None]:
    try:
        raw = path.read_bytes()
        return read_json_text(raw), None
    except Exception as exc:
        return None, str(exc)


def iter_sources(path: Path, workspace_root: Path):
    relative_path = path.relative_to(workspace_root).as_posix()
    if path.suffix.lower() == ".json":
        obj, error = load_json_workflow(path)
        if error:
            yield relative_path, "json", None, error
        else:
            yield relative_path, "json", obj, None
        return

    if path.suffix.lower() != ".zip":
        return

    try:
        with zipfile.ZipFile(path) as archive:
            members = [member for member in archive.namelist() if member.lower().endswith(".json")]
            if not members:
                yield relative_path, "zip", None, "archive_without_json"
                return
            for member in members:
                try:
                    raw = archive.read(member)
                    obj = read_json_text(raw)
                    yield f"{relative_path}::{member}", "zip_json", obj, None
                except Exception as exc:
                    yield f"{relative_path}::{member}", "zip_json", None, str(exc)
    except Exception as exc:
        yield relative_path, "zip", None, str(exc)


def build_section_reports(
    sections: list[SectionSpec],
    inventories: dict[str, EnvironmentInventory],
    workspace_root: Path,
) -> list[SectionReport]:
    reports: list[SectionReport] = []

    for section in sections:
        env_urls = [inventories[name].url for name in section.env_names if name in inventories]
        report = SectionReport(
            title=section.title,
            env_names=section.env_names,
            env_urls=env_urls,
            offline_envs=[name for name in section.env_names if not inventories.get(name) or not inventories[name].online],
        )

        available = set().union(*(inventories[name].node_types for name in section.env_names if inventories.get(name) and inventories[name].online))

        for pattern in section.patterns:
            matches = expand_pattern(workspace_root, pattern)
            if not matches:
                report.unmatched_patterns.append(pattern)
                continue

            for match in matches:
                for source_label, source_kind, obj, error in iter_sources(match, workspace_root):
                    if error == "archive_without_json":
                        report.archive_without_json.append(source_label)
                        continue
                    if error:
                        report.invalid_sources.append({"source": source_label, "error": error})
                        continue
                    class_types = collect_class_types(obj)
                    missing_class_types = normalize_missing_classes(class_types, available) if available else []
                    report.workflow_records.append(
                        WorkflowRecord(
                            source=source_label,
                            source_kind=source_kind,
                            class_types=class_types,
                            missing_class_types=missing_class_types,
                        )
                    )

        report.workflow_records.sort(key=lambda item: (0 if item.missing_class_types else 1, item.source))
        report.unmatched_patterns.sort()
        report.archive_without_json.sort()
        report.invalid_sources.sort(key=lambda item: item["source"])
        reports.append(report)

    return reports


def print_summary(reports: list[SectionReport], inventories: dict[str, EnvironmentInventory]) -> None:
    print("=== 环境状态 ===")
    for name, inventory in inventories.items():
        if inventory.online:
            print(f"[OK] {name} -> {inventory.url}  已注册节点 {len(inventory.node_types)}")
        else:
            print(f"[OFFLINE] {name} -> {inventory.url}  {inventory.error or '无法访问'}")

    print("\n=== 工作流校验 ===")
    for report in reports:
        total = len(report.workflow_records)
        missing = sum(1 for item in report.workflow_records if item.missing_class_types)
        print(f"\n[{report.title}]")
        print(f"环境: {', '.join(report.env_names)}")
        print(f"工作流源: {total}  缺节点工作流: {missing}")
        if report.offline_envs:
            print(f"离线环境: {', '.join(report.offline_envs)}")
        if report.unmatched_patterns:
            print("未匹配路径模式:")
            for pattern in report.unmatched_patterns:
                print(f"  - {pattern}")
        if report.archive_without_json:
            print("ZIP 中未发现 JSON:")
            for source in report.archive_without_json:
                print(f"  - {source}")
        if report.invalid_sources:
            print("无法解析的来源:")
            for item in report.invalid_sources:
                print(f"  - {item['source']}: {item['error']}")
        for record in report.workflow_records:
            if not record.missing_class_types:
                continue
            missing_text = ", ".join(record.missing_class_types)
            print(f"  - {record.source}: {missing_text}")


def write_reports(report_dir: Path, reports: list[SectionReport], inventories: dict[str, EnvironmentInventory]) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = report_dir / f"test_workflow_env_validation-{timestamp}.json"
    md_path = report_dir / f"test_workflow_env_validation-{timestamp}.md"

    payload = {
        "generated_at": timestamp,
        "inventories": {
            name: {
                "url": inventory.url,
                "online": inventory.online,
                "node_count": len(inventory.node_types),
                "error": inventory.error,
            }
            for name, inventory in inventories.items()
        },
        "sections": [asdict(report) for report in reports],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = [
        "# TEST 工作流环境校验报告",
        "",
        f"生成时间: {timestamp}",
        "",
        "## 环境状态",
        "",
    ]
    for name, inventory in inventories.items():
        if inventory.online:
            lines.append(f"- {name}: 在线，{inventory.url}，已注册节点 {len(inventory.node_types)}")
        else:
            lines.append(f"- {name}: 离线，{inventory.url}，错误: {inventory.error or '无法访问'}")

    for report in reports:
        lines.extend([
            "",
            f"## {report.title}",
            "",
            f"- 环境: {', '.join(report.env_names)}",
            f"- 工作流源数: {len(report.workflow_records)}",
            f"- 缺节点工作流数: {sum(1 for item in report.workflow_records if item.missing_class_types)}",
        ])
        if report.offline_envs:
            lines.append(f"- 离线环境: {', '.join(report.offline_envs)}")
        if report.unmatched_patterns:
            lines.append("- 未匹配路径模式:")
            lines.extend([f"  - {pattern}" for pattern in report.unmatched_patterns])
        if report.archive_without_json:
            lines.append("- ZIP 中未发现 JSON:")
            lines.extend([f"  - {source}" for source in report.archive_without_json])
        if report.invalid_sources:
            lines.append("- 无法解析的来源:")
            lines.extend([f"  - {item['source']}: {item['error']}" for item in report.invalid_sources])
        missing_records = [item for item in report.workflow_records if item.missing_class_types]
        if missing_records:
            lines.append("- 仍缺的 class_type:")
            lines.extend([f"  - {item.source}: {', '.join(item.missing_class_types)}" for item in missing_records])
        else:
            lines.append("- 仍缺的 class_type: 无")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="按安装文档分组校验 TEST 工作流的环境节点可用性")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    env_config = load_environment_config(args.config)
    sections = parse_doc_sections(args.doc, list(env_config.keys()))
    if not sections:
        print("未从安装文档解析到任何环境分组。", file=sys.stderr)
        return 2

    inventories: dict[str, EnvironmentInventory] = {}
    for name, info in env_config.items():
        inventory = fetch_inventory(info["url"])
        inventory.name = name
        inventories[name] = inventory

    reports = build_section_reports(sections, inventories, WORKSPACE_ROOT)
    print_summary(reports, inventories)
    json_path, md_path = write_reports(args.report_dir, reports, inventories)
    print("\n=== 报告输出 ===")
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())