from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.validation import stage07_single_case_advisory as advisory


class TestStage07SingleCaseAdvisory(unittest.TestCase):
    def test_read_env_key_accepts_assignment_or_plain_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deepseek_api_key.env"
            path.write_text("DEEPSEEK_API_KEY='ds-test'\n", encoding="utf-8")
            self.assertEqual(advisory.read_env_key(path, "DEEPSEEK_API_KEY"), "ds-test")

            path.write_text("sk-plain\n", encoding="utf-8")
            self.assertEqual(advisory.read_env_key(path, "OPENAI_API_KEY"), "sk-plain")

    def test_extract_json_object_strips_markdown_fence(self) -> None:
        self.assertEqual(
            advisory.extract_json_object('```json\n{"decision": "accept_ready"}\n```'),
            {"decision": "accept_ready"},
        )

    def test_build_user_prompt_contains_return_schema_and_package(self) -> None:
        prompt = advisory.build_user_prompt(
            {
                "paper_id": "1",
                "target_view": {"input_text": "A 40-year-old woman had SPS."},
            }
        )
        payload = json.loads(prompt)
        self.assertEqual(payload["package"]["paper_id"], "1")
        self.assertIn("return_schema", payload)


if __name__ == "__main__":
    unittest.main()
