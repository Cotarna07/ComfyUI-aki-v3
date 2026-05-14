from __future__ import annotations

import unittest
from pathlib import Path

from pipeline.common.io import read_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = PROJECT_ROOT / "configs" / "comfy_workflows"
ROUTES = (
    "establish_scene",
    "dialogue_heavy_expression",
    "action_performance",
    "transition_atmosphere",
    "repair_only",
)


class ComfyWorkflowMappingTests(unittest.TestCase):
    def test_required_route_workflows_and_mappings_exist(self) -> None:
        for route in ROUTES:
            with self.subTest(route=route):
                self.assertTrue((WORKFLOW_DIR / f"{route}.json").exists())
                self.assertTrue((WORKFLOW_DIR / f"{route}.mapping.json").exists())

    def test_mappings_point_to_real_node_inputs(self) -> None:
        for route in ROUTES:
            with self.subTest(route=route):
                workflow = read_json(WORKFLOW_DIR / f"{route}.json")
                mapping = read_json(WORKFLOW_DIR / f"{route}.mapping.json")
                self.assertEqual(mapping["route"], route)
                self.assertIn("fields", mapping)
                for field_name, targets in mapping["fields"].items():
                    target_list = targets if isinstance(targets, list) else [targets]
                    self.assertTrue(target_list, field_name)
                    for target in target_list:
                        node_id = str(target["node_id"])
                        input_name = str(target["input"])
                        self.assertIn(node_id, workflow, field_name)
                        self.assertIn(input_name, workflow[node_id].get("inputs", {}), field_name)

    def test_route_specific_required_fields(self) -> None:
        expected = {
            "establish_scene": {"positive_prompt", "negative_prompt", "seed", "output_prefix", "width", "height", "length", "fps"},
            "dialogue_heavy_expression": {"positive_prompt", "negative_prompt", "input_image", "seed", "output_prefix", "width", "height", "length", "fps"},
            "action_performance": {"positive_prompt", "negative_prompt", "input_image", "seed", "output_prefix", "width", "height", "length", "fps"},
            "transition_atmosphere": {"positive_prompt", "negative_prompt", "seed", "output_prefix", "width", "height", "length", "fps"},
            "repair_only": {"positive_prompt", "negative_prompt", "input_image", "mask_image", "seed", "output_prefix"},
        }
        for route, required_fields in expected.items():
            with self.subTest(route=route):
                mapping = read_json(WORKFLOW_DIR / f"{route}.mapping.json")
                self.assertTrue(required_fields.issubset(set(mapping["fields"])))


if __name__ == "__main__":
    unittest.main()
