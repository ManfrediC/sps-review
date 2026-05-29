from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "09_build_langextract_examples.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage09_langextract_examples", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestStage09LangExtractExampleBootstrap(unittest.TestCase):
    def write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_manual_fields_excludes_only_provenance_and_empty_values(self) -> None:
        module = load_module()
        row = {
            "extractor": "MC",
            "Reference": "75",
            "case_ID": "",
            "age_description": "39",
            "sex": "F",
            "empty_field": "",
        }

        self.assertEqual(
            module.manual_fields_from_row(row),
            {"age_description": "39", "sex": "F"},
        )

    def test_repo_path_keeps_absolute_paths_absolute(self) -> None:
        module = load_module()
        absolute_path = Path(module.REPO_ROOT).resolve() / "qa" / "validation" / "example.json"

        self.assertEqual(module.repo_path(str(absolute_path)), absolute_path)

    def test_retryable_gemini_error_recognises_temporary_demand_failure(self) -> None:
        module = load_module()

        self.assertTrue(
            module.retryable_gemini_error(
                RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand.")
            )
        )
        self.assertFalse(module.retryable_gemini_error(RuntimeError("429 prepayment credits are depleted.")))

    def test_parse_args_defaults_to_openai_gpt_model(self) -> None:
        module = load_module()

        args = module.parse_args([])
        gemini_args = module.parse_args(["--provider", "gemini"])

        self.assertEqual(args.provider, "openai")
        self.assertEqual(args.model_id, module.DEFAULT_OPENAI_MODEL)
        self.assertEqual(gemini_args.model_id, module.DEFAULT_GEMINI_MODEL)

    def test_retryable_openai_error_excludes_billing_failures(self) -> None:
        module = load_module()

        self.assertTrue(module.retryable_openai_error(RuntimeError("rate limit exceeded")))
        self.assertFalse(module.retryable_openai_error(RuntimeError("insufficient_quota billing")))

    def test_select_pilot_records_joins_reviewed_index_to_manual_rows(self) -> None:
        module = load_module()
        temp_base = Path(module.REPO_ROOT) / "pytest_workspace_tmp"
        temp_base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_base) as tmp_dir:
            root = Path(tmp_dir)
            target_json = root / "stage07" / "75.json"
            target_json.parent.mkdir(parents=True, exist_ok=True)
            target_json.write_text(
                json.dumps({"paper_id": "75", "input_text": "A 39-year-old woman presented with spasms."}),
                encoding="utf-8",
            )
            target_rel = str(target_json.resolve().relative_to(Path(module.REPO_ROOT).resolve()))
            index_path = root / "index.csv"
            manual_path = root / "manual.csv"
            self.write_csv(
                index_path,
                ["paper_id", "manually_reviewed_MC", "stage07_target_view_json_path"],
                [
                    {
                        "paper_id": "75",
                        "manually_reviewed_MC": "TRUE",
                        "stage07_target_view_json_path": target_rel,
                    },
                    {
                        "paper_id": "92",
                        "manually_reviewed_MC": "FALSE",
                        "stage07_target_view_json_path": "missing/stage07/92.json",
                    },
                ],
            )
            self.write_csv(
                manual_path,
                ["extractor", "Reference", "case_ID", "age_description", "sex"],
                [{"extractor": "MC", "Reference": "75", "case_ID": "", "age_description": "39", "sex": "F"}],
            )

            records = module.select_pilot_records(
                limit=10,
                explicit_ids=[],
                index_path=index_path,
                manual_path=manual_path,
            )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].paper_id, "75")
        self.assertEqual(records[0].case_id, "")
        self.assertEqual(records[0].manual_fields, {"age_description": "39", "sex": "F"})

    def test_select_pilot_records_can_exclude_previous_pilot_ids(self) -> None:
        module = load_module()
        temp_base = Path(module.REPO_ROOT) / "pytest_workspace_tmp"
        temp_base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_base) as tmp_dir:
            root = Path(tmp_dir)
            stage07_dir = root / "stage07"
            stage07_dir.mkdir(parents=True, exist_ok=True)
            rows = []
            manual_rows = []
            for paper_id in ("75", "524"):
                target_json = stage07_dir / f"{paper_id}.json"
                target_json.write_text(
                    json.dumps({"paper_id": paper_id, "input_text": f"Source text for {paper_id}."}),
                    encoding="utf-8",
                )
                target_rel = str(target_json.resolve().relative_to(Path(module.REPO_ROOT).resolve()))
                rows.append(
                    {
                        "paper_id": paper_id,
                        "manually_reviewed_MC": "TRUE",
                        "stage07_target_view_json_path": target_rel,
                    }
                )
                manual_rows.append(
                    {
                        "extractor": "MC",
                        "Reference": paper_id,
                        "case_ID": "",
                        "age_description": "39",
                    }
                )
            index_path = root / "index.csv"
            manual_path = root / "manual.csv"
            self.write_csv(index_path, ["paper_id", "manually_reviewed_MC", "stage07_target_view_json_path"], rows)
            self.write_csv(manual_path, ["extractor", "Reference", "case_ID", "age_description"], manual_rows)

            records = module.select_pilot_records(
                limit=10,
                explicit_ids=[],
                excluded_ids=["75"],
                index_path=index_path,
                manual_path=manual_path,
            )

        self.assertEqual([record.paper_id for record in records], ["524"])

    def test_validate_case_output_rejects_missing_exact_quote(self) -> None:
        module = load_module()
        record = module.PilotRecord(
            paper_id="75",
            case_id="",
            target_view_json_path=Path("qa/validation/example.json"),
            source_text="A 39-year-old woman presented with spasms.",
            manual_fields={"age_description": "39"},
        )
        output = module.BootstrappedCaseExample(
            paper_id="75",
            case_id="",
            model_id="gemini-2.5-flash",
            field_groundings=[
                module.FieldGrounding(
                    field_name="age_description",
                    spreadsheet_value="39",
                    evidence_mode="exact_quote",
                    extraction_text="A 40-year-old woman",
                    supporting_snippets=[],
                    reasoning_short="Age phrase.",
                    supports_manual_value=True,
                )
            ],
        )

        rows = module.validate_case_output(record, output)

        self.assertEqual(rows[0]["validator_status"], "quote_not_found")

    def test_validate_case_output_flags_missing_field(self) -> None:
        module = load_module()
        record = module.PilotRecord(
            paper_id="75",
            case_id="",
            target_view_json_path=Path("qa/validation/example.json"),
            source_text="A 39-year-old woman presented with spasms.",
            manual_fields={"age_description": "39", "sex": "F"},
        )
        output = module.BootstrappedCaseExample(
            paper_id="75",
            case_id="",
            model_id="gemini-2.5-flash",
            field_groundings=[
                module.FieldGrounding(
                    field_name="age_description",
                    spreadsheet_value="39",
                    evidence_mode="exact_quote",
                    extraction_text="39-year-old",
                    supporting_snippets=[],
                    reasoning_short="Age phrase.",
                    supports_manual_value=True,
                )
            ],
        )

        rows = module.validate_case_output(record, output)

        self.assertIn("missing_from_model_output", {row["validator_status"] for row in rows})

    def test_promote_from_review_groups_accepted_rows_with_blank_case_id(self) -> None:
        module = load_module()
        temp_base = Path(module.REPO_ROOT) / "pytest_workspace_tmp"
        temp_base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_base) as tmp_dir:
            root = Path(tmp_dir)
            target_json = root / "stage07" / "75.json"
            target_json.parent.mkdir(parents=True, exist_ok=True)
            target_json.write_text(
                json.dumps({"input_text": "A 39-year-old woman presented with spasms."}),
                encoding="utf-8",
            )
            target_rel = str(target_json.resolve().relative_to(Path(module.REPO_ROOT).resolve()))
            review_rows = [
                {
                    "paper_id": "75",
                    "case_id": "",
                    "field_name": "age_description",
                    "spreadsheet_value": "39",
                    "model_spreadsheet_value": "39",
                    "evidence_mode": "exact_quote",
                    "extraction_text": "39-year-old",
                    "char_start": "2",
                    "char_end": "13",
                    "supporting_snippets_json": "[]",
                    "supports_manual_value": "TRUE",
                    "reasoning_short": "Age phrase.",
                    "validator_status": "passed",
                    "review_status": "accepted",
                    "review_notes": "",
                    "target_view_json_path": target_rel,
                },
                {
                    "paper_id": "75",
                    "case_id": "",
                    "field_name": "sex",
                    "spreadsheet_value": "F",
                    "model_spreadsheet_value": "F",
                    "evidence_mode": "exact_quote",
                    "extraction_text": "woman",
                    "char_start": "17",
                    "char_end": "22",
                    "supporting_snippets_json": "[]",
                    "supports_manual_value": "TRUE",
                    "reasoning_short": "Sex phrase.",
                    "validator_status": "passed",
                    "review_status": "rejected",
                    "review_notes": "",
                    "target_view_json_path": target_rel,
                },
            ]

            examples = module.build_langextract_examples_from_review(review_rows)

        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["paper_id"], "75")
        self.assertEqual(examples[0]["case_id"], "")
        self.assertEqual(len(examples[0]["extractions"]), 1)
        self.assertEqual(examples[0]["extractions"][0]["extraction_class"], "age_description")

    def test_build_from_span_plan_preserves_all_gold_values_with_string_attributes(self) -> None:
        module = load_module()
        temp_base = Path(module.REPO_ROOT) / "pytest_workspace_tmp"
        temp_base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_base) as tmp_dir:
            root = Path(tmp_dir)
            target_json = root / "stage07" / "75.json"
            target_json.parent.mkdir(parents=True, exist_ok=True)
            source_text = "A 39-year-old\nwoman presented with spasms."
            target_json.write_text(json.dumps({"input_text": source_text}), encoding="utf-8")
            target_rel = str(target_json.resolve().relative_to(Path(module.REPO_ROOT).resolve()))
            span_plan_rows = [
                {
                    "paper_id": "75",
                    "case_id": "",
                    "field_name": "age_description",
                    "spreadsheet_value": "39",
                    "model_spreadsheet_value": "39",
                    "original_evidence_mode": "exact_quote",
                    "original_validator_status": "passed",
                    "coverage_quality": "direct_exact_span_ready",
                    "langextract_recommendation": "candidate_for_promotion_after_spot_check",
                    "support_spans_json": json.dumps(
                        [
                            {
                                "span_text": "39-year-old\nwoman",
                                "char_start": 2,
                                "char_end": 19,
                                "span_role": "support",
                                "selection_source": "test",
                                "match_mode": "exact",
                            }
                        ]
                    ),
                    "target_view_json_path": target_rel,
                }
            ]

            validation = module.validate_span_plan_rows(span_plan_rows)
            examples = module.build_langextract_examples_from_span_plan(span_plan_rows)

        self.assertEqual(validation["coverage_error_count"], 0)
        self.assertEqual(len(examples), 1)
        self.assertEqual(len(examples[0]["extractions"]), 1)
        extraction = examples[0]["extractions"][0]
        self.assertEqual(extraction["extraction_class"], "age_description")
        self.assertNotIn("\n", examples[0]["text"])
        self.assertEqual(extraction["extraction_text"], "39-year-old woman")
        self.assertEqual(extraction["attributes"]["value"], "39")
        self.assertEqual(extraction["attributes"]["char_start"], "2")
        self.assertIsInstance(extraction["attributes"]["support_span_count"], str)

    def test_build_from_span_plan_splits_overlapping_spans_for_langextract_alignment(self) -> None:
        module = load_module()
        temp_base = Path(module.REPO_ROOT) / "pytest_workspace_tmp"
        temp_base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_base) as tmp_dir:
            root = Path(tmp_dir)
            target_json = root / "stage07" / "75.json"
            target_json.parent.mkdir(parents=True, exist_ok=True)
            source_text = "A 39-year-old woman presented with spasms."
            target_json.write_text(json.dumps({"input_text": source_text}), encoding="utf-8")
            target_rel = str(target_json.resolve().relative_to(Path(module.REPO_ROOT).resolve()))
            shared_span = json.dumps(
                [
                    {
                        "span_text": "39-year-old",
                        "char_start": 2,
                        "char_end": 13,
                        "span_role": "support",
                        "selection_source": "test",
                        "match_mode": "exact",
                    }
                ]
            )
            base_row = {
                "paper_id": "75",
                "case_id": "",
                "model_spreadsheet_value": "",
                "original_evidence_mode": "exact_quote",
                "original_validator_status": "passed",
                "coverage_quality": "direct_exact_span_ready",
                "langextract_recommendation": "candidate_for_promotion_after_spot_check",
                "support_spans_json": shared_span,
                "target_view_json_path": target_rel,
            }
            span_plan_rows = [
                {**base_row, "field_name": "age_description", "spreadsheet_value": "39"},
                {**base_row, "field_name": "age_onset", "spreadsheet_value": "39"},
            ]

            examples = module.build_langextract_examples_from_span_plan(span_plan_rows)
            try:
                compatibility = module.validate_langextract_example_payload(examples)
            except SystemExit as exc:
                self.skipTest(str(exc))

        self.assertEqual(len(examples), 2)
        self.assertEqual(sum(len(example["extractions"]) for example in examples), 2)
        self.assertEqual(compatibility["alignment_issue_count"], 0)
        self.assertEqual(compatibility["attribute_error_count"], 0)

    def test_paid_gate_stops_before_gemini_import(self) -> None:
        module = load_module()
        record = module.PilotRecord(
            paper_id="75",
            case_id="",
            target_view_json_path=Path("qa/validation/example.json"),
            source_text="A 39-year-old woman presented with spasms.",
            manual_fields={"age_description": "39"},
        )

        with self.assertRaises(SystemExit):
            module.run_gemini_bootstrap(
                record,
                model_id="gemini-2.5-flash",
                allow_paid_run=False,
                env_file=Path("env/gemini.env"),
            )

    def test_paid_run_checkpoints_completed_records_before_later_failure(self) -> None:
        module = load_module()
        temp_base = Path(module.REPO_ROOT) / "pytest_workspace_tmp"
        temp_base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_base) as tmp_dir:
            root = Path(tmp_dir)
            target_json = root / "stage07" / "75.json"
            target_json.parent.mkdir(parents=True, exist_ok=True)
            target_json.write_text(
                json.dumps({"input_text": "A 39-year-old woman presented with spasms."}),
                encoding="utf-8",
            )
            records = [
                module.PilotRecord(
                    paper_id="75",
                    case_id="",
                    target_view_json_path=target_json,
                    source_text="A 39-year-old woman presented with spasms.",
                    manual_fields={"age_description": "39"},
                ),
                module.PilotRecord(
                    paper_id="92",
                    case_id="",
                    target_view_json_path=target_json,
                    source_text="A 39-year-old woman presented with spasms.",
                    manual_fields={"age_description": "39"},
                ),
            ]
            args = argparse.Namespace(
                output_dir=root / "out",
                provider="openai",
                model_id="gpt-5.5",
                gemini_env_file=Path("env/gemini.env"),
                openai_env_file=Path("env/openai_api_key.env"),
                openai_reasoning_effort="low",
                openai_max_output_tokens=8000,
                dry_run=False,
                allow_paid_run=True,
                api_retries=0,
                api_retry_wait_seconds=0.0,
            )
            calls = 0
            original = module.run_gemini_bootstrap_with_retries

            def fake_run(record, *, args):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("simulated later failure")
                return module.BootstrappedCaseExample(
                    paper_id=record.paper_id,
                    case_id=record.case_id,
                    model_id="gpt-5.5",
                    field_groundings=[
                        module.FieldGrounding(
                            field_name="age_description",
                            spreadsheet_value="39",
                            evidence_mode="exact_quote",
                            extraction_text="39-year-old",
                            supporting_snippets=[],
                            reasoning_short="Age phrase.",
                            supports_manual_value=True,
                        )
                    ],
                )

            module.run_gemini_bootstrap_with_retries = fake_run
            try:
                with self.assertRaises(RuntimeError):
                    module.write_paid_run_outputs(args, records)
            finally:
                module.run_gemini_bootstrap_with_retries = original

            candidate_lines = (args.output_dir / "field_candidates.jsonl").read_text(encoding="utf-8").splitlines()
            review_rows = module.read_csv_rows(args.output_dir / "field_review.csv")
            manifest = json.loads((args.output_dir / "run_manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(len(candidate_lines), 1)
        self.assertEqual(len(review_rows), 1)
        self.assertEqual(manifest["run_status"], "failed")
        self.assertEqual(manifest["completed_record_count"], 1)
        self.assertEqual(manifest["failed_paper_id"], "92")


if __name__ == "__main__":
    unittest.main()
