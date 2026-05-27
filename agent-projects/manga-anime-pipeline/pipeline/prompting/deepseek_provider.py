from __future__ import annotations

import json
import os
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from pipeline.prompting.base import PromptOptimizerConfig


DEFAULT_SYSTEM_PROMPT = """你是漫画改编短视频的提示词总监。
目标：把导演草稿改写成可直接用于 ComfyUI 的生产级 prompt。
要求：
1. 仅输出严格 JSON，不要 Markdown。
2. 保留输入里的 character_id、shot_id 和 workflow_route。
3. 正向提示词要兼顾角色身份、外观连续性、镜头语言、运动幅度、画面质量和动漫风格。
4. 负向提示词要覆盖身份漂移、发型/瞳色/校服变化、手部崩坏、文字水印、嘴部乱动、构图裁切错误。
5. 对 dialogue_light_motion 镜头，动作要克制，避免大幅口型和复杂肢体运动。
6. 角色 design_prompt 使用英文为主，可保留中文角色名；长度控制在 80-150 个英文词，必须包含发色、发型、瞳色、身高体型、校服细节、表情气质、角色设定图构图、光线、线条和背景约束。
7. 视频 positive_prompt 使用英文为主，可保留中文角色名；长度控制在 80-160 个英文词，必须包含角色锚点、场景、表情、动作幅度、镜头、风格、稳定性约束。
8. 不要要求模型生成新的可读文字；如涉及对话气泡，只描述“保留源图对白气泡布局/不要新增字幕”，避免 clear text/new text。
9. 输出字段必须包含 characters 和 shots。"""


class DeepSeekPromptOptimizer:
    provider_name = "deepseek"

    def __init__(self, config: PromptOptimizerConfig) -> None:
        self.config = config

    def optimize(self, prompt_pack: dict[str, Any]) -> dict[str, Any]:
        api_key = os.environ.get(self.config.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"DeepSeek API key is not set. Put it in environment variable {self.config.api_key_env}, not in repo files."
            )
        payload = {
            "model": self.config.model or "deepseek-v4-pro",
            "messages": [
                {"role": "system", "content": self.config.system_prompt or DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(prompt_pack)},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }
        response = _post_json(
            _chat_url(self.config.base_url or "https://api.deepseek.com"),
            payload,
            api_key=api_key,
            timeout_seconds=self.config.timeout_seconds,
        )
        content = _response_content(response)
        optimized = _parse_json_content(content)
        optimized.setdefault("optimizer", {})
        optimized["optimizer"].update(
            {
                "provider": self.provider_name,
                "model": payload["model"],
                "base_url": self.config.base_url or "https://api.deepseek.com",
            }
        )
        return optimized


def _build_user_prompt(prompt_pack: dict[str, Any]) -> str:
    compact = {
        "series_id": prompt_pack.get("series_id"),
        "chapter_id": prompt_pack.get("chapter_id"),
        "recommended_comfy_route": prompt_pack.get("recommended_comfy_route"),
        "characters": [
            {
                "character_id": item.get("character_id"),
                "display_name": item.get("display_name"),
                "visual_traits": item.get("visual_traits"),
                "performance_traits": item.get("performance_traits"),
                "continuity_prompt": item.get("continuity_prompt"),
                "negative_prompt": item.get("negative_prompt"),
            }
            for item in prompt_pack.get("characters", [])
        ],
        "shots": [
            {
                "shot_id": item.get("shot_id"),
                "workflow_route": item.get("workflow_route"),
                "main_character_ids": item.get("main_character_ids"),
                "dialogue_summary": item.get("dialogue_summary"),
                "story_role": item.get("story_role"),
                "shot_type": item.get("shot_type"),
                "emotion": item.get("emotion"),
                "action_level": item.get("action_level"),
                "character_continuity_prompts": item.get("character_continuity_prompts"),
                "draft_positive_prompt": item.get("final_positive_prompt"),
                "draft_negative_prompt": item.get("final_negative_prompt"),
                "input_image_path": item.get("input_image_path"),
                "input_crop_box": item.get("input_crop_box"),
            }
            for item in prompt_pack.get("shots", [])
        ],
    }
    schema_hint = {
        "characters": [
            {
                "character_id": "string",
                "display_name": "string",
                "design_prompt": "80-150 English words, key Chinese names allowed, production prompt for SDXL anime character sheet",
                "negative_prompt": "identity and anatomy constraints",
                "reference_notes": "short continuity anchor",
            }
        ],
        "shots": [
            {
                "shot_id": "string",
                "workflow_route": "string",
                "positive_prompt": "80-160 English words, key Chinese names allowed, video-ready prompt",
                "negative_prompt": "motion and identity constraints",
                "motion_prompt": "concise motion instruction",
                "camera_prompt": "concise camera instruction",
                "quality_notes": "short production QA note",
            }
        ],
    }
    return (
        "请优化下面的漫画短视频提示词包。输出必须是 JSON，结构参考 schema_hint。\n"
        f"schema_hint={json.dumps(schema_hint, ensure_ascii=False)}\n"
        f"input_prompt_pack={json.dumps(compact, ensure_ascii=False)}"
    )


def _post_json(url: str, payload: dict[str, Any], *, api_key: str, timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urlrequest.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urlrequest.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
    except urlerror.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek HTTP {error.code}: {detail or error.reason}") from error
    except urlerror.URLError as error:
        raise RuntimeError(f"DeepSeek request failed: {error.reason}") from error
    return json.loads(raw.decode("utf-8"))


def _chat_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def _response_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("DeepSeek response contains no choices")
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if not content:
        raise RuntimeError("DeepSeek response message.content is empty")
    return str(content)


def _parse_json_content(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"DeepSeek response is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError("DeepSeek JSON response must be an object")
    return value
