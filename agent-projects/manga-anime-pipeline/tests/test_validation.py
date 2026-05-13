from __future__ import annotations

import unittest

from pipeline.common.schemas import SHOT_SCHEMA
from pipeline.common.validation import SchemaValidationError, validate_json_schema


class ValidationTests(unittest.TestCase):
    def test_invalid_workflow_route_is_rejected(self) -> None:
        shot = {
            "shot_id": "s001",
            "source_pages": ["p001"],
            "source_windows": ["w001"],
            "source_ranges": [{"page_id": "p001", "box": [0, 0, 100, 100]}],
            "merge_with_prev": False,
            "merge_with_next": False,
            "story_role": "dialogue_progression",
            "shot_type": "dialogue",
            "anime_fit_score": 0.7,
            "main_characters": ["char_a"],
            "support_characters": [],
            "emotion": "neutral",
            "action_level": "low",
            "dialogue_summary": "mock",
            "continuity_notes": [],
            "crop_recommendation": {"type": "medium", "box": [0, 0, 100, 100]},
            "positive_prompt": "mock prompt",
            "negative_prompt": "mock negative",
            "style_anchor": "style",
            "workflow_route": "not_allowed",
            "confidence": 0.7,
        }
        with self.assertRaises(SchemaValidationError):
            validate_json_schema(shot, SHOT_SCHEMA, "shot")


if __name__ == "__main__":
    unittest.main()
