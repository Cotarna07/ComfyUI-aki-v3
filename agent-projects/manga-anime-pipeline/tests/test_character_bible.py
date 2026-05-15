from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.characters import build_character_bible
from pipeline.common.io import read_json


class CharacterBibleTests(unittest.TestCase):
    def test_build_character_bible_groups_visual_aliases_and_annotates_shots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            runtime_root = project_root / "runtime"
            manifest = {
                "series_id": "series",
                "chapter_id": "chapter",
                "director": {"provider": "qwen3vl", "model": "qwen3-vl"},
                "shots": [
                    {
                        "shot_id": "s1",
                        "source_windows": ["w1"],
                        "main_characters": ["{'name': '黑发角色', 'description': '深紫高马尾，金色眼睛，校服'}"],
                    },
                    {
                        "shot_id": "s2",
                        "source_windows": ["w2"],
                        "main_characters": ["里绪奈"],
                        "character_candidates": [
                            {
                                "name": "里绪奈",
                                "hair_color": "银白",
                                "hair_style": "long_hair",
                                "eye_color": "绿色",
                                "attire": "校服",
                                "role_scope": "main",
                            }
                        ],
                    },
                ],
            }

            bible, bible_path = build_character_bible(manifest, project_root, runtime_root)
            persisted = read_json(bible_path)

        self.assertEqual(bible["characters"], persisted["characters"])
        self.assertIn("character_bible_ref", manifest)
        self.assertIn("char_dark_ponytail", manifest["shots"][0]["main_character_ids"])
        self.assertIn("char_silver_longhair", manifest["shots"][1]["main_character_ids"])
        character_ids = {item["character_id"] for item in bible["characters"]}
        self.assertEqual(character_ids, {"char_dark_ponytail", "char_silver_longhair"})


if __name__ == "__main__":
    unittest.main()

