from lmstudio_comfyui_benchmark.config import QualityConfig
from lmstudio_comfyui_benchmark.prompt_quality import extract_prompt_pair, score_prompt_pair


def test_extract_prompt_pair_from_json() -> None:
    pair = extract_prompt_pair(
        '{"positive_prompt":"cinematic lighting, creator, studio, camera, composition, realistic, cover image",'
        '"negative_prompt":"watermark, text, low quality, noise, bad anatomy",'
        '"notes":"ok"}'
    )

    assert pair.parse_ok is True
    assert "cinematic" in pair.positive_prompt
    assert "watermark" in pair.negative_prompt


def test_score_prompt_pair() -> None:
    pair = extract_prompt_pair(
        '{"positive_prompt":"cinematic lighting, independent creator, night studio, photo realistic, cover image, '
        'natural shadows, detailed camera composition, editorial mood, high quality visual texture",'
        '"negative_prompt":"watermark, text, low quality, noise, blurry, bad anatomy, malformed hands",'
        '"notes":"ok"}'
    )
    score = score_prompt_pair(
        pair,
        QualityConfig(
            min_positive_chars=80,
            min_negative_chars=40,
            required_positive_terms=["cinematic", "lighting"],
            required_negative_terms=["watermark", "text"],
            penalize_non_english_prompt=True,
        ),
    )

    assert score.score >= 80
