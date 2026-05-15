from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image, ImageDraw, ImageFont

from pipeline.comfy.template_patcher import build_negative_prompt, build_positive_prompt
from pipeline.common.io import read_json, resolve_project_path, write_json


RUNTIME_ROOT = PROJECT_ROOT / "runtime" / "2026-05-15_test_projects_short_manga"
SERIES_ID = "test_projects_short_manga"
CHAPTER_ID = "ep001"
MANIFEST_PATH = RUNTIME_ROOT / "manifests" / SERIES_ID / CHAPTER_ID / "shot_manifest.json"
BIBLE_PATH = RUNTIME_ROOT / "characters" / SERIES_ID / CHAPTER_ID / "character_bible.json"
OUTPUT_DIR = RUNTIME_ROOT / "review"

CHARACTER_CROPS = {
    "char_dark_ponytail": [
        ("body", "tests/Test_projects/QQ20260515-145001.png", [70, 40, 610, 1190]),
        ("closeup", "tests/Test_projects/QQ20260515-145053.png", [0, 0, 560, 900]),
    ],
    "char_silver_longhair": [
        ("body", "tests/Test_projects/QQ20260515-145001.png", [500, 250, 970, 1230]),
        ("closeup", "tests/Test_projects/QQ20260515-145053.png", [420, 0, 1000, 900]),
    ],
}


