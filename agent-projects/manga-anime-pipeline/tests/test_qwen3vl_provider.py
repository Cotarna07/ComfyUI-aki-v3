from __future__ import annotations

import unittest
from unittest.mock import patch

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

    def test_ollama_mode_requires_api_model(self) -> None:
        provider = Qwen3VLDirector(
            config={"director": {"qwen3vl": {"mode": "ollama", "api_base": "http://127.0.0.1:11434", "api_model": ""}}}
        )
        with self.assertRaises(Qwen3VLBlockedError):
            provider.check_runtime()

    def test_ollama_mode_does_not_require_local_model_path(self) -> None:
        provider = Qwen3VLDirector(
            config={
                "director": {
                    "qwen3vl": {
                        "mode": "ollama",
                        "api_base": "http://127.0.0.1:11434",
                        "api_model": "huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M",
                    }
                }
            }
        )
        provider.check_runtime()

    def test_lm_studio_alias_maps_to_openai_compatible(self) -> None:
        provider = Qwen3VLDirector(
            config={
                "director": {
                    "qwen3vl": {
                        "mode": "lm_studio",
                        "api_base": "http://127.0.0.1:1234/v1",
                        "api_model": "qwen3-vl-local",
                    }
                }
            }
        )
        self.assertEqual(provider.config.mode, "openai_compatible")

    def test_ollama_dispatch_builds_shot(self) -> None:
        provider = Qwen3VLDirector(
            config={
                "director": {
                    "qwen3vl": {
                        "mode": "ollama",
                        "api_base": "http://127.0.0.1:11434",
                        "api_model": "huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M",
                    }
                }
            }
        )
        raw_json = (
            '{"workflow_route":"dialogue_light_motion","positive_prompt":"anime close shot","negative_prompt":"blurry",'
            '"anime_fit_score":0.8,"confidence":0.7}'
        )
        with patch.object(provider, "_call_ollama_once", return_value=raw_json):
            shots = provider.create_shots(
                {
                    "chapter_id": "chapter",
                    "page_id": "page",
                    "window_id": "window",
                    "source_box": [0, 0, 10, 10],
                },
                {},
            )
        self.assertEqual(shots[0]["provider"], "qwen3vl")
        self.assertEqual(shots[0]["workflow_route"], "dialogue_light_motion")

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
