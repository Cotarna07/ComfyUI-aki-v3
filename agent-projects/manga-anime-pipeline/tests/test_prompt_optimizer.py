from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from pipeline.prompting import create_prompt_optimizer
from pipeline.prompting.deepseek_provider import DeepSeekPromptOptimizer


class PromptOptimizerTests(unittest.TestCase):
    def test_disabled_optimizer_returns_input_shape(self) -> None:
        optimizer = create_prompt_optimizer({"provider": "disabled"})
        result = optimizer.optimize({"characters": [{"character_id": "c"}], "shots": [{"shot_id": "s"}]})
        self.assertEqual(result["optimizer"]["provider"], "disabled")
        self.assertEqual(result["characters"][0]["character_id"], "c")

    def test_deepseek_requires_env_key(self) -> None:
        optimizer = create_prompt_optimizer({"provider": "deepseek", "api_key_env": "MISSING_DEEPSEEK_KEY"})
        with self.assertRaisesRegex(RuntimeError, "environment variable"):
            optimizer.optimize({"characters": [], "shots": []})

    def test_deepseek_parses_json_response(self) -> None:
        optimizer = create_prompt_optimizer(
            {
                "provider": "deepseek",
                "api_key_env": "TEST_DEEPSEEK_KEY",
                "model": "deepseek-v4-pro",
            }
        )
        self.assertIsInstance(optimizer, DeepSeekPromptOptimizer)
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "characters": [{"character_id": "char_a", "design_prompt": "prompt"}],
                                "shots": [{"shot_id": "s1", "positive_prompt": "prompt"}],
                            }
                        )
                    }
                }
            ]
        }
        with patch.dict(os.environ, {"TEST_DEEPSEEK_KEY": "secret"}), patch(
            "pipeline.prompting.deepseek_provider._post_json", return_value=response
        ) as post_json:
            result = optimizer.optimize({"characters": [], "shots": []})
        self.assertEqual(result["characters"][0]["character_id"], "char_a")
        self.assertEqual(result["optimizer"]["provider"], "deepseek")
        payload = post_json.call_args.args[1]
        self.assertEqual(payload["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()

