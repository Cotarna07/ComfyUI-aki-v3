from __future__ import annotations

from pathlib import Path


def build_review_prompt(images: list[Path]) -> str:
    labels = "\n".join(f"- Image-{index}: {image.name}" for index, image in enumerate(images, start=1))
    focus = (
        "特别核对：仅在图中可见时，说明人物/驾驶员相对商品的位置，"
        "以及部件是否处于已安装、分离、可拆或拆解演示状态；未显示则不要推测。"
    )
    return (
        "你是电商商品图事实审查员和广告镜头规划助手。只依据提供的原始图片作答，"
        "不要把推测写成事实。\n"
        f"图片映射：\n{labels}\n"
        f"{focus}\n"
        "请严格输出一个 JSON 对象，字段如下：\n"
        "{\n"
        '  "product_identity": "可从图片确认的商品身份",\n'
        '  "source_facts": [{"fact": "事实", "evidence_images": ["Image-1"], "confidence": 0.0}],\n'
        '  "must_preserve": ["生成图必须保留的结构/颜色/配件/人物关系"],\n'
        '  "creative_allowed": ["原图支持或不改变商品事实的创意表达"],\n'
        '  "creative_forbidden": ["会误导真实商品展示的改动"],\n'
        '  "proposed_shots": [{"shot_id": "标识", "composition": "构图", "scene": "场景", '
        '"factual_basis": ["Image-1"], "use_as": "creative_ad_or_factual"}],\n'
        '  "warnings": ["不确定或需人工核验的信息"]\n'
        "}\n"
        "不要输出 Markdown 代码块，不要臆测包装文字、零件数量或未显示的功能。"
    )