def main() -> int:
    manifest = read_json(MANIFEST_PATH)
    bible = read_json(BIBLE_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    character_sheet = OUTPUT_DIR / "character_design_sheet.png"
    storyboard_sheet = OUTPUT_DIR / "storyboard_sheet.png"
    prompt_json = OUTPUT_DIR / "video_prompt_pack.json"
    prompt_md = OUTPUT_DIR / "video_prompt_pack.md"

    prompt_pack = build_prompt_pack(manifest, bible, character_sheet, storyboard_sheet)
    render_character_design_sheet(bible, character_sheet)
    render_storyboard_sheet(prompt_pack, storyboard_sheet)
    write_json(prompt_json, prompt_pack)
    write_prompt_markdown(prompt_pack, prompt_md)
    print(
        json.dumps(
            {
                "character_design_sheet": str(character_sheet),
                "storyboard_sheet": str(storyboard_sheet),
                "video_prompt_pack_json": str(prompt_json),
                "video_prompt_pack_md": str(prompt_md),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def render_character_design_sheet(bible: dict[str, Any], output_path: Path) -> None:
    characters = bible.get("characters", [])
    width = 1800
    card_h = 760
    margin = 48
    header_h = 110
    height = header_h + len(characters) * (card_h + 34) + margin
    image = Image.new("RGB", (width, height), "#f7f4ee")
    draw = ImageDraw.Draw(image)
    fonts = _fonts()
    draw.text((margin, 30), "角色设计图 / Character Design Sheet", font=fonts["title"], fill="#211f1d")
    draw.text((margin, 78), "基于测试漫画原图裁切 + Qwen3-VL 角色圣经归并；用于后续 ComfyUI 角色参考与提示词锚定。", font=fonts["small"], fill="#55504a")

    y = header_h
    for character in characters:
        draw.rounded_rectangle((margin, y, width - margin, y + card_h), radius=18, fill="#ffffff", outline="#d8d2c8", width=2)
        x = margin + 24
        crop_specs = CHARACTER_CROPS.get(character["character_id"], [])
        for label, rel_path, box in crop_specs:
            crop = _crop_image(resolve_project_path(PROJECT_ROOT, rel_path), box)
            crop.thumbnail((380, 560), Image.Resampling.LANCZOS)
            frame = Image.new("RGB", (400, 590), "#eee9df")
            fx = (frame.width - crop.width) // 2
            fy = 18
            frame.paste(crop, (fx, fy))
            d = ImageDraw.Draw(frame)
            d.text((18, 552), label, font=fonts["small"], fill="#50483f")
            image.paste(frame, (x, y + 86))
            x += 430

        text_x = margin + 900
        draw.text((text_x, y + 32), f"{character['display_name']}  ({character['character_id']})", font=fonts["heading"], fill="#191716")
        draw.text((text_x, y + 82), f"置信度: {character.get('confidence', '')}", font=fonts["body"], fill="#6a4130")
        traits = character.get("visual_traits", {})
        trait_lines = [
            f"发色: {traits.get('hair_color', '')}",
            f"发型: {traits.get('hair_style', '')}",
            f"眼睛: {traits.get('eye_color', '')}",
            f"服装: {traits.get('outfit', '')}",
            f"身高: {traits.get('height', '')}",
        ]
        draw_wrapped(draw, "\n".join(trait_lines), (text_x, y + 130), 790, fonts["body"], "#2e2a27", line_gap=8)
        draw.text((text_x, y + 310), "连续性提示词", font=fonts["label"], fill="#57423a")
        draw_wrapped(draw, character.get("continuity_prompt", ""), (text_x, y + 348), 790, fonts["body"], "#272422", line_gap=8)
        draw.text((text_x, y + 460), "负面约束", font=fonts["label"], fill="#57423a")
        draw_wrapped(draw, character.get("negative_prompt", ""), (text_x, y + 498), 790, fonts["body"], "#272422", line_gap=8)
        y += card_h + 34
    image.save(output_path)


def render_storyboard_sheet(prompt_pack: dict[str, Any], output_path: Path) -> None:
    shots = prompt_pack.get("shots", [])
    manifest = read_json(MANIFEST_PATH)
    width = 1900
    row_h = 560
    margin = 44
    header_h = 110
    height = header_h + len(shots) * (row_h + 28) + margin
    image = Image.new("RGB", (width, height), "#f4f6f4")
    draw = ImageDraw.Draw(image)
    fonts = _fonts()
    draw.text((margin, 28), "分镜图 / Storyboard Sheet", font=fonts["title"], fill="#171a16")
    draw.text((margin, 76), "每行对应一条 shot manifest，右侧为后续视频生成的镜头意图和 route。", font=fonts["small"], fill="#565d55")
    packet_map = _packet_map(manifest)

    y = header_h
    for index, shot in enumerate(shots, start=1):
        draw.rounded_rectangle((margin, y, width - margin, y + row_h), radius=18, fill="#ffffff", outline="#ccd5ca", width=2)
        thumb = _shot_thumbnail(shot, packet_map)
        thumb.thumbnail((430, 500), Image.Resampling.LANCZOS)
        frame = Image.new("RGB", (450, 510), "#e7ece5")
        frame.paste(thumb, ((frame.width - thumb.width) // 2, (frame.height - thumb.height) // 2))
        image.paste(frame, (margin + 24, y + 25))
        text_x = margin + 510
        draw.text((text_x, y + 30), f"{index}. {shot['shot_id']}  route={shot.get('workflow_route')}", font=fonts["heading"], fill="#171a16")
        draw.text((text_x, y + 78), f"角色ID: {', '.join(shot.get('main_character_ids', []))}", font=fonts["body"], fill="#34513a")
        draw.text((text_x, y + 118), f"情绪/动作: {shot.get('emotion')} / {shot.get('action_level')}", font=fonts["body"], fill="#573f32")
        draw.text((text_x, y + 160), "剧情摘要", font=fonts["label"], fill="#3d493b")
        draw_wrapped(draw, shot.get("dialogue_summary", ""), (text_x, y + 196), 1280, fonts["body"], "#242822", line_gap=7)
        draw.text((text_x, y + 300), "视频正向提示词", font=fonts["label"], fill="#3d493b")
        draw_wrapped(draw, shot.get("final_positive_prompt", ""), (text_x, y + 336), 1280, fonts["small"], "#252b23", line_gap=6)
        y += row_h + 28
    image.save(output_path)


def build_prompt_pack(
    manifest: dict[str, Any],
    bible: dict[str, Any],
    character_sheet: Path,
    storyboard_sheet: Path,
) -> dict[str, Any]:
    characters_by_id = {item["character_id"]: item for item in bible.get("characters", [])}
    shots = []
    packet_map = _packet_map(manifest)
    for shot in manifest.get("shots", []):
        character_prompts = [
            characters_by_id[character_id]["continuity_prompt"]
            for character_id in shot.get("main_character_ids", [])
            if character_id in characters_by_id
        ]
        character_negative_prompts = [
            characters_by_id[character_id]["negative_prompt"]
            for character_id in shot.get("main_character_ids", [])
            if character_id in characters_by_id
        ]
        final_positive = build_positive_prompt(shot)
        if character_prompts:
            final_positive = f"{final_positive}, character continuity: {'; '.join(character_prompts)}"
        final_negative = build_negative_prompt(shot)
        if character_negative_prompts:
            final_negative = _join_unique([final_negative, *character_negative_prompts])
        input_image_path, input_crop = _shot_input_ref(shot, packet_map)
        shots.append(
            {
                "shot_id": shot["shot_id"],
                "workflow_route": shot.get("workflow_route"),
                "main_character_ids": shot.get("main_character_ids", []),
                "dialogue_summary": shot.get("dialogue_summary"),
                "story_role": shot.get("story_role"),
                "shot_type": shot.get("shot_type"),
                "emotion": shot.get("emotion"),
                "action_level": shot.get("action_level"),
                "anime_fit_score": shot.get("anime_fit_score"),
                "confidence": shot.get("confidence"),
                "character_continuity_prompts": character_prompts,
                "final_positive_prompt": final_positive,
                "final_negative_prompt": final_negative,
                "input_image_path": input_image_path,
                "input_crop_box": input_crop,
                "source_windows": shot.get("source_windows", []),
                "crop_recommendation": shot.get("crop_recommendation", {}),
            }
        )
    return {
        "series_id": manifest.get("series_id"),
        "chapter_id": manifest.get("chapter_id"),
        "character_design_sheet": str(character_sheet.relative_to(PROJECT_ROOT)),
        "storyboard_sheet": str(storyboard_sheet.relative_to(PROJECT_ROOT)),
        "recommended_comfy_route": "dialogue_light_motion",
        "recommended_base_workflow": "configs/comfy_workflows/dialogue_light_motion.json",
        "characters": bible.get("characters", []),
        "shots": shots,
    }


def write_prompt_markdown(prompt_pack: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# 测试漫画视频生成提示词包",
        "",
        f"- 角色设计图：`{prompt_pack['character_design_sheet']}`",
        f"- 分镜图：`{prompt_pack['storyboard_sheet']}`",
        f"- 推荐 ComfyUI route：`{prompt_pack['recommended_comfy_route']}`",
        f"- 推荐基础工作流：`{prompt_pack['recommended_base_workflow']}`",
        "",
        "## 角色锚点",
        "",
    ]
    for character in prompt_pack["characters"]:
        lines.extend(
            [
                f"### {character['display_name']} / `{character['character_id']}`",
                "",
                f"- continuity_prompt: `{character['continuity_prompt']}`",
                f"- negative_prompt: `{character['negative_prompt']}`",
                f"- evidence_shots: `{', '.join(character.get('evidence_shots', []))}`",
                "",
            ]
        )
    lines.extend(["## 镜头提示词", ""])
    for shot in prompt_pack["shots"]:
        lines.extend(
            [
                f"### {shot['shot_id']} / `{shot['workflow_route']}`",
                "",
                f"- 角色：`{', '.join(shot['main_character_ids'])}`",
                f"- 剧情摘要：{shot['dialogue_summary']}",
                f"- 情绪/动作：{shot['emotion']} / {shot['action_level']}",
                f"- anime_fit_score/confidence：{shot['anime_fit_score']} / {shot['confidence']}",
                f"- 输入参考图：`{shot['input_image_path']}`",
                f"- 输入裁切框：`{shot['input_crop_box']}`",
                "",
                "正向提示词：",
                "",
                f"```text\n{shot['final_positive_prompt']}\n```",
                "",
                "负向提示词：",
                "",
                f"```text\n{shot['final_negative_prompt']}\n```",
                "",
            ]
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _packet_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    packets = {}
    for ref in manifest.get("source_packet_refs", []):
        packet = read_json(resolve_project_path(PROJECT_ROOT, ref))
        packets[packet["window_id"]] = packet
    return packets


def _shot_thumbnail(shot: dict[str, Any], packet_map: dict[str, dict[str, Any]]) -> Image.Image:
    window_id = (shot.get("source_windows") or [""])[0]
    packet = packet_map[window_id]
    path = resolve_project_path(PROJECT_ROOT, packet["window_image_path"])
    crop_box = (shot.get("crop_recommendation") or {}).get("box") or packet["source_box"]
    return _crop_image(path, crop_box)


def _shot_input_ref(shot: dict[str, Any], packet_map: dict[str, dict[str, Any]]) -> tuple[str, list[int]]:
    window_id = (shot.get("source_windows") or [""])[0]
    packet = packet_map[window_id]
    crop_box = (shot.get("crop_recommendation") or {}).get("box") or packet["source_box"]
    return packet["window_image_path"], crop_box


def _crop_image(path: Path, box: list[int]) -> Image.Image:
    with Image.open(path) as image:
        image = image.convert("RGB")
        x1, y1, x2, y2 = _clamp_box(box, image.width, image.height)
        return image.crop((x1, y1, x2, y2))


def _clamp_box(box: list[int], width: int, height: int) -> list[int]:
    x1 = max(0, min(width - 1, int(box[0])))
    y1 = max(0, min(height - 1, int(box[1])))
    x2 = max(x1 + 1, min(width, int(box[2])))
    y2 = max(y1 + 1, min(height, int(box[3])))
    return [x1, y1, x2, y2]


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    max_width: int,
    font: ImageFont.ImageFont,
    fill: str,
    line_gap: int = 6,
) -> None:
    x, y = xy
    for paragraph in str(text or "").splitlines() or [""]:
        line = ""
        for char in paragraph:
            candidate = line + char
            if draw.textlength(candidate, font=font) <= max_width or not line:
                line = candidate
            else:
                draw.text((x, y), line, font=font, fill=fill)
                y += font.size + line_gap
                line = char
        if line:
            draw.text((x, y), line, font=font, fill=fill)
            y += font.size + line_gap
        else:
            y += font.size + line_gap


def _join_unique(parts: list[str]) -> str:
    clauses: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for clause in str(part or "").split(","):
            text = clause.strip()
            key = text.lower()
            if text and key not in seen:
                clauses.append(text)
                seen.add(key)
    return ", ".join(clauses)


def _fonts() -> dict[str, ImageFont.FreeTypeFont]:
    font_path = _font_path()
    return {
        "title": ImageFont.truetype(font_path, 34),
        "heading": ImageFont.truetype(font_path, 26),
        "label": ImageFont.truetype(font_path, 22),
        "body": ImageFont.truetype(font_path, 21),
        "small": ImageFont.truetype(font_path, 18),
    }


def _font_path() -> str:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    raise FileNotFoundError("No Chinese-capable Windows font found")


if __name__ == "__main__":
    raise SystemExit(main())
