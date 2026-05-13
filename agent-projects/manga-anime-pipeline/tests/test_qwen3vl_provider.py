from __future__ import annotations

import unittest

from pipeline.director.provider_factory import create_director_provider
from pipeline.director.qwen3vl_provider import (
    Qwen3VLBlockedError,
    Qwen3VLDirector,
    _normalize_shot_payload,
    _parse_strict_json,
)


class Qwen3VLProviderTests(unittest.TestCase):
    def test_factory_aliases(self) -> None:
        for alias in ("qwen3vl", "qwen3-vl", "qwen_vl", "qwen-vl"):
            provider = create_director_provider(alias)
            self.assertIsInstance(provider, Qwen3VLDirector)

    def test_dry_run_blocked_mode_raises_blocked(self) -> None:
        provider = Qwen3VLDirector(config={"director": {"qwen3vl": {"mode": "dry_run_blocked", "model_path": ""}}})
        with self.assertRaises(Qwen3VLBlockedError):
            provider.check_runtime()

    def test_missing_model_path_raises_blocked(self) -> None:
        provider = Qwen3VLDirector(config={"director": {"qwen3vl": {"mode": "local", "model_path": ""}}})
        with self.assertRaises(Qwen3VLBlockedError):
            provider.check_runtime()

    def test_invalid_workflow_route_raises(self) -> None:
        with self.assertRaises(ValueError):
            _normalize_shot_payload(
                {
                    "workflow_route": "not_a_route",
                    "positive_prompt": "x",
                    "negative_prompt": "y",
                    "anime_fit_score": 0.5,
                    "confidence": 0.5,
                },
                packet={"chapter_id": "ch", "page_id": "p", "window_id": "w", "source_box": [0, 0, 10, 10]},
                context={},
                shot_index=0,
            )

    def test_empty_prompt_raises(self) -> None:
        with self.assertRaises(ValueError):
            _normalize_shot_payload(
                {
                    "workflow_route": "dialogue_light_motion",
                    "positive_prompt": "",
                    "negative_prompt": "y",
                    "anime_fit_score": 0.5,
                    "confidence": 0.5,
                },
                packet={"chapter_id": "ch", "page_id": "p", "window_id": "w", "source_box": [0, 0, 10, 10]},
                context={},
                shot_index=0,
            )

    def test_strict_json_parses_braces(self) -> None:
        text = "garbage {\"a\": 1, \"b\": [1,2]} trailing"
        parsed = _parse_strict_json(text, True)
        self.assertEqual(parsed["a"], 1)

    def test_strict_json_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            _parse_strict_json("not json at all", True)


if __name__ == "__main__":
    unittest.main()
