from __future__ import annotations

from pathlib import Path
from typing import Any


IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def _transform(input_size: int) -> Any:
    import torchvision.transforms as transforms
    from torchvision.transforms.functional import InterpolationMode

    return transforms.Compose(
        [
            transforms.Lambda(lambda image: image.convert("RGB")),
            transforms.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


def _closest_ratio(aspect_ratio: float, ratios: list[tuple[int, int]], area: int, image_size: int) -> tuple[int, int]:
    best = (1, 1)
    best_difference = float("inf")
    for ratio in ratios:
        difference = abs(aspect_ratio - ratio[0] / ratio[1])
        if difference < best_difference:
            best_difference = difference
            best = ratio
        elif difference == best_difference and area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
            best = ratio
    return best


def _tiles(image: Any, max_num: int, image_size: int) -> list[Any]:
    width, height = image.size
    ratios = sorted(
        {
            (columns, rows)
            for blocks in range(1, max_num + 1)
            for columns in range(1, blocks + 1)
            for rows in range(1, blocks + 1)
            if 1 <= columns * rows <= max_num
        },
        key=lambda pair: pair[0] * pair[1],
    )
    target = _closest_ratio(width / height, ratios, width * height, image_size)
    target_width = image_size * target[0]
    target_height = image_size * target[1]
    resized = image.resize((target_width, target_height))
    results: list[Any] = []
    for index in range(target[0] * target[1]):
        left = index % target[0] * image_size
        top = index // target[0] * image_size
        results.append(resized.crop((left, top, left + image_size, top + image_size)))
    if len(results) > 1:
        results.append(image.resize((image_size, image_size)))
    return results


def _load_image(path: Path, max_num: int, image_size: int = 448) -> Any:
    import torch
    from PIL import Image

    transform = _transform(image_size)
    image = Image.open(path).convert("RGB")
    return torch.stack([transform(tile) for tile in _tiles(image, max_num=max_num, image_size=image_size)])


def review_with_internvl(
    prompt: str,
    images: list[Path],
    model_id: str,
    max_tiles_per_image: int,
    max_new_tokens: int,
) -> str:
    model, tokenizer, torch = _load_engine(model_id)
    return _chat(
        model,
        tokenizer,
        torch,
        prompt,
        images,
        max_tiles_per_image,
        max_new_tokens,
    )


def review_each_with_internvl(
    prompts_and_images: list[tuple[str, Path]],
    model_id: str,
    max_tiles_per_image: int,
    max_new_tokens: int,
) -> list[str]:
    model, tokenizer, torch = _load_engine(model_id)
    return [
        _chat(
            model,
            tokenizer,
            torch,
            prompt,
            [image],
            max_tiles_per_image,
            max_new_tokens,
        )
        for prompt, image in prompts_and_images
    ]


def _load_engine(model_id: str) -> tuple[Any, Any, Any]:
    import torch
    from transformers import AutoModel, AutoTokenizer, BitsAndBytesConfig

    quantization_config = BitsAndBytesConfig(load_in_8bit=True)
    model = AutoModel.from_pretrained(
        model_id,
        dtype=torch.bfloat16,
        quantization_config=quantization_config,
        low_cpu_mem_usage=True,
        use_flash_attn=False,
        trust_remote_code=True,
        device_map="auto",
    ).eval()
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, use_fast=False)
    return model, tokenizer, torch


def _chat(
    model: Any,
    tokenizer: Any,
    torch: Any,
    prompt: str,
    images: list[Path],
    max_tiles_per_image: int,
    max_new_tokens: int,
) -> str:
    batches = [_load_image(path, max_num=max_tiles_per_image).to(torch.bfloat16).cuda() for path in images]
    pixel_values = torch.cat(batches, dim=0)
    patch_counts = [batch.size(0) for batch in batches]
    image_prefix = "\n".join(f"Image-{index}: <image>" for index in range(1, len(images) + 1))
    question = f"{image_prefix}\n{prompt}"
    generation_config = {"max_new_tokens": max_new_tokens, "do_sample": False}
    return str(
        model.chat(
            tokenizer,
            pixel_values,
            question,
            generation_config,
            num_patches_list=patch_counts,
        )
    )
