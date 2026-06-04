from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "validation"
    / "ollama_single_case_dry_run.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("ollama_single_case_dry_run", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def shared_string_index(strings: list[str], value: str) -> int:
    if value not in strings:
        strings.append(value)
    return strings.index(value)


def write_minimal_xlsx(path: Path) -> None:
    strings: list[str] = []
    rows = {
        1: {
            "B": "1.section: Identifier and case vignette",
            "F": "section: basic demographic data",
            "U": "3. section: disease onset, signs and symptoms",
            "AR": "4. section: established disease, signs and symptoms",
            "BV": "6. section: treatment",
        },
        2: {
            "A": "Initials of extractor",
            "B": "ID",
            "G": "Age at onset",
            "H": "Follow Up (years)",
            "I": "Time to diagnosis (years)",
            "L": "First manifestation (other)",
            "AI": "Time from onset to fully established disease (months)",
            "AJ": "Duration of follow up (months)",
            "BT": "Immunotherapy in detail (please describe dose, how many cycles, intervals)",
        },
        3: {
            "A": "extractor",
            "B": "Reference",
            "G": "age_onset",
            "H": "FU_duration",
            "I": "time_to_diagnosis",
            "L": "first_manifestation_mother",
            "AI": "onset_to_established",
            "AJ": "FU_duration",
            "BT": "immuntherapy_detail",
        },
    }
    sheet_rows = []
    for row_number, cells in rows.items():
        cell_xml = []
        for col, value in cells.items():
            idx = shared_string_index(strings, value)
            cell_xml.append(f'<c r="{col}{row_number}" t="s"><v>{idx}</v></c>')
        sheet_rows.append(f'<row r="{row_number}">{"".join(cell_xml)}</row>')

    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        + "".join(f"<si><t>{value}</t></si>" for value in strings)
        + "</sst>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Case Reports" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        "</worksheet>"
    )
    with zipfile.ZipFile(path, "w") as workbook_zip:
        workbook_zip.writestr("xl/sharedStrings.xml", shared_xml)
        workbook_zip.writestr("xl/workbook.xml", workbook_xml)
        workbook_zip.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        workbook_zip.writestr("xl/worksheets/sheet1.xml", sheet_xml)


class TestOllamaSingleCaseDryRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_contract_collapses_and_corrects_legacy_fields(self) -> None:
        workbook_path = self.tmp_path / "instructions.xlsx"
        write_minimal_xlsx(workbook_path)

        fields = self.module.build_contract_from_workbook(workbook_path)
        names = [field.name for field in fields]

        self.assertEqual(1, names.count("Followup_Duration_Months"))
        self.assertNotIn("FU_duration", names)
        self.assertIn("first_manifestation_other", names)
        self.assertNotIn("first_manifestation_mother", names)
        self.assertIn("immunotherapy_detail", names)
        self.assertNotIn("immuntherapy_detail", names)
        followup = next(field for field in fields if field.name == "Followup_Duration_Months")
        self.assertEqual(["H", "AJ"], followup.source_columns)
        self.assertIn("convert to months", followup.instruction)

    def test_manifest_selects_first_ten_manual_high_confidence_cases(self) -> None:
        text_dir = self.tmp_path / "data" / "extraction_json" / "text"
        text_dir.mkdir(parents=True)
        registry_path = self.tmp_path / "registry.csv"
        manual_path = self.tmp_path / "manual.csv"

        for paper_id in ["1", "2", "3"]:
            (text_dir / f"{paper_id}.json").write_text(
                json.dumps({"paper_id": paper_id, "pages": [{"page_index": 0, "text": "paper text"}]}),
                encoding="utf-8",
            )

        with manual_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Reference"])
            writer.writerow(["2"])
            writer.writerow(["1"])
            writer.writerow(["3"])

        with registry_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "paper_id",
                    "title",
                    "authors",
                    "source_category",
                    "source_subtype",
                    "preferred_text_json_path",
                    "preferred_text_source",
                    "count_eligible",
                    "likely_sps_case_count",
                    "count_confidence",
                    "count_manual_review_required",
                ],
            )
            writer.writeheader()
            for paper_id, confidence in [("1", "high"), ("2", "high"), ("3", "low")]:
                writer.writerow(
                    {
                        "paper_id": paper_id,
                        "title": f"title {paper_id}",
                        "authors": "authors",
                        "source_category": "single_case_report",
                        "source_subtype": "case_report",
                        "preferred_text_json_path": str(text_dir / f"{paper_id}.json"),
                        "preferred_text_source": "text",
                        "count_eligible": "true",
                        "likely_sps_case_count": "1",
                        "count_confidence": confidence,
                        "count_manual_review_required": "false",
                    }
                )

        records, skipped = self.module.build_manifest_records(
            manual_csv_path=manual_path,
            registry_path=registry_path,
            limit=2,
        )

        self.assertEqual(["2", "1"], [record["paper_id"] for record in records])
        self.assertEqual([], skipped[:1])

    def test_prompt_omits_fixed_metadata_from_model_fields(self) -> None:
        fields = [
            self.module.FieldSpec("extractor", "", "Initials", ["A"], ["Initials"], []),
            self.module.FieldSpec("Reference", "", "ID", ["B"], ["ID"], []),
            self.module.FieldSpec(
                "Followup_Duration_Months",
                "section",
                self.module.FOLLOWUP_INSTRUCTION,
                ["H", "AJ"],
                ["Follow Up (years)", "Duration of follow up (months)"],
                [],
            ),
            self.module.FieldSpec(
                "ethnicity",
                "section",
                "Ethnicity (select one)\n- white = White/Caucasian\n- other = other",
                ["F"],
                ["Ethnicity"],
                ["white", "other"],
            ),
        ]
        prompt = self.module.build_prompt(
            fields,
            {
                "paper_id": "12013",
                "title": "Example",
                "authors": "A",
                "source_category": "single_case_report",
                "source_subtype": "case_report",
                "likely_sps_case_count": "1",
                "count_confidence": "high",
            },
            "Follow-up was 2 years.",
        )

        self.assertIn("metadata fields outside the model", prompt)
        self.assertIn("Followup_Duration_Months", prompt)
        self.assertIn("convert years to months", prompt)
        self.assertIn("Use NA", prompt)
        self.assertIn("never use N/A", prompt)
        self.assertIn("verbatim_quote", prompt)
        self.assertIn("deterministic_derivation", prompt)
        self.assertIn("patient initials", prompt)
        self.assertIn("Hard quote constraint", prompt)
        self.assertIn("source order", prompt)
        self.assertIn("Do not stitch onset-history evidence into established-disease fields", prompt)
        self.assertNotIn("\n- white = White/Caucasian", prompt)
        self.assertNotIn("- extractor\n", prompt)
        self.assertNotIn("- Reference\n", prompt)

    def test_manual_values_expand_available_options(self) -> None:
        manual_path = self.tmp_path / "manual.csv"
        manual_path.write_text(
            "Reference,first_manifestation_mother\n1,sensory;pain;fatigue\n",
            encoding="utf-8",
        )
        fields = [
            self.module.FieldSpec(
                "first_manifestation_other",
                "section",
                "First manifestation (other)",
                ["L"],
                ["First manifestation (other)"],
                [],
            )
        ]

        augmented = self.module.augment_allowed_values_from_manual(fields, manual_path)

        self.assertEqual(["sensory", "pain", "fatigue"], augmented[0].allowed_values)

    def test_reviewed_qwen_symptoms_expand_available_symptom_options(self) -> None:
        manual_path = self.tmp_path / "manual.csv"
        manual_path.write_text("Reference\n1\n", encoding="utf-8")
        fields = [
            self.module.FieldSpec(
                "other_symptoms_onset",
                "section",
                "Other symptoms",
                ["Z"],
                ["Other symptoms"],
                ["sensory"],
            ),
            self.module.FieldSpec(
                "overview_established",
                "section",
                "Overview symptoms",
                ["AK"],
                ["Overview symptoms"],
                ["stiffness"],
            )
        ]

        augmented = self.module.augment_allowed_values_from_manual(fields, manual_path)

        self.assertIn("fatigue", augmented[0].allowed_values)
        self.assertIn("tingling", augmented[0].allowed_values)
        self.assertIn("fatigue", augmented[1].allowed_values)
        self.assertIn("tingling", augmented[1].allowed_values)

    def test_load_ollama_api_key_reads_only_named_value(self) -> None:
        env_path = self.tmp_path / "ollama.env"
        env_path.write_text("OTHER=value\nOLLAMA_API_KEY=abc123TOKEN\n", encoding="utf-8")

        self.assertEqual("abc123TOKEN", self.module.load_ollama_api_key(env_path))

    def test_validate_model_output_reports_missing_and_extra_fields(self) -> None:
        parsed = {
            "paper_id": "1",
            "extractions": [
                {
                    "field_name": "age_description",
                    "value": "43",
                    "verbatim_quote": "A 43-year-old woman",
                    "evidence_type": "verbatim_quote",
                    "derivation": "NA",
                    "confidence": "high",
                },
                {
                    "field_name": "unexpected",
                    "value": "x",
                    "verbatim_quote": "x",
                    "evidence_type": "verbatim_quote",
                    "derivation": "NA",
                    "confidence": "low",
                },
            ],
        }

        validation = self.module.validate_model_output(
            parsed,
            paper_id="1",
            expected_fields=["age_description", "sex"],
            parse_error=None,
        )

        self.assertEqual("failed", validation["status"])
        self.assertEqual(["sex"], validation["missing_fields"])
        self.assertEqual(["unexpected"], validation["extra_fields"])

    def test_validate_model_output_rejects_na_variant_and_non_numeric_age(self) -> None:
        parsed = {
            "paper_id": "1",
            "extractions": [
                {
                    "field_name": "age_description",
                    "value": "43-year-old",
                    "verbatim_quote": "A 43-year-old woman",
                    "evidence_type": "verbatim_quote",
                    "derivation": "NA",
                    "confidence": "high",
                },
                {
                    "field_name": "sex",
                    "value": "N/A",
                    "verbatim_quote": "N/A",
                    "evidence_type": "not_reported",
                    "derivation": "NA",
                    "confidence": "high",
                },
            ],
        }

        validation = self.module.validate_model_output(
            parsed,
            paper_id="1",
            expected_fields=["age_description", "sex"],
            parse_error=None,
            source_text="A 43-year-old woman was reported.",
        )

        self.assertEqual("failed", validation["status"])
        self.assertIn("invalid_values", validation["errors"])
        self.assertIn("age_description", validation["invalid_value_fields"])
        self.assertIn("sex", validation["invalid_value_fields"])

    def test_validate_model_output_accepts_whitelisted_derivation(self) -> None:
        parsed = {
            "paper_id": "1",
            "extractions": [
                {
                    "field_name": "age_onset",
                    "value": "40",
                    "verbatim_quote": "A 43-year-old woman with a 3-year history",
                    "evidence_type": "deterministic_derivation",
                    "derivation": "43 - 3 = 40",
                    "confidence": "high",
                }
            ],
        }

        validation = self.module.validate_model_output(
            parsed,
            paper_id="1",
            expected_fields=["age_onset"],
            parse_error=None,
            source_text="A 43-year-old woman with a 3-year history was described.",
        )

        self.assertEqual("passed", validation["status"])

    def test_case_id_accepts_article_initials_when_present_in_source(self) -> None:
        parsed = {
            "paper_id": "1",
            "extractions": [
                {
                    "field_name": "case_ID",
                    "value": "AE",
                    "verbatim_quote": "AE is a 43-year-old woman",
                    "evidence_type": "verbatim_quote",
                    "derivation": "NA",
                    "confidence": "high",
                }
            ],
        }

        validation = self.module.validate_model_output(
            parsed,
            paper_id="1",
            expected_fields=["case_ID"],
            parse_error=None,
            source_text="Case presentation\nAE is a 43-year-old woman.",
        )

        self.assertEqual("passed", validation["status"])

    def test_source_span_is_saved_for_ellipsis_quotes(self) -> None:
        parsed = {
            "paper_id": "1",
            "extractions": [
                {
                    "field_name": "time_to_diagnosis",
                    "value": "1",
                    "verbatim_quote": "beginning of 2016... At the beginning of 2017",
                    "evidence_type": "deterministic_derivation",
                    "derivation": "2017 - 2016 = 1",
                    "confidence": "medium",
                }
            ],
        }
        source_text = "Symptoms began at the beginning of 2016. At the beginning of 2017, SPS was confirmed."

        self.module.attach_quote_fragments(parsed, source_text)
        validation = self.module.validate_model_output(
            parsed,
            paper_id="1",
            expected_fields=["time_to_diagnosis"],
            parse_error=None,
            source_text=source_text,
        )

        fragments = parsed["extractions"][0]["verbatim_quote_fragments"]
        source_span = parsed["extractions"][0]["verbatim_quote_source_span"]
        self.assertFalse(parsed["extractions"][0]["verbatim_quote_exact"])
        self.assertEqual(["beginning of 2016", "At the beginning of 2017"], [item["text"] for item in fragments])
        self.assertTrue(all(item["matched_in_source"] for item in fragments))
        self.assertEqual("salvaged", source_span["status"])
        self.assertEqual("ellipsis_exact_span", source_span["method"])
        self.assertEqual("beginning of 2016. At the beginning of 2017", source_span["source_text"])
        self.assertEqual("passed", validation["status"])
        self.assertIn("quote_fragmented_but_fragments_found", validation["warnings"])
        self.assertIn("quote_salvaged_from_source_span", validation["warnings"])

    def test_source_span_salvage_uses_fuzzy_after_exact_fails(self) -> None:
        quote = "diagnosed as Parkinson's Disease... high serum level"
        source_text = (
            "The patient was diagnosed as Parkinsons Disease (PD). Later, high serum level of GAD antibodies "
            "confirmed SPS."
        )

        source_span = self.module.quote_source_span_record(quote, source_text)

        self.assertEqual("salvaged", source_span["status"])
        self.assertEqual("ellipsis_fuzzy_span", source_span["method"])
        self.assertIn("diagnosed as Parkinsons Disease", source_span["source_text"])
        self.assertIn("high serum level", source_span["source_text"])

    def test_reversed_ellipsis_fragments_are_saved_but_not_salvaged_as_span(self) -> None:
        quote = "complaints of stiffness, pain, balance disorder ... increased muscle spasms"
        source_text = (
            "The patient reported increased muscle spasms in 2016. Later examination recorded "
            "complaints of stiffness, pain, balance disorder."
        )
        parsed = {
            "paper_id": "1",
            "extractions": [
                {
                    "field_name": "overview_established",
                    "value": "stiffness; spasms",
                    "verbatim_quote": quote,
                    "evidence_type": "verbatim_quote",
                    "derivation": "NA",
                    "confidence": "medium",
                }
            ],
        }

        self.module.attach_quote_fragments(parsed, source_text)
        validation = self.module.validate_model_output(
            parsed,
            paper_id="1",
            expected_fields=["overview_established"],
            parse_error=None,
            source_text=source_text,
        )

        fragments = parsed["extractions"][0]["verbatim_quote_fragments"]
        self.assertTrue(all(fragment["matched_in_source"] for fragment in fragments))
        self.assertFalse(fragments[1]["in_source_order"])
        self.assertEqual("failed", parsed["extractions"][0]["verbatim_quote_source_span"]["status"])
        self.assertEqual("failed", validation["status"])
        self.assertIn("quote_not_in_source", validation["errors"])
        self.assertIn("quote_fragments_out_of_order", validation["errors"])
        self.assertNotIn("quote_fragments_found_out_of_order", validation["warnings"])
        self.assertEqual(["overview_established"], validation["quote_unordered_fragment_fields"])

    def test_out_of_order_middle_fragment_is_hard_error_even_when_span_salvages(self) -> None:
        quote = "numbness and tingling... recurrent falls... difficulty in walking"
        source_text = (
            "The patient reported numbness and tingling in 2016. She later had difficulty in walking. "
            "Only after that did the text mention recurrent falls."
        )
        parsed = {
            "paper_id": "1",
            "extractions": [
                {
                    "field_name": "other_symptoms_onset",
                    "value": "sensory; falls; gait_disorder",
                    "verbatim_quote": quote,
                    "evidence_type": "verbatim_quote",
                    "derivation": "NA",
                    "confidence": "medium",
                }
            ],
        }

        self.module.attach_quote_fragments(parsed, source_text)
        validation = self.module.validate_model_output(
            parsed,
            paper_id="1",
            expected_fields=["other_symptoms_onset"],
            parse_error=None,
            source_text=source_text,
        )

        self.assertEqual("salvaged", parsed["extractions"][0]["verbatim_quote_source_span"]["status"])
        self.assertEqual("failed", validation["status"])
        self.assertIn("quote_fragments_out_of_order", validation["errors"])
        self.assertEqual(["other_symptoms_onset"], validation["quote_unordered_fragment_fields"])
        self.assertNotIn("other_symptoms_onset", validation["quote_salvaged_fields"])

    def test_ellipsis_fragment_split_by_page_header_prefers_ordered_match(self) -> None:
        quote = "lumbar region... lower and upper extremities"
        source_text = (
            "Early symptoms included lower and upper extremities tingling. "
            "Later examination found rigidity in lumbar region as well as in lower and\n"
            "\n[Page 3]\n81Acta Neurologica Belgica (2021) 121:79-85\n1 3\n"
            "upper extremities."
        )
        parsed = {
            "paper_id": "1",
            "extractions": [
                {
                    "field_name": "stiffness_distribution_established_multiple",
                    "value": "lumb_prox_LE; UE",
                    "verbatim_quote": quote,
                    "evidence_type": "verbatim_quote",
                    "derivation": "NA",
                    "confidence": "medium",
                }
            ],
        }

        self.module.attach_quote_fragments(parsed, source_text)
        validation = self.module.validate_model_output(
            parsed,
            paper_id="1",
            expected_fields=["stiffness_distribution_established_multiple"],
            parse_error=None,
            source_text=source_text,
        )

        fragments = parsed["extractions"][0]["verbatim_quote_fragments"]
        self.assertEqual("ellipsis_fragment_gapped", fragments[1]["match_type"])
        self.assertTrue(fragments[1]["in_source_order"])
        self.assertIn("81Acta Neurologica Belgica", fragments[1]["source_text"])
        self.assertNotIn("quote_fragments_out_of_order", validation["errors"])

    def test_source_span_normalises_hyphenation_and_page_markers_before_fuzzy(self) -> None:
        quote = "rigidity in lumbar region as well as in lower and upper extremities"
        source_text = (
            "On examination, she showed signs of rigidity in lumbar region as well as in lower and\n"
            "\n[Page 3]\n"
            "upper extremities."
        )

        source_span = self.module.quote_source_span_record(quote, source_text)

        self.assertEqual("exact", source_span["status"])
        self.assertIn("rigidity in lumbar region", source_span["source_text"])
        self.assertIn("upper extremities", source_span["source_text"])

    def test_source_span_salvages_full_quote_split_by_page_header(self) -> None:
        quote = "rigidity in lumbar region as well as in lower and upper extremities"
        source_text = (
            "On examination, she showed signs of rigidity in lumbar region as well as in lower and\n"
            "\n[Page 3]\n81Acta Neurologica Belgica (2021) 121:79-85\n1 3\n"
            "upper extremities. She had no tremor."
        )

        source_span = self.module.quote_source_span_record(quote, source_text)
        fragments = self.module.quote_fragment_records(quote, source_text)

        self.assertEqual("salvaged", source_span["status"])
        self.assertEqual("begin_end_exact_span", source_span["method"])
        self.assertEqual(["full_quote_begin_fragment", "full_quote_end_fragment"], [item["match_type"] for item in fragments])
        self.assertTrue(all(item["matched_in_source"] for item in fragments))
        self.assertIn("rigidity in lumbar region", source_span["source_text"])
        self.assertIn("upper extremities", source_span["source_text"])


if __name__ == "__main__":
    unittest.main()
