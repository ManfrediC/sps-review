from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "10_langextract.py"


@dataclass
class FakeExtraction:
    extraction_class: str
    extraction_text: str
    alignment_status: str | None = None


def load_module():
    pipeline_dir = str(SCRIPT_PATH.parent)
    if pipeline_dir not in sys.path:
        sys.path.insert(0, pipeline_dir)
    spec = importlib.util.spec_from_file_location("langextract_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestLangExtractRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.input_dir = self.tmp_path / "text"
        self.raw_out_dir = self.tmp_path / "langextract_raw"
        self.summary_out_dir = self.tmp_path / "summary"
        self.input_dir.mkdir()
        self.raw_out_dir.mkdir()
        self.summary_out_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_to_example_data_preserves_langextract_attributes(self) -> None:
        examples = self.module.to_example_data(
            [
                {
                    "text": "A 39-year-old woman had spasms.",
                    "extractions": [
                        {
                            "extraction_class": "age_description",
                            "extraction_text": "39-year-old",
                            "attributes": {
                                "value": 39,
                                "case_id": "",
                                "field_flags": ["gold", "exact"],
                            },
                        }
                    ],
                }
            ]
        )

        self.assertEqual(len(examples), 1)
        self.assertEqual(
            examples[0].extractions[0].attributes,
            {"value": "39", "case_id": "", "field_flags": ["gold", "exact"]},
        )

    def test_process_file_skips_incorrect_reference_without_writing_outputs(self) -> None:
        module = self.module
        input_path = self.input_dir / "1841.json"
        input_path.write_text(
            json.dumps(
                {
                    "paper_id": "1841",
                    "source_filename": "1841_wrong.pdf",
                    "pages": [{"page_index": 0, "text": "Wrong attached PDF text."}],
                }
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(
            raw_out_dir=self.raw_out_dir,
            summary_out_dir=self.summary_out_dir,
            case_units_dir=self.tmp_path / "stage07_units",
            force=False,
            ignore_routing=False,
            include_individual=False,
            include_group=False,
            dry_run=False,
            model_id="gpt-4.1-mini",
            api_key=None,
            temperature=0.0,
            max_char_buffer=1200,
            batch_length=8,
            max_workers=4,
            extraction_passes=2,
        )

        outcome = module.process_file(
            path=input_path,
            args=args,
            prompt_assets={},
            heuristic_rows={},
            manual_rows={
                "1841": {
                    "final_source_category": "unclear_manual_review",
                    "final_source_subtype": "incorrect_reference",
                    "review_decision_notes": "Attached PDF resolves to another paper.",
                    "pdf_content_alignment_tag": "incorrect_reference",
                }
            },
        )

        self.assertEqual(outcome, "skipped_incorrect_reference")
        self.assertFalse((self.raw_out_dir / "1841.json").exists())
        self.assertFalse((self.summary_out_dir / "1841.json").exists())

    def test_process_file_uses_configured_stage07_units_dir(self) -> None:
        module = self.module
        input_path = self.input_dir / "9003.json"
        input_path.write_text(
            json.dumps(
                {
                    "paper_id": "9003",
                    "source_filename": "9003.pdf",
                    "pages": [{"page_index": 0, "text": "Source text is not used for split mode."}],
                }
            ),
            encoding="utf-8",
        )
        case_units_dir = self.tmp_path / "custom_stage07_units"
        case_units_dir.mkdir()
        (case_units_dir / "9003.json").write_text(
            json.dumps(
                {
                    "paper_id": "9003",
                    "source_filename": "9003.pdf",
                    "source_sha256": "abc123",
                    "source_text_json_path": "data/extraction_json/text/9003.json",
                    "publication_decision": {
                        "status": "publish_all_units",
                        "reason_code": "individual_units_match_stage06_count",
                        "reason": "Stable units found.",
                    },
                    "units": [
                        {
                            "unit_id": "9003__individual__001",
                            "unit_order": 1,
                            "unit_type": "individual",
                            "unit_label": "Patient 1",
                            "unit_text": "Patient 1 had painful spasms.",
                            "linked_shared_context_ids": [],
                            "source_span_refs": [{"page_index": 0}],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(
            raw_out_dir=self.raw_out_dir,
            summary_out_dir=self.summary_out_dir,
            case_units_dir=case_units_dir,
            force=False,
            ignore_routing=False,
            include_individual=False,
            include_group=False,
            dry_run=False,
            model_id="gpt-4.1-mini",
            api_key=None,
            temperature=0.0,
            max_char_buffer=1200,
            batch_length=8,
            max_workers=4,
            extraction_passes=2,
        )

        def fake_run_langextract(text, args, prompt_description, examples):
            self.assertEqual(text, "Patient 1 had painful spasms.")
            return SimpleNamespace(
                extractions=[FakeExtraction("individual_presentation", "painful spasms")]
            )

        original_run_langextract = module.run_langextract
        module.run_langextract = fake_run_langextract
        try:
            outcome = module.process_file(
                path=input_path,
                args=args,
                prompt_assets={
                    "individual_prompt": "individual prompt",
                    "individual_examples": ["individual example"],
                    "group_prompt": "group prompt",
                    "group_examples": ["group example"],
                },
                heuristic_rows={
                    "9003": {
                        "source_category": "case_series_or_multi_case",
                        "source_subtype": "case_series",
                        "classification_confidence": "high",
                    }
                },
                manual_rows={},
            )
        finally:
            module.run_langextract = original_run_langextract

        self.assertEqual(outcome, "processed")
        raw_payload = json.loads((self.raw_out_dir / "9003.json").read_text(encoding="utf-8"))
        self.assertEqual(
            raw_payload["source_case_series_units_path"],
            str(case_units_dir / "9003.json"),
        )

    def test_process_case_split_file_skips_stage07_manual_review_payload(self) -> None:
        module = self.module
        split_path = self.tmp_path / "stage07_units" / "9001.json"
        split_path.parent.mkdir(parents=True)
        split_path.write_text(
            json.dumps(
                {
                    "paper_id": "9001",
                    "publication_decision": {
                        "status": "manual_review_required",
                        "reason_code": "no_stable_units_found",
                        "reason": "No safe units published.",
                    },
                    "units": [],
                }
            ),
            encoding="utf-8",
        )

        outcome = module.process_case_split_file(
            paper_id="9001",
            split_path=split_path,
            out_raw=self.raw_out_dir / "9001.json",
            out_summary=self.summary_out_dir / "9001.json",
            args=argparse.Namespace(
                dry_run=False,
                model_id="gpt-4.1-mini",
                api_key=None,
                temperature=0.0,
                max_char_buffer=1200,
                batch_length=8,
                max_workers=4,
                extraction_passes=2,
            ),
            prompt_assets={},
            route={"resolved_langextract_mode": "individual_case_split"},
        )

        self.assertEqual(outcome, "skipped_stage07_manual_review")
        self.assertFalse((self.raw_out_dir / "9001.json").exists())
        self.assertFalse((self.summary_out_dir / "9001.json").exists())

    def test_process_case_split_file_processes_stage07_units(self) -> None:
        module = self.module
        split_path = self.tmp_path / "stage07_units" / "9002.json"
        split_path.parent.mkdir(parents=True)
        split_path.write_text(
            json.dumps(
                {
                    "paper_id": "9002",
                    "source_filename": "9002.pdf",
                    "source_sha256": "abc123",
                    "source_text_json_path": "data/extraction_json/text/9002.json",
                    "publication_decision": {
                        "status": "partial_publish_with_unresolved_remainder",
                        "reason_code": "individual_units_match_stage06_count",
                        "reason": "Stable units found.",
                    },
                    "shared_context_blocks": [
                        {
                            "context_id": "9002__shared__001",
                            "text": "Both units had positive antibodies.",
                            "source_span_refs": [{"page_index": 0}],
                        }
                    ],
                    "units": [
                        {
                            "unit_id": "9002__individual__001",
                            "unit_order": 1,
                            "unit_type": "individual",
                            "unit_label": "Patient 1",
                            "unit_text": "Patient 1 had axial stiffness.",
                            "linked_shared_context_ids": ["9002__shared__001"],
                            "source_span_refs": [{"page_index": 0}],
                        },
                        {
                            "unit_id": "9002__group__001",
                            "unit_order": 2,
                            "unit_type": "group",
                            "unit_label": "Antibody-positive subgroup",
                            "unit_text": "Two patients were reported as a subgroup.",
                            "linked_shared_context_ids": [],
                            "source_span_refs": [{"page_index": 1}],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        calls = []

        def fake_run_langextract(text, args, prompt_description, examples):
            calls.append(
                {
                    "text": text,
                    "prompt_description": prompt_description,
                    "examples": examples,
                }
            )
            if prompt_description == "group prompt":
                extraction = FakeExtraction("group_design", "group evidence")
            else:
                extraction = FakeExtraction("individual_presentation", "individual evidence")
            return SimpleNamespace(extractions=[extraction])

        original_run_langextract = module.run_langextract
        module.run_langextract = fake_run_langextract
        try:
            outcome = module.process_case_split_file(
                paper_id="9002",
                split_path=split_path,
                out_raw=self.raw_out_dir / "9002.json",
                out_summary=self.summary_out_dir / "9002.json",
                args=argparse.Namespace(
                    dry_run=False,
                    model_id="gpt-4.1-mini",
                    api_key=None,
                    temperature=0.0,
                    max_char_buffer=1200,
                    batch_length=8,
                    max_workers=4,
                    extraction_passes=2,
                ),
                prompt_assets={
                    "individual_prompt": "individual prompt",
                    "individual_examples": ["individual example"],
                    "group_prompt": "group prompt",
                    "group_examples": ["group example"],
                },
                route={"resolved_langextract_mode": "individual_case_split"},
            )
        finally:
            module.run_langextract = original_run_langextract

        self.assertEqual(outcome, "processed")
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            calls[0]["text"],
            "Patient 1 had axial stiffness.\n\nBoth units had positive antibodies.",
        )
        self.assertEqual(calls[0]["prompt_description"], "individual prompt")
        self.assertEqual(calls[1]["text"], "Two patients were reported as a subgroup.")
        self.assertEqual(calls[1]["prompt_description"], "group prompt")

        raw_payload = json.loads((self.raw_out_dir / "9002.json").read_text(encoding="utf-8"))
        self.assertEqual(
            raw_payload["extraction_modes"],
            {
                "individual": {"unit_count": 1, "extraction_count": 1},
                "group": {"unit_count": 1, "extraction_count": 1},
            },
        )
        self.assertEqual(raw_payload["unit_runs"][0]["prompt_mode"], "individual")
        self.assertEqual(raw_payload["unit_runs"][1]["prompt_mode"], "group")
        self.assertEqual(
            raw_payload["unit_runs"][0]["linked_shared_context_ids"],
            ["9002__shared__001"],
        )

        summary_payload = json.loads(
            (self.summary_out_dir / "9002.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            summary_payload["unit_runs"][0]["section_summaries"]["individual_presentation"],
            "individual evidence",
        )
        self.assertEqual(
            summary_payload["unit_runs"][1]["section_summaries"]["group_design"],
            "group evidence",
        )


if __name__ == "__main__":
    unittest.main()
