from __future__ import annotations

import json
import tempfile
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINES_DIR = REPO_ROOT / "src" / "pipelines"
if str(PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINES_DIR))

from stage07_XML import core, deepseek_client  # noqa: E402


class TestStage07XmlDeepSeekClient(unittest.TestCase):
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

    def test_deepseek_unit_selection_compiles_and_records_secret_free_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = self.write_text_json(
                tmp_path,
                "9101",
                "Patient 1\nA 42-year-old woman had axial stiffness.",
            )
            prepared = core.prepare_source(paper_id="9101", source_path=source_path)
            units = core.build_source_units(prepared)
            selection = {
                "segments": [
                    {
                        "targets": ["p1"],
                        "role": "patient_specific",
                        "confidence": "high",
                        "evidence": "Patient 1 unit",
                        "unit_ids": [units[0].unit_id],
                    }
                ]
            }
            response = SimpleNamespace(
                id="chatcmpl-test",
                model="deepseek-v4-pro",
                usage={"prompt_tokens": 20, "completion_tokens": 5},
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(selection)))],
            )
            fake_completions = SimpleNamespace(create=mock.Mock(return_value=response))
            fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))
            telemetry_rows: list[dict[str, str]] = []

            with mock.patch.object(deepseek_client, "OpenAI", return_value=fake_client) as openai_ctor:
                annotation = deepseek_client.annotate_with_deepseek_units(
                    prepared_source=prepared,
                    targets=[core.Target("p1", "patient", "Patient 1", "test")],
                    model="deepseek-v4-pro",
                    api_key="secret-test-key",
                    trace_dir=tmp_path / "trace",
                    telemetry_rows=telemetry_rows,
                )

            self.assertEqual(openai_ctor.call_args.kwargs["timeout"], 3600.0)
            request_payload = json.loads((tmp_path / "trace" / "9101.unit_selection.request.json").read_text(encoding="utf-8"))
            self.assertNotIn("block_spans", request_payload["user_payload"]["source_units"][0])
            self.assertNotIn("source_offsets", request_payload["user_payload"]["source_units"][0])
            self.assertIn("hint", request_payload["user_payload"]["source_units"][0])
            self.assertNotIn("g2", json.dumps(request_payload["user_payload"]["required_output_shape"]))
            self.assertEqual(annotation["annotation_mode"], "deepseek_unit_id_selection")
            self.assertEqual(len(annotation["segments"]), 1)
            self.assertEqual(telemetry_rows[0]["provider"], "deepseek")
            self.assertEqual(telemetry_rows[0]["architecture_variant"], "unit_ids")
            self.assertGreater(float(telemetry_rows[0]["estimated_cost_usd"]), 0)
            trace_text = "\n".join(path.read_text(encoding="utf-8") for path in (tmp_path / "trace").glob("*"))
            self.assertNotIn("secret-test-key", trace_text)
            self.assertNotIn("reasoning_content", trace_text)

    def test_deepseek_empty_response_is_review_gated_and_telemetred(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = self.write_text_json(
                tmp_path,
                "9102",
                "Patient 1\nA 42-year-old woman had axial stiffness.",
            )
            prepared = core.prepare_source(paper_id="9102", source_path=source_path)
            response = SimpleNamespace(
                id="chatcmpl-empty",
                model="deepseek-v4-pro",
                usage={"prompt_tokens": 20, "completion_tokens": 6000},
                choices=[SimpleNamespace(message=SimpleNamespace(content=""))],
            )
            fake_completions = SimpleNamespace(create=mock.Mock(return_value=response))
            fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))
            telemetry_rows: list[dict[str, str]] = []

            with mock.patch.object(deepseek_client, "OpenAI", return_value=fake_client):
                annotation = deepseek_client.annotate_with_deepseek_units(
                    prepared_source=prepared,
                    targets=[core.Target("p1", "patient", "Patient 1", "test")],
                    model="deepseek-v4-pro",
                    api_key="secret-test-key",
                    trace_dir=tmp_path / "trace",
                    telemetry_rows=telemetry_rows,
                )

            self.assertEqual(annotation["segments"], [])
            self.assertEqual(annotation["manual_review_reasons"], ["deepseek_unit_selection_empty_response"])
            self.assertEqual(telemetry_rows[0]["response_status"], "invalid_json:JSONDecodeError")
            self.assertEqual(telemetry_rows[0]["validation_status"], "manual_review_required")


if __name__ == "__main__":
    unittest.main()
