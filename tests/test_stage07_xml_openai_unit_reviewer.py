from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINES_DIR = REPO_ROOT / "src" / "pipelines"
if str(PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINES_DIR))

from stage07_XML import core, openai_unit_reviewer  # noqa: E402


class TestStage07XmlOpenAIUnitReviewer(unittest.TestCase):
    def write_text_json(self, root: Path, paper_id: str, text: str) -> Path:
        path = root / f"{paper_id}.json"
        path.write_text(
            json.dumps(
                {
                    "paper_id": paper_id,
                    "source_filename": f"{paper_id}.pdf",
                    "pages": [{"page_index": 0, "text": text}],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    def prepared_source(self, tmp_path: Path) -> core.PreparedSource:
        source_path = self.write_text_json(
            tmp_path,
            "9201",
            "\n\n".join(
                [
                    "Patient 1\nA 42-year-old woman had SPS and spasms.",
                    "Patient 2\nA 51-year-old man had SPS and stiffness.",
                    "Discussion\nBoth patients met diagnostic criteria and improved after baclofen.",
                ]
            ),
        )
        return core.prepare_source(paper_id="9201", source_path=source_path)

    def test_combined_mock_primary_and_review_patch_compiles_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prepared = self.prepared_source(Path(tmp))
            units = core.build_source_units(prepared)
            primary = {
                "segments": [
                    {
                        "targets": ["p1"],
                        "role": "patient_specific",
                        "confidence": "high",
                        "evidence": "direct patient one",
                        "unit_ids": [units[0].unit_id],
                    }
                ]
            }
            review_patch = {
                "decision": "patch",
                "target_additions": [],
                "additions": [
                    {
                        "targets": ["p1", "p2"],
                        "role": "shared",
                        "confidence": "high",
                        "evidence": "Both met criteria and improved after baclofen with shared context",
                        "unit_ids": [units[-1].unit_id],
                    }
                ],
                "removals": [],
                "manual_review_reasons": [],
            }

            annotation = openai_unit_reviewer.annotate_with_deepseek_openai_reviewed_units(
                prepared_source=prepared,
                targets=[
                    core.Target("p1", "patient", "Patient 1", "test"),
                    core.Target("p2", "patient", "Patient 2", "test"),
                ],
                openai_api_key="not-used",
                primary_selection_payload=primary,
                review_patch_payload=review_patch,
            )

        self.assertEqual(annotation["annotation_mode"], "deepseek_unit_id_selection_gpt54_reviewed")
        self.assertEqual(len(annotation["segments"]), 2)
        self.assertEqual(annotation["segments"][1]["role"], "shared")
        self.assertIn("gpt54_review_decision:patch", annotation["validation_warnings"])

    def test_openai_reviewer_uses_structured_outputs_and_records_gpt54_cost(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prepared = self.prepared_source(Path(tmp))
            units = core.build_source_units(prepared)
            primary = {"segments": [], "manual_review_reasons": []}
            response = SimpleNamespace(
                id="resp-test",
                model="gpt-5.4",
                status="completed",
                incomplete_details=None,
                usage={"input_tokens": 1000, "output_tokens": 100},
                output_text=json.dumps(
                    {
                        "decision": "approve",
                        "target_additions": [],
                        "additions": [],
                        "removals": [],
                        "manual_review_reasons": [],
                    }
                ),
            )
            fake_responses = SimpleNamespace(create=mock.Mock(return_value=response))
            fake_client = SimpleNamespace(responses=fake_responses)
            telemetry_rows: list[dict[str, str]] = []

            with mock.patch.object(openai_unit_reviewer, "OpenAI", return_value=fake_client):
                patch = openai_unit_reviewer.request_openai_review_patch(
                    prepared_source=prepared,
                    targets=[core.Target("p1", "patient", "Patient 1", "test")],
                    units=units,
                    primary_selection=primary,
                    model="gpt-5.4",
                    api_key="secret-test-key",
                    reasoning_effort="xhigh",
                    telemetry_rows=telemetry_rows,
                )

        self.assertEqual(patch["decision"], "approve")
        kwargs = fake_responses.create.call_args.kwargs
        self.assertEqual(kwargs["reasoning"]["effort"], "xhigh")
        self.assertEqual(kwargs["text"]["format"]["type"], "json_schema")
        user_payload = json.loads(kwargs["input"][1]["content"])
        self.assertNotIn("g2", json.dumps(user_payload))
        self.assertNotIn("source_offsets", json.dumps(user_payload["source_units"]))
        self.assertIn("risk", user_payload["source_units"][0])
        self.assertEqual(telemetry_rows[0]["model"], "gpt-5.4")
        self.assertEqual(telemetry_rows[0]["reasoning_effort"], "xhigh")
        self.assertGreater(float(telemetry_rows[0]["estimated_cost_usd"]), 0)


if __name__ == "__main__":
    unittest.main()
