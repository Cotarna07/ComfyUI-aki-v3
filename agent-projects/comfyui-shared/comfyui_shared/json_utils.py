"""LLM / VLM 模型输出 JSON 提取工具。

合并自两个独立实现：
- product-vlm-review/product_vlm_review/runtime.py  —— parse_json_object（公开）
- lmstudio-comfyui-benchmark/prompt_quality.py       —— _parse_json_object（私有）

两处逻辑相同：优先提取代码围栏内容，其次首尾括号截取，最后尝试原文。
"""

from __future__ import annotations

import json
import re
from typing import Any


def parse_json_object(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """从 LLM 文本回答中提取第一个 JSON 对象。

    返回 (parsed_dict, None) 成功；(None, error_msg) 失败。

    提取顺序：
    1. ```json ... ``` 围栏内容
    2. 原文首尾 { } 截取
    3. 原文整体

    示例::

        obj, err = parse_json_object(llm_response)
        if err:
            print("解析失败:", err)
    """
    stripped = text.strip()
    candidates: list[str] = []

    # 优先：代码围栏
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.append(fenced.group(1))

    # 其次：首尾括号截取
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first >= 0 and last > first:
        candidates.append(stripped[first : last + 1])

    # 兜底：整体
    candidates.append(stripped)

    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value, None

    return None, "模型回答中没有可解析的 JSON 对象"
