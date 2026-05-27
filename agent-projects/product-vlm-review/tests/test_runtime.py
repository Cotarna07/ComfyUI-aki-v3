import unittest

from product_vlm_review.runtime import parse_json_object


class ParseJsonObjectTests(unittest.TestCase):
    def test_parses_plain_json(self) -> None:
        parsed, error = parse_json_object('{"source_facts": []}')
        self.assertEqual({"source_facts": []}, parsed)
        self.assertIsNone(error)

    def test_parses_fenced_json(self) -> None:
        parsed, error = parse_json_object('answer\n```json\n{"warnings": []}\n```')
        self.assertEqual({"warnings": []}, parsed)
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
