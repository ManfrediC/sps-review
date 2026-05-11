from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINES_DIR = REPO_ROOT / "src" / "pipelines"
if str(PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINES_DIR))

from stage07_XML import core  # noqa: E402


class TestStage07XmlCore(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.output_paths = core.output_paths(self.tmp_path / "stage07_xml")
        core.ensure_output_dirs(self.output_paths)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_text_json(self, paper_id: str, text: str) -> Path:
        path = self.tmp_path / "text" / f"{paper_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def write_text_json_at(self, directory: str, paper_id: str, text: str) -> Path:
        path = self.tmp_path / directory / f"{paper_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def single_case_annotation(self, text: str, paper_id: str) -> dict:
        source_path = self.write_text_json(paper_id, text)
        prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
        return core.single_case_passthrough_annotation(prepared_source=prepared)

    def single_case_selected_text(self, text: str, paper_id: str) -> str:
        annotation = self.single_case_annotation(text, paper_id)
        return "\n".join(
            str(span.get("selected_text") or "")
            for segment in annotation.get("segments") or []
            for span in segment.get("spans") or []
        )

    def test_validated_block_offsets_insert_roundtrippable_xml(self) -> None:
        source_path = self.write_text_json(
            "9001",
            "Case 1 was a 42-year-old woman.\n\nCase 2 was a 55-year-old man.",
        )
        prepared = core.prepare_source(paper_id="9001", source_path=source_path)
        block = prepared.blocks[0]
        selected = "Case 1 was a 42-year-old woman."
        annotation = {
            "segments": [
                {
                    "targets": ["p1"],
                    "role": "patient_specific",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": block.block_id,
                            "start_offset": 0,
                            "end_offset": len(selected),
                            "selected_text": selected,
                        }
                    ],
                }
            ]
        }

        segments, report = core.validate_annotation_payload(
            annotation_payload=annotation,
            prepared_source=prepared,
            declared_targets=[core.Target("p1", "patient", "Patient 1", "test")],
        )
        annotated = core.insert_xml_tags(prepared.source_text, segments)
        core.validate_roundtrip(prepared.source_text, annotated, report)

        self.assertFalse(report.failed)
        self.assertEqual(report.roundtrip_status, "passed")
        self.assertEqual(core.strip_stage07_tags(annotated), prepared.source_text)
        self.assertIn('<seg id="s0001"', annotated)

    def test_write_registry_merges_existing_rows_by_paper_id(self) -> None:
        registry_path = self.tmp_path / "stage07_xml_registry.csv"
        existing = {
            "paper_id": "9001",
            "route_mode": "individual",
            "stage07_status": "ready_for_langextract",
        }
        core.write_registry([existing], registry_path)

        core.write_registry(
            [
                {
                    "paper_id": "9002",
                    "route_mode": "individual_case_split",
                    "stage07_status": "manual_review_required",
                },
                {
                    "paper_id": "9001",
                    "route_mode": "group",
                    "stage07_status": "ready_for_langextract",
                },
            ],
            registry_path,
        )

        with registry_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row["paper_id"] for row in rows], ["9001", "9002"])
        self.assertEqual(rows[0]["route_mode"], "group")
        self.assertEqual(rows[1]["route_mode"], "individual_case_split")

    def test_offset_text_mismatch_fails_validation(self) -> None:
        source_path = self.write_text_json("9002", "Case 1 had axial stiffness.")
        prepared = core.prepare_source(paper_id="9002", source_path=source_path)
        annotation = {
            "segments": [
                {
                    "targets": ["p1"],
                    "role": "patient_specific",
                    "spans": [
                        {
                            "block_id": "b0001",
                            "start_offset": 0,
                            "end_offset": 6,
                            "selected_text": "Wrong!",
                        }
                    ],
                }
            ]
        }

        _, report = core.validate_annotation_payload(
            annotation_payload=annotation,
            prepared_source=prepared,
            declared_targets=[core.Target("p1", "patient", "Patient 1", "test")],
        )

        self.assertTrue(report.failed)
        self.assertIn("offset_text_mismatch:l0001:b0001:0:6", report.errors)
        self.assertEqual(report.rejected_spans[0]["reason"], "offset_text_mismatch:l0001:b0001:0:6")

    def test_unique_selected_text_relocates_offset_mismatch(self) -> None:
        source_path = self.write_text_json(
            "9006",
            "Intro text. Case 1 had axial stiffness.",
        )
        prepared = core.prepare_source(paper_id="9006", source_path=source_path)
        selected = "Case 1 had axial stiffness."
        annotation = {
            "segments": [
                {
                    "targets": ["p1"],
                    "role": "patient_specific",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": "b0001",
                            "start_offset": 0,
                            "end_offset": len(selected),
                            "selected_text": selected,
                        }
                    ],
                }
            ]
        }

        segments, report = core.validate_annotation_payload(
            annotation_payload=annotation,
            prepared_source=prepared,
            declared_targets=[core.Target("p1", "patient", "Patient 1", "test")],
        )

        self.assertFalse(report.failed)
        self.assertEqual(segments[0].text, selected)
        self.assertEqual(segments[0].source_start, prepared.source_text.index(selected))
        self.assertIn("relocated_span:l0001:b0001:0:27->12:39", report.warnings)
        self.assertEqual(report.span_adjustments[0]["relocated_offsets"], {"start": 12, "end": 39})

    def test_normalised_selected_text_relocates_whitespace_mismatch(self) -> None:
        source_path = self.write_text_json(
            "9023",
            "Case 1 had stiff-person syndrome.\nThe patient improved after diazepam.",
        )
        prepared = core.prepare_source(paper_id="9023", source_path=source_path)
        selected = "Case 1 had stiff-person syndrome.\n\nThe patient improved after diazepam."
        annotation = {
            "segments": [
                {
                    "targets": ["p1"],
                    "role": "patient_specific",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": "b0001",
                            "start_offset": 0,
                            "end_offset": len(selected),
                            "selected_text": selected,
                        }
                    ],
                }
            ]
        }

        segments, report = core.validate_annotation_payload(
            annotation_payload=annotation,
            prepared_source=prepared,
            declared_targets=[core.Target("p1", "patient", "Patient 1", "test")],
        )

        self.assertFalse(report.failed)
        self.assertEqual(segments[0].text, prepared.source_text)
        self.assertEqual(
            report.warnings,
            [f"relocated_span:l0001:b0001:0:{len(selected)}->0:{len(prepared.blocks[0].text)}"],
        )
        self.assertEqual(report.span_adjustments[0]["match_strategy"], "normalised_whitespace")

    def test_source_units_preserve_exact_source_offsets(self) -> None:
        source_path = self.write_text_json(
            "9031",
            "Patient 1\nA 42-year-old woman had axial stiffness.\n\n"
            "Patient 2\nA 55-year-old man had startle-provoked spasms.",
        )
        prepared = core.prepare_source(paper_id="9031", source_path=source_path)

        units = core.build_source_units(prepared, max_unit_chars=80)

        self.assertGreaterEqual(len(units), 2)
        for unit in units:
            self.assertEqual(unit.text, prepared.source_text[unit.source_start:unit.source_end])
            self.assertTrue(unit.block_spans)
            for span in unit.block_spans:
                block = next(block for block in prepared.blocks if block.block_id == span["block_id"])
                self.assertEqual(
                    span["selected_text"],
                    block.text[span["start_offset"]:span["end_offset"]],
                )

    def test_unit_selection_compiles_to_valid_span_metadata(self) -> None:
        source_path = self.write_text_json(
            "9032",
            "Patient 1\nA 42-year-old woman had axial stiffness.\n\n"
            "Patient 2\nA 55-year-old man had startle-provoked spasms.",
        )
        prepared = core.prepare_source(paper_id="9032", source_path=source_path)
        units = core.build_source_units(prepared, max_unit_chars=80)
        patient_1_units = [unit.unit_id for unit in units if "Patient 1" in unit.text or "42-year-old" in unit.text]
        annotation = core.compile_unit_selection_payload(
            selection_payload={
                "segments": [
                    {
                        "targets": ["p1"],
                        "role": "patient_specific",
                        "confidence": "high",
                        "evidence": "Patient 1 source units",
                        "unit_ids": patient_1_units,
                    }
                ]
            },
            prepared_source=prepared,
            units=units,
        )

        segments, report = core.validate_annotation_payload(
            annotation_payload=annotation,
            prepared_source=prepared,
            declared_targets=[core.Target("p1", "patient", "Patient 1", "test")],
        )

        self.assertFalse(report.failed)
        self.assertFalse(annotation["manual_review_reasons"])
        self.assertIn("42-year-old woman", "\n".join(segment.text for segment in segments))

    def test_declared_target_references_from_unit_model_do_not_crash(self) -> None:
        report = core.ValidationReport()

        targets, diverged = core.merge_declared_targets(
            [core.Target("p1", "patient", "Patient 1", "test")],
            {"targets": ["p1", "p9"]},
            report,
        )

        self.assertEqual([target.target_id for target in targets], ["p1"])
        self.assertFalse(diverged)
        self.assertIn("ignored_declared_target_reference:p1", report.warnings)
        self.assertIn("invalid_declared_target_payload:t2", report.errors)

    def test_invalid_unit_selection_records_manual_review_reasons(self) -> None:
        source_path = self.write_text_json("9033", "Patient 1 had axial stiffness.")
        prepared = core.prepare_source(paper_id="9033", source_path=source_path)
        units = core.build_source_units(prepared)
        unit_id = units[0].unit_id

        annotation = core.compile_unit_selection_payload(
            selection_payload={
                "segments": [
                    {
                        "targets": ["p1"],
                        "role": "patient_specific",
                        "unit_ids": [unit_id, unit_id],
                    },
                    {
                        "targets": ["p1"],
                        "role": "patient_specific",
                        "unit_ids": ["u9999"],
                    },
                    {
                        "targets": ["p1"],
                        "role": "patient_specific",
                        "unit_ids": [],
                    },
                ]
            },
            prepared_source=prepared,
            units=units,
        )

        self.assertEqual(annotation["segments"], [])
        self.assertIn(f"duplicate_unit_ids:l0001:{unit_id}", annotation["manual_review_reasons"])
        self.assertIn("unknown_unit_ids:l0002:u9999", annotation["manual_review_reasons"])
        self.assertIn("missing_unit_ids:l0003", annotation["manual_review_reasons"])

    def test_scope_aware_units_keep_exact_offsets(self) -> None:
        source_path = self.write_text_json(
            "9034",
            "Patient 1 had SPS. Patient 2 had neuropathy. "
            "Serum samples from the three patients and controls were tested.",
        )
        prepared = core.prepare_source(paper_id="9034", source_path=source_path)

        units = core.build_source_units(prepared, max_unit_chars=500)

        self.assertGreaterEqual(len(units), 2)
        for unit in units:
            self.assertEqual(unit.text, prepared.source_text[unit.source_start:unit.source_end])

    def test_unit_features_detect_ocr_aliases_and_continuation(self) -> None:
        source_path = self.write_text_json(
            "9035",
            "Patient |\nA woman had stiff-person syndrome.\n\nShe improved after baclofen.",
        )
        prepared = core.prepare_source(paper_id="9035", source_path=source_path)
        units = core.build_source_units(prepared, max_unit_chars=80)
        target = core.Target("p1", "patient", "Patient 1", "test")

        features = core.build_unit_features(units, [target])

        ocr_unit = next(unit for unit in units if "Patient |" in unit.text)
        continuation_unit = next(unit for unit in units if "She improved" in unit.text)
        self.assertEqual(features[ocr_unit.unit_id].explicit_target_mentions, ("p1",))
        self.assertIn("ocr_patient_label", features[ocr_unit.unit_id].risk_flags)
        self.assertEqual(features[continuation_unit.unit_id].candidate_targets, ("p1",))
        self.assertIn("continuation", features[continuation_unit.unit_id].reason_codes)

    def test_unit_selection_roundtrips_source_unit_ids_to_target_views(self) -> None:
        source_path = self.write_text_json(
            "9036",
            "Patient 1\nA 42-year-old woman had axial stiffness.",
        )
        prepared = core.prepare_source(paper_id="9036", source_path=source_path)
        units = core.build_source_units(prepared)
        annotation = core.compile_unit_selection_payload(
            selection_payload={
                "route_mode": "individual_case_split",
                "segments": [
                    {
                        "targets": ["p1"],
                        "role": "patient_specific",
                        "confidence": "high",
                        "evidence": "Patient 1 source unit",
                        "unit_ids": [units[0].unit_id],
                    }
                ],
            },
            prepared_source=prepared,
            units=units,
        )

        result = core.process_paper(
            paper_id="9036",
            source_row={"preferred_langextract_mode": "individual_case_split"},
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="deepseek-v4-pro",
            annotation_payload=annotation,
        )

        self.assertEqual(result.segments_payload["segments"][0]["source_unit_ids"], [units[0].unit_id])
        self.assertEqual(result.target_view_payloads["p1"]["source_blocks"][0]["source_unit_ids"], [units[0].unit_id])

    def test_role_target_compatibility_rejects_group_target_as_patient_specific(self) -> None:
        source_path = self.write_text_json("9037", "The SPSD group improved after treatment.")
        prepared = core.prepare_source(paper_id="9037", source_path=source_path)
        block = prepared.blocks[0]

        _, report = core.validate_annotation_payload(
            annotation_payload={
                "segments": [
                    {
                        "targets": ["g1"],
                        "role": "patient_specific",
                        "confidence": "high",
                        "spans": [
                            {
                                "block_id": block.block_id,
                                "start_offset": 0,
                                "end_offset": len(block.text),
                                "selected_text": block.text,
                            }
                        ],
                    }
                ]
            },
            prepared_source=prepared,
            declared_targets=[core.Target("g1", "group", "SPSD group", "test")],
        )

        self.assertTrue(report.failed)
        self.assertIn("role_target_mismatch:l0001:patient_specific", report.errors)

    def test_case_series_target_views_use_stage07_case_series_unit_source(self) -> None:
        source_path = self.write_text_json(
            "9038",
            "Patient 1\nA woman had SPS.\n\nPatient 2\nA man had SPS.",
        )
        prepared = core.prepare_source(paper_id="9038", source_path=source_path)
        units = core.build_source_units(prepared, max_unit_chars=80)
        p1_units = [unit.unit_id for unit in units if "Patient 1" in unit.text or "A woman" in unit.text]
        p2_units = [unit.unit_id for unit in units if "Patient 2" in unit.text or "A man" in unit.text]
        annotation = core.compile_unit_selection_payload(
            selection_payload={
                "route_mode": "individual_case_split",
                "segments": [
                    {
                        "targets": ["p1"],
                        "role": "patient_specific",
                        "confidence": "high",
                        "evidence": "Patient 1 case",
                        "unit_ids": p1_units,
                    },
                    {
                        "targets": ["p2"],
                        "role": "patient_specific",
                        "confidence": "high",
                        "evidence": "Patient 2 case",
                        "unit_ids": p2_units,
                    },
                ],
            },
            prepared_source=prepared,
            units=units,
        )

        result = core.process_paper(
            paper_id="9038",
            source_row={"preferred_langextract_mode": "individual_case_split"},
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "2",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="deepseek-v4-pro",
            annotation_payload=annotation,
        )

        self.assertEqual(result.target_view_payloads["p1"]["unit_source"], "stage07_xml_case_series")
        self.assertEqual(result.target_view_payloads["p2"]["unit_source"], "stage07_xml_case_series")

    def test_process_multi_patient_annotation_builds_ready_target_views(self) -> None:
        text = (
            "Case 1 had axial stiffness and painful spasms.\n\n"
            "Case 2 had startle-provoked spasms.\n\n"
            "Both patients had anti-GAD antibodies."
        )
        source_path = self.write_text_json("9003", text)
        prepared = core.prepare_source(paper_id="9003", source_path=source_path)
        first = prepared.blocks[0]
        second = prepared.blocks[1]
        shared = prepared.blocks[2]
        annotation = {
            "segments": [
                {
                    "targets": ["p1"],
                    "role": "patient_specific",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": first.block_id,
                            "start_offset": 0,
                            "end_offset": len(first.text),
                            "selected_text": first.text,
                        }
                    ],
                },
                {
                    "targets": ["p2"],
                    "role": "patient_specific",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": second.block_id,
                            "start_offset": 0,
                            "end_offset": len(second.text),
                            "selected_text": second.text,
                        }
                    ],
                },
                {
                    "targets": ["p1", "p2"],
                    "role": "shared",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": shared.block_id,
                            "start_offset": 0,
                            "end_offset": len(shared.text),
                            "selected_text": shared.text,
                        }
                    ],
                },
            ]
        }

        result = core.process_paper(
            paper_id="9003",
            source_row={
                "preferred_langextract_mode": "individual_case_split",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "2",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        p1 = result.target_view_payloads["p1"]
        p2 = result.target_view_payloads["p2"]
        self.assertTrue(p1["ready_for_langextract"])
        self.assertTrue(p2["ready_for_langextract"])
        self.assertIn("Case 1 had axial stiffness", p1["input_text"])
        self.assertIn("Both patients had anti-GAD antibodies.", p1["input_text"])
        self.assertNotIn("Case 2 had startle", p1["input_text"])
        self.assertEqual(result.registry_row["n_ready_target_views"], "2")
        self.assertEqual(core.strip_stage07_tags(result.annotated_text), result.segments_payload["source_blocks"][0]["text"] + "\n\n" + result.segments_payload["source_blocks"][1]["text"] + "\n\n" + result.segments_payload["source_blocks"][2]["text"])

    def test_split_candidate_without_annotation_is_not_ready(self) -> None:
        source_path = self.write_text_json("9004", "Case 1 text.\n\nCase 2 text.")

        result = core.process_paper(
            paper_id="9004",
            source_row={
                "preferred_langextract_mode": "individual_case_split",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "2",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=None,
        )

        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertEqual(result.registry_row["n_segments"], "0")
        self.assertIn("missing_target_evidence:p1", result.registry_row["manual_review_reasons"])
        self.assertIn("missing_target_evidence:p2", result.registry_row["manual_review_reasons"])

    def test_targeted_background_segment_is_review_only(self) -> None:
        source_path = self.write_text_json(
            "9020",
            "Stiff-person syndrome is a generic disease background.\n\nCase details were unavailable.",
        )
        prepared = core.prepare_source(paper_id="9020", source_path=source_path)
        block = prepared.blocks[0]
        annotation = {
            "segments": [
                {
                    "targets": ["p1"],
                    "role": "background",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": block.block_id,
                            "start_offset": 0,
                            "end_offset": len(block.text),
                            "selected_text": block.text,
                        }
                    ],
                }
            ]
        }

        result = core.process_paper(
            paper_id="9020",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertEqual(result.target_view_payloads["p1"]["input_text"], "")
        self.assertIn("targeted_background_segment:l0001", result.registry_row["manual_review_reasons"])
        self.assertIn("missing_target_evidence:p1", result.registry_row["manual_review_reasons"])

    def test_abstract_methods_segment_is_audit_only(self) -> None:
        text = "Methods. We studied two women with stiff-person syndrome by immunocytochemistry."
        source_path = self.write_text_json("9021", text)
        prepared = core.prepare_source(paper_id="9021", source_path=source_path)
        block = prepared.blocks[0]
        annotation = {
            "segments": [
                {
                    "targets": ["p1", "p2"],
                    "role": "shared",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": block.block_id,
                            "start_offset": 0,
                            "end_offset": len(block.text),
                            "selected_text": block.text,
                        }
                    ],
                }
            ]
        }

        result = core.process_paper(
            paper_id="9021",
            source_row={
                "preferred_langextract_mode": "individual_case_split",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "2",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.segments_payload["segments"][0]["role"], "uncertain")
        self.assertEqual(result.segments_payload["segments"][0]["targets"], ["unknown"])
        self.assertEqual(result.target_view_payloads["p1"]["input_text"], "")
        self.assertIn("audit_only_unsafe_section_segment:l0001", result.registry_row["manual_review_reasons"])
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")

    def test_mixed_shared_patient_labels_are_audit_only(self) -> None:
        text = "Patient 1 had vitiligo; patient 2 had serum autoantibodies."
        source_path = self.write_text_json("9022", text)
        prepared = core.prepare_source(paper_id="9022", source_path=source_path)
        block = prepared.blocks[0]
        annotation = {
            "segments": [
                {
                    "targets": ["p1", "p2"],
                    "role": "shared",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": block.block_id,
                            "start_offset": 0,
                            "end_offset": len(block.text),
                            "selected_text": block.text,
                        }
                    ],
                }
            ]
        }

        result = core.process_paper(
            paper_id="9022",
            source_row={
                "preferred_langextract_mode": "individual_case_split",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "2",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.segments_payload["segments"][0]["role"], "uncertain")
        self.assertEqual(result.segments_payload["segments"][0]["targets"], ["p1", "p2"])
        self.assertEqual(result.target_view_payloads["p1"]["input_text"], "")
        self.assertIn("mixed_shared_patient_specific_segment:l0001", result.registry_row["manual_review_reasons"])
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")

    def test_single_patient_source_without_clear_window_requires_review(self) -> None:
        source_path = self.write_text_json(
            "9005",
            "A 40-year-old woman had SPS.\n\nShe improved after diazepam.",
        )

        result = core.process_paper(
            paper_id="9005",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=None,
        )

        self.assertEqual(result.registry_row["annotation_mode"], "deterministic_pass_through")
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertFalse(result.target_view_payloads["p1"]["ready_for_langextract"])
        self.assertIn("A 40-year-old woman had SPS.", result.target_view_payloads["p1"]["input_text"])
        self.assertIn("single_patient_clinical_window_uncertain", result.registry_row["manual_review_reasons"])

    def test_single_patient_source_gets_deterministic_clinical_window(self) -> None:
        source_path = self.write_text_json(
            "9008",
            "Library cover sheet.\n\nCasePresentation\nA patient had SPS.\nTreatment helped.\nTheCaseinContext\nGeneric SPS background.\nSelectedReading\nReference.",
        )

        result = core.process_paper(
            paper_id="9008",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=None,
        )

        self.assertEqual(result.registry_row["annotation_mode"], "deterministic_clinical_window")
        self.assertEqual(result.registry_row["ready_for_langextract"], "true")
        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("CasePresentation", text)
        self.assertIn("Treatment helped.", text)
        self.assertNotIn("Library cover sheet", text)
        self.assertNotIn("Generic SPS background", text)

    def test_batch041_bmj_single_case_keeps_case_material_only(self) -> None:
        source_path = self.write_text_json(
            "9041",
            "Unusual presentation of stiff- person syndrome in a patient with type 1 diabetes mellitus\n"
            "Munipalli\n"
            "SUMMARY\nHere, we describe a woman with stiff-limb syndrome who improved with treatment.\n"
            "BACKGROUND\nGeneric SPS background.\n"
            "CASE PRESENTATION\nThe patient was a woman in her early 40s with type 1 diabetes and right ankle stiffness.\n"
            "INVESTIGATIONS\nLaboratory evaluations showed elevated serum anti-GAD65 antibody.\n"
            "However, the patient's history of multiple by copyright.\n"
            "on December 22, 2023 at University Library Zurich. Protectedhttp://casereports.bmj.com/ BMJ Case Rep: first published as 10.1136/bcr-2021-247482 on 7 February 2022. Downloaded from\n"
            "2 Munipalli B, Shah JS. BMJ Case Rep 2022;15:e247482. doi:10.1136/bcr-2021-247482\n"
            "Case report\nautoimmune disorders raised clinical suspicion.\n"
            "TREATMENT\nThe patient was treated with diazepam and IVIg.\n"
            "OUTCOME AND FOLLOW-UP\nAfter 3 months, she regained the ability to drive.\n"
            "DISCUSSION\nGeneric SPS discussion.\n"
            "Patient's perspective\n"
            "I am feeling a little more secure on my feet. No falls.\n"
            "Learning points\nGeneric learning point.",
        )
        prepared = core.prepare_source(paper_id="9041", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9041",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertEqual(result.registry_row["ready_for_langextract"], "true")
        self.assertIn("The patient was a woman in her early 40s", text)
        self.assertIn("I am feeling a little more secure", text)
        self.assertIn("autoimmune disorders raised clinical suspicion", text)
        self.assertNotIn("Generic SPS background", text)
        self.assertNotIn("Generic SPS discussion", text)
        self.assertNotIn("Generic learning point", text)
        self.assertNotIn("Downloaded from", text)

    def test_batch041_retrospective_gad_cohort_is_deferred(self) -> None:
        source_path = self.write_text_json(
            "9042",
            "Serum glutamate decarboxylase antibodies and neurological disorders: when to suspect their association?\n"
            "Results\nA total of 173 patients (51.7% men, mean age 51.62) were included.\n"
            "One patient had stiff-person syndrome in the typical anti-GAD group.\n"
            "Discussion\nThis is an observational retrospective study including all patients for whom titers were requested.",
        )
        prepared = core.prepare_source(paper_id="9042", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9042",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.registry_row["annotation_mode"], "single_case_deferred_multi_case_source")
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertIn("not_single_case_for_stage07_singlecase", result.registry_row["manual_review_reasons"])

    def test_batch042_bilingual_case_keeps_clinical_windows_only(self) -> None:
        source_path = self.write_text_json(
            "9043",
            "Stiff-person syndrome with sensorimotor polyneuropathy - case report\n"
            "CLINICAL CASE REPORT\n"
            "A 68-year-old patient was admitted with deteriorated mobility and pain in both lower\n"
            "WST\n"
            "Generic Polish introduction should not be selected.\n"
            "limbs, more pronounced on the left side. The patient reported falls and prior emergency admissions.\n"
            "nowotworu (Sarva\n"
            "There were no pathological symptoms or dissociated sensory loss. Diagnostic tests were extended.\n"
            "na izbie\n"
            "the anti-GAD65 antibody test results led to the diagnosis. Treatment with baclofen and diazepam helped.\n"
            "DISCUSSION, DIAGNOSTIC CRITERIA\n"
            "Our patient presented with both axial symptoms and spasms.\n"
            "The diagnosis of classical SPS can be made clinically.\n"
            "Having been informed about possible treatment options, our patient refused immunomodulation.\n"
            "So far, trials are generic background.\n"
            "References\nGeneric reference.",
        )
        prepared = core.prepare_source(paper_id="9043", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9043",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 68-year-old patient was admitted", text)
        self.assertIn("Treatment with baclofen and diazepam helped", text)
        self.assertNotIn("Generic Polish introduction", text)
        self.assertNotIn("Generic reference", text)

    def test_batch042_frontiers_stiff_limb_excludes_generic_treatment_discussion(self) -> None:
        source_path = self.write_text_json(
            "9046",
            "Case Report: Amphiphysin Antibody-Associated Stiff-Limb Syndrome and Myelopathy.\n"
            "INTRODUCTION\nGeneric background.\n"
            "CASE PRESENTATION\n"
            "An 83-year-old white female presented with painful spasms and breast cancer.\n"
            "TABLE 1 | Summary of laboratory testing.\n"
            "Amphiphysin Positive Negative\n"
            "She was bedridden upon discharge and passed away within 6 months.\n"
            "DISCUSSION\n"
            "Our patient has myelopathic features including lower-extremity weakness and pyramidal tract sign.\n"
            "Based on the pathogenesis, there are two main treatment approaches for SPS.\n"
            "In a small randomized controlled trial with 16 patients who had SPS, IVIG was effective.\n"
            "Our patient has\n"
            "received oral glucocorticoids for presumed gout flare before hospitalization without significant response.\n"
            "Our patient responded to symptomatic management with diazepam, but not to PLEX.\n"
            "CONCLUSION\nGeneric conclusion.",
        )
        prepared = core.prepare_source(paper_id="9046", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9046",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("TABLE 1 | Summary of laboratory testing", text)
        self.assertNotIn("small randomized controlled trial", text)
        self.assertNotIn("Generic conclusion", text)

    def test_batch042_pediatric_perm_excludes_literature_tables(self) -> None:
        source_path = self.write_text_json(
            "9044",
            "Progressive Encephalomyelitis with Rigidity and Myoclonus with an Aggressive Presentation "
            "Mimicking Septic Shock\n"
            "Case Report\n"
            "A 16-year-old previously healthy Chinese girl presented with impaired consciousness and PERM.\n"
            "She improved after immunotherapy and no relapse was observed.\n"
            "Discussion\n"
            "Compared with other variants of SPS, PERM explained her encephalopathy and dysautonomia.\n"
            "In 2021, Chang reviewed generic cases.\n"
            "In contrast to other pediatric cases, our patient had an aggressive presentation mimicking shock.\n"
            "According to our literature review, other cases are summarised elsewhere.\n"
            "Table 1 Approach to children with stiffness.\n"
            "Table 2 Reported pediatric cases with progressive encephalomyelitis with rigidity and myoclonus.",
        )
        prepared = core.prepare_source(paper_id="9044", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9044",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 16-year-old previously healthy Chinese girl", text)
        self.assertIn("aggressive presentation mimicking shock", text)
        self.assertNotIn("Table 2 Reported pediatric cases", text)

    def test_batch042_frontiers_perm_keeps_current_case_table_row_only(self) -> None:
        source_path = self.write_text_json(
            "9045",
            "A case with unilateral brainstem symptoms in anti-GlyR antibody-positive PERM.\n"
            "Case presentation: A /seven.tnum/one.tnum-year-old man had left stiff face and myoclonus.\n"
            "KEYWORDS\n"
            "Case presentation\n"
            "A 71-year-old man was admitted with trismus, dysautonomia, and left-dominant rigidity.\n"
            "Discussion and conclusions\n"
            "This case presented with symptoms of unilateral brainstem dysfunction.\n"
            "TABLE /one.tnum\n"
            "A summary of published seropositive GlyR antibody positive PERM cases.\n"
            "Chang et al. 46 M other patient.\n"
            "Current case 71, M 3 days Left stiff face IVMP IVIG Oral corticosteroid - 5 No recurrence\n"
            "Frontiers in Neurology /zero.tnum/four.tnum\n"
            "In the present case, both R1 and R2 showed high amplitude on the left side.\n"
            "A summary of published cases follows.\n"
            "we administered immunotherapies from a relatively early stage, sparing the patient from ventilator usage.\n"
            "In conclusion, this is a rare case with hemifacial stiffness and left-dominant myoclonus.\n"
            "Data availability statement Generic data statement.",
        )
        prepared = core.prepare_source(paper_id="9045", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9045",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 71-year-old man was admitted", text)
        self.assertIn("Current case 71, M 3 days", text)
        self.assertNotIn("Chang et al.", text)
        self.assertNotIn("Generic data statement", text)

    def test_single_patient_source_gets_multi_window_clinical_selection(self) -> None:
        source_path = self.write_text_json(
            "9014",
            "Journal header.\n"
            "Summary: Following several months of low back pain, a 36-year-old man developed SPS. "
            "Treatment resulted in marked improvement of ambulation.\n"
            "Key Words: Stiff-person syndrome.\n"
            "Stiff-person syndrome is a generic disease background.\n"
            "Address correspondence to the author.\n"
            "CASE REPORT\n"
            "The patient was a 36-year-old right-handed black man with axial stiffness. "
            "He was happy with the results and did not wish more injections at this time.\n"
            "DISCUSSION\n"
            "Patients with stiff-person syndrome are treated with multiple systemic medications.\n"
            "The decreased tone of uninjected thigh muscles after injection was intriguing. "
            "In conclusion, treatment reduced the need for systemic agents.\n"
            "Acknowledgment: We thank the laboratory.\n"
            "REFERENCES\n"
            "1. Generic reference.",
        )

        result = core.process_paper(
            paper_id="9014",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=None,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertEqual(result.registry_row["annotation_mode"], "deterministic_clinical_window")
        self.assertIn("Following several months of low back pain", text)
        self.assertIn("The patient was a 36-year-old right-handed black man", text)
        self.assertIn("The decreased tone of uninjected thigh muscles", text)
        self.assertNotIn("generic disease background", text)
        self.assertNotIn("Address correspondence", text)
        self.assertNotIn("REFERENCES", text)

    def test_single_case_passthrough_annotation_emits_ready_unit_metadata(self) -> None:
        source_path = self.write_text_json(
            "9030",
            "A 40-year-old woman had SPS.\n\nShe improved after diazepam.",
        )
        prepared = core.prepare_source(paper_id="9030", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9030",
            source_row={
                "preferred_langextract_mode": "group",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        view = result.target_view_payloads["p1"]
        self.assertEqual(result.registry_row["route_mode"], "individual")
        self.assertEqual(result.registry_row["stage07_scope"], "single_case_v1")
        self.assertEqual(result.registry_row["stage07_status"], "ready_for_langextract")
        self.assertEqual(result.registry_row["unit_id"], "9030::p1")
        self.assertEqual(result.registry_row["unit_source"], "single_case_passthrough")
        self.assertEqual(view["unit_id"], "9030::p1")
        self.assertEqual(view["unit_type"], "individual_patient")
        self.assertEqual(view["unit_source"], "single_case_passthrough")
        self.assertTrue(view["ready_for_langextract"])
        self.assertIn("A 40-year-old woman had SPS.", view["input_text"])

    def test_single_case_passthrough_defers_obvious_multi_patient_source(self) -> None:
        source_path = self.write_text_json(
            "9031",
            "Patient 1\nA 54-year-old woman had sensory neuronopathy.\n\n"
            "Patient 2\nA 60-year-old woman had neuropathy.\n\n"
            "Patient 3\nA 67-year-old man had rigidity and myoclonus.\n",
        )
        prepared = core.prepare_source(paper_id="9031", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9031",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        view = result.target_view_payloads["p1"]
        self.assertEqual(result.registry_row["annotation_mode"], "single_case_deferred_multi_case_source")
        self.assertEqual(result.registry_row["annotation_model"], "none")
        self.assertEqual(result.registry_row["stage07_status"], "manual_review_required")
        self.assertIn("not_single_case_for_stage07_singlecase", result.registry_row["defer_reason"])
        self.assertFalse(view["ready_for_langextract"])

    def test_single_case_age_anchor_stops_before_adjacent_letter_author_block(self) -> None:
        source_path = self.write_text_json(
            "9032",
            "SIR-Stiff-man syndrome (SMS) improved with treatment.\n"
            "A 42-year-old man with SMS had painful spasms and lumbar hyperlordosis. "
            "He improved after vigabatrin.\n"
            "*Other Author, Another Author\n"
            "Department of Unrelated Medicine\n"
            "An unrelated adjacent letter described anorexia nervosa.",
        )
        prepared = core.prepare_source(paper_id="9032", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9032",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 42-year-old man with SMS", text)
        self.assertNotIn("Other Author", text)
        self.assertNotIn("anorexia", text)

    def test_single_case_numbered_case_report_stops_at_numbered_discussion(self) -> None:
        source_path = self.write_text_json(
            "9033",
            "1. Introduction\nStiff-man syndrome background.\n"
            "2. Case report\nA 55-year-old woman developed SMS and ataxia. Treatment helped.\n"
            "3. Discussion\nGeneric autoimmunity discussion.\n",
        )
        prepared = core.prepare_source(paper_id="9033", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9033",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 55-year-old woman developed SMS", text)
        self.assertNotIn("Generic autoimmunity discussion", text)

    def test_single_case_numbered_case_report_stops_at_numbered_methods(self) -> None:
        source_path = self.write_text_json(
            "9038",
            "Abstract\nA 55-year-old woman with stiff-man syndrome improved.\n"
            "1. Introduction\nDisease background.\n"
            "2. Case report\nA 55-year-old woman developed SMS and ataxia. Treatment helped.\n"
            "3. Materials and methods\nWestern blot methods.",
        )
        prepared = core.prepare_source(paper_id="9038", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9038",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 55-year-old woman developed SMS", text)
        self.assertNotIn("Disease background", text)
        self.assertNotIn("Western blot methods", text)

    def test_single_case_lowercase_case_report_does_not_match_reported_word(self) -> None:
        source_path = self.write_text_json(
            "9076",
            "This was the fourth case reported in the literature and the first locally.\n"
            "There has been one case report of acute torticollis associated with rib stress fractures.\n"
            "case report\n"
            "A 14-month-old girl had stiff-person syndrome and respiratory spasms.\n"
            "References\n1. Generic reference.\n",
        )
        prepared = core.prepare_source(paper_id="9076", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9076",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 14-month-old girl", text)
        self.assertNotIn("fourth case reported", text)
        self.assertNotIn("acute torticollis", text)

    def test_single_case_ignores_later_non_spsd_case_report_in_same_issue(self) -> None:
        source_path = self.write_text_json(
            "9078",
            "Paraneoplastic stiff-person syndrome: no tumor progression over 5 years\n"
            "Case report. Three years ago, we reported a 53-year old woman with atypical SPS "
            "who presented with stiffness predominantly of her right upper limb and trunk. "
            "After treatment she showed no clinical signs of SPS.\n"
            "References\n1. Stiff-man syndrome reference.\n"
            "Sporadic CJD clinically mimicking variant CJD\n"
            "Case report. A 55-year-old woman with no history of iatrogenic exposure to CJD "
            "developed cognitive impairment and prion protein abnormalities.\n",
        )
        prepared = core.prepare_source(paper_id="9078", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9078",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("53-year old woman", text)
        self.assertIn("atypical SPS", text)
        self.assertNotIn("55-year-old woman", text)
        self.assertNotIn("prion protein", text)

    def test_single_case_multi_case_heading_does_not_append_discussion_window(self) -> None:
        source_path = self.write_text_json(
            "9034",
            "Case Reports\n"
            "Case 1. A 34-year-old woman had SMS and constipation. Treatment helped.\n"
            "Case 2. A 28-year-old man had CMT and abdominal pain.\n"
            "Discussion\nOur patient had hypothyroidism. General GI dysmotility background.",
        )
        prepared = core.prepare_source(paper_id="9034", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9034",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("Case 1", text)
        self.assertNotIn("Case 2", text)
        self.assertNotIn("General GI dysmotility", text)

    def test_single_case_does_not_append_review_discussion_with_boxes(self) -> None:
        source_path = self.write_text_json(
            "9077",
            "Case Report\n"
            "A 28-year-old woman had stiff-person syndrome, lumbar hyperlordosis, high GAD antibodies, "
            "and improved with diazepam.\n"
            "Discussion\n"
            "The patient will also often experience stimulus-triggered falls and anxiety. "
            "Box 1 Criteria for glutamic acid decarboxylase antibody-associated stiff-person syndrome.\n"
            "DIFFERENTIAL DIAGNOSIS\n"
            "TREATMENT\n",
        )
        prepared = core.prepare_source(paper_id="9077", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9077",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 28-year-old woman", text)
        self.assertNotIn("Box 1", text)
        self.assertNotIn("DIFFERENTIAL DIAGNOSIS", text)

    def test_single_case_table_heuristic_ignores_stable_substring(self) -> None:
        source_path = self.write_text_json(
            "9040",
            "Case 1. A 34-year-old woman had SMS. Her weight was stable.",
        )
        prepared = core.prepare_source(paper_id="9040", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9040",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.validation_payload["manual_review_reasons"], [])
        self.assertNotIn("ambiguous_table_row_mapping", result.registry_row["manual_review_reasons"])

    def test_single_case_age_anchor_preserves_table_material(self) -> None:
        source_path = self.write_text_json(
            "9035",
            "Results\nThe disease of the 66-year-old woman with SMS started with neck stiffness. "
            "Diazepam helped.\nFig.1 Pathology image.\nTable 1 Cell density values.",
        )
        prepared = core.prepare_source(paper_id="9035", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9035",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("66-year-old woman with SMS", text)
        self.assertIn("Pathology image", text)
        self.assertIn("Cell density", text)

    def test_single_case_present_case_table_trims_literature_comparators(self) -> None:
        source_path = self.write_text_json(
            "9041",
            "Case Report\nA 14-month-old girl had stiff-person syndrome and spasms.\n"
            "From the Department of Child Neurology\nReceived January 1, 1997.\n\n"
            "Table 1. Comparison of present case with cases in the literature\n"
            "Bowler, 1960\n"
            "Age 7\n"
            "Outcome Good\n"
            "Present Case\n"
            "1 yr, 2 mo\n"
            "F\n"
            "High-dose diazepam, baclofen, valproate, steroids\n"
            "Good\n"
            "The child later attended normal school.\n"
            "Discussion\nGeneric stiff-person syndrome background.",
        )
        prepared = core.prepare_source(paper_id="9041", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9041",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 14-month-old girl", text)
        self.assertIn("Present Case", text)
        self.assertIn("High-dose diazepam", text)
        self.assertIn("normal school", text)
        self.assertNotIn("From the Department", text)
        self.assertNotIn("Bowler, 1960", text)
        self.assertNotIn("Generic stiff-person syndrome background", text)

    def test_single_case_table_footnote_does_not_stop_patient_findings(self) -> None:
        source_path = self.write_text_json(
            "9042",
            "Title: Stiff-man syndrome autopsy report.\n"
            "The disease of the 66-year-old woman started with neck stiffness and spasms. Diazepam helped.\n"
            "Table 1 Cell density in the cerebellar cortex.\n"
            "SMS patient (10 areas counted) 283 + 154 1,555 + 465\n"
            "* = 541,000 um2 per area\n"
            "Microscopical findings in the CNS\n"
            "In all regions a high-grade edema of the CNS was found.\n"
            "Discussion\nGeneric pathophysiology.",
        )
        prepared = core.prepare_source(paper_id="9042", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9042",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("SMS patient (10 areas counted)", text)
        self.assertIn("Microscopical findings", text)
        self.assertNotIn("Generic pathophysiology", text)

    def test_single_case_plain_results_section_is_preserved_until_discussion(self) -> None:
        source_path = self.write_text_json(
            "9046",
            "A 61-year-old man had stiff-person syndrome.\n"
            "Materials and methods\nQuantitative methods were described.\n"
            "Results\nPathological study showed loss of neurons in the SMS patient.\n"
            "Table 1 SMS patient 42 controls 20\n"
            "Discussion\nGeneric disease interpretation.",
        )
        prepared = core.prepare_source(paper_id="9046", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9046",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("Pathological study", text)
        self.assertIn("Table 1", text)
        self.assertNotIn("Generic disease interpretation", text)

    def test_single_case_whole_issue_selects_witherick_autopsy_letter(self) -> None:
        source_path = self.write_text_json(
            "9073",
            "Frontotemporal Dementia with Parkinsonism Presenting as Posterior Cortical Atrophy\n"
            "Case Report\nA 55-year-old woman had posterior cortical atrophy.\n"
            "References\n1. Unrelated reference.\n"
            "Pathological Findings in a Case of Stiff\n"
            "Person Syndrome with Anti-GAD\n"
            "Antibodies\n"
            "Stiff person syndrome (SPS) is an immune-mediated disease.\n"
            "A 69-year-old man was admitted with acute, severe, and painful spasm. "
            "Anti-GAD antibodies were positive (180 U/mL; normal < 1). "
            "Electron microscopy revealed vacuoles in caudal spinal motor neurons. "
            "These then appeared to bud off from the inner surface of the\n"
            "------------------------------------------------------------\n"
            "*Correspondence to: Marios Hadjivassiliou, Department of Neurology.\n"
            "Published online 24 May 2011 in Wiley Online Library. DOI: 10.1002/mds.23784\n"
            "vacuole into the vacuole itself and degenerate. There was no significant "
            "lymphocytic infiltrate. Diazepam and antispasmodics were used.\n"
            "The previous report\n"
            "referred to a 65-year-old man with SPS where neuropatho-\n"
            "logical examination revealed cytoplasmic vacuoles in the\n"
            "motor neurons in the lumbar spinal cord.\n"
            "5 The distribution of these abnormal motor neurons was relevant to this patient.\n"
            "Jonathan Witherick, MRCP,\n"
            "Royal Hallamshire Hospital, Sheffield,\n"
            "United Kingdom\n"
            "2138 Movement Disorders, Vol. 26, No. 11, 2011\n"
            "LETTERS: NEW OBSERVATIONS\n"
            "Downloaded from https://movementdisorders.onlinelibrary.wiley.com/doi/10.1002/mds.23784 "
            "by a library. Creative Commons License\n\n"
            "References\n1. Meinck HM, Thompson D. Stiff man syndrome and related conditions.\n"
            "FIG. 1. a: Vacuolation of lower motor neurons on light microscopy. "
            "f: One dorsal root ganglion cell contains a Lewy-like inclusion.\n"
            "LETTERS: NEW OBSERVATIONS\n"
            "Mutation in 5 0 Upstream Region of GCHI Gene Causes Familial Dopa-Responsive Dystonia\n",
        )
        prepared = core.prepare_source(paper_id="9073", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9073",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 69-year-old man", text)
        self.assertIn("Anti-GAD antibodies were positive", text)
        self.assertIn("vacuole into the vacuole itself", text)
        self.assertIn("FIG. 1. a: Vacuolation", text)
        self.assertNotIn("A 55-year-old woman had posterior cortical atrophy", text)
        self.assertNotIn("65-year-old man", text)
        self.assertNotIn("Marios Hadjivassiliou", text)
        self.assertNotIn("Meinck HM", text)
        self.assertNotIn("GCHI Gene", text)

    def test_single_case_embedded_perm_table_selects_case1_cells_only(self) -> None:
        source_path = self.write_text_json(
            "9089",
            "Abstract GlyR antibodies were measured in five patients, including one patient with PERM "
            "and two patients with OFS.\n"
            "Results\nThe clinical details of the five patients are given in Table 1.\n"
            "Case presentation\n"
            "Case 1 (idiopathic PERM)\n"
            "This 61-year-old woman was admitted with gait disturbance, lower-limb stiffness, "
            "painful spasms, and high-titre GAD antibodies.\n"
            "Table 1 Summary of clinical features, laboratory findings, and outcome\n"
            "Patient no. Case 1 Case 2 Case 3 Case 4 Case 5\n"
            "Age at onset/sex 61/F 41/F 38/M 28/F 34/M\n"
            "Diagnosis Idiopathic PERM Idiopathic OFS Idiopathic OFS Idiopathic OMS Idiopathic OMS\n"
            "Treatment IVMP, IVIg, CS, CYS IVMP, CS IVMP, CS IVMP, CS IVMP, CS\n"
            "Outcome\n(observation\nperiods)\nInitially improved but\ntwice relapsed\n(40 months)\n"
            "Improved without\nrelapse\n"
            "(Table 1). Thyroid function tests showed mild hypothyroidism. "
            "The patient remained free of symptoms on low corticosteroids and cyclosporine.\n"
            "Case 2 (idiopathic OFS)\n"
            "This 41-year-old woman had oscillopsia without SPSD.",
        )
        prepared = core.prepare_source(paper_id="9089", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9089",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("This 61-year-old woman", text)
        self.assertIn("Table 1 Summary", text)
        self.assertIn("Patient no. Case 1", text)
        self.assertIn("Age at onset/sex 61/F", text)
        self.assertIn("Diagnosis Idiopathic PERM", text)
        self.assertIn("Treatment IVMP, IVIg, CS, CYS", text)
        self.assertIn("Initially improved but", text)
        self.assertIn("Thyroid function tests", text)
        self.assertNotIn("five patients, including one patient", text)
        self.assertNotIn("41/F", text)
        self.assertNotIn("Idiopathic OFS", text)
        self.assertNotIn("Case 2", text)

    def test_single_case_stops_before_lab_method_subsections_but_keeps_results(self) -> None:
        source_path = self.write_text_json(
            "9048",
            "A 51 year old man had stiff-person syndrome and insulin dependent diabetes. "
            "Prednisolone improved mobility.\n"
            "AUTOANTIBODIES TO GAD, GAD EPITOPES, IA-2, IAA, AND ICA\n"
            "Antibodies were analysed by radioligand binding assays as previously described.\n"
            "Results\nPATIENT\nThe patient relapsed when prednisolone was reduced.\n"
            "Discussion\nGeneric mechanism.",
        )
        prepared = core.prepare_source(paper_id="9048", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9048",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 51 year old man", text)
        self.assertIn("The patient relapsed", text)
        self.assertNotIn("radioligand binding assays", text)

    def test_embedded_case_does_not_append_trial_results_section(self) -> None:
        source_path = self.write_text_json(
            "9047",
            "Case 10\nA 62-year-old woman with stiff-person syndrome improved with diazepam.\n"
            "RESULTS\nThe clinical rating score did not change in nine patients. Case 6 had myoclonus.\n",
        )
        prepared = core.prepare_source(paper_id="9047", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9047",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("Case 10", text)
        self.assertNotIn("nine patients", text)
        self.assertNotIn("Case 6", text)

    def test_single_case_does_not_append_adjacent_cst3_results_section(self) -> None:
        source_path = self.write_text_json(
            "9079",
            "Case report. A 39-year-old woman had stiff-person syndrome and improved with tiagabine.\n"
            "Results. The mean age at AD onset was 57 years. The CST3 genotype frequencies "
            "were compared in cases and controls (table).",
        )
        prepared = core.prepare_source(paper_id="9079", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9079",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("39-year-old woman", text)
        self.assertNotIn("CST3", text)
        self.assertNotIn("AD onset", text)

    def test_embedded_case_stops_at_uppercase_results_heading_with_inline_body(self) -> None:
        source_path = self.write_text_json(
            "9070",
            "Case 10\n"
            "A 62-year-old woman with stiff-person syndrome had spasms and anti-GAD antibodies.\n"
            "RESULTS  The clinical rating score did not change significantly in nine patients. "
            "Case 6 had myoclonus.",
        )
        prepared = core.prepare_source(paper_id="9070", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9070",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("62-year-old woman", text)
        self.assertNotIn("nine patients", text)
        self.assertNotIn("Case 6", text)

    def test_generic_conclusion_does_not_block_later_clinical_findings(self) -> None:
        source_path = self.write_text_json(
            "9049",
            "Introduction\nDisease background.\n"
            "Results\nClinical Findings\nA 58-year-old male had SMS with stiffness and spasms.\n"
            "Diazepam improved gait.\n"
            "Discussion\nIn conclusion, autoantibodies deserve further investigation.\n"
            "Experimental Procedures\nRat brain extracts were tested.",
        )
        prepared = core.prepare_source(paper_id="9049", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9049",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 58-year-old male", text)
        self.assertNotIn("autoantibodies deserve", text)
        self.assertNotIn("Rat brain extracts", text)

    def test_single_case_excludes_download_and_correspondence_boilerplate(self) -> None:
        source_path = self.write_text_json(
            "9043",
            "CASE REPORT\nA 55-year-old man had stiff-person syndrome.\n"
            "*Correspondence to: Dr. Example\n"
            "CCC 0148-639X/97/040493-06\n"
            "© 1997 John Wiley & Sons, Inc.\n"
            "Case of the Month MUSCLE & NERVE April 1997 493\n\n"
            "Treatment with diazepam helped.\n"
            "Movement Disorders, Vol. 11, No. 6, 1996\n"
            " 15318257, 1996, 6, Downloaded from https://example.test by Library. "
            "See the Terms and Conditions on Wiley Online Library for rules of use; "
            "OA articles are governed by the applicable Creative Commons License\n\n"
            "TABLE 1. Patient values\n"
            "SPS patient 42\n"
            "Discussion\nGeneric disease context.",
        )
        prepared = core.prepare_source(paper_id="9043", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9043",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 55-year-old man", text)
        self.assertIn("Treatment with diazepam helped", text)
        self.assertIn("TABLE 1. Patient values", text)
        self.assertNotIn("Correspondence", text)
        self.assertNotIn("Downloaded from", text)
        self.assertNotIn("Movement Disorders, Vol.", text)

    def test_single_case_excludes_mid_case_acta_page_header(self) -> None:
        source_path = self.write_text_json(
            "9074",
            "case report\n"
            "A 61-year-old man had stiff-person syndrome after tick-borne meningoencephalitis. "
            "In the begin-\n"
            "ACTA MEDICA (Hradec Kralove) 2011; 54(4):170-174\n\n"
            "171\n"
            "ning of September, he found a tick on his right thigh. Anti-GAD antibodies were high.",
        )
        prepared = core.prepare_source(paper_id="9074", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9074",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 61-year-old man", text)
        self.assertIn("ning of September", text)
        self.assertNotIn("ACTA MEDICA", text)

    def test_single_case_excludes_mid_case_jns_masthead(self) -> None:
        source_path = self.write_text_json(
            "9075",
            "Case report\n"
            "A 71-year-old woman had stiff-person syndrome with continuous motor unit activity. "
            "CMCT, calculated with\n"
            "Journal of the Neurological Sciences 314 (2012) 166 -168\n"
            "Abbreviations: CSP, cortical silent period; EMG, electromyographic; GABA, gamma-aminobutyric acid;\n"
            "0022-510\n"
            "doi:10.1016/j.jns.2011.10.023\n"
            "Contents lists available at SciVerse ScienceDirect\n"
            "Journal of the Neurological Sciences\n"
            "journal homepage: www.elsevier.com/locate/jns\n\n"
            "the F-wave method, was normal. Pregabalin improved rigidity and spasms.",
        )
        prepared = core.prepare_source(paper_id="9075", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9075",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 71-year-old woman", text)
        self.assertIn("the F-wave method", text)
        self.assertNotIn("Journal of the Neurological Sciences", text)
        self.assertNotIn("doi:10.1016", text)

    def test_single_case_exclusions_remove_batch011_page_furniture_but_keep_tables(self) -> None:
        text = (
            "Case report\n"
            "A 60-year-old woman had stiff-person syndrome and breast carcinoma.\n"
            "n engl j med 367; 9\n\n"
            "nejm.org\n\n"
            "august 30, 2012\n\n"
            "From the Departments of Neurology\n"
            "Example Hospital.\n"
            "N Engl J Med 2012; 367: 851-61.\n"
            "DOI: 10.1056/NEJMcpc1114036\n"
            "Copyright 2012 Massachusetts Medical Society.\n\n"
            "851\n\n"
            "The New England Journal of Medicine\n"
            "Copyright 2012 Massachusetts Medical Society. All rights reserved.\n\n"
            "Table 1. Laboratory Data.\n"
            "Glucose 119\n"
            "852\n\n"
            "n engl j med 367; 9\n\n"
            "Atorvastatin was discontinued.\n"
            "Funding: None.\n"
            "Conflict of interest: None.\n"
            "Brief Communication\n"
            "2012 The Authors\n"
            "Internal Medicine Journal 2012 Royal Australasian College of Physicians 205\n"
            "The diagnosis of SPS was supported by GAD antibodies.\n"
            "Brief Communication\n"
            "2012 The Authors\n"
            "Internal Medicine Journal 2012 Royal Australasian College of Physicians 206\n"
            "Baclofen helped the spasms.\n"
            "J Neurol (2012) 259:1566-1573 1567\n"
            "123\n"
            "The patient relapsed after corticosteroids were tapered.\n"
            "The two main goals of treatment are to enhance\n"
            "GABA neurotransmission and immunomodulation. IVIG helped 16 SPS patients in a trial.\n"
            "However, the combination of non-Hodgkin lymphoma, thymoma and SPS had not been described.\n"
            "Muscle\n"
            "Key words: anti-GAD autoantibody, insulin-dependent diabe- strength was almost normal.\n"
            "tes mellitus, y-aminobutyric acid neuron, cerebel- moderately hyperactive reflexes were present.\n"
            "lum\n"
            "A complete blood cell count was otherwise normal.\n"
            "Introduction\n"
            "U/ml remained high.\n"
            "Glutamic acid decarboxylase (GAD) is the main target of humoral autoimmunity. "
            "Wereviewed the case of a 46-year-old woman. (Internal Medicine 40: 968-971, 2001)\n"
            "Diazepam markedly decreased the contraction.\n"
            "From the First Department of Medicine, Hamamatsu University School of Medicine, Hamamatsu\n"
            "Received for publication January 19, 2001; Accepted for publication May 14, 2001\n"
            "968\n\n"
            "Internal\n\n"
            "Medicine Vol. 40, No. 9 (September 2001)\n\n"
            "Cerebellar Ataxia and Stiff-person\n\n"
            "Syndrome\n"
            "Figure 1. Magnetic resonance imaging showed cerebellar atrophy.\n"
            "Ataxia with Anti-GAD Antibodies\n\n"
            "Internal\n\n"
            "Medicine Vol. 40, No. 9 (September 2001)\n\n"
            "Cerebellar Ataxia and Stiff-person\n\n"
            "Syndrome\n"
            "References\n"
            "1. Generic citation.\n"
            "Internal\n\n"
            "Medicine Vol. 40, No. 9 (September 2001)\n\n"
            "971\n"
            "A 40-year-old female had stiff-person syndrome with invasive thymoma.\n"
            "q 2001 Elsevier Science B.V. All rights reserved.\n"
            "0022-510Xr01r$ - see front matter q 2001 Elsevier Science B.V. All rights reserved.\n"
            "PII: S 0022-510X 01 00602-5\n\n"
            "()H. Hagiwara et al. r Journal of the Neurological Sciences 193 2001 59-6260\n"
            "Fig. 1. Computed tomography showed an invasive thymoma.\n"
            "Table 1\n"
            "Stiff-person syndrome associated with thymoma\n"
            "Reporter Patient Course Anti-GAD Therapy Pathology Effect\n"
            "Piccolo and 54 M SPS-MG diazepam ND ND\n"
            "Nicholas 55 M SPS-MG baclofen thymectomy cortical type\n"
            "Aso et al. 21 F MG-SPS diazepam ND ND\n"
            "Present 40 F SPS steroid pulse Invasive thymoma effective\n"
            "case immunoadsorption lymphocytes predominant thymectomy\n"
            "In comparing the Nicholas case with the present case, the former corresponds to the cortical type and is accompanied by MG. "
            "In our case, pathological findings were predominantly lymphocytic.\n"
            "Acknowledgements\n"
            "We thank Dr. Meiko Shiina, from our department, for performing Western blot analysis.\n"
            "FIG. 2. Cutaneous silent period tracing.\n"
            "CLINICAL/SCIENTIFIC NOTES1190\n"
            "This patient's symptoms were confined to one lower limb.\n"
        )

        kept_ranges = core.subtract_source_ranges(
            text,
            [(0, len(text))],
            core.single_case_boilerplate_exclusion_ranges(text),
        )
        cleaned = "\n".join(text[start:end] for start, end in kept_ranges)

        self.assertIn("60-year-old woman", cleaned)
        self.assertIn("Table 1. Laboratory Data.", cleaned)
        self.assertIn("Glucose 119", cleaned)
        self.assertIn("Atorvastatin was discontinued", cleaned)
        self.assertIn("The diagnosis of SPS", cleaned)
        self.assertIn("Baclofen helped", cleaned)
        self.assertIn("relapsed after corticosteroids", cleaned)
        self.assertIn("However, the combination", cleaned)
        self.assertIn("strength was almost normal", cleaned)
        self.assertIn("moderately hyperactive reflexes", cleaned)
        self.assertIn("A complete blood cell count", cleaned)
        self.assertIn("U/ml remained high", cleaned)
        self.assertIn("Diazepam markedly decreased", cleaned)
        self.assertIn("Figure 1. Magnetic resonance imaging", cleaned)
        self.assertIn("40-year-old female", cleaned)
        self.assertIn("Fig. 1. Computed tomography", cleaned)
        self.assertIn("Present 40 F SPS", cleaned)
        self.assertIn("In our case, pathological findings", cleaned)
        self.assertIn("FIG. 2. Cutaneous silent period", cleaned)
        self.assertIn("This patient's symptoms", cleaned)
        self.assertNotIn("nejm.org", cleaned)
        self.assertNotIn("From the Departments", cleaned)
        self.assertNotIn("Internal Medicine Journal", cleaned)
        self.assertNotIn("J Neurol", cleaned)
        self.assertNotIn("16 SPS patients", cleaned)
        self.assertNotIn("Key words", cleaned)
        self.assertNotIn("Introduction", cleaned)
        self.assertNotIn("main target of humoral", cleaned)
        self.assertNotIn("From the First Department", cleaned)
        self.assertNotIn("Generic citation", cleaned)
        self.assertNotIn("Elsevier", cleaned)
        self.assertNotIn("PII:", cleaned)
        self.assertNotIn("Piccolo and", cleaned)
        self.assertNotIn("Nicholas 55 M", cleaned)
        self.assertNotIn("Nicholas case", cleaned)
        self.assertNotIn("Aso et al.", cleaned)
        self.assertNotIn("Acknowledgements", cleaned)
        self.assertNotIn("CLINICAL/SCIENTIFIC NOTES", cleaned)

    def test_single_case_exclusions_remove_batch012_footer_noise_and_appended_article(self) -> None:
        text = (
            "A 60-year-old man with stiff-person syndrome required ventilation.\n"
            "Case reports in the neurology litera-\n"
            "ture mention that patients with Stiff-Person Syndrome received anaesthesia. "
            "Johnson and Millar report a case in a 46-year-old woman.\n"
            "In our case, the patient remained sedated and stiffness returned after muscle relaxant wore off.\n"
            "N. Haslam\nK. Price\nNewcastle General Hospital,\nNewcastle upon Tyne NE4 6BE, UK\n"
            "E-mail: jahaslam@example.test\n"
            "M. Obara\nS. Sawamura\nM. Chinzei\nK. Komatsu\nK. Hanaoka\n"
            "Tokyo University School of Medicine,\nTokyo, Japan\nE-mail: obara@example.test\n"
            "Psychosomatics 43: 3, May-June 2002\n"
            "The patient needed odansetron.\n"
            "Received January 18, 2002; revised February 28, 2002; accepted March 5, 2002.\n"
            "From the Department of Psychiatry and Psychology.\n"
            "Copyright 2002 The Academy of Psychosomatic Medicine.\n"
            "243\n\nCase Reports\n"
            "crying episodes were reported.\n"
            "Figure 1 Myokymic discharges were recorded.\n"
            "J Neurol Neurosurg Psychiatry 2002;73:343-350 345\nwww.jnnp.com\n"
            "normal IgG index was documented.\n"
            "Letters 939\nwww.annrheumdis.com\n"
            "Downloaded from annrheumdis.\n"
            "RESULTS AND DISCUSSION\n"
            "Group characteristics were comparable. SSZ may be useful in active juvenile onset SpA.\n"
            "ACKNOWLEDGEMENT\nSupported by Kabi.\n"
            "Journal of\nCLINICAL\nNEUROMUSCULAR\nDISEASE\nVolume 14, Number 2\nDecember 2012\n"
            "From the Department of Neurology.\n"
            "Copyright 2012 by Lippincott Williams & Wilkins\nShort Report72\n"
            "extremities were normal.\n"
            "Correspondence: M. I. Vicente-Valor, Pharmacy Department, Hospital Universitario de la Ribera.\n"
            "Journal of Clinical Pharmacy and Therapeutics , 2013, 38, 71-73 doi: 10.1111/example\n"
            "Blackwell Publishing Ltd 71\n"
            "tremor-like movement after prolonged standing.\n"
        )

        kept_ranges = core.subtract_source_ranges(
            text,
            [(0, len(text))],
            core.single_case_boilerplate_exclusion_ranges(text),
        )
        cleaned = "\n".join(text[start:end] for start, end in kept_ranges)

        self.assertIn("A 60-year-old man", cleaned)
        self.assertIn("In our case, the patient remained", cleaned)
        self.assertIn("The patient needed odansetron", cleaned)
        self.assertIn("crying episodes were reported", cleaned)
        self.assertIn("Figure 1 Myokymic discharges", cleaned)
        self.assertIn("normal IgG index", cleaned)
        self.assertIn("extremities were normal", cleaned)
        self.assertIn("tremor-like movement", cleaned)
        self.assertNotIn("46-year-old woman", cleaned)
        self.assertNotIn("Newcastle General", cleaned)
        self.assertNotIn("Tokyo University", cleaned)
        self.assertNotIn("Psychosomatics 43", cleaned)
        self.assertNotIn("Academy of Psychosomatic", cleaned)
        self.assertNotIn("jnnp.com", cleaned)
        self.assertNotIn("juvenile onset SpA", cleaned)
        self.assertNotIn("CLINICAL\nNEUROMUSCULAR", cleaned)
        self.assertNotIn("Blackwell Publishing", cleaned)

    def test_single_case_defers_sms_sample_cohort_source(self) -> None:
        source_path = self.write_text_json(
            "9090",
            "Abstract\n"
            "Stiff-man syndrome is associated with GAD antibodies. We isolated five brain-reactive "
            "human monoclonal antibodies from peripheral blood of a patient newly diagnosed with SMS. "
            "The antigen was recognized by 12% (3/25) of SMS sera and 13% (2/15) of SMS cerebrospinal "
            "fluid (CSF) samples.",
        )
        prepared = core.prepare_source(paper_id="9090", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9090",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertEqual(result.registry_row["defer_reason"], "not_single_case_for_stage07_singlecase")

    def test_single_case_hyperekplexia_source_uses_actual_case_window(self) -> None:
        source_path = self.write_text_json(
            "9091",
            "Case report\n"
            "A 14-year-old girl with hyperekplexia having GLRB mutations\n"
            "Jun Mine a, Takeshi Taketani a\n"
            "Received 27 July 2012; accepted 24 October 2012\n"
            "Abstract\n"
            "The patient was a 14-year-old girl with mild mental retardation. "
            "Generalized stiffness was noted immediately after birth and GLRB gene mutations were identified.\n"
            "Keywords: Hyperekplexia; GLRB; Startle disease\n"
            "1. Introduction\n"
            "Generic glycinergic neurotransmission background and previously reported cases.\n"
            "Herein, we report the case of a 14-year-old girl with hyperekplexia who had novel GLRB mutations.\n"
            "2. Case report\n"
            "A girl was born at 40 weeks of gestation with a birth weight of 3190 g. "
            "Hypertonia appeared immediately after birth and generalized stiffness accompanied by cyanosis was noted. "
            "At 14 years of age, clonazepam resolved the startle responses.\n"
            "3. Discussion\n"
            "The GLRB gene, which was mutated in our patient, encodes glycine receptor subunit b. "
            "Testing for mutations will be particularly useful if startle responses continue.\n"
            "References\n"
            "[1] Bakker MJ. Startle syndromes.\n",
        )
        prepared = core.prepare_source(paper_id="9091", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9091",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("The patient was a 14-year-old girl", text)
        self.assertIn("A girl was born at 40 weeks", text)
        self.assertIn("clonazepam resolved the startle responses", text)
        self.assertNotIn("Jun Mine", text)
        self.assertNotIn("Generic glycinergic", text)
        self.assertNotIn("mutated in our patient", text)
        self.assertNotIn("Bakker MJ", text)

    def test_single_case_batch013_source_ranges_stop_before_generic_discussions(self) -> None:
        childhood_path = self.write_text_json(
            "9092",
            "Case report\n"
            "A case of childhood stiff-person syndrome with striatal lesions: A possible entity distinct from the classical adult form\n"
            "Abstract\n"
            "We report a 7-year-old girl with painful muscle spasms leading to childhood stiff-person syndrome.\n"
            "Case report\n"
            "A 7-year-old girl had painful spasms, negative anti-GAD antibodies, striatal lesions, "
            "intravenous immunoglobulin response, and mild learning disability at 3-year follow-up.\n"
            "3. Dis cussion\n"
            "SPS is an uncommon autoimmune disorder and further reports are needed.\n"
            "References\n1. Generic.\n",
        )
        colon_path = self.write_text_json(
            "9093",
            "C A S E R E P O R T Open Access\n"
            "Paraneoplastic stiff person syndrome associated with colon cancer misdiagnosed as idiopathic Parkinson's disease "
            "worsened after capecitabine therapy\n"
            "Case presentation\n"
            "A 55-year-old woman developed truncal and lower limb stiffness. Capecitabine aggravated stiffness, "
            "diazepam improved symptoms, and fluorouracil was continued without further neurological deterioration.\n"
            "An additional movie file shows this in more detail (see Additional file 1).\n"
            "Conclusions\n"
            "Published data support association of seronegative SPS and cancer in about 25% of cases.\n",
        )

        for paper_id, path, expected, unexpected in (
            ("9092", childhood_path, "3-year follow-up", "further reports are needed"),
            ("9093", colon_path, "without further neurological deterioration", "25% of cases"),
        ):
            prepared = core.prepare_source(paper_id=paper_id, source_path=path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            text = result.target_view_payloads["p1"]["input_text"]
            self.assertIn(expected, text)
            self.assertNotIn(unexpected, text)
            self.assertNotIn("Additional file 1", text)

    def test_single_case_exclusions_remove_batch013_page_furniture_but_keep_tables(self) -> None:
        text = (
            "Abstract\n"
            "A 7-year-old girl had childhood stiff-person syndrome.\n"
            "/C2112012 The Japanese Society of\n"
            "Case report\n"
            "A 7-year-old girl had intermittent pain and difï¬ƒ-\n"
            "0387-7604 /$ - see front matter /C2112012 The Japanese Society of\n"
            "http://dx.doi.org/10.1016/j.braindev.2012.08.003\n"
            "Abbreviations: DWI, diffusion-weighted imaging.\n"
            "E-mail address: example@example.org (M. Sanefuji).\n"
            "www.elsevie r.com/locate/ braindev\n"
            "Brain & Developme nt 35 (2013) 575-578\n"
            "culty in walking for 3 days.\n"
            "576 M. Sanefuji et al. / Brain & Developme nt 35 (2013) 575-578\n"
            "The spasms reduced after immunoglobulin.\n"
            "A 32-year-old male had stiff man syndrome and gradu-\n"
            "Authors’ affiliations: Respiratory Diseases and TB Research Center, Guilan.\n"
            "Corresponding author and reprints: Gilda Aghajanzadeh.\n"
            "E-mail:smassahnia@yahoo.com.\n"
            "Accepted for publication: 2 April 2012\n"
            "ally improved after thymectomy.\n"
            "TABLE 2. Modified Ashworth Scale Scores During the First Day of Intrathecal Baclofen Trial\n"
            "Wrist flexion 2 2 110100\n"
            "Average pain score 6/10 4/10 4/10 1/10\n"
            "Regional Anesthesia and Pain Medicine & Volume 38, Number 3, May-June 2013 Refractory Stiff-Person Syndrome\n"
            "* 2013 American Society of Regional Anesthesia and Pain Medicine 249\n"
            "Protected by copyright.\n"
            " on May 26, 2023 at University Library Zurich.http://rapm.bmj.com/ Regional Anesthesia & Pain Medicine: first published as 10.1097/AAP.0b013e318288b8f9 on 1 May 2013. Downloaded from\n"
            "baclofen dose was increased the following day.\n"
            "The literature reports only 5 cases of GAD-positive SPS patients treated with intrathecal baclofen therapy. "
            "However, these trials used single-injection baclofen. Our patient completed a 4-day trial of intrathecal baclofen.\n"
            "Clearly, further re-\nsearch needs to be done to determine exactly how intrathecal "
            "trialing with baclofen should be accomplished in these patients and whether trialing techniques "
            "will predict outcome of long-\nterm pump therapy.\n"
            "Derksen A, et al . BMJ Case Rep 2013. doi:10.1136/bcr-2013-008667 1\n"
            "Rare disease\n"
            "Anti-GlyR antibodies were found positive.\n"
            "Badzek et al. World Journal of Surgical Oncology 2013, 11:224 Page 2 of 3\n"
            "http://www.wjso.com/content/11/1/224\n"
            "Capecitabine aggravated stiffness.\n"
            "Journal of the Neurological Sciences 337 (2014) 235-237\n"
            "Corresponding author at: 83 Jalan Pergam, Singapore.\n"
            "E-mail address: mervyn.poh@gmail.com(M.Q.W. Poh).\n"
            "0022-510X/$ - see front matter 2013 Elsevier B.V. All rights reserved.\n"
            "http://dx.doi.org/10.1016/j.jns.2013.12.015\n"
            "Contents lists available at ScienceDirect\n"
            "Journal of the Neurological Sciences\n"
            "journal homepage: www.elsevier.com/locate/jns\n"
            "Methylprednisolone was replaced by diazepam.\n"
            "236 M.Q.W. Poh et al. / Journal of the Neurological Sciences 337 (2014) 235-237\n"
            "There was no evidence of residual malignancy.\n"
            "Table 2\n"
            "Anesthesia Management in Patients with SPS\n"
            "(Modified from Ferrandis R et al.)\n"
            "Cases have been performed successfully using total intravenous anesthesia.\n"
            "In the case presented, the patient was receiving a permanent catheter for treatment of his SPS with IVIG.\n"
            "In recent years, patients with other co-morbidities have been identified with SPS. "
            "A review of the literature indicates breast cancer and thymoma.\n"
            "In the case presented, the patient presented with the potential challenge of morbid obesity. "
            "However, monitored anesthesia care avoided exacerbation of his SPS.\n"
            "In summary, MAC with IV anesthetics can be used successfully in patients with SPS for minor procedures.\n"
            "M.E.J. ANESTH 22 (2), 2013\n"
            "Consent\n"
            "Written informed consent was obtained from the patient for publication.\n"
            "Additional file\n"
            "Additional file 1: Paraneoplastic stiff person syndrome.\n"
        )

        kept_ranges = core.subtract_source_ranges(
            text,
            [(0, len(text))],
            core.single_case_boilerplate_exclusion_ranges(text),
        )
        cleaned = "\n".join(text[start:end] for start, end in kept_ranges)

        self.assertIn("7-year-old girl", cleaned)
        self.assertIn("culty in walking", cleaned)
        self.assertIn("spasms reduced", cleaned)
        self.assertIn("32-year-old male", cleaned)
        self.assertIn("ally improved", cleaned)
        self.assertIn("Modified Ashworth Scale Scores", cleaned)
        self.assertIn("Wrist flexion", cleaned)
        self.assertIn("baclofen dose was increased", cleaned)
        self.assertIn("Our patient completed a 4-day trial", cleaned)
        self.assertIn("Anti-GlyR antibodies", cleaned)
        self.assertIn("Capecitabine aggravated", cleaned)
        self.assertIn("Methylprednisolone was replaced", cleaned)
        self.assertIn("no evidence of residual malignancy", cleaned)
        self.assertIn("permanent catheter for treatment", cleaned)
        self.assertIn("avoided exacerbation", cleaned)
        self.assertNotIn("The Japanese Society", cleaned)
        self.assertNotIn("dx.doi.org", cleaned)
        self.assertNotIn("E-mail", cleaned)
        self.assertNotIn("Brain & Developme", cleaned)
        self.assertNotIn("Authors", cleaned)
        self.assertNotIn("Guilan", cleaned)
        self.assertNotIn("Regional Anesthesia", cleaned)
        self.assertNotIn("single-injection baclofen", cleaned)
        self.assertNotIn("further re-", cleaned)
        self.assertNotIn("BMJ Case Rep", cleaned)
        self.assertNotIn("World Journal of Surgical Oncology", cleaned)
        self.assertNotIn("mervyn.poh", cleaned)
        self.assertNotIn("Contents lists", cleaned)
        self.assertNotIn("M.Q.W. Poh et al.", cleaned)
        self.assertNotIn("Anesthesia Management in Patients", cleaned)
        self.assertNotIn("other co-morbidities", cleaned)
        self.assertNotIn("M.E.J. ANESTH", cleaned)
        self.assertNotIn("Written informed consent", cleaned)

    def test_single_case_batch014_source_ranges_exclude_front_matter_and_generic_tails(self) -> None:
        botulinum_path = self.write_text_json(
            "9094",
            "Case Presentation\n"
            "Botulinum Toxin A Injection to Facial and Cervical Muscles in a Patient With Stiff Person Syndrome: A Case Report\n"
            "Abstract\n"
            "We present a case of a 48-year-old male patient with SPS whose facial and neck spasms improved "
            "after botulinum toxin A injections.\n"
            "Introduction\n"
            "Patients with SPS often have generic axial stiffness background.\n"
            "Case Presentation\n"
            "A 48-year-old white man with a history of SPS presented with generalized stiffness. "
            "He received 300 units approximately every 3 months with subjective improvement.\n"
            "Discussion\n"
            "Botulinum toxin is a neuromuscular paralytic toxin.\n",
        )
        anaesthesia_path = self.write_text_json(
            "9095",
            "Anesthesia in a patient with Stiff Person Syndrome\n"
            "Abstract Stiff Person Syndrome (SPS) is a rare disease. Here we present successful endotracheal "
            "intubation on an SPS patient. A 46 years old male patient was discharged walking with aid.\n"
            "PALAVRAS-CHAVE\n"
            "Portuguese duplicate abstract and publisher licence.\n"
            "Introduction\n"
            "Generic anaesthesia background.\n"
            "Case report\n"
            "A 46-year-old male patient was diagnosed with SPS 7 years previously. "
            "He underwent surgery without neuromuscular blocker and was discharged walking with aid again.\n"
            "Discussion\n"
            "Stiff Person Syndrome was first described by Moersch and Woltman.\n",
        )
        hyperekplexia_path = self.write_text_json(
            "9096",
            "Clinical Reasoning:\n"
            "A 35-year-old woman with hyperstartling,\n"
            "stiffness, and accidental falls\n"
            "SECTION 1\n"
            "A 35-year-old woman presented with accidental falls since age 14 and a positive head retraction reflex.\n"
            "Questions for consideration:\n"
            "1. What is the differential diagnosis?\n"
            "GO TO SECTION 2\n"
            "SECTION 2\n"
            "Generic startle-reflex and stiff-person syndrome differential background.\n"
            "GO TO SECTION 3\n"
            "SECTION 3\n"
            "Genetic testing confirmed the Arg271Gln mutation in heterozygosity. "
            "The patient was started on clonazepam and reported notable improvement.\n"
            "DISCUSSION This patient's presentation posed challenges due to absence of family history.\n"
            "As Bakker et al. suggest, extensive history taking is needed in all patients.\n"
            "AUTHOR CONTRIBUTIONS\n"
            "Dr. Russo drafted the manuscript.\n",
        )

        cases = (
            ("9094", botulinum_path, "A 48-year-old white man", ("Patients with SPS often", "Botulinum toxin is")),
            (
                "9095",
                anaesthesia_path,
                "A 46-year-old male patient",
                ("Portuguese duplicate", "Sociedade Brasileira", "Moersch and Woltman"),
            ),
            ("9096", hyperekplexia_path, "Arg271Gln mutation", ("Generic startle-reflex", "AUTHOR CONTRIBUTIONS")),
        )
        for paper_id, path, expected, unexpected_values in cases:
            prepared = core.prepare_source(paper_id=paper_id, source_path=path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            text = result.target_view_payloads["p1"]["input_text"]
            self.assertIn(expected, text)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, text)

    def test_single_case_exclusions_remove_batch014_page_furniture(self) -> None:
        text = (
            "Case report\n"
            "The 69 years old female had stiff person syndrome and elevated blood sugar. "
            "Laboratory tests showed serum C-\n"
            "206 SOOS: LADA type diabetes, celiac diasease, cerebellar ataxia and stiff person syndrome\n"
            "ABBREVIATIONS\n"
            "GAD: glutaminic acid decarboxylase\n"
            "soos_UJ ISZ TUKOR ALAP ANGOL.qxd  2014.05.19.  14:48  Page 206\n"
            "Az alabbi dokumentumot magancelra toltottek le az eLitMed.hu webportalrol. "
            "A dokumentum felhasznalasa a szerzoi jog szabalyozasa ala esik.\n"
            "peptide levels below the normal range.\n"
            "JOURNAL OF THE NATIONAL MEDICAL ASSOCIATION VOL 108, NO 3, AUTUMN 2016 169\n"
            "the patient was diagnosed with SPS and improved with IVIG.\n"
            "Case presentation\n"
            "A 55-year-old Sri Lankan female had progressive difficulty walking. Her lower limbs would\n"
            "Open Access\n"
            "BMC Research Notes\n"
            "*Correspondence: thashichang@gmail.com\n"
            "1 Department of Clinical Medicine, Faculty of Medicine, University of Colombo\n"
            "Full list of author information is available at the end of the article\n"
            "Page 2 of 4Chang et al. BMC Res Notes  (2016) 9:468\n"
            "go into severe painful spasms after unexpected noise.\n"
        )

        kept_ranges = core.subtract_source_ranges(
            text,
            [(0, len(text))],
            core.single_case_boilerplate_exclusion_ranges(text),
        )
        cleaned = "\n".join(text[start:end] for start, end in kept_ranges)

        self.assertIn("serum C-", cleaned)
        self.assertIn("peptide levels", cleaned)
        self.assertIn("improved with IVIG", cleaned)
        self.assertIn("go into severe painful spasms", cleaned)
        self.assertNotIn("ABBREVIATIONS", cleaned)
        self.assertNotIn("eLitMed", cleaned)
        self.assertNotIn("JOURNAL OF THE NATIONAL MEDICAL ASSOCIATION", cleaned)
        self.assertNotIn("BMC Research Notes", cleaned)
        self.assertNotIn("Correspondence", cleaned)

    def test_single_case_batch015_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9097",
                "Case Presentation\n"
                "Stiff Person Syndrome With Evidence of Nonspecific\n"
                "Focal Myositis Secondary to Sustained Muscle Contraction:\n"
                "A Case Report\n"
                "Abstract\n"
                "We report the case of a 36-year-old woman with SPS and nonspecific focal myositis.\n"
                "Introduction\n"
                "Generic background on patients with SPS.\n"
                "Case Presentation\n"
                "A 36-year-old woman presented with progressive rigidity and pain. "
                "Sustained contraction of the biceps was prominent (Figure 1A).\n"
                "PM R 10 (2018) 1426-1430 www.pmrjournal.org\n"
                "1934-1482/$ - see front matter 2018 by the American Academy of Physical Medicine and Rehabilitation\n"
                "https://doi.org/10.1016/j.pmrj.2018.04.007\n"
                "After IVIG therapy, CK levels were mostly normalized.\n"
                "Figure 1. Inspection of the left arm showed hypertrophic change.\n"
                "1427S.-W. No et al. / PM R 10 (2018) 1426-1430\n"
                " 19341563, 2018, 12, Downloaded from https://onlinelibrary.wiley.com/doi/10.1016/j.pmrj.2018.04.007 by test. Creative Commons License\n"
                "Discussion\n"
                "Generic discussion and diagnostic criteria table.\n",
                ("A 36-year-old woman", "After IVIG therapy", "Figure 1"),
                ("Generic background", "pmrjournal", "Downloaded from", "Generic discussion"),
            ),
            (
                "9098",
                "Longitudinal gait assessment in a stiff person syndrome\n"
                "Case description\n"
                "The patient was a 12-year-old boy with progressive stiffness. Further investigations excluded\n"
                "Case report 377\n"
                "0342-5282 Copyright 2018 Wolters Kluwer Health, Inc. All rights reserved.\n"
                "secondary causes, such as neoplasia or autoimmune disorders. Intravenous immunoglobulin was started.\n"
                "Fig. 1\n"
                "Kinematics angles showed improvement from T0 to T2.\n"
                "378 International Journal of Rehabilitation Research 2018, Vol 41 No 4\n"
                "Copyright r 2018 Wolters Kluwer Health, Inc. All rights reserved.\n"
                "BTX-A was injected into the right Trapezius.\n"
                "All procedures followed Good Clinical Practice guidelines.\n"
                "Discussion\n"
                "Generic gait-analysis discussion.\n",
                ("12-year-old boy", "Intravenous immunoglobulin", "BTX-A was injected"),
                ("Wolters Kluwer", "All procedures followed", "Generic gait-analysis"),
            ),
            (
                "9099",
                "Stiff person syndrome with elevated titers of antibodies against cardiolipin and beta2 glycoprotein 1: "
                "a case report and literature review\n"
                "Case report\n"
                "A 40-year male patient was admitted due to limited mouth opening and had\n"
                "Abstract\n"
                "A duplicate abstract summary should not split the case narrative.\n"
                "Keywords: Stiff Person Syndrome\n"
                "Corresponding authors: Example.\n"
                "Accepted 30 April 2018\n"
                "no recent history of trauma and surgery.\n"
                "This study was approved by the institutional review board. Written informed consent was obtained from the patient.\n"
                "A week before admission, the patient had unexplained limited mouth opening. "
                "At D13, anti-cardiolipin and anti-beta2-GPI antibodies were elevated. "
                "At one year follow-up, the symptoms were completely resolved.\n"
                "Discussion\n"
                "Generic antibody literature review.\n",
                ("A 40-year male", "no recent history", "At one year follow-up"),
                ("duplicate abstract", "Corresponding authors", "Written informed consent", "Generic antibody"),
            ),
            (
                "9100",
                "C A S E R E P O R T Open Access\n"
                "A case report of rigidity and recurrent lower limb myoclonus: progressive encephalomyelitis rigidity and myoclonus syndrome, a chameleon\n"
                "Degeneffe et al.\n"
                "Abstract\n"
                "Background: Generic PERM background.\n"
                "Case presentation: We report a case of a 62 year old patient admitted for repetitive myoclonus and rigidity.\n"
                "Conclusions: Generic conclusion.\n"
                "Background\n"
                "Generic background section.\n"
                "Case presentation\n"
                "The clinical story of this 62 year old woman started in 2007 with lower back pain. "
                "Table 1 Diagnostic work-up showed GAD65 95. "
                "She was able to walk without assistance.\n"
                "Degeneffe et al. BMC Neurology  (2018) 18:173 Page 2 of 6\n"
                "Myoclonus rapidly disappeared after treatment.\n"
                "Discussion and conclusions\n"
                "Generic discussion.\n",
                ("62 year old woman", "Table 1 Diagnostic work-up", "Myoclonus rapidly disappeared"),
                ("Generic PERM background", "BMC Neurology", "Generic discussion"),
            ),
            (
                "9101",
                "Treatment of Possible PERM Underlying Malignant Catatonia and Accompanying Psychotic Symptoms With Modified Electroconvulsive Therapy\n"
                "Author Information and web navigation.\n"
                "We prescet a cate of pail: PERM with psychiatric symptoms in a 47-yearok woman. "
                "The patient's vital signs were normal and she had dysarthria, dysphagia and urinary retention.\n"
                "(4 Wbers Alwerr Sieaith. fac, All reghn acervel,\n"
                "A therapeutic regimen of oral diazepam reduced hyperexplexia. "
                "After modified ECT, the patient's agitation and delusions diminished completely.\n"
                "Culay-Sumic et al reported psychiatric symptoms accompanying SPS.\n",
                ("47-yearok woman", "A therapeutic regimen", "delusions diminished"),
                ("Author Information", "Wbers Alwerr", "Culay-Sumic"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch016_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9102",
                "Atypical low back pain: stiff-person syndrome\n"
                "Stiff-person syndrome is a rare neurological condition. We report a case in a 35-year-old woman.\n"
                "CASE-REPORT\n"
                "A 35-year-old woman was referred for a two-year history of low back pain. "
                "Needle electromyography showed continuous motor unit firing. "
                "Figure 1. Needle electromyogram of the paraspinal muscles showed continuous firing. "
                "After one month, the patient was pain-free.\n"
                "DISCUSSION\n"
                "Generic diagnosis and management review.\n",
                ("35-year-old woman", "Figure 1", "pain-free"),
                ("rare neurological condition", "Generic diagnosis"),
            ),
            (
                "9103",
                "Anaesthetic management of a patient with a unique combination of anti-N-methyl-D-aspartate receptor encephalitis and stiff-person syndrome\n"
                "Summary\n"
                "Here, we describe a 26-year-old woman with psychosis, rigidity and fever who was treated under general anaesthesia.\n"
                "BaCkground\n"
                "Generic SPS and anti-NMDAR background.\n"
                "CaSe preSenT aTion\n"
                "A 26-year-old Vietnamese-American woman was admitted with headache and bizarre behaviour. "
                "She had rigidity of the upper and lower extremities and underwent laparoscopic tumour removal.\n"
                "ouTCome and Follow-up\n"
                "She was eventually discharged on POD 24 with concurrent anti-NMDAR encephalitis and SPS.\n"
                "diSCuSSion\n"
                "Generic anaesthetic considerations.\n",
                ("26-year-old woman", "tumour removal", "POD 24"),
                ("Generic SPS", "Generic anaesthetic"),
            ),
            (
                "9104",
                "Stiff-man syndrome in\n"
                "childhood\n"
                "Previous unrelated issue article.\n"
                "little affected. He could not get up from the squatting position. "
                "Electromyography showed continuous motor unit activity and diazepam response. "
                "He was discharged able to perform activities of daily living.\n"
                "CASE HISTORY\n"
                "A boy aged 11 was seen because of intermittent stiffness and painful spasms of the limb muscles. "
                "There was no family history of similar illness.\n"
                "COMMENT\n"
                "The diagnosis in this patient was based on stimulus-sensitive painful muscle spasms and CMUA. "
                "Differential diagnoses such as myotonia and tetanus were considered and excluded.\n"
                "Various subgroups of the stiff-man syndrome have been described.\n"
                "Bilateral hypoperfusion retinopathy\n"
                "A man aged 83 described visual loss.\n",
                ("A boy aged 11", "continuous motor unit activity", "diagnosis in this patient"),
                ("Previous unrelated", "Various subgroups", "Bilateral hypoperfusion"),
            ),
            (
                "9105",
                "Effects of immunotherapy on motor cortex excitability in Stiff Person Syndrome\n"
                "Abstract A number of cortical and spinal excitability variables have been tested in a patient with Stiff Person Syndrome before and after immunotherapy.\n"
                "Keywords Stiff Person Syndrome\n"
                "Introduction\n"
                "Generic cortical excitability background.\n"
                "Case report\n"
                "A 39 year-old woman suffered for 2 years from spasm attacks. "
                "IViG was administered and mycophenolate mofetil was introduced with normalization of anti-GAD antibodies.\n"
                "Neurophysiological testing and results\n"
                "The startle response showed clear reflex responses at T0 and a normal pattern at T2.\n"
                "Discussion\n"
                "Generic cortical physiology discussion.\n"
                "Table 1 Neurophysiological variables tested at baseline (T0) and after immunotherapy.\n"
                "Startle response Exaggerated Not done Normal\n"
                "J Neurol (2010) 257:281-285 283\n"
                "More generic discussion.\n",
                ("39 year-old woman", "mycophenolate mofetil", "Startle response Exaggerated"),
                ("Generic cortical", "More generic discussion"),
            ),
            (
                "9106",
                "Reversible stiff person syndrome presenting as an initial symptom in a patient with colon adenocarcinoma\n"
                "An 82-year-old previously healthy woman complained of neck and upper back stiffness. "
                "Colonofiberoscopy revealed sigmoid colon adenocarcinoma. "
                "The patient's stiff person syndrome responded well to daily diazepam and she recovered completely. "
                "Thus, we believed it to be a paraneoplastic syndrome.\n"
                "272  Y.-L. Liu et al.\n"
                "Stiff person syndrome is a rare neurologic disorder first identified by Moersch and Woltman.\n"
                "Declaration of interest: none.\n",
                ("82-year-old", "colon adenocarcinoma", "paraneoplastic syndrome"),
                ("Moersch and Woltman", "Declaration of interest"),
            ),
            (
                "9107",
                "Angiosarcoma previous article discussion.\n"
                "Rituximab treatment of stiff-person syndrome in a patient with thymoma, diabetes mellitus and autoimmune thyroiditis\n"
                "abstract\n"
                "Stiff-person syndrome is an autoimmune neurological disorder. We report rituximab treatment in a patient with SPS associated with a thymoma.\n"
                "/C2112009 Elsevier Ltd. All rights reserved.\n"
                "1. Introduction\n"
                "Generic SPS immunology.\n"
                "2. Case report\n"
                "A 53-year-old caucasian man was admitted for painful muscle spasms. "
                "Rituximab was followed by complete remission and disappearance of anti-amphiphysin antibodies.\n"
                "3. Discussion\n"
                "Generic B cell discussion.\n"
                "Table 1\n"
                "Change in serum antiglutamic decarboxylase and anti-amphiphysin autoantibodies.\n"
                "Case Reports / Journal of Clinical Neuroscience 17 (2010) 389-391 391\n",
                ("53-year-old caucasian man", "complete remission", "Table 1"),
                ("Angiosarcoma", "Generic B cell"),
            ),
            (
                "9108",
                "Stiff Person Syndrome as the Initial\n"
                "Manifestation of Systemic Lupus\n"
                "A 48-year-old woman with an 8-month history of painful bilateral thoracic and lumbar spasms. "
                "Electromyography revealed continuous activity of the lumbar paraspinal muscles.\n"
                "Potential conflict of interest: Nothing to report.\n"
                "Published online 13 January 2010 in Wiley InterScience.\n"
                "Screening for breast, lung, and ovarian malignancy was negative. "
                "The patient developed photosensitive rash and treatment was initiated with prednisone and hydroxychloroquine.\n"
                "The co-occurrence of additional immunogenic responses in patients with SPS is common.\n",
                ("48-year-old woman", "continuous activity", "prednisone and hydroxychloroquine"),
                ("Potential conflict", "Published online", "co-occurrence"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_exclusions_remove_batch016_page_furniture(self) -> None:
        text = (
            "The patient denied diabetes or similar\n"
            "Editor: N/A.\n"
            "The authors received no financial support for the research, authorship, and publication of this article.\n"
            "Ethical review is not necessary since this is a case report. Informed consent was obtained from the patient for publication.\n"
            "Copyright 2019 the Author(s). Published by Wolters Kluwer Health, Inc.\n"
            "How to cite this article: Zhang CG. Medicine 2019;98:49(e18160).\n"
            "Received: 23 March 2019 / Accepted: 30 October 2019\n"
            "http://dx.doi.org/10.1097/MD.0000000000018160\n"
            "Clinical Case Report Medicine\n"
            "OPEN\n"
            "1\n"
            "symptoms among his family members.\n"
            "Informed consent was obtained from the patient for the description, data utilization, and publication of this report.\n"
            "* Correspondence and reprints.\n"
            "E-mail address: example@example.org (P. Gallien).\n"
            "She also reported lumbar curvature.\n"
            "2 Gharedaghi MH, et al. BMJ Case Rep 2018. doi:10.1136/bcr-2017-223261\n"
            "reminder of important clinical lesson\n"
            "HIV and West Nile virus were negative.\n"
            "Journal of the Neurological Sciences 291 (2010) 118 -120\n"
            "1 Both authors contributed equally to this manuscript.\n"
            "0022-510\n"
            "doi:10.1016/j.jns.2009.12.025\n"
            "Contents lists available at ScienceDirect\n"
            "Journal of the Neurological Sciences\n"
            "journal homepage: www .elsevier.com/locate/jns\n"
            "sign was bilaterally positive.\n"
            "119C. Schmidt et al. / Journal of the Neurological Sciences 291 (2010) 118 -120\n"
            "according to the ABVD protocol.\n"
            "Department of Medicine (Neurology and Rheumatology) , Shinshu University School of Medicine, Matsumoto\n"
            "Received for publication August 26, 2009; A ccepted for publication October 5, 2009\n"
            "Correspondence to Dr. Masayuki Matsuda, matsuma@shinshu-u.ac.jp\n"
            "Inter Med 49: 237-241, 2010 DOI: 10.2169 /internalmedicine.49.2821\n"
            "238\n"
            "Figure 1. Spontaneous motor unit activity disappeared after diazepam.\n"
            "of 375 mg/m2 after obtaining informed consent. The Local\n"
            "Ethical Committee approved rituximab for use in this pa-\n"
            "tient. After starting rituximab, symptoms improved.\n"
            "Inter Med 49: 237-241, 2010 DOI: 10.2169 /internalmedicine.49.2821\n"
            "240\n"
            "thalmopathy was improved.\n"
        )

        kept_ranges = core.subtract_source_ranges(
            text,
            [(0, len(text))],
            core.single_case_boilerplate_exclusion_ranges(text),
        )
        cleaned = "\n".join(text[start:end] for start, end in kept_ranges)

        self.assertIn("The patient denied diabetes", cleaned)
        self.assertIn("symptoms among his family members", cleaned)
        self.assertIn("She also reported lumbar curvature", cleaned)
        self.assertIn("HIV and West Nile virus were negative", cleaned)
        self.assertIn("sign was bilaterally positive", cleaned)
        self.assertIn("according to the ABVD protocol", cleaned)
        self.assertIn("Figure 1. Spontaneous motor unit activity", cleaned)
        self.assertIn("of 375 mg/m2", cleaned)
        self.assertIn("After starting rituximab", cleaned)
        self.assertIn("thalmopathy was improved", cleaned)
        self.assertNotIn("Editor: N/A", cleaned)
        self.assertNotIn("Informed consent was obtained from the patient", cleaned)
        self.assertNotIn("E-mail address", cleaned)
        self.assertNotIn("BMJ Case Rep", cleaned)
        self.assertNotIn("Schmidt et al.", cleaned)
        self.assertNotIn("Contents lists available", cleaned)
        self.assertNotIn("Received for publication", cleaned)
        self.assertNotIn("after obtaining informed consent", cleaned)
        self.assertNotIn("Ethical Committee", cleaned)
        self.assertNotIn("Inter Med 49", cleaned)

    def test_single_case_batch017_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9109",
                "Successful Immune Moderation Treatment for Progressive Encephalomyelitis with Rigidity and Myoclonus\n"
                "Abstract\n"
                "We herein report a case of PERM in a 48-year-old woman with rigidity and myoclonus treated with IV immunoglobulin.\n"
                "Introduction\n"
                "Generic PERM background.\n"
                "Case Report\n"
                "A 48-year-old woman experienced lower limb numbness and low back pain. "
                "Surface electromyography showed co-contractions and diazepam response. "
                "Treatment with IV immunoglobulin, azathioprine and levetiracetam improved limb rigidity and myoclonus.\n"
                "Discussion\n"
                "Generic SPS treatment background.\n"
                "In conclusion, generic case summary.\n",
                ("48-year-old woman", "co-contractions", "azathioprine"),
                ("Generic PERM", "Generic SPS", "In conclusion"),
            ),
            (
                "9110",
                "Stiff Young Woman\n"
                "Background\nGeneric paraneoplastic SPS background.\n"
                "Case Description\n"
                "Without a significant previous medical history, a 36-year-old Caucasian female developed rigidity and painful spasms. "
                "A spiculated mass was identified in the left breast and pathology showed invasive breast cancer.\n"
                "Therapy and course\n"
                "Symptoms vanished completely within 4 weeks following resection.\n"
                "Discussion\n"
                "Generic paraneoplastic discussion.\n"
                "Key points\n"
                "Author block.\n"
                "Fig. 3 Ultrasonography of the left breast with an oval mass lesion.\n"
                "Dankerl P et al. Stiff Young Woman footer.\n",
                ("36-year-old Caucasian female", "invasive breast cancer", "Fig. 3"),
                ("Generic paraneoplastic", "Author block", "Dankerl P et al."),
            ),
            (
                "9111",
                "Role of Osteopathic Manipulative Treatment in the Management of Stiff Person Syndrome\n"
                "Report of Case\n"
                "A 52-year-old man presented with a 10-year history of diagnosed SPS. "
                "He reported current daily symptoms and improved after osteopathic manipulative treatment.\n"
                "Figure. Areas of pain and tissue texture abnormalities.\n"
                "The natural follow-up with this patient would have been to compare GAD antibody levels.\n"
                "Conclusion\n"
                "Generic OMT conclusion.\n"
                "crease in OMT frequency. Three subsequent treatments were scheduled and the patient could lie supine. "
                "The patient has since been lost to follow-up.\n"
                "Discussion\n"
                "Generic SPS mechanism.\n",
                ("52-year-old man", "Figure. Areas", "lie supine"),
                ("Generic OMT", "Generic SPS mechanism", "natural follow-up"),
            ),
            (
                "9112",
                "A Case of Stiff Person Syndrome: Immunomodulatory Effect\n"
                "Abstract: This report demonstrates ineffective benzodiazepine therapy of SPS and successful rituximab and tizanidine therapy.\n"
                "INTRODUCTION\n"
                "Generic SPS introduction.\n"
                "CASE PRESENTATION\n"
                "A 39-year-old woman without underlying malignancy was previously treated with diazepam. "
                "Therapeutic plasma exchange and rituximab were used. "
                "The patient became able to walk and was discharged.\n"
                "DISCUSSION\n"
                "Generic benzodiazepine discussion.\n",
                ("39-year-old woman", "rituximab", "able to walk"),
                ("Generic SPS", "Generic benzodiazepine"),
            ),
            (
                "9113",
                "GAD Antibodies as Key Link Between Chronic Intestinal Pseudoobstruction, Autonomic Neuropathy, and Limb Stiffness\n"
                "Abstract: We are reporting the case of a young woman with severe dysmotility, autonomic neuropathy and stiff limb syndrome.\n"
                "INTRODUCTION\n"
                "Generic CIP background.\n"
                "CONSENT\n"
                "Written informed consent was obtained from the patient for publication.\n"
                "CASE REPORT\n"
                "First symptoms began at the age of 28. At the age of 37 she had spasms in her right leg. "
                "Table 1 Autonomic testing showed absent galvanic skin response.\n"
                "Maier et al Medicine /C15 Volume 94, Number 31, August 2015\n"
                "2 | www.md-journal.com Copyright # 2015 Wolters Kluwer Health, Inc. All rights reserved.\n"
                "Monthly IVIg stabilised body weight and normalized muscle tone.\n"
                "Medicine /C15 Volume 94, Number 31, August 2015 GAD Antibodies in Chronic Intestinal Pseudoobstruction\n"
                "Copyright # 2015 Wolters Kluwer Health, Inc. All rights reserved. www.md-journal.com | 3\n"
                "DISCUSSION\n"
                "Generic CIP discussion.\n",
                ("age of 28", "Table 1", "Monthly IVIg"),
                ("Generic CIP", "Written informed consent", "Wolters Kluwer", "www.md-journal.com"),
            ),
            (
                "9114",
                "A Rare Case of Childhood Stiff Person Syndrome Associated With Pleuropulmonary Blastoma\n"
                "abstract\n"
                "PATIENT DESCRIPTION: A 3-year, 5-month-old girl had painful spasms and recovered after chemotherapy with immunotherapy.\n"
                "Keywords: stiff person syndrome\n"
                "Introduction\n"
                "Generic childhood SPS background.\n"
                "Patient Description\n"
                "This 3-year, 5-month-old girl was admitted for gradually worsening postural tremor. "
                "Electromyography showed continuous motor unit potential at rest. "
                "At her 22-month follow-up she had recovered completely.\n"
                "Discussion\n"
                "Generic paediatric SPS discussion.\n",
                ("3-year, 5-month-old girl", "continuous motor unit", "22-month follow-up"),
                ("Generic childhood", "Generic paediatric"),
            ),
            (
                "9115",
                "Stiff-arm syndrome\n"
                "A 56-year-old woman experienced progressive stiffness and painful spasms in the right arm. "
                "She had anti-GAD antibodies and benefited from diazepam and IV immunoglobulin.\n"
                "Enrique Urrea-Mendoza author block.\n"
                "Figure Limited range of right arm movements\n"
                "The patient demonstrates the extent of her range of movements when asked to abduct and extend the arm.\n"
                "VIDEO\n"
                "AAN advert and web footer.\n",
                ("56-year-old woman", "anti-GAD antibodies", "Figure Limited range"),
                ("author block", "AAN advert"),
            ),
            (
                "9116",
                "Extremely rare coincidence of non-radiographic axial spondyloarthropathy HLA-B27 positive and Stiff Person Syndrome\n"
                "Abstract\n"
                "Our 51-year-old female patient was diagnosed with axial-spondyloarthropathy and SPS 7 years after initial symptoms.\n"
                "Anti-GAD, HLA-B27\n"
                "Introduction\n"
                "Generic SPS and SpA background.\n"
                "A 51-year-old woman presented for the first time with severe pain in the lumbar region. "
                "A laboratory measurement of the anti-GAD antibody in serum was 167 U/mL and EMG showed continuous motor unit activity.\n"
                "Discussion\n"
                "Generic diagnostic delay discussion.\n"
                "hemogram, routine biochemical analysis, acute phase reactants, and tumor markers were normal. "
                "In 2013 a rheumatologist suspected SPS.\n"
                "Conflict of interest\n"
                "None.\n",
                ("51-year-old female patient", "167 U/mL", "suspected SPS"),
                ("Generic SPS", "Generic diagnostic", "Conflict of interest"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch018_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9118",
                "Case Report\nMultiple anesthetics for a patient with\nstiff-person syndrome\n"
                "Authors and affiliations.\n"
                "Abstract Stiff-person syndrome background. This report describes the clinical course for a single patient "
                "with stiff-person syndrome who received general anesthesia on 3 separate occasions.\n"
                "(c) 2016 Elsevier Inc. All rights reserved.\n"
                "1. Introduction\nGeneric anesthesia background.\n"
                "2. Case description\n"
                "A 45-year-old woman with hypertension presented for 3 separate general anesthetics within 2 years. "
                "The first procedure was a total thyroidectomy. She later underwent laparoscopic cholecystectomy and hysterectomy.\n"
                "3. Discussion\nGeneric anesthesia literature.\n"
                "Table Neuromuscular monitoring using peripheral nerve stimulator.\n"
                "A. Cholecystectomy 10:45 4/4 Rocuronium 45 mg.\n"
                "B. Hysterectomy 9:50 0/4 Rocuronium 140 mg.\n"
                "blockade. In 3 studies generic comparison.\n",
                ("single patient", "45-year-old woman", "Rocuronium 45 mg"),
                ("Elsevier", "Generic anesthesia", "3. Discussion", "In 3 studies"),
            ),
            (
                "9119",
                "Anesthetic management of a parturient with Stiff person syndrome for urgent cesarean delivery\n"
                "ABSTRACT\nThe authors describe their management of a parturient with Stiff person syndrome who underwent urgent cesarean delivery.\n"
                "/C2112016 Elsevier Ltd. All rights reserved.\n"
                "Keywords: Stiff person syndrome\n"
                "Introduction\nGeneric parturient SPS background.\n"
                "Case report\n"
                "A 30-year-old nulliparous patient with SPS was admitted at 24 weeks of gestation. She reported limb contractures.\n"
                "Accepted May 2016\nCorrespondence to: Brent T. Boettcher DO.\nE-mail address: bboettcher@mcw.edu\n"
                "International Journal of Obstetric Anesthesia 85\n"
                "required assistance for many activities of daily living. Cesarean delivery was urgently scheduled and epidural anesthesia was used.\n"
                "Discussion\nGeneric neuraxial anaesthesia background.\n",
                ("parturient", "30-year-old", "epidural anesthesia"),
                ("Elsevier", "Correspondence", "E-mail", "Generic neuraxial"),
            ),
            (
                "9120",
                "Anesthetic Considerations of Stiff-Person\nSyndrome: A Case Report\n"
                "Generic introduction and literature.\n"
                "Case Summary\n"
                "A 56-year-old African American woman with a diagnosis of SPS was scheduled for a left hemicolectomy. "
                "Her GAD antibodies were elevated and she was discharged home on postoperative day 4.\n"
                "D iscussion\nGeneric anaesthetic discussion.\nREFERENCES\n1. Reference.\n",
                ("56-year-old", "left hemicolectomy", "postoperative day 4"),
                ("Generic anaesthetic", "REFERENCES"),
            ),
            (
                "9121",
                "Paraneoplastic stiff person syndrome with small cell carcinoma of the bladder and anti-Ri antibodies\n"
                "ABSTRACT\nWe present a case report of paraneoplastic SPS, small cell carcinoma of the bladder and anti-Ri antibodies.\n"
                "1. Introduction\nGeneric paraneoplastic background.\n"
                "2. Case report\n"
                "A 46-year-old man presented with progressive gait disorder and lower-limb stiffness. "
                "Two years later, neurological symptoms reappeared with secondary obstructive acute\n"
                "https://doi.org/10.1016/j.clineuro.2018.08.020\nReceived 7 January 2018; Accepted 11 August 2018\n"
                "Corresponding author.\nE-mail addresses: example@example.org\n0303-8467/ (c) 2018 Elsevier B.V. All rights reserved.\nT\n"
                "renal failure. He was treated with hemodialysis but died due to complications.\n"
                "3. Discussion\nGeneric anti-Ri discussion.\n",
                ("46-year-old man", "renal failure", "died due to complications"),
                ("E-mail", "3. Discussion", "Generic anti-Ri"),
            ),
            (
                "9122",
                "Anti-glutamic acid decarboxylase (GAD) positive cerebellar Ataxia with transitioning to progressive encephalomyelitis with rigidity and myoclonus responsive to immunotherapy\n"
                "ABSTRACT\nWe present a case of a 65-year-old African American male who developed PERM and improved after IVIg.\n"
                "1. Introduction\nGeneric PERM background.\n"
                "2. Methods\nWe searched PubMed and Medline.\n"
                "3. Discussion\n3.1. Case report\n"
                "A 65 year old African-American male was admitted with ataxia, myoclonus, encephalopathy and rigidity. "
                "Anti-GAD antibodies were positive and on day 14 after IVIg his mental status and stiffness improved.\n"
                "3.2. Case discussion\nGeneric discussion of anti-GAD PERM.\nSources of funding\nNone.\n",
                ("65 year old", "Anti-GAD", "day 14 after IVIg"),
                ("2. Methods", "Case discussion", "Sources of funding"),
            ),
            (
                "9123",
                "Femur Neck Fracture in a Patient with\nStiff Person Syndrome\nA Case Report\n"
                "Abstract\nCase: A 57-year-old man with a known case of stiff person syndrome presented with right groin pain. "
                "Right primary cementless total hip replacement was performed.\n\nS\n\ntiff person syndrome generic background.\n"
                "Disclosure: Potential conflicts are online.\nThe patient was informed that data would be submitted for publication, and he provided consent.\n"
                "Case Report\n57-year-old man diagnosed with SPS 2 years ago presented with right groin pain and inability to bear weight. "
                "He underwent total hip replacement and at 24-month follow-up HHS was 87.\n"
                "Discussion\nGeneric fracture discussion.\n",
                ("57-year-old man", "total hip replacement", "24-month follow-up"),
                ("Disclosure", "provided consent", "Generic fracture"),
            ),
            (
                "9124",
                "Chronic intestinal pseudo-obstruction with dilated biliary tract as a spectrum of stiff person syndrome in a nondiabetic patient\n"
                "Abstract\nHere, we report the case of a 44-year-old woman hospitalized for rapidly progressive CIPO and biliary tract dilatation.\n"
                "Keywords: Stiff Person Syndrome\n"
                "Introduction\nGeneric SPS and CIPO background.\n"
                "Case report\nA 44-year-old woman was referred for progressive abdominal pain, weight loss, stiffness and constipation. "
                "Cyclophosphamide and rituximab improved rheumatologic, intestinal and biliary signs.\n"
                "Discussion\nGeneric CIPO discussion.\n",
                ("44-year-old woman", "abdominal pain", "rituximab improved"),
                ("Generic SPS", "Generic CIPO"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch019_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9126",
                "A Case of Treatment Resistance and Complications in a Patient with Stiff Person Syndrome and Cerebellar Ataxia\n"
                "Case description\n"
                "The patient first presented at the age of 50 years with a 9-month history of right lower limb spasms.\n"
                "Columbia University Libraries\nFreely available online\nAbstract\nBackground: generic anti-GAD background.\n"
                "Citation: journal citation and correspondence metadata.\n"
                "There was no previous medical history. Serum and CSF anti-GAD antibodies were positive. IVIg led to symptom resolution.\n"
                "Figure 1. Schematic Timeline of clinical progression.\n"
                "unsteadiness on the right later progressed to ataxia, rituximab was tried, and diabetic ketoacidosis followed high-dose steroids.\n"
                "Discussion\nGeneric GAD discussion.\nReferences\n1. Reference.\n",
                ("50 years", "anti-GAD antibodies", "diabetic ketoacidosis"),
                ("generic anti-GAD", "Citation:", "Generic GAD discussion", "References"),
            ),
            (
                "9127",
                "Stiff Person Syndrome and Type 1 Diabetes Mellitus\n"
                "CASE PRESENTATION\n"
                "A 23-year-old Hispanic woman with SPS had high anti-GAD titres, seizure-like episodes, apheresis, IVIG and new insulin requirements.\n"
                "Received May 6, 2018\nDISCUSSION\nGeneric SPS discussion.\n"
                "Here, we report an insulin-naive patient with known SPS who developed large insulin requirements. "
                "Our patient can be categorized as having T1DM with concomitant insulin resistance.\n"
                "T1DM SPS generic comparison table.\n"
                "Our patient was diagnosed with SPS at 19 years old and developed T1DM 4 years after initial SPS diagnosis.\n"
                "CONCLUSION\nGeneric conclusion.\nCorresponding Author: metadata.\n",
                ("23-year-old", "apheresis", "concomitant insulin resistance", "developed T1DM"),
                ("Received May", "Generic SPS", "generic comparison table", "Corresponding Author"),
            ),
            (
                "9128",
                "Poster 90\nIntrathecal Baclofen Pump Placement in a Patient with Stiff Person Syndrome: A Case Report.\n"
                "Disclosures: no disclosures.\n"
                "Case Description: A 32-year-old woman with stiff person syndrome and POTS had progressive weakness and spasticity.\n"
                "Setting: Inpatient Rehabilitation Unit.\n"
                "Results or Clinical Course: anti-GAD antibody was negative. An intrathecal baclofen pump improved spasticity and rehabilitation goals.\n"
                "Discussion: Baclofen may manage spasticity when oral therapy is inadequate.\n"
                "Conclusions: This case highlights an intrathecal baclofen pump for management of spasticity.\n"
                "Poster 91\nSerotonin Syndrome in Chronic Kidney Disease Patient.\n"
                "Case Description: A 50-year-old woman with serotonin syndrome.\n",
                ("32-year-old", "intrathecal baclofen pump", "anti-GAD antibody was negative"),
                ("Serotonin Syndrome", "50-year-old woman with serotonin"),
            ),
            (
                "9129",
                "Therapeutic Plasma Exchange in a Patient with Paraneoplastic Variant of Stiff-Person Syndrome\n"
                "Authors and departments.\n"
                "Background/Case Studies: We present a 75-y-old female patient with sudden gait impairment and amphiphysin antibodies.\n"
                "Study Design/Methods: She received Solu-Medrol, IVIG, plasma exchange and Rituxan.\n"
                "Results/Findings: She improved when using a walker.\n"
                "Conclusion: TPE may be valuable in patients unresponsive to first-line therapies.\n"
                "Disclosure of Commercial Conflict of Interest\nNothing to disclose.\n",
                ("75-y-old female", "amphiphysin", "Rituxan"),
                ("Authors and departments", "uncommon disorder", "Disclosure of Commercial"),
            ),
            (
                "9130",
                "EFFICACY OF LEVETIRACETAM IN A CASE OF STIFF-PERSON SYNDROME - CASE REPORT\n"
                "The patient signed a term of consent.\n"
                "2 CASE PRESENTATION\n"
                "She was a 50-year-old woman with a three-year history of progressive painful muscular rigidity and spasms. "
                "Anti-GAD was positive and levetiracetam brought remarkable improvement.\n"
                "Figure 1\n3 DISCUSSION\nGeneric levetiracetam discussion.\n4 CONCLUSION\nGeneric conclusion.\n",
                ("50-year-old woman", "Anti-GAD", "levetiracetam brought remarkable improvement"),
                ("term of consent", "Generic levetiracetam", "Generic conclusion"),
            ),
            (
                "9131",
                "Progressive Encephalomyelitis with Rigidity and Myoclonus: Anesthesia and Glycine Receptor Antibodies\n"
                "GlyR antibody-mediated PERM.\n"
                "CASE DESCRIPTION\n"
                "A 40-year-old man with GlyR antibody-mediated PERM presented for resection of a perianal tumor. "
                "Sevoflurane reduced rigidity and surgery concluded after 2 hours.\n"
                "Progressive encephalomyelitis with rigidity and myoclonus (PERM) is a rare autoimmune condition.\n"
                "Accepted for publication July 11, 2013.\nDISCUSSION\nGeneric anaesthesia discussion.\n",
                ("40-year-old man", "perianal tumor", "Sevoflurane reduced rigidity"),
                ("Accepted for publication", "Generic anaesthesia"),
            ),
            (
                "9132",
                "STIFF-PERSON SYNDROME ASSOCIATED WITH MYOTONIC DYSTROPHY TYPE 2 - A CASE REPORT\n"
                "Abstract\nWe describe a case study of a 46-year-old man with severe SPS and myotonic dystrophy type 2.\n"
                "Souhrn\nCzech duplicate abstract.\n"
                "Case report\nA 45-year-old man was admitted with progressive muscle stiffness, diplopia and urinary bladder dysfunction. "
                "Intravenous methylprednisolone helped, and intravenous immunoglobulins led to complete remission.\n"
                "proLekare.cz | 30.6.2023\n106\nSTIFF-PERSON SYNDROME ASSOCIATED WITH MYOTONIC DYSTROPHY TYPE 2 - A CASE REPORT\n"
                "Cesk Slov Ne urol N 2014; 77/ 110(1): 104-108\n"
                "He remained stable on prednisone, baclofen and intravenous immunoglobulins.\n"
                "Discussion\nGeneric myotonic dystrophy discussion.\nReferences\n1. Reference.\n",
                ("46-year-old man", "A 45-year-old man", "complete remission", "remained stable"),
                ("Czech duplicate", "proLekare", "Generic myotonic", "References"),
            ),
            (
                "9133",
                "Scoliosis in Childhood Onset Stiff Person Syndrome\nInfo & Disclosures\nAbstract\n"
                "OBJECTIVE: We report a case.\nBACKGROUND: Generic childhood SPS background.\nDESIGN/METHODS: Case report and review literature. "
                "A 20 years old African American woman recently had a posterior spinal fusion for progressive scoliosis. "
                "Serum anti GAD65 antibody was markedly elevated, IVIG improved prolonged spasms, and she remained wheel chair bound at follow up. "
                "CONCLUSIONS: The diagnosis of SPS should be considered in spinal column deformities.\n"
                "Study Supported by: none\nDisclosure: author disclosures.\n",
                ("20 years old", "posterior spinal fusion", "anti GAD65", "IVIG improved"),
                ("OBJECTIVE", "Generic childhood", "Study Supported", "Disclosure:"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch020_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9134",
                "Rhabdomyolysis in Stiff Person Syndrome: Case Report. (P2.078)\n"
                "Info & Disclosures\nAbstract\nOBJECTIVE: generic objective. BACKGROUND: generic SPS background. "
                "DESIGN/METHODS:A 50-year-old man with recurrent episodes of severe limb and back spasms was diagnosed with SPS by positive serum anti-GAD antibodies. "
                "RESULTS: He had CPK elevations of 55,000 and 22,000 U/L and acute renal failure during both admissions. "
                "CONCLUSIONS: Rhabdomyolysis can be seen in autoimmune SPS exacerbations.\n"
                "Disclosure: author disclosures.\n",
                ("50-year-old man", "CPK elevations", "acute renal failure"),
                ("generic SPS", "Disclosure:"),
            ),
            (
                "9135",
                "Favorable response of botulinum toxin to the axial hypertonia in stiff-person syndrome\n"
                "Case report: The case of a female patient of 20 years with axial hypertonia, lumbar lordosis and positive anti-GAD serum. "
                "Management starts with benzodiazepines, baclofen and immunoglobulin for 4 cycles (2 g/\n"
                "Groupsa Male unrelated table row.\n"
                "kg every 2 months); without sustained response. Botulinum toxin type A improved spasms, pain, posture and independent way.\n"
                "Conclusion: Botulinum toxin can be a therapeutic option.\n"
                "doi:10.1016/j.jns.2015.08.265\nDysferlinopathies in Uruguay: unrelated abstract.\n",
                ("female patient of 20 years", "positive anti-GAD", "Botulinum toxin"),
                ("Groupsa Male", "Dysferlinopathies", "unrelated table"),
            ),
            (
                "9136",
                "Stiff person syndrome in a 64 year old male Filipino:\na case report\n"
                "P. Blanco, N.J. Belonguel. Department of Internal Medicine.\n"
                "A 64-year-old Filipino man presented with progressive left thigh rigidity and involuntary muscle contraction. "
                "EMG NCV studies showed sustained interference patterns and anti-GAD Ab was negative. "
                "Oral benzodiazepine and baclofen afforded relief of spasms and stiffness.\n"
                "doi:10.1016/j.jns.2015.08.91\nDifferentiating apathy and depression in Parkinson disease.\n",
                ("64-year-old Filipino man", "anti-GAD Ab was negative", "baclofen afforded relief"),
                ("Department of Internal Medicine", "Parkinson disease"),
            ),
            (
                "9137",
                "Status spasticus and psoas muscle edema due to anti-GAD antibody associated stiff-man syndrome\n"
                "Abstract\nGeneric ICU background.\n"
                "Case Report\nA 64-year-old man with diabetes presented with severe back pain, leg spasms, psoas myoedema and CPK 16,000 U/l. "
                "He required intubation, vecuronium, IVIG and diazepam and was asymptomatic at 6 months.\n"
                "Discussion\nGeneric differential diagnosis and Table 1.\nReferences\n1. Reference.\n",
                ("64-year-old man", "CPK 16,000", "asymptomatic at 6 months"),
                ("Generic ICU", "Table 1", "References"),
            ),
            (
                "9138",
                "Three cases of elevated IL-1beta in common variable immunodeficiency (CVID) with autoimmune complications\n"
                "RESULTS: Case 1 is a 56 year-old female with Hashimoto thyroiditis. "
                "Case 2 is a 49 year-old male with arthritis. "
                "Case 3 is a 26 year-old female with CVID on IVIG and stiff-person's syndrome with limited improvement on corticosteroids, benzodiazepines and rituximab. "
                "Her flu-like symptoms improved with anakinra but muscle stiffness persisted.\n"
                "CONCLUSIONS: Patients with CVID may have altered cytokines.\n",
                ("26 year-old female", "stiff-person's syndrome", "anakinra"),
                ("56 year-old", "49 year-old", "CONCLUSIONS:"),
            ),
            (
                "9139",
                "Poster 237\nBilateral Hip Fracture During Hospitalization for Spasm Exacerbation in an Adult with Stiff Person Syndrome: A Case Report\n"
                "Disclosures: no relevant relationships.\n"
                "Case/Program Description: The patient is a 47-year-old woman with breast cancer history and stiff person syndrome. "
                "She developed recurrent spasms, severe hip pain, bilateral hip fractures and total hip arthroplasty.\n"
                "Setting: Tertiary care hospital.\nResults: Four months later she had hip pain and spasms.\n"
                "S237Abstracts / PM R 8 (2016) S151-S332\nDiscussion: First reported bilateral hip fractures in SPS.\n"
                "Poster 238\nUnrelated rehabilitation robot case.\n",
                ("47-year-old woman", "bilateral hip fractures", "First reported"),
                ("Disclosures:", "S237Abstracts", "Unrelated rehabilitation"),
            ),
            (
                "9140",
                "Poster 360\nAcute Rehabilitation of a Patient with Stiff Person Syndrome (SPS) and GAD-Antibody Cerebellar Ataxia: A Case Report\n"
                "Disclosures: none.\n"
                "Case/Program Description: The patient presented after months of progressive gait instability and low back pain. "
                "He developed dysarthria, dysphagia and ataxia, had elevated GAD antibody, was treated with IVIG, diazepam and baclofen, and required plasmapheresis.\n"
                "Setting: Acute inpatient rehabilitation.\nResults: Functional Independence Measure declined from 21 to 20.\n"
                "Poster 361\nImpact of early intervention with botulinum toxin in post-stroke spasticity.\n",
                ("progressive gait instability", "elevated GAD antibody", "plasmapheresis"),
                ("Disclosures:", "Poster 361", "post-stroke"),
            ),
            (
                "9141",
                "A novel approach to the treatment of Stiff-Person-Syndrome with Botulinum Toxin: A Case Report\n"
                "Case/Program Description: Patient is a 53-year-old man with low back pain, leg cramps, elevated anti-GAD antibodies and SPS. "
                "Botulinum toxin injections improved pain relief, stiffness, ROM, falls, balance and gait.\n"
                "Poster 259\nBilateral Corpus Callosum Stroke unrelated neurostimulants case.\n",
                ("53-year-old man", "elevated anti-GAD", "Botulinum toxin injections"),
                ("Poster 259", "Corpus Callosum", "neurostimulants"),
            ),
            (
                "9142",
                "How a Flexible Differential Yielded an Elusive Diagnosis: A Case Report\n"
                "Case/Program Description: A 48-year-old woman had lumbar pain, spasticity, immobility, frequent falls and increased lower extremity tone. "
                "Diazepam improved symptoms and anti-GAD-65 antibodies established SPS.\n"
                "Poster 317\nDose-Related Response for Carpal Tunnel Syndrome.\n",
                ("48-year-old woman", "Diazepam improved symptoms", "anti-GAD-65"),
                ("Poster 317", "Carpal Tunnel"),
            ),
            (
                "9143",
                "Rhabdomyolysis and Autoimmune Variant Stiff-person Syndrome\n"
                "Abstract\nGeneric background.\n"
                "Case Report\nA 50-year-old man with recurrent painful back spasms had positive serum GAD antibodies. "
                "During two admissions he had CPK 55,559 U/L and 22,400 U/L with acute kidney injury, leukocytosis, IV fluids and IVIG.\n"
                "Discussion and Conclusions\nGeneric SPS mechanism.\nCorrespondence: metadata.\nReferences\n1. Reference.\n",
                ("50-year-old man", "CPK 55,559", "acute kidney injury"),
                ("Generic background", "Correspondence:", "References"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch021_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9144",
                "Pediatric stiff-person syndrome with renal failure\n"
                "Introduction\nGeneric pediatric SPS background.\n"
                "Case Report\nAn 8-year-old male child had progressive jerky movements, painful spasms, oliguria and high coloured urine.\n"
                "Address for correspondence: metadata.\n"
                "ABSTRACT\nGeneric abstract.\n"
                "His blood counts and MRI were normal. GAD65 was positive, rituximab decreased myoclonus, renal function returned to normal, and spasms subsided.\n"
                "Discussion\nGeneric paediatric discussion.\n"
                "Table 1: Investigations results SPS\nCSF GAD 65 antibody ELISA 116.1 IU/ml. RFT creatinine 3.9 mgm %. Urine myoglobin Positive. Serum CPK 14680.\n"
                "Kumar and Savida: page header.\n",
                ("8-year-old", "GAD65 was positive", "Serum CPK 14680"),
                ("Generic pediatric", "Address for correspondence", "Generic paediatric", "page header"),
            ),
            (
                "9145",
                "Stiff-person Syndrome with Cerebellar Manifestations and Foot Deformities\n"
                "1. Introduction\nGeneric introduction.\n"
                "2. Case report\nA 67-year-old woman with diabetes had episodic lower limb and axial stiffness, frequent falls, deformed feet, anti-GAD 7513 U/mL and response to diazepam.\n"
                "q All authors certify metadata.\n3. Discussion\nGeneric discussion.\n",
                ("67-year-old woman", "anti-GAD 7513", "diazepam"),
                ("Generic introduction", "q All authors", "Generic discussion"),
            ),
            (
                "9146",
                "STIFF PERSON SYNDROME WITH NEGATIVE ANTI-GAD65 ANTIBODIES. CASE REPORT\n"
                "CASE REPORT\nWe present a case of a 42 years old woman admitted for painful neck stiffness, sweating, gait impairment and muscular weakness. "
                "Anti-GAD and anti-Borrelia antibodies were negative, MRI was normal, and plasma exchange achieved slight improvement.\n"
                "ROMANIAN JOURNAL OF NEUROLOGY - VOLUME XII, NO. 3, 2013 157\n"
                "DISCUSSION\nGeneric SPS discussion.\n",
                ("42 years old woman", "Anti-GAD", "plasma exchange"),
                ("ROMANIAN JOURNAL", "Generic SPS discussion"),
            ),
            (
                "9147",
                "Inpatient Physiotherapy Management for Stiff-Person Syndrome: A Case Report\n"
                "Abstract\nIntroduction: generic physiotherapy background. Case Presentation: abstract duplicate. Copyright metadata.\n"
                "1. Introduction\nGeneric introduction.\n"
                "2. Case Presentation\nThe patient was a 65-year-old female with SPS. She received plasmapheresis and 14 sessions of physiotherapy. "
                "Table 1. Timeline of Patient History. November 2013 Hospitalization for plasmapheresis and physiotherapy. "
                "Table 2. PFMP total 35/63 pre-intervention and 49/63 post-intervention. "
                "Table 3. Treatment Type and Progress included ambulation with walker and stair practice.\n"
                "3. Discussion\nGeneric physiotherapy discussion.\n",
                ("65-year-old female", "Table 2", "49/63 post-intervention", "stair practice"),
                ("Copyright metadata", "Generic introduction", "Generic physiotherapy"),
            ),
            (
                "9148",
                "(Pseudo)hemidystonia associated with anti-glutamic acid decarboxylase antibodies - a case report\n"
                "Authors, departments and correspondence metadata.\n"
                "A 55-year-old woman with type 1 diabetes, thyroiditis and vitiligo presented with abnormal painful posturing of the left hemibody. "
                "CSF and serum anti-GAD antibodies were detected, EMG showed continuous motor unit activity, and IVIG improved neck, knee and foot movement. "
                "Figure 1 Clinical features.\n"
                "Disclosure of conflicts of interest\nReferences\n1. Reference.\n",
                ("55-year-old woman", "anti-GAD antibodies", "IVIG improved"),
                ("Authors, departments", "Disclosure of", "References"),
            ),
            (
                "9149",
                "P.026\nAcute lower limb spasticity: Stiff person syndrome responsive to immunomodulatory therapy in an adolescent female\n"
                "Background: generic SPS background. Methods: Case Study Results: Herein we report a 15 year old female presenting with acute spasticity, EMG continuous motor unit activity, GAD65 antibodies >25,000 units/ml, and improvement after rituximab.\n"
                "Conclusions: SPS should be considered in acquired spasticity in children.\n"
                "P.027\nComparative effectiveness of flexible vs rigid neuroendoscopy.\n",
                ("15 year old female", "GAD65 antibodies", "rituximab"),
                ("generic SPS background", "P.027", "neuroendoscopy"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch022_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9150",
                "Spontaneous Bilateral Hip Fractures in Stiff Person Syndrome\n"
                "Case Report\nAuthors.\nDisclosures: none.\n"
                "Case/Program Description: A 46-year-old woman with breast carcinoma developed bilateral lower extremity stiffening, positive anti-GAD, spasms, femoral neck fracture and right hip fracture.\n"
                "Results: She transferred to acute inpatient rehabilitation and improved Functional Independence Measure scores.\n"
                "Level of Evidence: Level V\nS224 Abstracts / PM R 9.\n",
                ("46-year-old woman", "anti-GAD", "right hip fracture"),
                ("Authors.", "Disclosures:", "Level of Evidence"),
            ),
            (
                "9151",
                "Stiff Person Syndrome Without Axial Stiffness\n"
                "Case Report\nDisclosures: none.\n"
                "Case/Program Description: Ms. S had progressive bilateral leg pain, lower-extremity rigidity, high GAD65 antibody titres, diazepam, IVIG, and SPS without axial stiffness or hyperekplexia.\n"
                "Conclusions: Benzodiazepines can be beneficial in these cases.\n"
                "Level of Evidence: Level V\nS224 Abstracts / PM R 9.\n",
                ("Ms. S", "GAD65", "without axial stiffness"),
                ("Disclosures:", "Level of Evidence", "S224 Abstracts"),
            ),
            (
                "9152",
                "Progressive Encephalomyelitis with Rigidity and Myoclonus Associated With Anti-GlyR Antibodies and Hodgkin's Lymphoma: A Case Report\n"
                "Introduction: abstract duplicate.\n"
                "A 60-year-old previously healthy man had progressive gait disturbance, painful spasms, dysphonia, dysphagia, positive anti-GlyR antibodies, plasmapheresis and Hodgkin lymphoma treated with ABVD.\n"
                "Written informed consent was obtained.\nBackground\nGeneric PERM background.\nReferences\n1. Reference.\n",
                ("60-year-old", "anti-GlyR", "ABVD"),
                ("abstract duplicate", "Written informed consent", "Generic PERM", "References"),
            ),
            (
                "9153",
                "O-35 The Stiff Person Syndrome. Neurophysiological findings\n"
                "Background: generic SPS background.\n"
                "Material and methods: We present a 28-year-old male patient with weight loss, orthostatic hypotension, stiffness and painful spasms. "
                "Results: EMG showed continuous involuntary activity, GlyR antibodies were positive, and IVIG plus plasma exchange gave moderate improvement. "
                "Conclusions: Neurophysiology led to the diagnosis.\n"
                "O-36 Listening the sound of neuromuscular junction.\n",
                ("28-year-old male patient", "GlyR antibodies", "plasma exchange"),
                ("generic SPS", "O-36", "neuromuscular junction"),
            ),
            (
                "9154",
                "Longitudinally Extensive Dorsal Column Lesion in a Patient with Longstanding Anti-Hu and Anti-Amphphysin Autoimmunity\n"
                "Results\nIn 2003, a 57-year-old man presented with body spasms, leg stiffness and dysphagia. "
                "He had elevated antiGAD65, later anti-Hu and anti-amphiphysin antibodies, gait ataxia and a C2-T1 dorsal column lesion.\n"
                "Conclusions: Anti-Hu autoimmunity should be considered.\n"
                "Authors/Disclosures\nPresenter metadata.\n",
                ("57-year-old man", "anti-amphiphysin", "C2-T1"),
                ("Authors/Disclosures", "Presenter metadata"),
            ),
            (
                "9155",
                "Double Hit and Excellent Treatment Response\n"
                "Objective: generic objective.\n"
                "Background: A 29-year-old woman with abnormal movements, progressive muscle stiffness, seizures, elevated serum and CSF GAD-65, AMPA antibody and oligoclonal bands. "
                "Results: IVIG, diazepam, lamotrigine and rituximab led to near complete resolution. "
                "Conclusions: SPS-plus can respond to immunotherapies.\n"
                "Disclosure: author disclosures.\n",
                ("29-year-old woman", "GAD-65", "rituximab"),
                ("generic objective", "Disclosure:"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch023_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9160",
                "Bortezomib for the Treatment of Refractory Stiff Person Spectrum Disorder\n"
                "Objective: generic objective.\n"
                "Results: We report a 58-year-old woman with SPSD, elevated serum and CSF anti-GAD, failed IVIG, plasmapheresis, mycophenolate, rituximab, and improved after five cycles of bortezomib.\n"
                "Conclusions: Bortezomib seems promising in patients with SPSD.\n"
                "Disclosure: author disclosures.\n",
                ("58-year-old woman", "five cycles of bortezomib"),
                ("generic objective", "Conclusions:", "Disclosure:"),
            ),
            (
                "9161",
                "A Rare Case of Non-Neoplastic Anti-GAD Positive Cerebellar Ataxia and Progressive Encephalomyelitis with Rigidity and Myoclonus (PERM), Responsive to IVIG\n"
                "Objective: We present a case of a 65-year-old male with cerebellar ataxia, myoclonus, rigidity, anti-GAD antibodies and IVIG response.\n"
                "Background: PERM is a rare subset of SPS with generic relapsing-remitting background.\n"
                "Design/Methods: n/a\n"
                "Results: A 65-year-old African American male post kidney transplant developed ataxia, encephalopathy, myoclonic jerks, axial stiffness, elevated anti-GAD65 >250 IU/mL and improvement after IVIG.\n"
                "Conclusions: The case returned to baseline following IVIG administration.\n"
                "Disclosure: author disclosures.\n",
                ("65-year-old male", "anti-GAD65 >250", "returned to baseline"),
                ("PERM is a rare subset", "Design/Methods", "Disclosure:"),
            ),
            (
                "9162",
                "Stiff Person Syndrome as a Mimic of Parkinsonism\n"
                "Background: generic SPS background.\n"
                "A previously healthy 44-year-old right handed woman presented with dysarthria, left sided stiffness, lumbar back pain, unilateral rigidity, hyperreflexia and positive GAD65.\n"
                "Design/Methods: NA\nResults: NA\n"
                "Conclusions: Age, unilateral rigidity and motoric slowness suggested young-onset Parkinson disease, but the case highlights SPS as a mimic and GAD65 testing.\n"
                "Disclosure: author disclosures.\n",
                ("44-year-old", "positive GAD65", "SPS as a mimic"),
                ("generic SPS", "Design/Methods", "Disclosure:"),
            ),
            (
                "9163",
                "A Stiff Person Case Admitted Phsysical Medicine and Rehabilitation Outpatient Clinic with Low Back Pain\n"
                "Abstract\nStiff-Person Syndrome generic background. We report a case of SPS with Hashimotoâ€™s thyroiditis who complained of low back pain, hyperlordosis, robotic gait, CSF anti-GAD and IVIG response.\n"
                "Keywords: Back pain.\nIntroduction\nGeneric introduction.\n"
                "Case Report\nA 26-year-old female patient had low back pain, abdominal and back muscle contraction, Hashimotoâ€™s thyroiditis, complex partial seizures, CSF anti-GAD 65 +++, IVIG, diazepam, baclofen and improved gait.\n"
                "For case presentation, written consent was obtained from the patient.\n"
                "Discussion\nGeneric discussion.\nThe patientâ€™s pain and stiffness decreased and her gait improved.\n"
                "Conclusion\nIn this case, we described SPS with autoimmune thyroiditis.\n"
                "Informed Consent: metadata.\nPeer-review: metadata.\nAuthor Contributions: metadata.\nFinancial Disclosure: none.\n",
                ("26-year-old female", "CSF anti-GAD 65", "pain and stiffness decreased"),
                ("Generic introduction", "For case presentation", "Peer-review", "Financial Disclosure"),
            ),
            (
                "9164",
                "Cases Neurology Clinical Practice\nAnti-GAD antibody\nsyndrome with\nconcomitant cerebellar\nataxia, stiff person\nsyndrome, and limbic\nencephalitis\n"
                "42-year-old man initially presented with progressive vertigo, leg stiffness, dysarthria, diplopia, anti-GAD antibodies, SPS, autoimmune cerebellar ataxia and IVIG. Serum and CSF paraneoplastic\n"
                "Practical\nImplications\nMultiple neurologic syndromes sidebar.\nDepartment of Neurology metadata.\nCorrespondence to: metadata.\n"
                "panel including voltage-gated potassium channel antibodies was negative. He received plasmapheresis and methylprednisolone for limbic encephalitis and was discharged with outpatient rituximab.\n"
                "DISCUSSION\nGeneric anti-GAD discussion.\n",
                ("42-year-old man", "plasmapheresis", "outpatient rituximab"),
                ("Practical", "Department of Neurology", "Correspondence", "Generic anti-GAD"),
            ),
            (
                "9165",
                "50\nUnrelated asthma abstract.\n"
                "52\nAnti-GAD65 Positive Stiff-Person Syndrome: Novel Association with Common Variable Immune Deficiency\n"
                "RATIONALE: generic SPS background.\n"
                "METHODS: Here we report a case of a middle aged female patient with common variable immunodeficiency on SCIG who developed stiff-person syndrome, EMG findings indicative of SPS and positive GAD65 antibodies.\n"
                "RESULTS: Her SPS symptoms responded to clonazepam, levetiracetam and higher doses of SCIG.\n"
                "CONCLUSIONS: generic PID conclusion.\nJ ALLERGY CLIN IMMUNOL.\n",
                ("middle aged female", "common variable immunodeficiency", "higher doses of SCIG"),
                ("Unrelated asthma", "generic SPS background", "CONCLUSIONS:", "J ALLERGY"),
            ),
            (
                "9166",
                "P72\nProgressive encephalomyelitis with rigidity and myoclonus with antibodies to glycine receptor presenting with temporo-mandibular joint dislocation\n"
                "R. Mahdi Aljedani\nIntroduction. Generic PERM background.\n"
                "Methods. We report a case of severe PERM with anti-GlyR Ab treated with corticosteroids, plasma exchanges and rituximab.\n"
                "Results. A 68- year-old male developed TMJ dislocation, autonomic dysfunction, generalized stiffness, jerky movements, CSF lymphocytic pleocytosis, anti-GlyR antibodies in serum and CSF, PE, methylprednisolone and rituximab.\n"
                "Conclusions. PERM started with unilateral TMJ dislocation and improved with immunosuppression.\n"
                "P73\nNext unrelated vaccine abstract.\n",
                ("68- year-old male", "anti-GlyR antibodies", "immunosuppression"),
                ("Generic PERM", "P73", "unrelated vaccine"),
            ),
            (
                "9167",
                "Stiff Person Syndrome: An Elusive Diagnosis in a Pediatric Patient\n"
                "Background: generic paediatric SPS background. A case is presented of a seventeen-year-old male with one year of symptoms, walker dependence, extreme stiffness, painful spasms, EMG continuous motor unit action potentials, IVIG response, GAD antibody >250 IU/mL and interval IVIG.\n"
                "Design/Methods: NA\nResults: NA\nConclusions: NA\n",
                ("seventeen-year-old male", "GAD antibody >250", "interval IVIG"),
                ("generic paediatric", "Design/Methods", "Results: NA"),
            ),
            (
                "9168",
                "Abstract\nA follow -up of a 59-year -old female patient with stiff person syndrome, diabetes and autoimmune thyroiditis reported painful spasms, elevated GAD, GABAergic therapy and anxiety.\n"
                "Keywords: stiff person syndrome.\nINTRODUCTION\nGeneric SPS introduction.\nClinical observation\nThe female patient X, 59 years old had walking impairment, fear to fall, leg stiffness, diabetes, autoimmune thyroiditis, lumbar hyperlordosis, GAD 265.00 IU/ml in blood and 120.40 IU/ml in CSF, diazepam response, baclofen, clonazepam, agoraphobia and a recommendation for pregabalin plus cognitive behavioral therapy (CBT).\n"
                "Table. Criteria of SPS [3]. Generic diagnostic table.\nFig.1 generic caption.\nThus, in the patient  with SPS, under 3 year medical supervision, rigidity and painful spasms reduced while phobia persisted.\n"
                "DISCUSSION\nA diagnosis of S PS in the patient who received treatment was made on disease criteria, with motor disorders, EMG activity, high GAD in blood and CSF, insulin-dependent diabetes and autoimmune thyroiditis as observed case features.\n"
                "The absence of necrosis generic muscle literature. Titin is a component of myosin.\n"
                "In the course of treatment with GABAergic drugs and correction of endocrinopathy, movement disorders in the patient with SP S decreased significantly, however anxiety and phobic disorders prevailed.\n"
                "Pathogenesis of phobia is generic.\n"
                "When assessing mental status of the patient, avoiding behaviour reached agoraphobia.\n"
                "According to the current standards generic anxiety treatment.\n"
                "It should be noted  that treatment with the use of antidepressants was not efficient for the patient; therefore pregabalin was prescribed in combination with psychotherapy.\n"
                "Cognitive -behavioral therapy generic explanation.\n"
                "Thus, subsequent management  of the patie nt with idiopathic SP S showed GABAergic drugs have long-term permanent effects.\n"
                "REFERENCES\n1. Reference.\n",
                ("59-year", "Clinical observation", "265.00 IU/ml", "pregabalin", "long-term permanent effects"),
                ("Generic SPS introduction", "Table. Criteria", "Titin is a component", "REFERENCES"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch024_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9169",
                "stiff person syndrome An unusual paraneoplastic manifestation with underlying carcinoid tumour\n"
                "Abstract generic SPS background. We report a 58 \n"
                "year old Sri Lankan male with stiff person syndrome, high GAD antibody titre, classical electromyographic changes and underlying carcinoid tumour.\n"
                "Keywords: Paraneoplastic.\n"
                "Address correspondence metadata.\n"
                "CASE REPORT\nA previously healthy 58 year old Sri Lankan male presented with progressive walking difficulty, painful back stiffness, spasms, hyperlordosis and spastic gait.\n"
                "INTRODUCTION\nGeneric South Asia SPS background.\n"
                "were normal. Even though he was initially able to walk, mobility reduced, GAD antibody titre was 1826.0 IU/ml, liver biopsy showed neuroendocrine tumour, IV methylprednisolone, IVIG, diazepam and chemotherapy improved symptoms.\n"
                "DISCUSSION\nGeneric SPS discussion.\n"
                "In our patient with possible \nparaneoplastic SPS secondary to a carcinoid tumour, anti-GAD titers were high.\n"
                "SPS has never been previously reported in association with a carcinoid tumour. Table 1 comparator carcinoid syndromes.\n"
                "In our patient, the primary site of the carcinoid tumour was not found, octreotide was used and he became almost completely asymptomatic.\n"
                "In conclusion, this is the first report of SPS as a paraneoplastic neurologic syndrome with underlying carcinoid tumour.\n"
                "DISCLOSURE\nFinancial support: None.\n",
                ("58 year old Sri Lankan male", "1826.0 IU/ml", "octreotide", "asymptomatic"),
                ("Generic South Asia", "Table 1 comparator", "DISCLOSURE"),
            ),
            (
                "9170",
                "Stiff Person Syndrome Associated \nwith Compartment Syndrome\n"
                "Abstract\nGeneric SPS background. We describe \n"
                "a patient who presented initially with compartment syndrome and was later diagnosed with SPS. This case illustrates varied manifestations.\n"
                "Introduction\nGeneric compartment background.\n"
                "Downloaded from metadata.\n"
                "Case Report  \nA 66-year-old Chinese Singaporean man had left calf pain, raised creatinine kinase, fasciotomy, bilateral hip pain, lower back and bilateral lower limb stiffness, spasms, continuous motor unit activity and anti-GAD antibody >300 U/mL.\n"
                "Downloaded from metadata.\n"
                "The patient was treated for SPS initially with oral clonazepam, baclofen, levetiracetam, prednisolone and intravenous immunoglobulin with gradual improvement.\n"
                "Discussion\nGeneric ACS discussion.\n"
                "Conclusion\nOur case report highlights SPS presenting with compartment syndrome requiring emergent fasciotomy.\n"
                "Statement of Ethics\nConsent metadata.\nDisclosure Statement\nNo conflicts.\n",
                ("66-year-old Chinese", "anti-GAD antibody >300", "gradual improvement", "emergent fasciotomy"),
                ("Generic compartment", "Downloaded from", "Disclosure Statement"),
            ),
            (
                "9171",
                "Proceedings neighbour.\n"
                "We present a case of Stiff Person Syndrome in a 38-year old Filipina presenting with two years history of progressive axial and peripheral muscle rigidity, painful spasms, elevated anti-glutamic acid decarboxylase titers 1,708 IU/mL, continuous involuntary activation on surface electromyography, clonazepam and IVIG response.\n"
                "doi:10.1016/j.jns.2019.10.1 140\n"
                "Restless Legs Syndrome unrelated abstract.\n",
                ("38-year old Filipina", "1,708 IU/mL", "IVIG response"),
                ("Proceedings neighbour", "Restless Legs"),
            ),
            (
                "9172",
                "Background paraneoplastic SPS. We report a 58 year old Sri\n"
                "Lankan male with SPS with a high GAD antibody titre and classical electro myographic changes, who was found to have an underlying carcinoid tumour.\n"
                "doi:10.1016/j.jns.2019.10.1336\n"
                "Neurophysiological study of autonomic nervous system in amyotrophic lateral sclerosis.\n",
                ("58 year old Sri", "high GAD antibody", "carcinoid tumour"),
                ("amyotrophic lateral sclerosis", "Neurophysiological"),
            ),
            (
                "9173",
                "Case Report: Stiff Person Syndrome with Thymoma\n"
                "ABSTRACT Background generic. Case. We herein report a 68-year-old man with gait disturbance due to painful muscle rigidity, anterior mediastinal tumor, high anti-GAD antibody, benzodiazepine and baclofen response, type B2 thymoma and gradual postoperative improvement.\n"
                "KEY WORDS\nINTRODUCTION\nGeneric SPS thymoma background.\n"
                "CASE\nA 68-year-old man was referred with painful muscle rigidity, hyperlordosis, normal MRI and continuous motor unit activity. Table 1 presents laboratory findings.\n"
                "Department of Surgery metadata.\n"
                "Table 1. Laboratory Findings on Admission\nCEA 24 ng/ml AFP 44 ng/ml Anti-aquaporin 4 antibody 15 U/ml Anti-cardiolipin antibody 47 U/ml.\n"
                "Figure 1. Chest computed tomography showed an anterior mediastinal tumor. Prednisolone did not affect symptoms; anti-GAD antibody titer was >2,000; IVIG, benzodiazepine and baclofen improved walking; radical thymectomy showed type B2 thymoma; Figure 3 showed the patient able to walk using a cane.\n"
                "DISCUSSION\nThis patient had neurological symptoms of painful muscle rigidity, anterior mediastinal tumor and high serum anti-GAD antibody, so SPS was considered a PNS associated with thymoma.\n"
                "SPS is a rare neurological syndrome with generic history. Table 2 Literature Review comparator patients.\n"
                "CONCLUSION\nA patient with SPS and thymoma was described. Thymectomy might be useful for symptomatic relief when SPS is associated with thymoma.\n"
                "AS iti CANE junk.\nREFERENCES\n1. Reference.\n",
                ("68-year-old man", "CEA 24", "type B2 thymoma", "able to walk using a cane"),
                ("Generic SPS thymoma", "Table 2 Literature", "AS iti", "REFERENCES"),
            ),
            (
                "9174",
                "Low-Dose Naltrexone for SPS\n"
                "ABSTRACT generic. We present the case of a 59-year-old woman diagnosed with SPS who experienced reduction in symptoms after Low-Dose Naltrexone, with reduced pain, anxiety, depression, agoraphobia and muscle tightness up to 12 months. We conclude generic research is warranted.\n"
                "Introduction\nGeneric LDN background.\n"
                "Case presentation\nLF is a 59-year old woman with long-standing diffuse muscle pain, gabapentin, diazepam, baclofen, IVIG and oxycodone exposure. After compounded oral naltrexone she had 50% pain reduction at six weeks and dramatic reductions at twelve months.\n"
                "Discussion\nGeneric LDN discussion.\nConflict of Interest: none.\n",
                ("59-year-old woman", "LF is a 59-year old", "50% pain reduction", "twelve months"),
                ("Generic LDN", "We conclude generic", "Conflict of Interest"),
            ),
            (
                "9175",
                "Trismus as a Presenting Symptom in a Case of Progressive Encephalopathy with Rigidity and Myoclonus\n"
                "Abstract\nIn this report we present a clinical case of trismus. The patient developed respiratory insufficiency, myoclonus, ovarian teratoma, seronegative PERM, plasmapheresis response and later death from complications.\n"
                "Downloaded from metadata.\n"
                "Introduction generic.\nCase Presentation  \nA 73-year-old woman presented with trismus, respiratory distress, cyanosis, hypoxic cardiac arrest, myoclonus, ovarian teratoma, negative anti-GAD, anti-NMDA, anti-GlyR and anti-amphiphysin antibodies, methylprednisolone and plasmapheresis response.\n"
                "Downloaded from metadata.\n"
                "breathing assistance. During the days following this improvement there were complications, sepsis, intestinal perforations and the patient died of multi organ failure. No autopsy was performed.\n"
                "Discussion\nGeneric trismus discussion.\n",
                ("73-year-old woman", "ovarian teratoma", "plasmapheresis response", "multi organ failure"),
                ("Introduction generic", "Downloaded from", "Generic trismus"),
            ),
            (
                "9176",
                "Rituximab improves not only back stiffness but also stiff eyes in stiff person syndrome\n"
                "ABSTRACT\nObjective: We recorded saccade movements in an SPS patient manifesting with stiff eyes and evaluated rituximab.\n"
                "Methods: We repeatedly conducted recordings on a 42-year-old male SPS patient with slow saccade.\n"
                "Results: VGS velocity improved after rituximab and muscle rigidity and gait instability also improved.\n"
                "Conclusion: Slow saccade improved after rituximab administration.\n"
                "1. Introduction\nGeneric SPS eye movement background.\n"
                "Fig. 1. The time course showed DFPP, IVIG and rituximab; back stiffness improved after DFPP; ocular symptoms and gait instability improved after two courses of rituximab.\n"
                "patients when a stiffness scale was used generic trial background.\n"
                "2. Methods\n2. 1. Case presentation\nThe patient was a 42-year-old man with hyperthyroidism, epilepsy, painful back muscle spasms at age 39, serum anti-GAD 96, 000 IU/mL and CSF anti-GAD 1500 IU/mL.\n"
                "Fig. 2. Experimental trace caption.\n"
                "3. Results\nSuperimposed traces showed slow eye movement after IVIG and improvement after rituximab. VGS velocity significantly increased after rituximab.\n"
                "neurotransmission. For example, generic glycine discussion.\n"
                "Fig. 4. The saccade velocity compared with amplitude showed Vmax increased after rituximab administration.\n"
                "5. Conclusion\nReferences\nSlow saccades were observed in a patient with SPS, which improved after rituximab administration.\n"
                "[1] L. M. Levy reference.\n",
                ("42-year-old male", "96, 000 IU/mL", "VGS velocity", "Vmax increased"),
                ("Generic SPS eye", "stiffness scale", "Experimental trace", "Levy reference"),
            ),
            (
                "9177",
                "anti-GAD antibody-associated stiff person syndrome and cerebellar ataxia\n"
                "2.CaseReport\nA 36-year-old woman had unexplained weight loss, ataxic gait, anti-GAD 65 antibodies 1091 U/mL in serum and CSF, IV methylprednisolone, IVIG, plasma exchange, rituximab, insulin-dependent diabetes, later paraspinal cramps and spasms, and Table 1 shows evidence of exteroceptive reflexes typical of spinal reflex myoclonus.\n"
                "3.Discussion\nWe report a young woman who first presented with cerebellar dysfunction and later developed signs and symptoms consistent with stiff person syndrome.\n"
                "Anti-GAD antibody syndromes encompass generic review.\n"
                "In this case report, we highlight the rare combination of stiff person syndrome and cerebellar ataxia due to anti-GAD antibodies.\n"
                "ConflictsofInterest\nNo conflicts.\nReferences\n1. Reference.\n",
                ("36-year-old woman", "1091 U/mL", "Table 1 shows evidence", "rare combination"),
                ("generic review", "ConflictsofInterest", "References"),
            ),
            (
                "9178",
                "Autoimmune musicogenic epilepsy associated with anti-glutamic acid decarboxylase antibodies and Stiff-person syndrome\n"
                "2 | CASE REPORT\nA 61-year-old right-handed woman with seropositive SPS, diabetes, epilepsy and hypothyroidism had falls, truncal stiffness, spasms, anti-GAD-Ab titer 800 nmol/L, music-triggered seizures and serum showed an elevated anti-GAD-Ab titer.\n"
                "Received: metadata.\n"
                "Abstract unrelated front matter.\n"
                "of 1280 nmol/L. Brain MRI was normal. She was treated with levetiracetam and later IVIG with improvement of SPS symptoms, glycemic values and seizure frequency.\n"
                "3 | DISCUSSION\nWe describe an association between MRS and SPS related to anti-GAD-Ab, with musicogenic reflex seizures in SPS.\n"
                "Musicogenic epilepsy is a rare generic discussion.\n"
                "Epileptic seizures should be suspected in patients with SPS and new onset paroxysmal episodes. Immunotherapy should be considered.\n"
                "ACKNOWLEDGMENTS\nNo support.\n"
                "TABLE 1 Overview of case reports on anti-GAD-Ab and musicogenic reflexive seizures\nPresent \ncase\n1 61y, Female, right-handed, onset 58y, apnea automotor seizure, weekly listening and singing religious music, left TL, normal MRI, SPS, hypothyroidism, DM, 1280 nmol/L, levetiracetam, every 2 mo, IVIG.\n"
                "Falip et al comparator patient.\n",
                ("61-year-old", "1280 nmol/L", "IVIG with improvement", "Present \ncase"),
                ("Received:", "generic discussion", "ACKNOWLEDGMENTS", "Falip et"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch025_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9180",
                "Generic neuro-oncology abstract.\n"
                "stiff limb syndrome associated to anti-NMDAR antibodies.\n"
                "MATERIAL AND METHODS: We report the case of a stiff limb syndrome associated to anti-NMDAR antibodies. The patient, a French 44-year male, had painful spasms in both legs, difficulty walking, multiple falls, response to benzodiazepines and baclofen, and no alternative diagnosis.\n"
                "RESULTS: Anti NMDA-R antibodies were identified in blood and CSF; GAD-ab was negative; oncological evaluation was negative; IVIG was given after partial symptomatic improvement.\n"
                "CONCLUSION: This is the first case report of an association between anti NMDA-R and stiff limb syndrome.\n"
                "P11 PRECLINICAL NEURO-ONCOLOGY\nGlioma abstract.\n",
                ("French 44-year male", "Anti NMDA-R antibodies", "IVIG"),
                ("Generic neuro-oncology", "Glioma abstract"),
            ),
            (
                "9181",
                "Stiff-Person Syndrome and Limbic \nEncephalopathy Associated With GAD-antibody: \nA Case Report\n"
                "Objective: generic spectrum objective.\n"
                "Background: generic GADA background.\n"
                "Method: A 29-year-old Chinese woman presented with paroxysmal numbness, memory loss, trunk stiffness, gait problems, hippocampal MR changes, continuous motor unit activity and GAD65 1:320 in serum and CSF.\n"
                "Results: We diagnose GADA associated neurological syndrome presenting with limbic encephalitis and stiff-person syndrome responding to IVIG and glucocorticoid.\n"
                "Conclusion: LE and SPS associated with anti-GADA could coexist and respond to immunomodulatory therapy.\n"
                "References: generic references.\n",
                ("29-year-old Chinese woman", "GAD65 1:320", "IVIG and glucocorticoid"),
                ("generic spectrum", "References:"),
            ),
            (
                "9182",
                "Stiff Limb Syndrome Progressing to Stiff Man Syndrome in a non-diabetic man\n"
                "Objective: generic SPS background.\n"
                "Background: We present a case of non-diabetic man with stiff limb syndrome who progressed to stiff person syndrome.\n"
                "Method: A 52-year-old male from the Congo presented with right lower extremity and abdominal stiffness, walker use, broad-based gait, curled toes and prominent abdominal muscles.\n"
                "Results: Anti-GAD antibody was greater than 50,000, HbA1c was normal, CT showed no neoplasm and diazepam improved ambulation.\n"
                "Conclusion: There was significant improvement with benzodiazepine.\n"
                "References: generic references.\n",
                ("52-year-old male", "greater than 50,000", "diazepam improved"),
                ("generic SPS background", "References:"),
            ),
            (
                "9183",
                "Intranasal midazolam for treating acute respiratory crises in a woman with stiff person syndrome\n"
                "Here, we report the clinical history of a 55-year-old woman affected by SPS since about 10 years, with autoimmune comorbidities, truncal stiffness, lumbar lordosis, spasms, urinary retention, dysphagia and respiratory crises.\n"
                "From the Department metadata.\n"
                "Table Past or concurrent autoimmune comorbidities experienced by the patient\nIdiopathic thrombocytopenic purpura, antiphospholipid syndrome, myasthenia gravis and insulin-dependent diabetes mellitus.\n"
                "with azathioprine and cyclosporine A, rituximab, diazepam and baclofen. Nasal midazolam 2.5 mg in each nostril interrupted respiratory crises; relatives treated more than 20 crises at home.\n"
                "Classification of evidence\nStudy funding\nDisclosure\nAppendix Authors\n",
                ("55-year-old woman", "myasthenia gravis", "more than 20 crises"),
                ("From the Department", "Study funding", "Appendix Authors"),
            ),
            (
                "9184",
                "Effectiveness of Combined\nImmunoglobulin and Glucocorticoid Treatments in a Patient With Stiff Limb Syndrome\n"
                "CASE PRESENTATION\nA 55-year-old female had bilateral lower limb spasms, lumbar hyperlordosis, positive anti-GAD65 IgG, negative anti-amphiphysin antibody and severe painful spasms.\n"
                "TABLE 1 | Paraneoplastic neurological antibody results.\nAnti-GAD antibody IgG ++ 1:32; Anti-GAD65 antibody IgG +++ ; anti-amphiphysin antibody negative.\n"
                "Symptoms improved after IVIG and methylprednisolone; at 8 months she walked with little assistance without painful spasms.\n"
                "DISCUSSION\nAlthough our patient showed typical painful spasms, she was diagnosed with SLS.\n"
                "The age, history, sex and 40 literature patients are generic.\n"
                "Our patientâ€™s muscle spasms were partially reduced by diazepam but improved with IVIG and glucocorticoid.\n"
                "TABLE 2 | Reported cases of stiff limb syndrome.\nComparator patients.\n"
                "CONCLUSION\nIn summary, we reported on an SLS patient with elevated anti-GAD antibody in serum who gained notable effects with combined IVIG and glucocorticoid.\n"
                "DATA AVAILABILITY STATEMENT\nETHICS STATEMENT\n",
                ("55-year-old female", "Anti-GAD65 antibody", "at 8 months", "combined IVIG"),
                ("Comparator patients", "DATA AVAILABILITY", "ETHICS STATEMENT"),
            ),
            (
                "9185",
                "Rehabilitation Challenges in a Rare Combination of Stiff-\nMan Syndrome, Cerebellar Ataxia, and Grave's Disease\n"
                "Disclosures: metadata.\n"
                "Case/Program Description: A\n 33-year-old woman had cerebellar ataxia, Stiff-man Syndrome, dysarthria, stiff lower extremities, ataxic gait, physical therapy and monthly IVIG infusions.\n"
                "Setting: University Hospital\n"
                "Results: Her deficits included dysarthria, stiff lower extremities and ataxic gait.\n"
                "Discussion: Stiff-man syndrome generic background. Our patient developed ataxia prior to stiffness and had initially low anti-GAD titers.\n"
                "Conclusions: This presentation highlights Grave's Disease, Stiff-man Syndrome and cerebellar ataxia with rehabilitation challenges.\n"
                "Level of Evidence: Level V\nPoster 264: unrelated cerebral fat embolism.\n",
                ("33-year-old woman", "monthly IVIG", "low anti-GAD titers"),
                ("Disclosures:", "Poster 264"),
            ),
            (
                "9186",
                "Surgical Treatment for Toe Deformities in\nStiff-Person Syndrome\n"
                "Abstract\nCase: Stiff-person syndrome with a 76-year-old woman suffering painful rigid toe deformities regained walking ability after metatarsal osteotomy and cutting toe extensors.\n"
                "Conclusion: For patients generic surgical conclusion.\n"
                "Fig. 1-A\nFigs. 1-A and 1-B Preoperative photographs of claw toe deformities.\n"
                "Disclosure: conflict metadata.\n"
                "Fig. 2-A\nFigs. 2-A and 2-B Preoperative radiographs showed claw toe deformities.\n"
                "antiglutamic acid decarboxylase generic diagnostic text.\n"
                "Case Report\n76-year-old woman visited with difficulty walking due to painful toe deformities, anti-GAD antibodies, diazepam response, steroid-induced diabetes, metatarsal shortening osteotomy, K-wire fixation and 18-month follow-up walking without foot pain.\n"
                "Discussion\nThe clinical manifestations in the present case were restricted to the left limb and classified as SLS. In summary, a patient with stiff-person syndrome regained walking ability by metatarsal shortening osteotomy and cutting toe extensors.\n"
                "Ryutaro Takeda author metadata.\nReferences\n1. Reference.\n",
                ("76-year-old woman", "Fig. 2-A", "18-month follow-up", "regained walking ability"),
                ("Disclosure:", "generic diagnostic text", "Ryutaro Takeda", "References"),
            ),
            (
                "9187",
                "Exogenous Insulin Injection-Induced Stiff-Person Syndrome in a Patient With Latent Autoimmune Diabetes\n"
                "INTRODUCTION generic.\n"
                "CASE REPORT\nA 43-year-old man with body mass index 28.2 had diabetes, insulin injections, abdominal stiffness, painful spasms, impaired walking, positive GAD65-Ab, diazepam, clonazepam, baclofen and phenobarbital.\n"
                "TABLE 1 | Results of laboratory tests.\nGAD65-Ab 110 U/mL, IA2-Ab 0.31, C-peptide 0.26, HbA1c 13.4.\n"
                "His GAD65-Ab level was positive and LADA was diagnosed.\n"
                "TABLE 2 | Main clinical features of Stiff-person syndrome.\nGeneric diagnostic table.\n"
                "Intravenous immunoglobulin (IVIG) led to a poor response, plasmapheresis improved symptoms, and split insulin degludec twice daily prevented diabetic ketoacidosis with tolerable stiffness.\n"
                "DISCUSSION\nGeneric SPS discussion.\n"
                "CONCLUSION\nIn conclusion, we presented a case of SPS in a patient with LADA and insulin-therapy dilemma.\n"
                "ETHICS STATEMENT\nAUTHOR CONTRIBUTIONS\nREFERENCES\n",
                ("43-year-old man", "GAD65-Ab 110", "split insulin degludec", "LADA"),
                ("Generic diagnostic table", "Generic SPS discussion", "ETHICS STATEMENT", "AUTHOR CONTRIBUTIONS"),
            ),
            (
                "9188",
                "Stiff Person Syndrome and \nAcetylcholine Receptor Ganglionic \nNeuronal Antibodies\n"
                "Abstract\nWe describe the case of a 64 -year-old woman with stiff person syndrome and positivity for acetylcholine receptor ganglionic neuronal antibodies.\n"
                "Introduction\nGeneric AChRGN background.\n"
                "Case Report  \nA 64 -year-old woman had rigidity while walking, involuntary tongue movements, stiff abdomen, robotic gait, GAD65 antibodies, diazepam, baclofen, IVIG, plasmapheresis, rituximab, cyclophosphamide, benign breast biopsy, AChRGN Ab 0.06 and GAD65 Ab 9.\n"
                "Discussion\nUntil now, we have ruled out paraneoplastic causes in our patient and centered on immunological ones.\n"
                "Downloaded from metadata.\n"
                "Our patientâ€™s AChRGN Ab was positive. As far as we are aware, AChRGN Ab have not been reported in SPS, and these antibodies might be elevated due to a direct immunological cause.\n"
                "More studies should be done in patients with similar characteristics.\n"
                "Statement of Ethics\nDisclosure Statement\nFunding Sources\nAuthor Contributions\nReferences\n",
                ("64 -year-old woman", "AChRGN Ab 0.06", "rituximab", "direct immunological cause"),
                ("Generic AChRGN", "Downloaded from", "Statement of Ethics", "Funding Sources"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch026_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9190",
                "Amphiphysin expression in a case of occult cancer with paraneoplastic stiff-person syndrome\n"
                "1 | INTRODUCTION\n"
                "A 35-year-old woman with massive painful rigidity and spasms had swollen axillary lymph nodes, ductal metastatic carcinoma, occult breast cancer, high-titer anti-amphiphysin autoantibodies, continuous co-contraction on electromyography, and paraneoplastic stiff-person syndrome. She did not respond to IVIG or plasma exchange but responded rapidly to high-dose methyl-prednisolone; rigidity and spasms went into remission.\n"
                "Pittock et al. evaluated 71 patients with generic anti-amphiphysin paraneoplastic syndromes.\n"
                "Sommer et al. proved generic antibody transfer background.\n"
                "As far as we know, this is the first case where amphiphysin expression was detected in a metastatic lesion from occult breast cancer with PSP. The present case showed steroid therapy was very effective for the management of stiffness.\n"
                "DISCLOSURE\nConflict of interest: none.\n",
                ("35-year-old woman", "ductal metastatic carcinoma", "high-dose methyl", "steroid therapy"),
                ("Pittock et al.", "Sommer et al.", "DISCLOSURE"),
            ),
            (
                "9191",
                "Multiple antibody positive autoimmune encephalomyelitis; Role of immunosuppression in relapsing disease\n"
                "Background: generic glycine receptor background.\nDesign/Methods: NA\n"
                "Results: A previously healthy 70-year-old female on levothyroxine had jerking legs with stiffness, facial spasm, dysphagia, positive glycine receptor, GAD65 and NMDAR antibodies, relapsing disease, methylprednisolone, IVIG, rituximab and significant improvement in axial and limb rigidity.\n"
                "Conclusions: This case highlights favourable immunosuppression response and association with autoimmune thyroiditis.\n"
                "Disclosure: Dr. Example has nothing to disclose.\n",
                ("70-year-old female", "glycine receptor", "rituximab", "axial and limb rigidity"),
                ("generic glycine", "described previously", "Disclosure:"),
            ),
            (
                "9192",
                "Spastic Dysarthria as a presenting sign of Stiff Person Syndrome\n"
                "Background: generic stroke mimic background.\nDesign/Methods: Cases were included.\n"
                "Results: 56 year old right handed female with hypertension and vitiligo presented with dysarthria and right upper motor neuron facial weakness, negative stroke work-up, anti-GAD antibodies, diazepam and IVIG treatment with improvement of spasticity and intermittent spastic dysarthria.\n"
                "Conclusions: Stiff person syndrome can present with acute spastic dysarthria mimicking stroke. In one retrospective study, patients had generic cohort findings. Our malignancy work up was negative.\n"
                "Study Supported by:\nDisclosure: nothing to disclose.\n",
                ("56 year old right handed female", "anti-GAD antibodies", "intermittent spastic dysarthria", "malignancy work"),
                ("generic stroke", "retrospective study", "Study Supported", "Disclosure:"),
            ),
            (
                "9193",
                "Improvement of Stiff Person Syndrome Symptoms During Pregnancy\n"
                "Objective: generic pregnancy objective.\nBackground: generic estrogen background.\nDesign/Methods: Case\n"
                "Results: A 23-year-old G1P0 woman presented with severe intermittent spasms and stiff gait triggered by startle, bright lights and temperature extremes. Anti-GAD65 antibodies were present. During pregnancy she stopped IVIG and required only 10 mg diazepam daily with continued improvement in SPS symptoms.\n"
                "Conclusions: We present a case of anti-GAD65-associated SPS in a woman who symptomatically improved with pregnancy.\n"
                "Study Supported by: N/A\nDisclosure: nothing to disclose.\n",
                ("23-year-old G1P0 woman", "Anti-GAD65", "continued improvement"),
                ("generic estrogen", "Four reports", "Study Supported", "Disclosure:"),
            ),
            (
                "9194",
                "F58. Unrelated abstract.\n"
                "F59. Spasmodic reflex myoclonus-an characteristic electrophysiological manifestation for the diagnosis of Stiff-person syndrome\n"
                "Introduction: generic SPS and hyperekplexia background.\n"
                "Methods: Multichannel surface electromyogram and accelerometer recordings were conducted over the lumbar paraspinalis, rectus abdominalis, quadriceps and hamstring muscles.\n"
                "Results: The results demonstrated that episodes of spontaneous onset of spasm of the low trunk and legs lasted seconds to minutes. The serum levels of anti-glutamic acid decarboxylase 65 antibodies was 164 IU.\n"
                "Conclusion: The unique EMG pattern can help identify SPS in the SPS patient.\n"
                "doi: 10. 1016/j.clinph. 2018. 04. 222\nF60. Unrelated dystonia abstract.\n",
                ("spontaneous onset of spasm", "164 IU", "unique EMG pattern"),
                ("F58. Unrelated", "Introduction: generic", "Multichannel surface", "F60. Unrelated"),
            ),
            (
                "9195",
                "395 STIFF PERSON SYNDROME WITH REFLEX MYOCLONUS AND OCCUPATIONAL INCAPACITY. CASE REPORT\n"
                "Introduction: generic occupational background.\n"
                "Methods 39 years old worker, purified water seller, with lumbar pain, muscle rigidity, myoclonus, chorea, hypertonic lower limbs, diazepam, and pain aggravation while presenting spasms.\n"
                "Results Electromyography compatible with cervical and lumbar radiculopathy. Magnetic resonance without alterations. Diagnosis was stiff person syndrome with myoclonus version, determining incapacity due to low compatibility with his job.\n"
                "Discussion Progressively severe muscle stiffness generic background.\n"
                "1341 CONTRIBUTION OF WORKPLACE PSYCHOSOCIAL FACTORS unrelated abstract.\n",
                ("39 years old worker", "Electromyography compatible", "incapacity"),
                ("generic occupational", "Discussion Progressively", "CONTRIBUTION OF WORKPLACE"),
            ),
            (
                "9196",
                "Stiff Young Woman: Case report\n"
                "Objective: To describe a rare presentation.\nMethods: Case-report.\n"
                "Results: A 27-year-old young woman developed intermittent paroxysmal distal contractions of the left lower limb, type 1 diabetes mellitus, hyperreactivity to auditory and tactile stimuli, serum anti-glutamic acid decarboxylase (GAD65) positive and CSF confirmation. EMG was compatible with SPS.\n"
                "Conclusions: This case report describes a rare presentation of SPS with focal onset and subsequent generalization.\n",
                ("27-year-old young woman", "GAD65", "EMG was compatible"),
                ("Objective:", "Methods:"),
            ),
            (
                "9197",
                "Stiff Limb Syndrome: A Rare Variant of Stiff Person's Syndrome\n"
                "Objective: generic spectrum objective.\n"
                "Background: A 79-year-old woman presented with progressive bilateral leg weakness and cramps, multiple falls, lower-extremity rigidity, positive GAD65 antibodies, diazepam response and diagnosis of stiff limb syndrome.\n"
                "Conclusions: Our case report describes a patient with focal neurological symptoms and autoimmune work-up in the elderly population.\n"
                "Disclosure: Dr. Example has nothing to disclose.\n",
                ("79-year-old woman", "GAD65 antibodies", "diazepam response"),
                ("generic spectrum", "Disclosure:"),
            ),
            (
                "9198",
                "Clinical pilates-based physiotherapy training program for SPS\n"
                "Abstract\nThe aim of the present report is to show the effects of a clinical pilates-based physiotherapy training program in a case with Stiff Person Syndrome. A 43-year-old female with a 3-year history of SPS participated in the study and improved in range of motion, flexibility, strength, pain and balance parameters.\n"
                "Keywords Stiff Person Syndrome Physiotherapy Pilates training\n"
                "Introduction\nGeneric introduction background.\n"
                "Case presentation\nAE is a 43-year-old women who referred to physiotherapy center with low back pain and gait disturbances associated with SPS, high serum GAD antibodies, recurrent falls, lumbar rigidity, gabapentin, benzodiazepine and weekly IVIG.\n"
                "81Acta Neurologica Belgica (2021) 121:79-85\n1 3\n"
                "Intervention\nCP-based physiotherapy training was performed twice a week during 8 weeks with a certified physiotherapist and a home program.\n"
                "Results\nTable 1 shows the results of balance and functional mobility tests and flexibility measurements. The patient stated the spasm score as 9/10 before treatment and 5/10 after treatment.\n"
                "Discussion\nKaraoglan et al. showed generic literature benefits.\n"
                "Table 1  Comparison of pre-test and post-test of balance, functional mobility and flexibility measurements\nTUG (sec) 7.9 6.1\n30-s CST (repetitions) 19 19\nBerg Balance Scale (point) 52 54\n"
                "83Acta Neurologica Belgica (2021) 121:79-85\n1 3\n"
                "More generic discussion.\n"
                "Table 2  Comparison of pre-test and post-test measurements of Manual Muscle Test and Range of Motion\nBack extension 3 3 4 4 15 20\nHip flexion 4 4 5 5 105 115 107 115\n"
                "Table 3  Comparison of pre-test and post-test Pain Quality Assessment Scale (PQAS)\nCramping 9 5\nHeavy 10 8\nTotal 120 89\n"
                "84 Acta Neurologica Belgica (2021) 121:79-85\n1 3\n"
                "Conclusion\nPhysiotherapy-based clinical Pilates training provided improvements in ROM, flexibility, strength, functional mobility and balance measurements and decreased pain level in the patient with SPS. Although we have promising results, bigger samples are needed.\n"
                "Compliance with ethical standards\nConflict of interest none.\n",
                ("43-year-old female", "AE is a 43-year-old", "TUG (sec)", "Total 120 89", "Physiotherapy-based"),
                ("Generic introduction", "Karaoglan", "Acta Neurologica Belgica", "bigger samples", "Conflict of interest"),
            ),
            (
                "9199",
                "Paraneoplastic Stiff Person Syndrome in Breast Cancer\n"
                "Abstract\nStiff person syndrome generic background. We present the case of a patient with paraneoplastic SPS, presenting with muscle cramps of lower extremities, right breast tumor and positive anti-amphiphysin antibodies.\n"
                " © 2020 The Author(s)\nDownloaded from http://karger.com/crn/article-pdf/example.pdf\n"
                "Introduction\nGeneric SPS introduction.\n"
                "Case Presentation  \nA 68 -year-old, right-handed female presented with bilateral lower-extremity stiffness and severe pain, worsened by stimuli such as light, touch, sound and stress, associated with\n"
                "Downloaded from http://karger.com/crn/article-pdf/12/3/339/2515730/000508942.pdf by University of Calgary user on 09 May 2023\n\nCase Rep Neurol 2020;12:339-347\nDOI: 10.1159/000508942 © 2020 The Author(s). Published by S. Karger AG, Basel\nwww.karger.com/crn\nVacaras et al.: Paraneoplastic Stiff Person Syndrome in Breast Cancer\n\n\n341\n"
                "urine retention. Workup showed breast carcinoma, negative anti-GAD antibodies, positive anti-amphiphysin antibodies, diazepam, clonazepam, baclofen, levetiracetam, botulinum toxin, respiratory failure and death.\n"
                "Discussion\nStiff person syndrome generic prevalence.\nHere, we present the case of a female patient with paraneoplastic SPS. Her main clinical symptoms were muscle cramps, frequent falls, severe muscle rigidity and spasms. In our case, anti-GAD antibodies were negative and anti-amphiphysin antibodies were positive. The particularity of this case was early cancer stage with severe symptoms and partial response.\n"
                "Conclusion\nIn this report, we described the case of a patient with severe symptoms at an early stage of malignancy, only partially responsive to therapy, and with poor prognosis.\n"
                "Acknowledgements\nThanks to clinical teams.\nStatement of Ethics\nConsent metadata.\nReferences\n1. Generic reference.\n"
                "Table 1. Drug dosage administered during hospitalization in our unit\nDiazepam intramuscular 40 30 30 20\nClonazepam oral 1.5 1.5 2 1.25\nLevetiracetam 750 750 750 750\nBaclofen oral 100 100 100 100\n"
                "Table 2. Dalakas criteria of SPS present in our patient\nRigidity in lower extremities and lumbar paraspinal muscles\nSpasms precipitated by noise, light, touch, stress\nPositive anti-amphiphysin antibodies (western blot)\nDownloaded from http://karger.com/crn/article-pdf/example.pdf\n",
                ("68 -year-old", "positive anti-amphiphysin", "respiratory failure", "Table 2. Dalakas", "Positive anti-amphiphysin"),
                ("The Author(s)", "Generic SPS introduction", "Downloaded from", "Acknowledgements", "Statement of Ethics", "References"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch027_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9200",
                "Stiff-Person Syndrome Outpatient Rehabilitation: Case Report\n"
                "Case Presentation\nHistory\nSymptoms started around 2 years ago for our 46-year-old female patient with progressing stiffness, inability to sit, stand, or walk independently, confirmed SPS, clonazepam, baclofen and steroids.\n"
                "Physical Therapy Examination\nTable 1 shoulder and hip flexibility findings.\nTable 2 Berg Balance Scale, Barthel Index, Rivermead Mobility Index and Trunk Impairment Scale.\n"
                "J Neurosci Rural Pract 2020;11:651-653\nCase Report\nArticle published online: 2020-08-20\n\n652\nStiff-Person Syndrome Outpatient Rehabilitation  Khan et al.\nJournal of Neurosciences in Rural Practice   Vol. 11   No. 4/2020\n"
                "Intervention\nThe patient received therapeutic exercises and improved muscle flexibility, balance and function.\n"
                "Institutional Review Board\nFaculty metadata.\nConflict of Interest\nNone declared.\nReferences\n1. Reference.\n",
                ("46-year-old female", "Table 2", "therapeutic exercises"),
                ("J Neurosci Rural", "Institutional Review Board", "Conflict of Interest", "References"),
            ),
            (
                "9201",
                "Progressive Encephalomyelitis With Rigidity and Myoclonus With Thymoma: A Case Report and Literature Review\n"
                "CASE PRESENTATION\nA 60-year-old female patient had unstable walking, stiff legs, falls, dysarthria, myoclonus, positive GAD antibody, thymoma, clonazepam response and telephone follow-up with recurrent swallowing difficulty.\n"
                "Su et al. Progressive Encephalomyelitis With Rigidity\nLaboratory tests were normal.\n"
                "DISCUSSION\nGeneric PERM tumor discussion.\n"
                "TABLE 1 | Eleven reported cases of PERM associated with tumors; comparator cases.\n",
                ("60-year-old female", "positive GAD antibody", "thymoma", "telephone follow-up"),
                ("Su et al.", "DISCUSSION", "Eleven reported cases", "comparator cases"),
            ),
            (
                "9202",
                "Levodopa-responsive progressive encephalomyelitis with rigidity and myoclonus associated with glycine receptor antibodies\n"
                "This 41-year-old man with prior history of hepatitis C developed respiratory distress, fixed limb rigidity, generalized myoclonus, GlyR antibodies in serum and CSF, levodopa response, symptom resolution except mild neurogenic bladder, and stable 24 month follow-up.\n"
                "This case prompted a review of the literature, showing generic GlyR features (Table 1).\n"
                "To the best of our knowledge, this is the first case of GlyR antibody-associated PERM manifested by levodopa responsive axial hypotonia and oculomotor abnormalities.\n"
                "Contents lists available at ScienceDirect\nParkinsonism and Related Disorders\n"
                "negative DATscan favors the notion that dopa-responsiveness was caused by functional abnormalities. In conclusion, this case expands the phenotypic spectrum of GlyR antibody-associated PERM.\n"
                "Informed written consent: Patient gave written informed consent.\nVideo: consent metadata.\n",
                ("41-year-old man", "GlyR antibodies", "levodopa response", "negative DATscan"),
                ("review of the literature", "Contents lists", "Informed written consent", "Video:"),
            ),
            (
                "9203",
                "McArdle Disease vs. Stiff-Person Syndrome: A Case Report Highlighting the Similarities Between Two Rare and Distinct Disorders\n"
                "CASE DESCRIPTION\nA 41-year-old man had exertional weakness, cramping, rhabdomyolysis work-up, initial McArdle diagnosis, later stiffness and spasms, repeat GAD65-Ab positivity, plasma exchange, clonazepam, rituximab and baclofen.\n"
                "DISCUSSION\nThis patient's diagnostic history features progression from one rare pathology to another and highlights nuanced diagnostic challenges.\n"
                "Frontiers in Neurology | www.frontiersin.org 3 November 2020 | Volume 11 | Article 529985\n\nGodbe et al. McArdle Disease and SPS Similarities\n"
                "Following the transition of symptoms, Stiff Person Syndrome was diagnosed and this patient's treatment regimen included plasma exchange and benzodiazepines.\n"
                "ETHICS STATEMENT\nConsent metadata.\nAUTHOR CONTRIBUTIONS\nAuthor metadata.\n",
                ("41-year-old man", "GAD65-Ab", "plasma exchange", "diagnostic challenges"),
                ("Frontiers in Neurology", "ETHICS STATEMENT", "AUTHOR CONTRIBUTIONS"),
            ),
            (
                "9204",
                "Advanced Progression of Scoliosis After Intrathecal Baclofen in an Adult With Stiff Person Syndrome: A Case Report\n"
                "CASE PRESENTATION AND RESULTS\nThis is a 59-year-old woman with CIDP, SPS and stable thoracolumbar scoliotic curvature who had intractable spasms and functional deterioration.\n"
                "Stiff person syndrome is a neuroimmunological disorder characterized by progressive muscular rigidity.\nFunding: None.\nAddress correspondence metadata.\n"
                "immunoglobulin (before SPS diagnosis), gabapentin, pregabalin, positive anti-GAD antibodies, intrathecal baclofen trial, pump placement, baclofen dose titration, reduced spasms, returned ambulation, worsening scoliosis with Cobb angle 40 and 50 degrees, and spinal fusion with functional improvement.\n"
                "DISCUSSION\nThis case report demonstrates intrathecal baclofen may contribute to accelerated scoliotic progression in patients with SPS. Figure 1 baseline x-rays. Downloaded from http://journals.lww.com/aacr by example\nCopyright 2020 International Anesthesia Research Society. Unauthorized reproduction of this article is prohibited.\n2 cases-anesthesia-analgesia.org  A & A PRACTICE\n"
                "Figure 2 follow-up x-rays showed advanced progression. Ultimately this case report demonstrates caution when treating adult SPS patients with intrathecal baclofen.\n"
                "DISCLOSURES\nName: author metadata.\n",
                ("59-year-old woman", "intrathecal baclofen", "Cobb angle 40", "functional improvement"),
                ("Funding:", "Address correspondence", "Downloaded from", "DISCLOSURES"),
            ),
            (
                "9205",
                "Rigid lower back pain: a case of stiff person syndrome\n"
                "Case description: A 61-year-old woman known for Hashimoto thyroiditis had low back pain, truncal rigidity, progressive scoliosis, hyperlordosis, muscle spasms, constant lumbar paraspinal muscular activity, high anti-GAD and favourable evolution with diazepam.\n"
                "Physiopathology and diagnosis: generic anti-GAD pathophysiology.\nTreatment and prognosis: generic IVIG randomized controlled trial and case series.\n"
                "Conclusion: SPS is a rare and challenging diagnosis in patient presenting with chronic LBP; recurrent spasm elicited by stress and hyperlordosis should alert rheumatologists.\n",
                ("61-year-old woman", "high anti-GAD", "diazepam", "recurrent spasm"),
                ("generic anti-GAD", "randomized controlled trial", "case series"),
            ),
            (
                "9206",
                "Treatment of progressive encephalomyelitis with rigidity and myoclonic jerks with rituximab: a case report\n"
                "Case report\nA 60-year-old female presented with paraspinal rigidity, muscle spasms, scoliosis, Hashimoto thyroiditis, ataxic gait, glycine receptor antibodies and rituximab response restoring ability to eat and walk using cross bars.\n"
                "Discussion\nGeneric PERM discussion.\nDisclosure\nNo conflicts.\n",
                ("60-year-old female", "glycine receptor", "rituximab response", "cross bars"),
                ("Generic PERM", "Disclosure"),
            ),
            (
                "9207",
                "Variant form of stiff-man syndrome with neck pain: report of a case treated with muscle afferent block\n"
                "continuous discharges at rest in the trapezius, deltoid, biceps and triceps muscles. Muscle afferent block decreased pain from 83 mm to 39 mm and sustained rigidity disappeared.\n"
                "Key words Stiff-man syndrome.\nIntroduction generic.\n"
                "Case report\nA 64-year-old man was first aware of stiffness and pain in the neck 5 years ago, had rigidity of sternocleidomastoid and trapezius muscles, no response to diazepam and baclofen, and surface electromyograms showed\n"
                "Address correspondence to: Y. Mori\nReceived metadata.\n"
                "The discharges on other muscles were also decreased. Table 1 blood chemistry after MAB. Table 2 clinical characteristics were reported and our patient exhibited six fully. In summary, MAB with local anesthetics and alcohol was effective for pain and muscle rigidity in a patient with a possible variant form of stiff-man syndrome. Further study is desirable.\n"
                "References\n1. Reference.\n",
                ("64-year-old man", "83 mm to 39 mm", "Table 1", "Table 2", "MAB with local anesthetics"),
                ("Key words", "Address correspondence", "Further study", "References"),
            ),
            (
                "9208",
                "A Patient With Atypical Stiff-Person Syndrome: An Electrophysiological Study\n"
                "Abstract\nWe describe a patient with insulin-dependent diabetes mellitus who noticed pain and stiffness in the neck, painful spasms and rigidity of the right thigh, continuous motor unit activity, anti-GAD antibodies and oligoclonal bands.\n"
                "J Clin Neuromusc Dis 2001;3:20-22. Copyright 2001 Lippincott Williams & Wilkins.\n"
                "Case Report\nWe describe a 34-year-old patient with insulin-dependent diabetes mellitus, neck pain, right thigh spasms, anti-GAD antibodies, oligoclonal bands, IVIG, clonazepam and baclofen improvement.\n"
                "From the Institute of Neurological Sciences.\nAddress reprint requests metadata.\nDownloaded from http://journals.lww.com/jcnmd by example\n"
                "using bipolar silver chloride electrodes, Table 1 nerve conduction data, low-threshold cutaneomuscular reflexes and no long tract involvement.\n"
                "Discussion\nWe consider that our patient has a focal stiff-person syndrome. Our patient seems to have a form a focal stiff-person syndrome involving proximal muscles and cervical paraspinal muscles.\nReferences\n1. Reference.\n",
                ("insulin-dependent diabetes", "34-year-old", "using bipolar", "focal stiff-person"),
                ("Copyright", "Downloaded from", "References"),
            ),
            (
                "9209",
                "Stiffness, Spasticity, or Both: A Case Report of Stiff-Person Syndrome\n"
                "Abstract\nWe describe a patient who presented with ill-defined stiffness, exaggerated startle response, elevated anti-GAD antibody titers and sustained response to IVIG.\n"
                "We review the clinical features, pathologic mechanism, and treatment of this disorder.\n"
                "Case Presentation\nThe patient was a 41-year-old woman with cramps, spasms, fatigue, Hashimoto thyroiditis, baclofen and diazepam without improvement, brisk reflexes and normal strength.\n"
                "From the *Department of Neurology.\nCopyright 2002 Lippincott Williams.\n"
                "normal head magnetic resonance image, normal electrodiagnostic study, stiff walking, chest tightness, startle responses, elevated serum anti-GAD65 at 228 U/mL, IVIG treatment, walking 10 meters improved from 14 to 9 seconds, stiffness score improved from 7 to 3, and spasms resolved.\n"
                "Discussion\nThe first description of this entity was by Moersch and Woltman.\nOur patient had most characteristics consistent with the disorder, including elevated anti-GAD antibody titers. This case emphasizes the wide variance of SPS phenotypes.\nOther diseases may resemble SPS, such as myelitis.\nTreatment\nGeneric diazepam and baclofen review. In our patient, the response to a brief course of IVIG treatment was unusual and endured at least 10 months. In summary, key features are stiffness, distribution and startle response.\nReferences\n1. Reference.\n",
                ("41-year-old woman", "anti-GAD65 at 228", "14 to 9 seconds", "10 months"),
                ("We review the clinical", "Copyright", "Moersch", "Other diseases", "References"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch028_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9210",
                "Stiff limb syndrome: a case report\n"
                "Case presentation\nA 49-year-old man had progressive stiffness, painful spasms, anti-GAD antibodies and stiff limb syndrome.\n"
                "* Correspondence author metadata.\n"
                "HIV, syphilis, and HTLV testing were negative. He improved with diazepam, baclofen and immunotherapy.\n"
                "SLS is a variant of stiff person syndrome.\n"
                "Consent\nPublication consent metadata.\n",
                ("49-year-old man", "HIV, syphilis", "improved with diazepam"),
                ("Correspondence", "SLS is a variant", "Consent"),
            ),
            (
                "9211",
                "Stiff person syndrome presenting with sudden onset of shortness of breath and difficulty moving the right arm: a case report\n"
                "Case presentation\nA 27-year-old Hispanic woman had shortness of breath, difficulty moving the right arm, spasms and positive anti-GAD antibodies.\n"
                "* Correspondence author metadata.\n"
                "palpitations and lightheadedness preceded recurrent rigidity; diazepam and IVIG improved symptoms.\n"
                "The GAD antibody is found in a number of neurological conditions.\n"
                "Consent\nConsent metadata.\n",
                ("27-year-old Hispanic woman", "palpitations", "IVIG improved symptoms"),
                ("Correspondence", "The GAD antibody", "Consent"),
            ),
            (
                "9212",
                "Stiff man syndrome and anaesthetic considerations\n"
                "CASE REPORT\nA 55 year old lady suffering from SPS underwent bilateral amputation with combined spinal epidural anaesthesia.\n"
                "Dr. Harsha Shanthanna, Clinical Fellow in Anesthesiology and Pain, McMaster University.\n"
                "Correspondence: author email metadata.\n"
                "desired level; but adequate level was achieved with epidural anaesthesia and she was discharged home without complications.\n"
                "REFERENCES\n1. Generic reference.\n",
                ("55 year old lady", "epidural anaesthesia", "discharged home"),
                ("Dr. Harsha", "Correspondence", "REFERENCES"),
            ),
            (
                "9213",
                "Childhood Stiff-Person Syndrome Improved with Rituximab\n"
                "Case Report\nThe patient is a 12-year-old right-handed Hispanic boy with painful axial contractions, exaggerated startle response, anti-GAD antibody positivity, diazepam partial response and marked improvement with rituximab.\n"
                "Materials and Methods\nA Medline search for stiff-person syndrome and rituximab was performed.\n"
                "Results\nTable 1 included a 41-year-old patient and other published cases.\n"
                "Discussion\nThis childhood case demonstrates the classic features of SPS and the remarkable clinical improvement with rituximab.\n"
                "Although a double-blind placebo-controlled trial described other cases.\n"
                "Downloaded from http://karger.com/crn/example.pdf by user.\n",
                ("12-year-old right-handed Hispanic boy", "marked improvement with rituximab", "This childhood case"),
                ("Materials and Methods", "41-year-old patient", "Although a double-blind", "Downloaded from"),
            ),
            (
                "9214",
                "Case Summary\nStiff Person Syndrome diagnostic dilemma\nA female in her 20s with DM1 had difficulty ambulating, lower extremity weakness, rigidity, positive anti-GAD antibodies and IVIG response.\n"
                "Clini Cal Medi Cine i nsights journal front matter.\n"
                "and lower extremities, and the strengt improved after therapy with diazepam and baclofen.\n"
                "d iscussion\nGeneric SPS background.\nOur patient did respond well to triple therapy: diazepam, baclofen, and IVIG.\n"
                "Author Contributions\nAuthor metadata.\n",
                ("female in her 20s", "lower extremities", "triple therapy"),
                ("Clini Cal", "Generic SPS background", "Author Contributions"),
            ),
            (
                "9215",
                "Stiff-Person Syndrome and Graves' Disease: A Pediatric Case Report\n"
                "A 9-year-old female child presented with falls, diffuse leg pain, progressive gait disorder and Graves disease.\n"
                "Keywords pediatric SPS.\n"
                "A 9-year-old right-handed female child had positive anti-GAD antibodies, diazepam, IVIG and thyroid treatment.\n"
                "1 Department of Neurology author metadata.\n"
                "she had little clinical improvement until methylprednisolone and plasmapheresis were given.\n"
                "Discussion\nGeneric paediatric SPS review.\n"
                "In conclusion, this case highlights the association between SPS and Graves disease.\n"
                "Author Contributions\nAuthor metadata.\n"
                "Table 1. Results T3 T4 TSH TRAb at admission and after treatment.\n"
                "2 Child Neurology Open page footer.\n",
                ("9-year-old female child", "plasmapheresis", "Table 1. Results"),
                ("Department of Neurology", "Generic paediatric", "Author Contributions"),
            ),
            (
                "9216",
                "Therapeutic considerations in a case of progressive encephalomyelitis with rigidity and myoclonus\n"
                "1. Case\nA 63-year-old man developed gait disturbance, myoclonus, anti-GlyR antibodies, tracheostomy, rituximab treatment and stable modified Rankin score of 4.\n"
                "2. Discussion\nWedescribeapatientwithtypicalPERM whose diagnosis was delayed and who continued to need nursing support.\n"
                "More information is needed to characterize the full spectrum of neurologic disorders associated with GlyR antibodies.\n"
                "Acknowledgements\nFunding and author metadata.\n",
                ("63-year-old man", "anti-GlyR antibodies", "nursing support"),
                ("More information is needed", "Acknowledgements"),
            ),
            (
                "9217",
                "Progressive Encephalomyelitis with Rigidity and Myoclonus in an Intellectually Disabled Patient Mimicking Neuroleptic Malignant Syndrome\n"
                "We present a case of 32-year-old male with intellectual disability who developed seizures, rigidity, elevated creatine kinase and PERM mimicking neuroleptic malignant syndrome.\n"
                "CASE REPORT\nA 32-year-old man had anti-glycine receptor antibodies, IVIG, steroids and improvement after treatment.\n"
                "DISCUSSION\nPERM has significant clinical overlap with NMS.\nTable 1. Clinical similarities, differences and diagnostic features in PERM and NMS.\n"
                "described in the literature. It is therefore unsurprising that our patient was initially diagnosed with NMS. Our patient required multiple antiepileptics and seizure control was achieved with IVIG.\n"
                "Conflicts of Interest\nThe authors declare no conflicts.\n",
                ("32-year-old male", "anti-glycine receptor antibodies", "Our patient required"),
                ("Clinical similarities", "Conflicts of Interest"),
            ),
            (
                "9218",
                "Why It Is Not Always Anxiety: A Tough Diagnosis of Stiff Person Syndrome\n"
                "A30-year-oldHaitianfemalewithapastmedicalhistory of anxiety disorder had recurrent panic attacks, muscle stiffness and spasms.\n"
                "Hindawi\nCase Reports in Neurological Medicine\nVolume 2017, Article ID 7431092, 3 pages\nhttps://doi.org/10.1155/2017/7431092\n\n2 CaseReportsinNeurologicalMedicine\n"
                "Table1:DiagnosticcriteriaforgeneralizedanxietydisordercomparedtoDalakascriteriaforSPS. Note. Text in italic represents symptoms/signsforthepatient.\n"
                "andthyroidfunctionwerewithinnormalranges.The patient had elevated GAD antibodies and improved with plasmapheresis.\n"
                "2. Discussion\nGeneric discussion and references.\n",
                ("A30-year-oldHaitianfemale", "Table1:Diagnosticcriteria", "improved with plasmapheresis"),
                ("Hindawi", "Case Reports in Neurological Medicine", "Generic discussion"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch029_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9220",
                "Difficult to Treat Focal, Stiff Person Syndrome of the Left Upper Extremity\n"
                "Hindawi\nCase Reports in Neurological Medicine\nVolume 2017, Article ID 2580620, 3 pages\n"
                "2. Case Presentation\nOurpatientisa46-year-oldmalewithahistoryofHodgkin lymphoma, anti-GAD-65 positive focal SLS, left upper extremity pain, diazepam, baclofen, plasmapheresis, botulinum toxin and no improvement after discharge.\n"
                "3. Discussion\nGeneric anti-GAD background.\n"
                "4. Conclusion\nOur case demonstrates a case of anti-GAD-65 antibody positive focal SLS resistant to benzodiazepines and botulinum toxin injection.\n"
                "Conflicts of Interest\nNo conflicts.\n",
                ("46-year-oldmale", "left upper extremity pain", "resistant to benzodiazepines"),
                ("Hindawi", "Generic anti-GAD", "Conflicts of Interest"),
            ),
            (
                "9221",
                "Anti-glutamic acid decarboxylase antibody syndrome\n"
                "Case Presentation\nA 49-year-old plumber presented with blurred vision, slurred speech, ataxia, anti-GAD antibodies, IV steroids and IVIG response.\n"
                "CSF oligoclonal band was negative.\n"
                "1\n1\n2\n1\n\n"
                "Open Access Case\nReport\n\nDOI:\n 10.7759/cureus.4851\n"
                "How to cite this article\n"
                "Yilmaz F M, Little D, Gallagher M, et al. (June 06, 2019) Anti-glutamate Dehydrogenase Antibody Positive Cerebellar Ataxia and Stiff Person Syndrome Responding to Dual Treatment with Steroids and Intravenous Immunoglobulin: A Case Presentation and Literature Review. Cureus 11(6): e4851.\n"
                "DOI 10.7759/cureus.4851\n\n"
                "anti-GAD was positive with a titer of >250 international units per milliliter.\n"
                "Discussion\nIn addition to hypothyroidism, our patient was diagnosed with type 2 diabetes mellitus.\n"
                "Conclusions\nWe presented a case with anti-GAD ab positive cerebellar ataxia treated with IV steroids followed by IVIG.\n"
                "2019 Yilmaz et al. Cureus 11(6): e4851. DOI 10.7759/cureus.4851\n"
                "2\n of \n6\n\n"
                "Appendices\nTest Value Reference Range\nGlutamic acid decarboxylase >250 <5 IU/mL\n"
                "Additional Information\nDisclosures\nHuman subjects: Consent was obtained.\n",
                ("49-year-old plumber", "anti-GAD was positive", "type 2 diabetes", "Glutamic acid decarboxylase >250"),
                ("Open Access Case", "How to cite this article", "Cureus", "Disclosures", "Consent was obtained"),
            ),
            (
                "9222",
                "Utility of Botulinum Injections in Stiff-Person Syndrome\n"
                "2. Discussion\nOur discussion begins with a case report.\n"
                "A 38-year-old female with anxiety, depression and Grave's disease had diffuse muscle pain, spasms, anti-GAD positivity and improvement after Botox injections.\n"
                "In 2003, Davis and Jabbari reported improvement in a 36-year-old male with stiff-person syndrome.\n"
                "Conflicts of Interest\nNone.\n",
                ("38-year-old female", "improvement after Botox injections"),
                ("36-year-old male", "Conflicts of Interest"),
            ),
            (
                "9223",
                "A Case of Anti-glutamic Acid Decarboxylase-65 Antibody Positive Stiff Person Syndrome Presenting Initially as Acute Peripheral Vestibulopathy\n"
                "Case Presentation\nA 58-year-old previously healthy female patient presented with vertigo, imbalance, back pain, gait ataxia and delayed SPS diagnosis.\n"
                "Discussion\nOur patient initially presented with atypical cerebellar symptoms and improved dramatically with IVIG.\n"
                "Conclusions\nThis case demonstrates delayed diagnosis and treatment.\n"
                "Additional Information\nDisclosures\nHuman subjects: Consent was obtained.\n",
                ("58-year-old previously healthy female", "atypical cerebellar symptoms", "IVIG"),
                ("Disclosures", "Consent was obtained"),
            ),
            (
                "9224",
                "Improving Ambulation and Minimizing Disability with Therapeutic Plasma Exchange in a Stiff-person Syndrome Patient with Recurrent Falls\n"
                "Case Presentation\nA 68-year-old man presented with severe right thigh pain, left leg spasms, recurrent falls, hip fracture, failed IVIg and seven TPE treatments.\n"
                "Discussion\nSPS is a rare disorder characterized by stiffness and spasms.\n"
                "In this patient with symptoms of severe uncontrolled SPS, this patient regained enough mobility to ambulate without assistance.\n"
                "Conclusions\nThis case suggests TPE may offer an effective treatment modality.\n"
                "Additional Information\nDisclosures\nHuman subjects: Consent was obtained.\n",
                ("68-year-old man", "seven TPE treatments", "ambulate without assistance"),
                ("SPS is a rare", "Additional Information", "Disclosures", "Consent was obtained"),
            ),
            (
                "9225",
                "Stiff-Person Syndrome: A Case Report and Review of the Literature\n"
                "Case report\nPresentation\nA 57-year-old female presented with muscle spasms, intermittent diplopia, gaze-evoked nystagmus, IVIG and Blenderm occlusion.\n"
                "Discussion\nThe patient discussed in this case report initially had a left inferior rectus weakness and was diagnosed with SPS.\n"
                "SPS is a rare neurological disorder. There is currently a paucity of literature relating to ophthalmic problems patients with SPS experience.\n"
                "Table 2: Reported neuro-ophthalmic problems associated with stiff-person syndrome.\n"
                "Smith and Storey: Stiff-Person Syndrome\n66\n"
                "References\n1. Reference.\n",
                ("57-year-old female", "gaze-evoked nystagmus", "left inferior rectus weakness"),
                ("SPS is a rare", "paucity of literature", "Table 2", "Smith and Storey", "References"),
            ),
            (
                "9226",
                "Spasms and Myoclonus in a Young Woman With Hashimoto Thyroiditis\n"
                "A 39-year-old woman presented with worsening spasms, urinary retention, Hashimoto thyroiditis, severe rigidity, myoclonus, positive GAD65 antibodies and IVIG response.\n"
                "JAMA Neurology May 2020 Volume 77, Number 5 (Reprinted)\nCopyright 2020 American Medical Association.\n"
                "Diagnosis\nD. Progressive encephalomyelitis with rigidity and myoclonus\n"
                "Discussion\nThe patient's severe clinical features included rigidity and painful spasms, supporting PERM.\n"
                "ARTICLE INFORMATION\nReferences and author metadata.\n",
                ("39-year-old woman", "Diagnosis", "supporting PERM"),
                ("Copyright", "ARTICLE INFORMATION"),
            ),
            (
                "9227",
                "Involuntary movement in stiff-person syndrome with amphiphysin antibodies\n"
                "2. Case presentation\nA 69-year-old man was admitted with progressive stiffness, dyspnea and mandibular involuntary movement. All symp-\n"
                "Editor: Maya Saranathan.\nCorrespondence: author metadata.\nCopyright metadata.\n"
                "toms disappeared after falling asleep. Physical examination showed increased muscle tone and amphiphysin antibodies.\n"
                "3. Discussion\nGeneric SPS background.\nOur patient had prominent neck and arm stiffness and no malignancy after 1 year.\n"
                "Acknowledgments\nAuthor contributions.\n",
                ("69-year-old man", "amphiphysin antibodies", "no malignancy after 1 year"),
                ("Editor:", "Correspondence", "Generic SPS background", "Acknowledgments"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch030_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9228",
                "CASE REPORT Open Access\n"
                "Stiff-person syndrome in a patient with comorbid bipolar and panic disorders: A case report and literature review\n"
                "Background\nGeneric SPS background.\n"
                "Case Report\nThe patient was a 58-year-old white female with SPS, panic disorder with agoraphobia, bipolar I disorder, type 1 diabetes, and chronic leukemia. She trialed fluoxetine, hydroxyzine, valproic acid, propranolol, and clonazepam.\n"
                "Ment Health Clin [Internet]. 2020;10(3):95-9. DOI: 10.9740/mhc.2020.05.095 97\n"
                "Downloaded from http://meridian.allenpress.com/mhc/article-pdf/10/3/95/2494459/mhc_2020_05_095.pdf by user\n"
                "Conclusion\nOur patient with SPS and comorbid bipolar and panic disorder benefited most from benzodiazepine therapy.\n"
                "References\n1. Reference.\n",
                ("58-year-old white female", "valproic acid", "benzodiazepine therapy"),
                ("literature review", "Generic SPS background", "Downloaded from", "References"),
            ),
            (
                "9229",
                "Case Report\nStiff-PersonSyndrome:SeeingPastComorbiditiestoReachtheCorrectDiagnosis\n"
                "Correspondence should be addressed to Jared Hicken.\nCopyright open access.\n"
                "Stiff-person syndrome is generic background.\n"
                "2.CasePresentation\nThepatientwasa65-year-oldAfrican-Americanfemalewith chronic anxiety, hypothyroidism, spasms triggered by loud noises, GAD antibodies >250 IU/mL, diazepam, tizanidine, IVIG, and stable discharge.\n"
                "3.Discussion\nAlthough the patient presented with very typical symptoms for SPS, her comorbid anxiety and hypothyroidism delayed diagnosis. Per\nreviewbyWitteetal.,in150casesofSPS generic review text.\n"
                "Upon diagnosis of our patient, various treatment methods were used to improve the patient's condition. The patient was initially started on diazepam and\n"
                "Table 1: Diagnostic criteria of stiff-person syndrome [7].\nGeneric diagnostic criteria.\n2 Case Reports in Neurological Medicine\n"
                "tizanidine, and she later improved with IVIG.\n4.Conclusions\nThis patient presented with typical SPS symptoms despite comorbid conditions, as stated in previous reviews[1,2].\n"
                "DataAvailability\nNo datasets.\nConsent\nCould not be obtained.\nConflictsofInterest\nNone.\n",
                ("65-year-oldAfrican-Americanfemale", "GAD antibodies >250", "tizanidine", "typical SPS symptoms"),
                ("Correspondence", "Copyright", "generic background", "reviewbyWitte", "Table 1", "Table 2", "reviews", "DataAvailability", "Consent", "Conflict"),
            ),
            (
                "9230",
                "Chin Med Sci J\nCASE REPORT\n"
                "otiff-Person Syndrome Associated with Anti-Glutamic\nAcid Decarboxylase Autoimmune Encephalitis\nin a Young Woman: A Case Report\n"
                "Abstract A 34-year-old female with stiff-person syndrome is reported. She had anti-GAD autoimmune encephalitis, unstable gait, leg stiffness, and improved with plasma exchange.\n"
                "INTRODUCTION\nGeneric GAD background.\nReceived September 12, 2019; accepted February 24, 2020.\n*Corresponding author E-mail: example@example.org.\n"
                "CASE DESCRIPTION\nA 34-year-old female was referred due to unstable gait and leg stiffness lasting two months. Her serum anti-GAD titer was >2000 IU/mL.\n"
                "DISCUSSION\nFigure 1. Representative patient images of the 34-year-old female patient with stiff-person syndrome.\n"
                "Conflict of interests\nThe authors declared no conflicting interests.\nCompliance with ethics\nWritten informed consent was obtained.\n",
                ("34-year-old female", "plasma exchange", "anti-GAD titer was >2000"),
                ("Generic GAD background", "Received September", "Corresponding author", "Conflict of interests", "informed consent"),
            ),
            (
                "9231",
                "Severe Chin-on-Chest Cervical Spine Deformity in\nthe Setting of Stiff-Person Syndrome\n"
                "The patient was informed that his case would be submitted for publication, and he provided consent.\n"
                "Case Report\nhe patient is a 64-year-old man with anti-GAD-antibodypositive SPS who presented with severe chin-on-chest deformity, neck pain, IVIG, plasmapheresis, and posterior spinal fusion.\n"
                "3\nd\n\nSTIFF-PERSON SYNDROME\n\nd\n\nAWnYQp/Il QrHD3i3D0Od Ryi7TvSFl4Cf3VC4/OAVpDDa8KKGKV0Ymy+78= on 05/29/2023\n"
                "Discussion\nPS is a rare, debilitating, and progressive autoimmune disorder.\n"
                "This case was complicated by many factors. In summary, SPS is a rare and complicated disorder. We describe a case of SPS in the setting of extreme spinal disease and deformity with successful outcome.\n"
                "Stephen R. Stephan, MD1\n1Department of Orthopaedic Surgery.\nORCID iD for S. R. Stephan: 0000-0003-2079-8657\nReferences\n1. Reference.\n",
                ("64-year-old man", "posterior spinal fusion", "successful outcome"),
                (
                    "provided consent",
                    "PS is a rare, debilitating",
                    "SPS is a rare and complicated",
                    "STIFF-PERSON SYNDROME",
                    "AWnYQp",
                    "ORCID",
                    "Department of Orthopaedic",
                    "References",
                ),
            ),
            (
                "9232",
                "CASE REPORT\nA 31-year-old man was diagnosed with Hodgkin's disease with cervical, hilar and\n"
                "From the Cattedra di Patologia Speciale Medica, Divisione di\nOncologia, Universita di Modena, and the Clinica Neurologica V,\nUniversita di Milano, Italy.\nReceived May 30, 1990; accepted July 5, 1990.\nCorrespondence: Dr. M. Federico, Cattedra di Patologia\nSpeciale Medica, Divisione di Oncologia, Universita, sion\nvia del Pozzo 71, 41100 Modena, Italy.\n"
                "mediastinal node involvement. Diazepam improved stiffness and chemotherapy led to remission.\nDISCUSSION\nOur patient's clinical picture was consistent with SMS.\n",
                ("31-year-old man", "mediastinal node involvement"),
                ("Cattedra", "Correspondence", "via del Pozzo"),
            ),
            (
                "9233",
                "Poster 258\nA Novel Approach to the Treatment of\nStiff-Person-Syndrome with Botulinum Toxin: A\nCase Report\n"
                "Disclosures: none.\n"
                "Case/Program Description: Patient is a 53-year-old man with low back pain, leg cramps, SPS, elevated anti-GAD antibodies, IVIG, PLEX, Rituximab, and botulinum toxin injections.\n"
                "Results: After bilateral treatment with botulinum toxin injections, patient noted significant pain relief, fewer falls, and improved gait mechanics.\n"
                "Discussion: Stiff-Person-Syndrome is an uncommon autoimmune process. Traditional treatment includes benzodiazepines.\n"
                "Conclusions: Use of botulinum toxin in refractory symptoms for SPS can improve overall function with improved pain control, gait mechanics, and balance.\n"
                "Level of Evidence: Level V\n",
                ("53-year-old man", "botulinum toxin injections", "improved gait mechanics"),
                ("Disclosures", "uncommon autoimmune process", "Traditional treatment", "Level of Evidence"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch031_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9234",
                "Abstract\nA patient with progressive encephalomyelitis with rigidity and oat cell carcinoma is described.\n"
                "KEY WORDS: Progressive encephalomyelitis with rigidity. Stiff-man syndrome.\n"
                "Progressive encephalomyelitis with rigidity: a paraneoplastic presentation of oat cell carcinoma of the lung. Case report.\n"
                "Case report\nA 63-year-old man developed painful spasms, rigidity, myoclonus, and oat cell carcinoma. Diazepam and baclofen improved spasms.\n"
                "Discussion\nThis patient's course was consistent with paraneoplastic progressive encephalomyelitis with rigidity.\n"
                "References\n1. Reference.\n",
                ("63-year-old man", "oat cell carcinoma", "Diazepam"),
                ("KEY WORDS", "References"),
            ),
            (
                "9235",
                "A Fatal Case of Neuroleptic Malignant Syndrome in a Patient with Stiff Leg Syndrome\n"
                "Summary\nStiff leg syndrome is considered as a focal form of stiff person syndrome. A patient with stiff leg syndrome developed malignant neuroleptic syndrome after haloperidol and died despite treatment.\n"
                "Introduction\nGeneric SPS and NMS background.\n"
                "Case report\nA 55-year-old woman had stiff leg syndrome, painful spasms, diazepam therapy, neuroleptic exposure, fever, rigidity, and fatal neuroleptic malignant syndrome.\n"
                "Discussion\nThe sequence in this patient suggested neuroleptic malignant syndrome superimposed on stiff leg syndrome.\n"
                "According to the DSM-IV criteria, the diagnosis of NMS has generic criteria.\n"
                "Our patient had some of the risk factors such as diabetes mellitus and haloperidol.\n"
                "Successful treatment of this syndrome depends on generic treatment.\n"
                "No signs of autonomic hyperactivity were observed in our patient before the catastrophic process. The present rigidity, spasms and agitation might also have contributed to the development of clinical picture of severe NMS in our patient.\n"
                "Complication of NMS are renal failure and other generic complications.\n"
                "Correspondence to:\nZ. Nur Baykara, Department of Neurology, Example University.\n"
                "References\n1. Reference.\n",
                ("55-year-old woman", "fatal neuroleptic malignant syndrome", "risk factors"),
                ("Generic SPS", "DSM-IV criteria", "Successful treatment", "Complication of NMS", "Correspondence", "Z. Nur Baykara", "References"),
            ),
            (
                "9236",
                "247P Study supported by AFM\nAn unrelated abstract reported a different neuromuscular disorder.\n"
                "Stiff-Man Syndrome with GAD-Like Immunoreactivity: Response of a Patient to Plasmapheresis and Immunosuppression\n"
                "Objective: We report our second patient with stiff-man syndrome and GAD-like immunoreactivity.\n"
                "Methods: The patient underwent plasmapheresis and immunosuppression.\n"
                "Results: Stiffness and spasms improved after treatment.\n"
                "Conclusions: This patient responded to plasma exchange and immunosuppression.\n"
                "248P Treatment by Chlorambucil in an unrelated abstract.\n",
                ("second patient", "plasmapheresis", "Stiffness and spasms improved"),
                ("Study supported by AFM", "unrelated abstract", "248P Treatment by Chlorambucil"),
            ),
            (
                "9237",
                "A case ofprogressive encephalomyelitis with rigidity and positive antiglutamic acid dehydrogenase antibodies\n"
                "Correspondence to the journal editor.\nAbstract A woman with rigidity is summarised.\n"
                "Case report\nA 50 year old woman first developed truncal rigidity, spasms, positive antiglutamic acid decarboxylase antibodies, diazepam treatment, and later respiratory failure.\n"
                "Discussion\nThe case was compatible with progressive encephalomyelitis with rigidity.\n"
                "Solilena\n\nand co-workers of\nWe are grateful to colleagues for technical assistance.\n"
                "References\n1. Reference.\n",
                ("50 year old woman", "truncal rigidity", "diazepam treatment"),
                ("Correspondence", "Solilena", "We are grateful", "References"),
            ),
            (
                "9238",
                "Case 27-2012: A 60-Year-Old Woman with Painful Muscle Spasms and Hyperreflexia\n"
                "The Massachusetts General Hospital front matter. Copyright 2012.\n"
                "Pr e sen tat ion  of  C a se\nA 60-year-old woman was admitted with painful spasms, hyperreflexia, axial rigidity, diabetes, and suspected stiff-person syndrome.\n"
                "The New England Journal of Medicine\nDownloaded from nejm.org at Example Library on May 26, 2023. For personal use only. No other uses without permission.\n Copyright 2012 Massachusetts Medical Society. All rights reserved.\nT h e  n e w  e ng l a n d  j o u r n a l  o f  m e d ic i n e\nn engl j med 367;9 nejm.org august 30, 2012852\n"
                "Differential diagnosis\nThe discussant concluded that the patient's features supported stiff-person syndrome.\n"
                "The Stiff Person Syndrome\nThe clinical presentation of the stiff person syndrome is progressive stiffness and rigidity of the axial muscles. The syndrome is due to diminished function of GABA.\n"
                "Table 1. Laboratory Data.\nCreatine kinase 1498 U/liter on admission.\n"
                "Presented at the postgraduate course Internal Medicine: Comprehensive Review and Update 2011, sponsored by the Harvard Medical School Department of Continuing Medical Education and Massachusetts General Hospital.\n"
                "No potential conflict of interest relevant to this article was reported.\n"
                "Disclosure forms were provided by the authors.\nReferences\n1. Reference.\n",
                ("60-year-old woman", "painful spasms", "supported stiff-person syndrome", "Table 1", "Creatine kinase"),
                ("Massachusetts General Hospital", "Downloaded from", "Copyright", "clinical presentation", "Presented at the postgraduate", "No potential conflict", "Disclosure", "References"),
            ),
            (
                "9239",
                "Stiff-person syndrome in a woman with breast cancer\n"
                "Case report. This 59-year-old woman developed progressive stiffness, anti-amphiphysin antibodies, breast cancer, diazepam response, and plasma exchange.\n"
                "From the Department of Neurology (Drs. Rosin and Meinck), University of Heidelberg, Germany.\n"
                "Address correspondence and reprint requests to Dr. Rosin.\n"
                "94 Copyright 0 1998 by the American Academy of Neurology\n"
                "Her stiffness later improved after tumour treatment and immunotherapy.\n"
                "January 1998 NEUROLOGY 50 97\n"
                "Conclusion\nThis patient had paraneoplastic stiff-person syndrome associated with breast cancer.\n",
                ("59-year-old woman", "anti-amphiphysin antibodies", "breast cancer"),
                ("Department of Neurology", "Address correspondence", "Copyright", "NEUROLOGY 50 97"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch032_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9240",
                "P737\nAn unrelated abstract.\n"
                "P738\nBrainstem involvement as onset of stiff limb syndrome: A case report\n"
                "Background: The stiff limb syndrome may include brainstem involvement.\n"
                "Case Report: We describe the case of a 66-year-old woman with dysarthria, dysphagia, severe dyskinesia, lower limb rigidity, and abnormal startle response.\n"
                "Conclusion: Cranial district involvement was combined to the worsening of rigidity.\n"
                "P739\nCabergoline in advanced RLS: A double-blind trial\nPatient no. 1 unrelated table.\n",
                ("66-year-old woman", "dysarthria", "lower limb rigidity"),
                ("P737", "P739", "Cabergoline", "unrelated table"),
            ),
            (
                "9241",
                "P777\nStiff-person syndrome associated with anti-amphiphysin antibodies\nCase Report: We report on a 71 years old female patient with another syndrome.\n"
                "P778\nStiff-person syndrome presenting with asymmetric axial muscle\nspasms and hypertrophy\nC. Chuang (New York, NY, USA)\n"
                "Objective: To describe an atypical presentation of Stiff-person syndrome.\n"
                "Background: Stiff-Person syndrome causes continuous motor unit activity. An asymmet-\n"
                "POSTER SESSION 5, WEDNESDAY, NOVEMBER 13, 2002 S241\nMovement Disorders, Vol. 17, Suppl. 5, 2002\n 15318257, 2002, S5, Downloaded from https://movementdisorders.onlinelibrary.wiley.com/doi/10.1002/mds.10353 by EVIDENCE AID - BELGIUM, Wiley Online Library on [07/06/2023]. See the Terms and Conditions (https://onlinelibrary.wiley.com/terms-and-conditions) on Wiley Online Library for rules of use; OA articles are governed by the applicable Creative Commons License\n"
                "ric subtype had not been described. Methods: A detailed history was obtained from our patient with asymmetric axial spasms and hypertrophy.\n"
                "Conclusion: This is the first case of documented Stiff-Person syndrome with marked asymmetric axial muscle involvement.\n"
                "P779\nSuccessful treatment of restless legs syndrome.\n",
                ("C. Chuang", "asymmetric axial spasms", "marked asymmetric axial muscle involvement"),
                ("P777", "another syndrome", "Downloaded from", "Creative Commons", "P779", "restless legs"),
            ),
            (
                "9242",
                "Mo-351\nDeep brain stimulation hardware failure.\n"
                "Mo-352\nRehabilitation and orthopedic management of Stiff Person\nsyndrome\n"
                "Objective: We report the case of a 71-year-old female with painful muscle spasm and anti-amphiphysin antibodies.\n"
                "She underwent inpatient rehabilitation, intrathecal baclofen pump, tendon surgery, and intense physical therapy. Maintenance therapy: ITB at\n"
                "Movement Disorders, Vol. 24, Suppl. 1, 2009\nS481\n 15318257, 2009, S1, Downloaded from https://movementdisorders.onlinelibrary.wiley.com/doi/10.1002/mds.22628 by EVIDENCE AID - BELGIUM, Wiley Online Library on [07/06/2023]. See the Terms and Conditions (https://onlinelibrary.wiley.com/terms-and-conditions) on Wiley Online Library for rules of use; OA articles are governed by the applicable Creative Commons License\n"
                "800 micrograms/day, no oral anti-spasticity medication or neurotoxin injections.\n"
                "Mo-353\nDeep brain stimulation for Holmes tremor.\n",
                ("71-year-old female", "intrathecal baclofen", "800 micrograms/day"),
                ("Mo-351", "Movement Disorders", "Downloaded from", "Mo-353", "Holmes tremor"),
            ),
            (
                "9243",
                "POS.120\nThe Stiff Person Syndrome: A Single Case\nReport of Almost Complete Recovery 12\nWeeks following Immunomodulatory\nTherapy with IVIG and Plasmapheresis\n"
                "OBJECTIVE: To reverse stiffness in a 36 year old lady with progressive stiffness.\n"
                "BACKGROUND: The patient was well until the birth of her baby, then developed stiffness, spasms, positive anti-GAD antibody, PEG tube, and tracheostomy.\n"
                "DESIGN/METHODS: Five plasma exchanges and intravenous immunoglobulin were given.\n"
                "RESULTS: Twelve weeks later, she was walking unaided and independent.\n"
                "A376 NEUROLOGY 54 April 2000 (Suppl 3)\n",
                ("36 year old lady", "positive anti-GAD antibody", "walking unaided"),
                ("A376", "NEUROLOGY 54"),
            ),
            (
                "9244",
                "CASE REPORT\nProgressive Encephalomyelitis With Rigidity: A Case Report\n"
                "Abstract\nResults: A 50-year-old man developed tonic extensor spasms, cervical cord signal changes, CSF pleocytosis, and dramatic improvement on corticosteroid therapy.\n"
                "Case report. A 50-year-old man presented with painful tonic spasms and sensory changes.\n"
                "#9\nPlease address correspondence to Ranka Baraba, PhD, MD,\nGeneral Hospital Sveti Duh, Department of Neurology, Zagreb (e-mail: example@example.org).\nG 2010 by the American Paraplegia Society\nEncephalomyelitis With Rigidity 73\n"
                "MRI of the spinal cord showed an intramedullary lesion. Corticosteroid therapy was life-saving.\n",
                ("50-year-old man", "cervical cord signal", "Corticosteroid therapy"),
                ("address correspondence", "Department of Neurology", "e-mail", "American Paraplegia"),
            ),
            (
                "9245",
                "PO5.115\nA Videography Documented Case Report:\nAntibody-Negative Stiff-Person Syndrome Joanna S.\nFong, Derk Krieger, Cleveland, OH\n"
                "OBJECTIVE: Our aim is to further characterize antibody-negative Stiff-Person Syndrome and response to plasmapheresis.\n"
                "BACKGROUND: Stiff-Person Syndrome is rare.\n"
                "DESIGN/METHODS: We report the case of a 37 year-old Caucasian man with rheumatoid arthritis and six-year history of progressive muscle spasms and rigidity.\n"
                "RESULTS: Antibody testing was negative and the patient displayed a dramatic clinical response to plasmapheresis.\n"
                "CONCLUSIONS/RELEVANCE: The diagnosis can be made based on clinical presentation and response to therapy.\n"
                "Disclosure: Dr. Fong has nothing to disclose. Dr. Krieger has nothing to disclose.\n"
                "P05.116\nALS-Associated Cu/Zn SOD Mutant Protein Is Linked to VEGF mRNA Destabilization.\n",
                ("37 year-old Caucasian man", "plasmapheresis", "clinical presentation"),
                ("Disclosure", "P05.116", "VEGF", "ALS-Associated"),
            ),
            (
                "9246",
                "Comorbid Idiopathic Parkinson's Disease and Stiff Person Syndrome: A Case Report\n"
                "Objective: To report a rare case.\n"
                "Case: A 67-\nyear-old Caucasian male presented with bilateral lower extremity muscle spasms and rigidity, positive anti-GAD antibodies, plasma exchange response, and later freezing.\n"
                "Conclusion: SPS and idiopathic Parkinson disease can be comorbid.\n"
                "Disclosure: Dr. Lustig has nothing to disclose. Dr. Blevins has nothing to disclose.\n",
                ("67-", "anti-GAD antibodies", "plasma exchange"),
                ("Disclosure", "nothing to disclose"),
            ),
            (
                "9247",
                "ABSTRACT DETAILS\nTitlePartial Stiff Person Syndrome as a Stroke Mimic\nPresentations\nP13 - Poster Session 13\n"
                "Background\nSPS is an immune-mediated neurological disorder characterized by rigidity.\n"
                "Objective\nTo report a rare case of partial stiff person syndrome.\n"
                "Design/Methods\nOur patient is a 62 year old female who presented with right arm and leg weakness, body locked sensation, hyperreflexia, increased tone, elevated GAD, and oligoclonal bands.\n",
                ("62 year old female", "body locked sensation", "elevated GAD"),
                ("ABSTRACT DETAILS", "Poster Session", "immune-mediated neurological disorder"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch033_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9330",
                "A CASE OF UNDIAGNOSED STIFF-PERSON SYNDROME REQUIRING MECHANICAL VENTILATORY SUPPORT\n"
                "Case Reports: We present a case. A 38 year-old women was transferred for acute onset myoclonus, "
                "required ventilation, had lower extremity rigidity, EMG slow continuous firing, CSF GAD65 antibody 124 nmol/L, "
                "and was discharged independently ambulatory on oral therapy.\n"
                "\u00a9 2012 by the Society of Critical Care Medicine and Lippincott Williams & Wilkins",
                ("38 year-old", "CSF GAD65 antibody", "independently ambulatory"),
                ("Lippincott", "Critical Care Medicine"),
            ),
            (
                "9331",
                "Clinical Importance\nGeneric poster purpose.\nPatient Case\n"
                "HPI : A 54-year old female presented with high fevers and mental status changes attributed to urosepsis.\n"
                "PMH : SPS (anti-GAD 65 Ab+) diagnosed 2004, ITB pump placed 2004.\n"
                "Hospital Day 80\nDischarged with ITB 1200mcg/day, baclofen, diazepam, tizanidine, and cyproheptadine.\n"
                "Severe, Prolonged Baclofen Withdrawal Following a Second\nCatheter Failure in a Patient with Stiff Person Syndrome\n"
                "Discussion\nGeneric baclofen withdrawal background.",
                ("54-year old female", "anti-GAD 65", "ITB 1200mcg/day"),
                ("Clinical Importance", "Discussion", "Generic baclofen"),
            ),
            (
                "9332",
                "A Rare Case of Amphiphysin-associated Stiff Person Syndrome in a Male Patient with Breast Cancer\n"
                "Objective: Generic objective.\nResults: A 53-year-old man developed upper-torso stiffness, gait instability, "
                "positive amphiphysin antibody, breast cancer, modified radical mastectomy, and improvement after cancer treatment.\n"
                "Conclusions: We present a rare case of paraneoplastic-related SPS in a man with breast cancer.\n"
                "Disclosure: Dr. Example has nothing to disclose.",
                ("53-year-old man", "amphiphysin", "breast cancer"),
                ("Disclosure", "nothing to disclose"),
            ),
            (
                "9333",
                "P379\nRopinirole trial in restless legs syndrome.\nResults: 930 patients improved.\n"
                "P380\nTreatment resistant jerky stiff person syndrome\n"
                "Background: Jerky SPS is an atypical form of SPS.\n"
                "Methods: Here we present a case of a 28 male with neck and back pain, generalised stiffness, and jerks.\n"
                "Results: anti-GAD titre rose to 105 and EMG demonstrated spontaneous motor activity.\n"
                "P381\nUnrelated Parkinson disease abstract.",
                ("28 male", "anti-GAD", "spontaneous motor activity"),
                ("Ropinirole", "930 patients", "P381", "Parkinson"),
            ),
            (
                "9334",
                "Plasmapheresis and immunosuppression in stiff-man syndrome with type 1 diabetes: a 2-year study\n"
                "The patient is a 36-year-old white woman with type 1 diabetes who developed axial stiffness, "
                "GAD65 antibodies, plasmapheresis response, and two years of follow-up.\n"
                "In summary, plasmapheresis was effective in controlling clinical symptoms of SMS.\n"
                "734\nAcknowledgements This study was supported.\nReferences\n1. Generic reference.",
                ("36-year-old white", "GAD65", "plasmapheresis"),
                ("Acknowledgements", "Generic reference"),
            ),
            (
                "9335",
                "TherapeuticPlasmaExchange\ninanUncommonDisease:\nStiff-PersonSyndrome:CaseReport\n"
                "CASE REPORT\nA 39-year-old male had generalized muscle spasms and seizures, positive anti-GAD antibodies, "
                "seven plasma exchanges, marked clinical improvement, and two-year follow-up without re-treatment.\n"
                "DISCUSSION\nOur patient also had involuntary spasms lasting all day and continuous motor unit activity.\n"
                "CONCLU SION\nTPE can be an alternative treatment for SPS.\n"
                "Turkiye Klinikleri J Med Sci 2012;32(6) 1765\n1. Cabo-Lopez reference.",
                ("39-year-old male", "marked clinical improvement", "continuous motor unit activity"),
                ("CONCLU SION", "Cabo-Lopez", "reference"),
            ),
            (
                "9336",
                "AUTOIMMUNE MYASTHENIA-GRAVIS WITH THYMOMA FOLLOWING REMISSION OF STIFF-MAN SYNDROME\n"
                "Case report\nThe early clinical features of this case were reported. This male patient developed at the age of 54 a syndrome of "
                "Received 27 Jun 1989 -- Accepted 30 October 1989 177\nThe Italian Journal of Neurological Sciences\n"
                "continuous muscle fiber activity, later autoimmune myasthenia gravis, thymoma, and serum and CSF samples under informed consent.\n"
                "Address reprint requests to:\nDr. Giovanni Piccolo\nReferences\n[1] Generic.",
                ("age of 54", "continuous muscle fiber activity", "thymoma"),
                ("Received 27 Jun", "Italian Journal", "Address reprint", "Generic"),
            ),
            (
                "9337",
                "Stiff person syndrome (SPS): Literature review and case report\n"
                "Case report\nApproval to report this case was granted by the Ethics Committee. The patient gave written informed consent.\n"
                "We present a case of a 45-year-old black female with progressive pain and stiffness, anti-GAD65 titre >100, "
                "diazepam, valproic acid, IVIG, and improved mobility at 9-month follow-up.\n"
                "Conclusion\nSPS should be included in the differential diagnosis.\nAcknowledgement. Editorial preparation.\nReferences\n1. Barker.",
                ("45-year-old black female", "anti-GAD65", "9-month follow-up"),
                ("Ethics Committee", "informed consent", "Acknowledgement", "Barker"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch034_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9340",
                "P-458\nUnrelated motor neuron abstract.\n"
                "P-459\nStiff Person Syndrome (SPS): A Pediatric Case Report\n"
                "Introduction: We report a case with onset at 8 years.\n"
                "Clinical evulation: A previously healthy, athletic 8 year old girl had pain, stiffness, GAD-65 antibodies, corticosteroid response, and IVIg benefit.\n"
                "P-460\nMonomelic amyotrophy report of 15 cases.",
                ("8 year old girl", "GAD-65", "IVIg"),
                ("P-458", "Monomelic", "15 cases"),
            ),
            (
                "9341",
                "266P\nUhthoff symptom cohort.\n"
                "267P\nPurely Torsional Nystagmus in a Patient\nwith the Stiff-Man Syndrome: A Case Report\n"
                "Case report. A 36-year-old male with a 2-year history of typical stiff-man syndrome developed blurred vision and torsional nystagmus.\n"
                "Conclusions. Stiff-man syndrome may involve GABAergic vestibular function.\n"
                "268P\nThe Clinical Spectrum of Horizontal End-On-End Saccades.",
                ("36-year-old male", "torsional nystagmus", "vestibular"),
                ("Uhthoff", "268P", "Horizontal"),
            ),
            (
                "9342",
                "INTERACTN CASE SUMMARY\nThe case of a 30-year-old man with subacute gait instability.\n"
                "Case Summary\nA 30-year-old healthy man had weakness, stiffness, uncontrollable spasms, thymoma, positive acetylcholine receptor antibodies, and GAD antibodies.\n"
                "Diagnosis: Myasthenia Gravis-Stiff Person Syndrome (MG-SPS) in the setting of metastatic thymoma\n"
                "Discussion\nGeneric SPS background.",
                ("30-year-old healthy man", "thymoma", "MG-SPS"),
                ("INTERACTN", "Generic SPS background"),
            ),
            (
                "9343",
                "Unrelated interferon-beta case.\n"
                "Treatment with intravenous prednisone\nand immunoglobulin in a case of\nprogressive encephalomyelitis with\nrigidity\n"
                "We report a case of PEMRS with anti-GAD antibodies.\n"
                "A 67 year old woman had progressive gait disturbance, painful spasms, anti-GAD antibodies in serum and CSF, intravenous immunoglobulin, prednisone, and freedom from cramps.\n"
                "We thank Dr Example for antibody testing.\nJ A MOLINA\nReferences\n1. Generic.",
                ("67 year old woman", "anti-GAD", "freedom from cramps"),
                ("Unrelated interferon", "We thank", "Generic"),
            ),
            (
                "9344",
                "Stiff Limb Syndrome: A Case Report and Diagnostic Criteria*\n"
                "Case Description\n65 year old female presented with lower extremity spasms, valium response, negative anti-GAD antibodies, and EMG findings consistent with stiff person syndrome.\n"
                "Results\nThe current case had lower extremity tone and characteristic EMG findings.\n"
                "Diagnostic Stiff Limb Stiff Person Points Syndrome Syndrome\nGeneric diagnostic table.\n"
                "Exam\nOutcome\nReferences\nOn exam she had increased tone in her lower extremities and hyperesthesia. She was treated with gabapentin, oxycontin, valium, baclofen, and IVIG.\n"
                "1 Barker R A, Review of 23 patients.",
                ("65 year old female", "negative anti-GAD", "IVIG"),
                ("Generic diagnostic table", "1 Barker", "Review of 23"),
            ),
            (
                "9345",
                "Anti-GAD antibody-positive myoclonic leg jerks\n"
                "Case report\nA 62-year-old man presented with progressive involuntary jerk movements, diabetes, gluteal contractions, anti-GAD antibodies, IVIg, azathioprine, and symptom control.\n"
                "D. Velardo (&) /C1A. Nuara /C1V. Martinelli /C1G. Comi /C1R. Fazio\n"
                "Division of Neuroscience, San Raffaele Scientific Institute,\nVia Olgettina, 60, Milan, Italy\n"
                "e-mail: velardo.daniele@example.org\n123\nNeurol Sci (2015) 36:647-648\nDOI 10.1007/s10072-014-2058-0\n"
                "CSF studies were normal and whole body CT excluded solid neoplasms.\n"
                "Conflict of interest The authors report no disclosures.\nReferences\n1. Generic.",
                ("62-year-old man", "anti-GAD", "azathioprine", "CSF studies"),
                ("Conflict of interest", "disclosures", "Generic", "e-mail", "Velardo"),
            ),
            (
                "9346",
                "IMMUNE SYSTEM MODULATION IN A PATIENT WITH STIFF-MAN\nSYNDROME AND INSULIN-DEPENDENT DIABETES MELLITUS.\n"
                "The modulation therapies were carried out in a 36 year old female patient who has both IDDM and SMS. Plasmapheresis improved clinical symptoms.\n"
                "101A\nNext abstract.",
                ("36 year old female", "IDDM and SMS", "Plasmapheresis"),
                ("101A", "Next abstract"),
            ),
            (
                "9347",
                "GLYCINE RECEPTOR ANTIBODY MEDIATED PROGRESSIVE\nENCEPHALOMYELITIS WITH RIGIDITY AND MYOCLONUS\n"
                "A 40-year-old man was intubated with respiratory compromise, ophthalmoplegia, severe limb rigidity, stimulus sensitive myoclonus, and positive anti-glycine receptor antibodies.\n"
                "A8\nJ Neurol Neurosurg Psychiatry footer.",
                ("40-year-old man", "anti-glycine receptor", "myoclonus"),
                ("A8", "footer"),
            ),
            (
                "9348",
                "The patient is a 33-year-old Caucasian female with SPS, high GADA, normal glucose tolerance, prednisolone, tizanidine, and stable symptoms.\n"
                "Copyright 2010 John Wiley & Sons, Ltd. Diabetes Metab Res Rev 2010; 26: 271-279.\nDOI: 10.1002/dmrr\nGAD65- and Proinsulin-Specific T Cells in Stiff-Person Syndrome 273\n"
                "Figure 1 showed persistent GAD65 antibody activity.",
                ("33-year-old Caucasian", "high GADA", "Figure 1"),
                ("Copyright", "Diabetes Metab", "DOI: 10.1002"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch035_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9350",
                "LETTERS TO THE EDITOR\nSTIFF PERSON SYNDROME IMPROVEMENT\nWITH CHEMOTHERAPY IN A PATIENT WITH\nCUTANEOUS T CELL LYMPHOMA\n"
                "A 57-year-old Caucasian woman developed cutaneous T cell lymphoma and later painful back and abdominal spasms, anti-GAD65 antibodies, plasma exchange, rituximab, alemtuzumab, and sustained walking unaided.\n"
                "T-cell-depleting therapies have a potential to confer more robust and long-lasting modulation of immune processes in SPS, but the safety and efficacy needs to be studied prospectively.\n"
                "FIGURE 1. Primary cutaneous T-cell lymphoma.\nGoran Rakocevic, MD\n1. Generic reference.\nFLEXOR HALLUCIS BREVIS SPASM\nA 30-year-old man presented with twitches.",
                ("57-year-old Caucasian woman", "anti-GAD65", "alemtuzumab", "prospectively"),
                ("FLEXOR HALLUCIS", "30-year-old man", "Generic reference", "Goran Rakocevic"),
            ),
            (
                "9351",
                "SC203\nEvidence for degradation of sarcomeric cytoskeletal proteins\n"
                "Objective: To investigate structure of muscle and cytoskeleton proteins titin and nebulin in stiff person syndrome (SPS).\n"
                "Background: A 49-year-old lady with stiffness and tension of axial muscles developed vertical diplopia, dysarthrophonia, ataxia. SPS was diagnosed.\n"
                "Design and methods: Biopsy from erector spinae muscle was analyzed.\n"
                "Results: Structure of the muscle tissue was normal and twofold decrease of titin and nebulin was found.\n"
                "Conclusions: Sustained increase of muscle activity leads to destruction of titin and nebulin.\n"
                "16 Short Communications\nSC204\nAutosomal-dominant GTPCH1-deficient DRD.",
                ("49-year-old lady", "Biopsy", "titin and nebulin"),
                ("SC204", "GTPCH1", "16 Short Communications"),
            ),
            (
                "9352",
                "Spinal segmental myoclonus in both legs associated with antibodies to glycine receptors\n"
                "Case report\nA 69-year-old man was given a diagnosis of intestinal follicular lymphoma, later developed hypertonia, bilateral synchronous myoclonus, positive anti-GlyR antibodies, steroid pulse therapy, IV immunoglobulin, and persistent mild stiffness.\n"
                "Written informed consent was obtained from the patient for these routine clinical examinations, treatments, and publication of the case report.\n"
                "*These authors contributed equally.\nMORE ONLINE\nVideo\nPRACTICAL IMPLICATIONS\nCopyright line.\n"
                "Discussion\nCo-contraction in both legs of our patient developed slowly, and GlyR-Abs cause myoclonus derived from not only the brainstem but also the spine.\n"
                "Author contributions\nH. Nanaura drafted the manuscript.\nReferences\n1. Generic.",
                ("69-year-old man", "anti-GlyR", "publication of the case report", "Co-contraction"),
                ("MORE ONLINE", "PRACTICAL IMPLICATIONS", "Author contributions", "Generic"),
            ),
            (
                "9353",
                "Our patient is the first reported case of SPS with MRI striatal abnormalities.\n"
                "Case report\nA 69-year-old woman came in for consultation with back pain, stiffness, progressive difficulty walking, diabetes mellitus, and Serum anti-GAD level was 14 000 U/ml.\n"
                "Cerebral MRI showed bright hyperintense changes in both striatal regions, more intense in the right striatum corresponding to\n"
                "Figure 1 Fundoscopy of gyrate atrophy.\nPublished Online First 6 November 2006\nCompeting interests: None declared.\nPostScript 657\nwww.jnnp.com\nJ Neurol Neurosurg Psychiatry: first published as 10.1136/jnnp.2006.099705 on 16 May 2007. Downloaded from\n"
                "the more symptomatic left side), and a lesion in the left middle cerebellar peduncle on T2. Treatment was started with L-dopa without improvement, then diazepam and intravenous immunoglobulin helped her walk without aid.\n"
                "Figure 1 (A,B) Normal post-gadolinium T1.\n658 PostScript\nwww.jnnp.com\nJ Neurol Neurosurg Psychiatry: first published as 10.1136/jnnp.2006.099705 on 16 May 2007. Downloaded from\n"
                "and eye movement abnormalities without evidence of myasthenia over 12 years.\n"
                "Discussion\nEither functional or structural striatal abnormalities may play a role in SPS, but more studies are needed to confirm this hypothesis.\n"
                "P L Guardado Santervas\nReferences\n1 Generic.",
                ("69-year-old woman", "Serum anti-GAD", "the more symptomatic left side", "intravenous immunoglobulin", "confirm this hypothesis"),
                ("Fundoscopy", "Downloaded from", "Competing interests", "P L Guardado", "References"),
            ),
            (
                "9354",
                "P7.5\nUnrelated Parkinson abstract.\n"
                "P7.6\nFollow-up in Stiff Person Syndrome with immunoglobulin treatment\n"
                "Introduction: Stiff Person Syndrome is rare.\n"
                "Objectives: To present the 4-year follow-up of a 62-year-old patient clinically and electrophysiologically diagnosed with stiff person syndrome.\n"
                "Methods: IV immunoglobulin was administered once a month. He became asymptomatic six months after the beginning of the treatment.\n"
                "Results: The first two EMG studies showed continuous muscular activity and the later studies were within normal limits.\n"
                "Conclusion: Four years after the diagnosis he remains asymptomatic, with normal EMG studies.\n"
                "P7.7\nPrefrontal stimulation in Tourette syndrome.",
                ("62-year-old patient", "IV immunoglobulin", "normal EMG studies"),
                ("P7.5", "Tourette", "P7.7"),
            ),
            (
                "9355",
                "Poster 277\nUnrelated visual rehabilitation.\n"
                "Poster 278\nRehabilitation of Stiff Person Syndrome Presenting\nAfter Laminectomy: A Case Report.\n"
                "Patients or Programs: A 39-year-old woman with worsening spasticity after laminectomy.\n"
                "Program Description: The patient had insulin-dependent diabetes, elevated Anti-GAD75 antibody titer, IVIG, baclofen, and inpatient rehabilitation.\n"
                "Results: After 2 weeks of acute inpatient rehabilitation, axial and limb stiffness and functional mobility improved.\n"
                "Discussion: Stiff person syndrome requires individualized rehabilitation.\n"
                "Conclusions: Intensive rehabilitation can improve functional outcome.\n"
                "Poster 279\nOne Year Follow-up of Body Mass Index.",
                ("39-year-old woman", "Anti-GAD75", "functional mobility improved", "Intensive rehabilitation"),
                ("Poster 277", "Body Mass Index", "Poster 279"),
            ),
            (
                "9356",
                "Poster 407\nUnrelated palpation study.\n"
                "Poster 408\nSevere Spasticity in a Patient With Stiff Person\nSyndrome: A Case Report.\n"
                "Patients or Programs: A 59-year-old woman with a 10-year history of stiff person syndrome (SPS).\n"
                "Program Description: The patient presented with pain, tremors, spasticity, stiffness, jerking and myoclonic movements that hindered ambulation.\n"
                "Results: Levetiracetam helped dystonic and myoclonic symptoms; tizanidine allowed rehabilitation and ambulation with a walker.\n"
                "Discussion: SPS can make rehabilitation efforts challenging.\n"
                "Conclusions: The rehabilitation treatment program should begin with symptom reduction and then a carefully developed exercise program.\n"
                "Poster 409\nIntractable Back Pain Alleviated by Peripheral Nerve Stimulation.",
                ("59-year-old woman", "Levetiracetam", "tizanidine", "exercise program"),
                ("Poster 407", "Poster 409", "Peripheral Nerve Stimulation"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch035_defers_three_generation_gad_family(self) -> None:
        source_path = self.write_text_json(
            "9357",
            "Clinical and immunological studies in a 3-generation family with very high titers of anti-GAD antibodies.\n"
            "Objective: To study clinicopathological parameters in a 3-generation family with high-titer anti-GAD antibodies.\n"
            "Design/Methods: Sera from three family members (female index patient, her father and her paternal grandmother) were serially tested.\n"
            "Results: All patients had high-titer anti-GAD antibodies. The index patient, a 25-year-old woman, developed typical SPS. Her father and grandmother have DM1 with very high-GAD titers.\n"
            "Conclusions: This is the first family with very high anti-GAD titers in 3 generations.",
        )
        prepared = core.prepare_source(paper_id="9357", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
        result = core.process_paper(
            paper_id="9357",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.registry_row["annotation_mode"], "single_case_deferred_multi_case_source")
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertIn("not_single_case_for_stage07_singlecase", result.registry_row["defer_reason"])

    def test_single_case_batch036_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9360",
                "1.312\nUnrelated kyphosis abstract.\n"
                "1.313\nSTIFF PERSON SYNDROME ASSOCIATED WITH AUTOIMMUNE\nTHYROIDITIS AND SARCOIDOSIS OF INTRATHORACIC LYMPH\nNODES: CASE REPORT\n"
                "We represent case report of stiff person syndrome (SPS) with eye movement disorders in a patient with autoimmune thyroiditis and sarcoidosis.\n"
                "The patient P., 50, suffers from significant strain, muscle stiffness, anti-GAD antibodies, diazepam, plasma exchange, immunoglobulins, steroid therapy, and botulinotherapy with walking improvement.\n"
                "1.314\nNEUROLOGICAL SYNDROMES ASSOCIATED WITH GLUTAMIC ACID DECARBOXYLASE ANTIBODIES: A BRAZILIAN SERIES\n12 patients.",
                ("patient P., 50", "anti-GAD", "botulinotherapy"),
                ("kyphosis", "BRAZILIAN SERIES", "12 patients"),
            ),
            (
                "9361",
                "Relapsing Anti-Glycine Receptor Antibody Mediated Encephalitis with Rigidity and Myoclonus\n"
                "Info & Disclosures\nAbstract\n"
                "Objective: To describe a clinical case of PERM caused by anti-glycine receptor antibodies.\n"
                "Background: We report a case of relapsing PERM.\n"
                "Design/Methods: A 65 year old man presented with severe hyperekplexia, rigidity, ptosis, gaze palsies, CSF pleocytosis, and anti-glycine receptor antibodies.\n"
                "Results: Ten years later he relapsed with ptosis, ophthalmoplegia, hyperekplexia, limb rigidity, and high titres in serum and CSF, improving with immunomodulation.\n"
                "Conclusions: Relapsing PERM required combined aggressive immunosuppressive treatment.\n"
                "Disclosure: Dr. Example has nothing to disclose.",
                ("65 year old man", "Ten years later", "immunosuppressive treatment"),
                ("Info & Disclosures", "Disclosure", "nothing to disclose"),
            ),
            (
                "9362",
                "Methods: Unrelated H-wave study.\nResults: H-wave amplitude.\nConclusion: gastrocnemius aponeurosis.\ndoi:10.1016/j.clinph.2011.11.197\n"
                "116. Stiff person syndrome improvement with chemotherapy\nin a patient with cutaneous T cell lymphoma--G. Rakocevic\n"
                "Introduction: Stiff person syndrome can be paraneoplastic.\n"
                "Objectives: The authors describe a patient with anti-GAD positive SPS and long-standing cutaneous T cell lymphoma.\n"
                "Methods: The patient is a 57-year-old woman diagnosed with T cell lymphoma at age 40 years and GAD-positive SPS at age 46 years.\n"
                "Results: She received rituximab, alemtuzumab, tacrolimus, azathioprine, and IVIg with near-resolution of SPS-related painful muscle spasms.\n"
                "Conclusion: SPS symptoms benefit from T and B cell-targeted therapies.\n"
                "doi:10.1016/j.clinph.2011.11.198\n117. Superficial radial sensory neuropathy.",
                ("57-year-old woman", "alemtuzumab", "near-resolution"),
                ("H-wave", "gastrocnemius", "Superficial radial"),
            ),
            (
                "9363",
                "040 RASH DECISIONS - DERMATOLOGICAL MANIFESTATIONS\n"
                "W e describe the case of a 72 year old woman with sequential cranial nerve palsies, rash, and signs suggestive of aphagia and\n"
                "J Neurol Neurosurg Psychiatry 2013;84:e2 17 of 95\nABN Abstracts\nLIBRARY. Protected by copyright.\nDownloaded from\n"
                "Ramsey-Hunt syndrome. On day 66 she developed truncal and limb rigidity, was glycine receptor (GlyR) antibody positive, and improved with corticosteroids and IVIG.\n"
                "Indeed our patient has made a substantial recovery with aggressive immunotherapy.\n"
                "REFERENCES\n1 Generic.",
                ("72 year old woman", "Ramsey-Hunt", "GlyR", "aggressive immunotherapy"),
                ("Downloaded from", "ABN Abstracts", "REFERENCES", "Generic"),
            ),
            (
                "9364",
                "MASSON\nRev Neurol (Paris) 1998\n"
                "Syndrome de « l’homme raide » traité par immunoglobulines intraveineuses\n"
                "Nous rapportons l'observation d'un syndrome de l'homme raide.\n"
                "Cas 02/96. Un homme de 48 ans, aide soignant, diabetique insulinodependant, consulta pour une raideur axiale, spasmes intermittents, anti-GAD positif, Diazepam, Valproate de Sodium, puis Ig IV pendant 5 jours.\n"
                "En mars 1996 le patient pouvait a nouveau courir. Dix-huit mois apres le debut du traitement par Ig IV, l'amelioration clinique persistait.\n"
                "En conclusion, cette observation rappelle que les Ig IV constituent une alternative therapeutique interessante.\n"
                "C. Sevrin\nREFERENCES\nAmato reference.",
                ("Un homme de 48 ans", "anti-GAD", "Dix-huit mois", "alternative therapeutique"),
                ("MASSON", "C. Sevrin", "REFERENCES", "Amato reference"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            self.assertEqual(result.registry_row["ready_for_langextract"], "true")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch037_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9370",
                "STIFF-MAN SYNDROME : A CASE REPORT\n"
                "Aziz Sonawalla*\n"
                "Introductory review of stiff-man syndrome.\n"
                "CASE REPORT:\n\nMAQ, a 50-year-old male, was first seen with low back pain radiating to the thighs.\n"
                "X-rays of the lumbosacral spine were negative and neurological examinations were usually unremarkable.\n"
                "* Dr. Aziz Sonawalla,\nConsultant Physician\nReceived for publication: January 2, 1995\nAccepted: March 1, 1995\n"
                "On examination, mild spasm was noted and diazepam produced marked relief.\n"
                "Many\nAziz Sonawalla\npatients were totally bedbound before treatment.\n"
                "It is important to arrive at a positive diagnosis.\n"
                "REFERENCES\n1. Lorish review.",
                ("MAQ, a 50-year-old male", "diazepam", "positive diagnosis"),
                ("Introductory review", "* Dr. Aziz", "Received for publication", "Aziz Sonawalla", "REFERENCES", "Lorish"),
            ),
            (
                "9371",
                "Anti-CV2 associated cerebellar syndrome.\n"
                "The previous letter described an unrelated patient with small cell lung cancer.\n"
                "Successfultreatmentofstiffman syn-\n"
                "dromewithintravenousimmunoglobu-\n"
                "lin\n"
                "Stiffmansyndromeisarareconditioncharacterisedbyprogressivestiffness.\n"
                "A 43yearoldman developedlowback pain six years before admission and later developed sudden stiffness of the legs.\n"
                "Serumanti-GAD antibodies were found and intravenousimmunoglobulin improved walking and spasms.\n"
                "ROGER ABARKER\nCDAVIDMARSDEN\n1ToroC reference.\n"
                "The next letter describes unrelated headache treatment.",
                ("A 43yearoldman", "Serumanti-GAD", "intravenousimmunoglobulin"),
                ("Anti-CV2", "small cell lung cancer", "ROGER ABARKER", "ToroC", "unrelated headache"),
            ),
            (
                "9374",
                "CASE REPORT\nSTIFF PERSON SYNDROME WITH ATYPICAL FEATURES AND A FAVOURABLE\nOUTCOME WITH STEROIDS\n"
                "ABSTRACT \nStiff Person Syndrome is rare. Here we describe a male patient with stiff person syndrome having atypical features like pyramidal signs and generalised convulsions. Oral methylprednisone had a dramatic effect.\n"
                "Keywords: Stiff person syndrome and steroids\n"
                "ATIPIK BULGULARI OLAN TURKISH DUPLICATE ABSTRACT.\n"
                "INTRODUCTION\nGeneric history of stiff-person syndrome and 14 patients.\n"
                "CASE REPORT\n\nA forty year old male patient with complaints of difficulty of swallowing, generalised muscle spasms and generalised seizures was admitted to our clinic.\n"
                "Serum antiGAD Ab was positive and steroids improved his walking and EMG findings.\n"
                "DISCUSSION\n\nAccording to the criteria of diagnosis of stiff person syndrome established by Gordon, normal motor and sensory examinations are the rule.\n"
                "Our patient had pyramidal signs in both lower extremities and generalised seizures. We could only investigate serum antiGAD Ab in our patient and we could not perform the test for techal antibodies.\n"
                "It is not a must for every SPS patient to have antibodies.\n"
                "According to Barker, half of the patients became wheelchair bound. In another report of two patients, prednisone was observed in both cases.\n"
                "Our patient produced a good response to steroids and the clinical and neurophysiological findings improved quite rapidly.\n"
                "Our report therefore bares similarity to the report of Piccolo et al.\nREFERENCES\n1. Generic.",
                (
                    "male patient with stiff person syndrome",
                    "A forty year old male patient",
                    "serum antiGAD Ab",
                    "pyramidal signs",
                    "good response to steroids",
                ),
                (
                    "TURKISH DUPLICATE",
                    "INTRODUCTION",
                    "14 patients",
                    "It is not a must",
                    "According to Barker",
                    "two patients",
                    "Our report therefore",
                    "REFERENCES",
                ),
            ),
            (
                "9372",
                "Generic stiff limb diagnostic criteria.\n"
                "Here,we report the case of a 69\n"
                "year old woman with clinical,electrophysiological and laboratory findings consistent with a stiff limb syndrome of the right leg.\n"
                "Glutamic acid decarboxylase antibodies (GAD-Ab) levels were elevated in serum and CSF.\n"
                "Both stiffness and spasms responded to intravenous and oral diazepam.\n"
                "The response to sudden auditory or tactile stimuli is consistent with a stiff limb syndrome [3,4,8].Corresponding to the clinical\n"
                "LETTER TO THE EDITORS\nTable 1 Synopsis of reported cases of the stiff-limb syndrome\n"
                "Barker RA review of 23 patients. Total n=13.\nReferences\n1. Barker review.",
                ("Here,we report the case of a 69", "GAD-Ab", "oral diazepam", "consistent with a stiff limb syndrome"),
                ("Generic stiff limb", "Table 1", "Barker", "n=13", "References"),
            ),
            (
                "9373",
                "Learning objectives about muscle stiffness.\n"
                "Case Presentation\nA 41-year-old right-handed African-American woman presented with gradual onset of stiffness and painful spasms affecting her right lower extremity.\n"
                "On examination she had exaggerated lumbar lordosis and stone-like consistency of lumbar paraspinal muscles on palpation.\n"
                "What Is the Differential\nDiagnosis of Muscle Stiffness?\n"
                "The differential diagnosis is extensive; Table 1 outlines diseases including Parkinson disease and tetanus.\n"
                "What Is the Diagnosis in the\nPresented Case?\n"
                "Our patient had slowly progressive muscle stiffness with superimposed stimulus-induced muscle spasms.\n"
                "Serum islet-cell cytoplasmic antibodies were elevated and EMG revealed continuous motor unit activity. Thus the findings were consistent with SPS.\n"
                "What Is Stiff-person Syndrome?\nGeneric syndrome review and Table 3 symptoms.\n"
                "What Is the Treatment for SPS?\nGeneric treatment review with several studies.\n"
                "Clinical Course of the Presented\nCase\n"
                "The patient had a CT scan of her chest that revealed a hypertrophic thymus. The thymus was removed surgically without improvement.\n"
                "She was treated with diazepam and baclofen, ambulated without support, and received IVIG treatments for worsening spasms.\n"
                "Summary\nGeneric SPS summary.\nReferences\n1. Generic.",
                (
                    "41-year-old right-handed African-American woman",
                    "islet-cell cytoplasmic antibodies",
                    "consistent with SPS",
                    "hypertrophic thymus",
                    "IVIG treatments",
                ),
                (
                    "Learning objectives",
                    "What Is the Differential",
                    "Table 1",
                    "Parkinson disease",
                    "What Is Stiff-person Syndrome",
                    "What Is the Treatment",
                    "Generic SPS summary",
                    "References",
                ),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            self.assertEqual(result.registry_row["ready_for_langextract"], "true")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch038_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9380",
                "Abstract: The stiff person syndrome is rare. We present a case of a 49year-old female with exacerbation of SPS treated with Therapeutic plasma exchange.\n"
                "xx\n* Corresponding author: Piotr F. Czempik, Department of Anaesthesiology, e-mail: pczempik@example.org\n"
                "Keywords: glutamic acid decarboxylase, procedure efficacy, procedure safety, stiff person syndrome, therapeutic plasma exchange\n"
                "Case report\nA 49year-old female had anti-GAD SPS, diabetes, Hashimoto thyroiditis, botulinum toxin, diazepam, gabapentin and levetiracetam.\n"
                "Past medical history, along with adverse effects that the patient developed, is presented in Table 1.\n"
                "Table 1 Comorbidities and adverse effects: diabetes, Hashimoto thyroiditis, sedation.\n"
                "4 Conclusion\nTherapeutic plasma exchange may be a useful adjunct therapy for exacerbation of SPS not responding to standard medical therapy.\n"
                "530\nPiotr F. Czempik et al.\n"
                "in this clinical setting remains undetermined and requires further research.\n"
                "Conflict of interests: Authors state no conflict of interest.\nData availability statement: Data available on request.\nReferences\n[1] Generic.",
                ("49year-old female", "anti-GAD SPS", "Table 1", "Therapeutic plasma exchange", "clinical setting remains"),
                ("Conflict of interests", "Data availability", "References", "Piotr F. Czempik"),
            ),
            (
                "9381",
                "Case report\nA 63-year-old man presented with recurrent generalized epileptic seizures for one day after nivolumab treatment.\n"
                "On admission he had limbic encephalitis, cerebellar ataxia, stiff person syndrome and bilateral horizontal\n"
                "* Sara Mariotto\nsara.mariotto@univr.it\n1 Department of Neurology\n7 Neurology Unit, University of Verona\nhttps://doi.org/10.1007/s10072-021-05312-0\n/ Published online: 11 May 2021\nNeurological Sciences (2021) 42:4289-4291\n"
                "persistent nystagmus. CSF showed oligoclonal bands, and serum and CSF were positive for GAD65 and PDE10A-IgG.\n"
                "Conclusion\nThis case expands the spectrum of GAD65-associated conditions induced by ICI and the patient died.\n"
                "Availability of data and material Not applicable.\nAuthors' contribution Generic.\nDeclarations\nConflict of interest Generic.\nReferences\n1. Generic.",
                ("63-year-old man", "nivolumab", "persistent nystagmus", "PDE10A-IgG", "patient died"),
                ("Sara Mariotto", "Published online", "Availability of data", "Authors' contribution", "Conflict of interest", "References"),
            ),
            (
                "9382",
                "Case Report\nWe report profound worsening of symptoms in response to citalopram in an 80-year-old-right handed woman with a 16-year history of a SPS.\n"
                "She had elevated GAD antibodies and responded well to diazepam and gabapentin.\n"
                "*Correspondence to: Dr Example.\n"
                "33% reduction in her symptoms was recorded after citalopram was weaned, and the Naranjo algorithm score was 7.\n"
                "Discussion\n"
                "Citalopram, however, has broader literature around SSRI use in SPS.\n"
                "TABLE 1 The stiffness index\nPre-citalopram On citalopram Post-citalopram\nTotal 1 3 1\n"
                "MOVEMENT DISORDERS CLINICAL PRACTICE footer.\n"
                "Author Roles\n1. Research project roles.\nDisclosures\nEthical compliance.\nFunding Sources and Conflict of Interest: None.\nFinancial Disclosures for the Previous 12 Months: None.\nReferences\n1. Generic.",
                ("80-year-old-right handed woman", "GAD antibodies", "Naranjo algorithm", "TABLE 1 The stiffness index", "Total 1 3 1"),
                (
                    "Correspondence to",
                    "Discussion",
                    "broader literature",
                    "MOVEMENT DISORDERS",
                    "Author Roles",
                    "Disclosures",
                    "Funding Sources",
                    "Financial Disclosures",
                    "References",
                ),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            self.assertEqual(result.registry_row["ready_for_langextract"], "true")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch039_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9390",
                "Abstract\nStiff Person Syndrome background. In this paper, we report a case of a 25-year-old Vietnamese female patient with SPS and anti-SOX1 antibodies.\n"
                "The patient had complete remission with IVIG.\n"
                "Â© 2022 The Author(s). Published by S. Karger AG, Basel.\n"
                "Case Presentation\nA 25-year-old female patient had progressive spasms, anti-GAD antibodies, anti-SOX1 antibodies, IVIG response, and ovarian teratoma workup.\n"
                "xx 2022 The Author(s). Published by S. Karger AG, BaselDOI: 10.1159/000523988\n"
                "Conclusion: IVIG may be appropriate in this patient.\n"
                "243\nCase Rep Neurol 2022 footer\nNguyen et al.: Stiff Person Syndrome: A Case Report from Vietnam\nwww.karger.com/crn\nCopyright.",
                ("25-year-old Vietnamese female", "complete remission", "anti-SOX1 antibodies", "IVIG response"),
                ("Karger", "Case Rep Neurol", "Nguyen et al.", "www.karger", "Copyright"),
            ),
            (
                "9391",
                "ABSTRACT\nIntroduction: generic SPS background.\n"
                "Case report; In this report, we present a rare case of a 79-year-old woman with bilateral lower extremity weakness, high GAD antibodies, oral diazepam, and improvement.\n"
                "Conclusion: The presentation of SPS can vary.\n"
                "Q KEYWORDS:\nPurchase options.\nFunding\nWebsite tail.\nPrivacy policy Cookies Terms.",
                ("79-year-old woman", "GAD antibodies", "oral diazepam", "Conclusion"),
                ("Purchase options", "Funding", "Website tail", "Privacy policy"),
            ),
            (
                "9392",
                "ABSTRACT\nCase report: A 38-year-old woman with stiff-person syndrome had intractable spasms, IVIG cycles, intrathecal baclofen trial, permanent pump implantation, and independent ambulation.\n"
                "Conclusion: Intrathecal baclofen therapy was successful.\n"
                "Correspondence address: Bruce Zhang, Temple University Hospital. E-mail: bruce.zhang@example.org\n"
                "This is an open access article under the CC BY-NC license. www.medicaljournals.se/jrm-cc\nFoundation of Rehabilitation Information\ndoi: 10. 2340/20030711-1000052\np. 2 of 5\nJRM-CC\nB. Zhang et al.\n"
                "ACKNOWLEDGEMENT\nPoster presentation and conflicts.",
                ("38-year-old woman", "intrathecal baclofen", "permanent pump", "independent ambulation"),
                ("Correspondence address", "open access", "ACKNOWLEDGEMENT", "conflicts"),
            ),
            (
                "9393",
                "Pediatric stiff limb syndrome with polyautoimmunity\n"
                "3. Case presentation\n"
                "An 18-month-old female presented with inability to bear weight, anti-GAD-65 antibodies, anti-islet cell antibodies, IVIG, and clonazepam response.\n"
                "Fig. 1. Flow chart of literature searching and review.  \nD.A. Nie et al.\nJournal of Neuroimmunology 367 (2022) 577865\n3\n"
                "4. Discussion\n"
                "Literature review of 53 pediatric cases.\n"
                "Table 1 \nResults of the CSF/serum autoimmune tests. Initial workup 4.79 396 TPO 505 anti-islet 1280. IVIG follow-up values.\n"
                "Table 2\nClinical characteristics of the pediatric onset cohort, n = 53.",
                ("18-month-old female", "anti-GAD-65", "IVIG", "Table 1", "anti-islet 1280"),
                ("Literature review", "Table 2", "n = 53", "D.A. Nie et al.", "Flow chart"),
            ),
            (
                "9394",
                "2.CasePresentation\nPT_he patient is a 50-year-old woman with chronic low back pain, lower limb stiffness, high anti-GAD, IVIG, rituximab, and walker-assisted recovery.\n"
                "3.Discussion\nA cohort of 17/23 patients improved.\n4.Conclusion\nGeneric conclusion.\nData Availability\nNone.",
                ("50-year-old woman", "anti-GAD", "rituximab", "walker-assisted recovery"),
                ("17/23", "Generic conclusion", "Data Availability"),
            ),
            (
                "9395",
                "Case report: Amphiphysin-IgG autoimmunity\n"
                "Case presentation\nA 54-year-old male presented with disturbance of consciousness, amphiphysin-IgG in serum and CSF, appendiceal goblet cell carcinoma, methylprednisolone response, and recurrence with paraneoplastic cerebellar dysfunction.\n"
                "Diagnostic assessment supported amphiphysin-IgG autoimmunity.\n"
                "Discussion\nGeneric PNS literature.\nAuthor contributions\nFunding\nReferences",
                ("54-year-old male", "amphiphysin-IgG", "methylprednisolone", "Diagnostic assessment"),
                ("Generic PNS", "Author contributions", "Funding", "References"),
            ),
            (
                "9396",
                "Case Report\nA Case of Anti-GAD 65 Autoimmune Encephalitis Associated with Focal Segmental Stiff-Person Syndrome\n"
                "Chen Zhang, Yuwei Dai, Binhong Han\n* Correspondence: yangli762@csu.edu.cn\n"
                "Abstract: Glutamic acid decarboxylase (GAD) antibody-related encephalitis was complicated with focal segmental stiffness-person syndrome in a middle-aged woman. The right limb stiffness improved after immunotherapy.\n"
                "Keywords: glutamic acid decarboxylase\n1. Introduction\nGeneric autoimmune encephalitis background.\n"
                "2. Case Description\nA 44-year-old woman developed drug-resistant epilepsy, stiffness of the right limb, positive anti-GAD 65 antibody, seizures, and completely disappeared limb stiffness after immunotherapy.\n"
                "Brain Sci. 2023, 13, 369. https://doi.org/10.3390/brainsci13020369 https://www.mdpi.com/journal/brainsci\nBrain Sci. 2023, 13, 369 2 of 8\n"
                "3. Discussion\nGeneric discussion.\nAuthor Contributions\nFunding\nReferences",
                ("Abstract:", "44-year-old woman", "anti-GAD 65", "right limb", "completely disappeared"),
                ("Chen Zhang", "Correspondence", "1. Introduction", "Brain Sci.", "Generic discussion", "Author Contributions", "Funding", "References"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            self.assertEqual(result.registry_row["ready_for_langextract"], "true")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch040_source_ranges_keep_case_material_only(self) -> None:
        cases = (
            (
                "9401",
                "Progressive encephalomyelitis with rigidity and myoclonus associated with anti-glycine receptor antibodies and urothelial carcinoma\n"
                "Abstract \nBackground PERM is rare.\nCase presentation A 72-years-old Caucasian male had dysarthria, dysphagia, trismus, anti-GlyR antibodies, IVIG, and chemotherapy response.\nConclusion This is a single case.\nKeywords PERM\n"
                "Background\n*Correspondence:\ntrygve@example.org\nPage 2 of 5Ali et al. Journal of Medical Case Reports          (2023) 17:330 \n"
                "Case presentation\nA 72-years-old Caucasian male was admitted with painful tongue weakness, dysphagia, bladder cancer metastases, anti-GlyR antibodies, intravenous immunoglobulin, chemotherapy, and stabilization.\n"
                "Page 3 of 5Ali et al. Journal of Medical Case Reports          (2023) 17:330 \nDiscussion\nGeneric PERM literature.",
                ("Abstract", "72-years-old Caucasian male", "anti-GlyR", "intravenous immunoglobulin", "stabilization"),
                ("Correspondence", "Page 2 of 5", "Page 3 of 5", "Generic PERM literature"),
            ),
            (
                "9402",
                "Thymoma-Related Stiff-Person Syndrome with Successfully Treated by Surgery\n"
                "Case Report\nA 26-year-old woman visited neurology with lower limbs convulsions and gait disturbance. Baclofen and clonazepam "
                "Introduction: Stiff-person syndrome (SPS) is a rare autoimmune neurological disorder. Presentation of Case: A 26-year-old woman had a thymoma. Sasaki A, et al.\n"
                "administered as symptomatic treatment were highly effective. She underwent extended thymectomy and had no recurrence over 44 months.\n"
                "Discussion\nTable 1 Case of surgically resected thymoma-related Stiff-person syndrome\nDisclosure Statement\nNo disclosures to report.",
                ("26-year-old woman", "Baclofen and clonazepam", "extended thymectomy", "44 months"),
                ("Introduction:", "Sasaki A, et al.", "Table 1", "Disclosure Statement"),
            ),
            (
                "9407",
                "Immunotherapy-Responsive Neuropathic Pain and Allodynia in a Patient With Glycine Receptor Autoantibodies\n"
                "Case Report\nA 33-year-old woman had sensory disturbance, GlyR autoantibodies in serum and CSF, PERM, plasma exchange, rituximab, independent mobility, and improved neuropathic pain during follow-up.\n"
                "This case suggests that glycinergic neurotransmission may contribute to analgesic development.\n7",
                ("33-year-old woman", "GlyR", "PERM", "independent mobility", "neuropathic pain"),
                ("This case suggests", "analgesic development"),
            ),
            (
                "9403",
                "Teaching Video NeuroImage: Hung-Up Reflex in Stiff Limb Syndrome\n"
                "A 45-year-old woman developed intermittent gait disorder, left leg stiffness, continuous motor unit activity, GAD65 antibodies, stiff limb syndrome, and response to diazepam.\n"
                "Appendix Authors\nAuthor contribution table.\nFootnote\nTeaching slides links.\nReferences\n1. Background paper.",
                ("45-year-old woman", "GAD65", "stiff limb syndrome", "diazepam"),
                ("Appendix Authors", "Footnote", "References"),
            ),
            (
                "9404",
                "Postoperative hypotonia in a patient with stiff person syndrome\n"
                "Abstract\nClinical features A 46-yr-old female patient with SPS had TIVA and sugammadex response. A literature review identified six instances.\n"
                "Case report\nInformed consent was obtained. A 46-yr-old female (165 cm, 70 kg) with SPS underwent lumpectomy, TIVA, rocuronium, postoperative hypotonia, and sugammadex reversal.\n"
                "123\n1420 N. Elsherbini et al.\nThe option of a strictly regional/local anesthesia technique was not discussed. General anesthesia was maintained by propofol and remifentanil infusion\n"
                "Table 1 continued\nReport Age\nJohnson 1995 postoperative weakness.\n123\n1422 N. Elsherbini et al.\n"
                "Maintenance of an appropriate depth of anesthesia was achieved. Sugammadex 250 mg was administered and the patient was extubated.\n"
                "Discussion\nTable 1 Summary of case reports describing the use of muscle relaxants in patients with stiff person syndrome.",
                ("46-yr-old female", "lumpectomy", "rocuronium", "sugammadex", "extubated"),
                ("A literature review", "Discussion", "Table 1", "N. Elsherbini et al."),
            ),
            (
                "9405",
                "Glutamic acid decarboxylase (GAD) antibody- positive paraneoplastic stiff person syndrome associated with mediastinal liposarcoma\n"
                "Case report\nTo cite: Yohannan B et al. doi:10.1136/bcr-2022-250639\nCorrespondence to\nDr Arthi Sridhar\nSUMMARY\nWe report a case of a young woman with seizures, painful spasms, anti-GAD-positive SPS, mediastinal liposarcoma, tumour resection, IVIG, and improvement.\n"
                "BACKGROUND\nGeneric background.\nCASE PRESENTATION\nA young woman in her 20s had seizure, painful muscle spasms, mediastinal mass, anti-GAD antibodies, tumour resection, IVIG, and improved activities of daily living.\n"
                "DISCUSSION\nGeneric SPS background.\nContributors\nFunding",
                ("SUMMARY", "young woman", "anti-GAD", "mediastinal", "IVIG"),
                ("To cite", "Correspondence", "Generic background", "DISCUSSION", "Contributors", "Funding"),
            ),
            (
                "9406",
                "A 41-year-old female initially presented with rash, weakness, myositis, myasthenia gravis, thymoma, and stiff limb syndrome.\n"
                "Email: jiangyun@bjhmoh.cn\nCite this article: Jiang Y, Hou S, Zhang H, Zhang J, and Guo H. (2023) Coexisting Stiff Limb Syndrome. The Canadian Journal of Neurological Sciences 50: 472 -474, https://doi.org/10.1017/cjn.2022.51\n© The Author(s), 2022. Published by Cambridge University Press on behalf of Canadian Neurological Sciences Federation\nThe Canadian Journal of Neurological Sciences (2023), 50, 472 -474\ndoi:10.1017/cjn.2022.51\nhttps://doi.org/10.1017/cjn.2022.51 Published online by Cambridge University Press\n"
                "After operation, the persistent flexion disappeared. Le Journal Canadien Des Sciences Neurologiques 473\nhttps://doi.org/10.1017/cjn.2022.51 Published online by Cambridge University Press\nIn summary, thymoma can induce MG, myositis, and SLS.",
                ("41-year-old female", "thymoma", "stiff limb syndrome", "persistent flexion disappeared"),
                ("Cite this article", "Published online", "Le Journal Canadien"),
            ),
        )

        for paper_id, text, expected_values, unexpected_values in cases:
            source_path = self.write_text_json(paper_id, text)
            prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
            annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
            result = core.process_paper(
                paper_id=paper_id,
                source_row={
                    "preferred_langextract_mode": "individual",
                    "langextract_eligible": "true",
                },
                manual_row={},
                stage06_row={
                    "preferred_text_json_path": str(source_path),
                    "likely_sps_case_count": "1",
                    "count_confidence": "high",
                    "count_eligible": "true",
                },
                paths=self.output_paths,
                manifest_run_id="test_stage07_xml",
                annotation_model="gpt-5.5",
                annotation_payload=annotation,
            )
            selected = result.target_view_payloads["p1"]["input_text"]
            self.assertEqual(result.registry_row["annotation_mode"], "single_case_clinical_window")
            self.assertEqual(result.registry_row["ready_for_langextract"], "true")
            for expected in expected_values:
                self.assertIn(expected, selected)
            for unexpected in unexpected_values:
                self.assertNotIn(unexpected, selected)

    def test_single_case_batch040_defers_anti_gad_encephalitis_cohort(self) -> None:
        source_path = self.write_text_json(
            "9400",
            "Clinical characteristics and treatment outcome of anti-GAD encephalitis\n"
            "All 32 patients received immunomodulatory therapies. "
            "The 30 patients with follow-up records were divided into two groups: seizure-free group (group 1, n = 11) and seizure group (group 2, n = 19). "
            "Table 2 Treatments and outcome in anti-GAD encephalitis. "
            "A 37-year-old female patient had stiff-person syndrome, but the article reports a cohort and comparative outcomes.",
        )
        prepared = core.prepare_source(paper_id="9400", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
        result = core.process_paper(
            paper_id="9400",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.registry_row["annotation_mode"], "single_case_deferred_multi_case_source")
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertIn("not_single_case_for_stage07_singlecase", result.registry_row["defer_reason"])

    def test_single_case_batch036_defers_paraneoplastic_case_series(self) -> None:
        source_path = self.write_text_json(
            "9365",
            "A case series of central and peripheral nervous system involvement in paraneoplastic syndromes\n"
            "Material and methods: We reviewed clinical data of definite paraneoplastic syndrome during 2002-2011.\n"
            "Results: We identified 68 patients with definite diagnosis of paraneoplastic syndrome. 29 cases developed a neuropathy, 21 cases presented cerebellar degeneration, and 1 case stiff person syndrome, brainstem encephalitis and choreic syndrome.",
        )
        prepared = core.prepare_source(paper_id="9365", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
        result = core.process_paper(
            paper_id="9365",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.registry_row["annotation_mode"], "single_case_deferred_multi_case_source")
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertIn("not_single_case_for_stage07_singlecase", result.registry_row["defer_reason"])

    def test_single_case_defers_intrathecal_gad_group_cohort(self) -> None:
        source_path = self.write_text_json(
            "9117",
            "Intrathecal-specific glutamic acid decarboxylase antibodies at low titers in autoimmune neurological disorders\n"
            "Materials and methods\n"
            "We selected patients whose CSF tested positive for GAD-Abs.\n"
            "Results\n"
            "A total of 32 patients were screened. Finally, the remaining 19 patients tested positive for GAD-Abs in CSF. "
            "Table 1 Demographic and clinical characteristics of patients with intrathecal-specific GAD-Abs. "
            "Variables Total patients (n = 19). Neurological syndromes Limbic encephalitis 6 (31.6) "
            "Stiff-person syndrome 1 (5.3). Four patients presented with isolated epilepsy, three with cerebellar ataxia, and one with stiff-person syndrome.\n",
        )
        prepared = core.prepare_source(paper_id="9117", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
        result = core.process_paper(
            paper_id="9117",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.registry_row["annotation_mode"], "single_case_deferred_multi_case_source")
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertIn("not_single_case_for_stage07_singlecase", result.registry_row["defer_reason"])

    def test_single_case_defers_scmusd_group_series(self) -> None:
        source_path = self.write_text_json(
            "9125",
            "Spontaneous continuous motor unit single discharges\n"
            "Methods: Needle EMG recordings were screened.\n"
            "Results: Spontaneous continuous motor unit single discharges were identified in 24 recordings from 14 patients. "
            "Neurogenic disorders were diagnosed in 12 patients, limb girdle muscle dystrophy in one patient, "
            "and stiff-limb syndrome was diagnosed in one patient.\n",
        )
        prepared = core.prepare_source(paper_id="9125", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
        result = core.process_paper(
            paper_id="9125",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.registry_row["annotation_mode"], "single_case_deferred_multi_case_source")
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertIn("not_single_case_for_stage07_singlecase", result.registry_row["defer_reason"])

    def test_single_case_age_anchor_accepts_years_old_phrase(self) -> None:
        source_path = self.write_text_json(
            "9045",
            "Interlibrary loan header.\n"
            "A 40 years old man had stiff-person syndrome with abdominal stiffness. "
            "Serum and CSF were\n"
            "*Dept. of Medicine, Example Hospital.\n"
            "Received : 1.1.1998; Accepted : 2.1.1998\n"
            "836\n"
            "positive for GAD antibodies.\n"
            "REFERENCES\n1. Generic reference.",
        )
        prepared = core.prepare_source(paper_id="9045", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9045",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 40 years old man", text)
        self.assertIn("Serum and CSF were", text)
        self.assertIn("positive for GAD antibodies", text)
        self.assertNotIn("Interlibrary loan header", text)
        self.assertNotIn("Dept. of Medicine", text)
        self.assertNotIn("Generic reference", text)

    def test_single_case_batch045_keeps_target_jns_abstract_only(self) -> None:
        selected = self.single_case_selected_text(
            "118835\nLong-term MRI changes in a patient with Kelch like protein 11-associated paraneoplastic neurological syndrome\n"
            "Results\nA 49-year-old man presented with ataxia and hearing loss.\n"
            "doi:10.1016/j.jns.2021.1 18835\n"
            "118836\nThe use of combined therapy with CFPE and IVIG in a patient with\n"
            "refractory standard therapy for stiff person syndrome\n"
            "Background and aims\nPatient, female 56 years old. The disease debuted with stiffness and pain in the muscles of the back.\n"
            "Methods\nTreatment started with IVIG and benzodiazepine therapy.\n"
            "Results\nThis therapy significantly reduced the severity of rigidity.\n"
            "Conclusions\nIVIG and plasmapheresis can be used in combination.\n"
            "doi:10.1016/j.jns.2021.1 18836\n"
            "118837\nStudy of clinical profile of autoimmune encephalitis.\n",
            paper_id="9145",
        )

        self.assertIn("The use of combined therapy", selected)
        self.assertIn("female 56 years old", selected)
        self.assertIn("reduced the severity of rigidity", selected)
        self.assertNotIn("Long-term MRI changes", selected)
        self.assertNotIn("118837", selected)

    def test_single_case_batch045_keeps_only_ana_m207_listing(self) -> None:
        annotation = self.single_case_annotation(
            text=(
                "M206. Spirituality and Religiosity in Parkinson Disease\n"
                "Shadi Ghourchian, MD.\n"
                "M207. Stiff Person Syndrome in a Patient with Atypical\n"
                "Carcinoid Tumor of the Lung Secondary to\n"
                "Antiamphiphysin Antibodies: A Case Report and\n"
                "Literature Review\n"
                "Khawla Abusamra, MD, Padmaja Sudhakar, MD.\n"
                "M208. Synucleionopathy-Associated Microglia Uncovered\n"
                "by a Novel Multiple System Atrophy-Cerebellar Type\n"
            ),
            paper_id="9146",
        )
        selected = "\n".join(
            str(span.get("selected_text") or "")
            for segment in annotation.get("segments") or []
            for span in segment.get("spans") or []
        )

        self.assertIn("M207. Stiff Person Syndrome", selected)
        self.assertIn("Case Report and", selected)
        self.assertNotIn("M206. Spirituality", selected)
        self.assertNotIn("M208. Synucleionopathy", selected)
        self.assertEqual(annotation.get("annotation_mode"), "single_case_deferred_multi_case_source")
        self.assertIn(
            "not_single_case_for_stage07_singlecase",
            annotation.get("manual_review_reasons") or [],
        )

    def test_single_case_batch045_lung_cancer_report_excludes_literature_review_tail(self) -> None:
        selected = self.single_case_selected_text(
            "Case Report\nParaneoplastic stiff-person syndrome with\n"
            "lung cancer: a case report and literature review\n"
            "Abstract: Stiff person syndrome is a rare autoimmune disease. We reported a case of SPS. "
            "The patient presented with stiffness and convulsions of lower limbs.\n"
            "Keywords: Stiff person syndrome (SPS), paraneoplastic syndrome\n"
            "Introduction\nWe reviewed the relevant literature on SPS published in recent years.\n"
            "Case description\nA female patient aged 43 years presented with paroxysmal symptoms. "
            "The patient was diagnosed with SPS and lung adenocarcinoma. The patient regularly took the above-mentioned drugs after surgery.\n"
            "Discussion\nSPS is an autoimmune disease. Using stiff person syndrome as the retrieval method, 61 cases were extracted.\n"
            "Table 1. Clinical characteristics of patients with stiff person syndrome and cancers\n"
            "References\n[1] Patel K.\n",
            paper_id="9147",
        )

        self.assertIn("We reported a case of SPS", selected)
        self.assertIn("female patient aged 43 years", selected)
        self.assertNotIn("We reviewed the relevant literature", selected)
        self.assertNotIn("Table 1. Clinical characteristics", selected)
        self.assertNotIn("References", selected)

    def test_single_case_batch045_excludes_aan_copyright_footer(self) -> None:
        selected = self.single_case_selected_text(
            "A 60-year-old previously healthy man presented with progressive stiffness and anti-GAD65 antibody disease.\n"
            "Prompt recognition of the condition is critical because early immunotherapy may confer a better prognosis.\n"
            "e904 Copyright © 2021 American Academy of Neurology\n"
            "Copyright © 2021 American Academy of Neurology. Unauthorized reproduction of this article is prohibited.\n"
            "Discussion\nGAD65 autoimmunity is associated with a spectrum of neurologic syndromes.\n",
            paper_id="9148",
        )

        self.assertIn("A 60-year-old previously healthy man", selected)
        self.assertNotIn("Copyright © 2021 American Academy of Neurology", selected)

    def test_single_case_batch046_brain_sci_report_stops_before_discussion(self) -> None:
        selected = self.single_case_selected_text(
            "Abstract: Antibodies to glutamic acid decarboxylase (GAD) can accompany SPS.\n"
            "Case Presentation A 46-year-old woman developed visual acuity loss and later stiffness.\n"
            "The patient was treated with intravenous immunoglobulin with mild improvement.\n"
            "5. Discussion GAD antibody-spectrum disorders entail a wide spectrum of clinical entities.\n"
            "Author Contributions: All authors approved the manuscript.\n",
            paper_id="9149",
        )

        self.assertIn("A 46-year-old woman", selected)
        self.assertIn("mild improvement", selected)
        self.assertNotIn("5. Discussion", selected)
        self.assertNotIn("Author Contributions", selected)

    def test_single_case_batch046_frontiers_report_keeps_patient_perspective_not_admin(self) -> None:
        selected = self.single_case_selected_text(
            "CASE DESCRIPTION A 62-year-old Japanese man was transferred with progressive intermittent painful spasms.\n"
            "ANTIBODY ASSAYS We measured antibodies against neuronal surface proteins.\n"
            "PATIENT PERSPECTIVE The patient reported marked functional recovery.\n"
            "DATA AVAILABILITY STATEMENT The original contributions are included in the article.\n"
            "ETHICS STATEMENT Consent was obtained.\n",
            paper_id="9150",
        )

        self.assertIn("A 62-year-old Japanese man", selected)
        self.assertIn("ANTIBODY ASSAYS", selected)
        self.assertIn("PATIENT PERSPECTIVE", selected)
        self.assertNotIn("DATA AVAILABILITY STATEMENT", selected)

    def test_single_case_batch046_video_neuroimage_excludes_submission_footer(self) -> None:
        selected = self.single_case_selected_text(
            "VIDEO NEUROIMAGE Proprioceptive Stimuli as a New Type of Trigger for Epilepsy in Stiff Person Syndrome\n"
            "A healthy 74-year-old woman was diagnosed with Stiff-Person syndrome and later had seizures induced by knee flexion.\n"
            "Study Funding No targeted funding reported.\n"
            "Learn how to prepare and submit your manuscript at: NPub.org/NGAuthors\n",
            paper_id="9151",
        )

        self.assertIn("A healthy 74-year-old woman", selected)
        self.assertIn("seizures induced by knee flexion", selected)
        self.assertNotIn("Study Funding", selected)
        self.assertNotIn("Learn how to prepare", selected)

    def test_single_case_batch046_perm_facial_palsy_keeps_case_window(self) -> None:
        selected = self.single_case_selected_text(
            "PERM Initiated as Facial Palsy INTRODUCTION Stiff person spectrum disorder includes immune-mediated disorders.\n"
            "CASE PRESENTATION A 61-year-old previously healthy male baker was admitted for left-sided facial weakness.\n"
            "FOLLOW-UP AND OUTCOME He improved after immunotherapy but had residual spasms.\n"
            "DISCUSSION Several reports mentioned facial weakness during disease progression.\n"
            "CONCLUSION The PERM is a rare autoimmune disorder with complex symptoms.\n"
            "DATA AVAILABILITY STATEMENT Data are unavailable.\n",
            paper_id="9152",
        )

        self.assertIn("A 61-year-old previously healthy male baker", selected)
        self.assertIn("FOLLOW-UP AND OUTCOME", selected)
        self.assertNotIn("INTRODUCTION", selected)
        self.assertNotIn("DISCUSSION", selected)
        self.assertNotIn("CONCLUSION", selected)
        self.assertNotIn("DATA AVAILABILITY", selected)

    def test_single_case_batch046_varicella_perm_excludes_front_matter_and_admin(self) -> None:
        selected = self.single_case_selected_text(
            "Case Report PUBLISHED 29 November OPEN ACCESS EDITED BY reviewers.\n"
            "Introduction Progressive encephalomyelitis with rigidity and myoclonus can follow varicella-zoster virus.\n"
            "Case report A 75-year-old male patient had headache and clusters of blisters.\n"
            "A diagnosis of anti-GlyR antibody- positive PERM induced by varicella-zoster virus was made.\n"
            "Discussion The patient had typical clinical manifestations of PERM.\n"
            "Data availability statement The datasets are not readily available.\n"
            "Author contributions JY and XX conceived the idea.\n",
            paper_id="9153",
        )

        self.assertIn("A 75-year-old male patient", selected)
        self.assertIn("anti-GlyR antibody- positive PERM", selected)
        self.assertNotIn("OPEN ACCESS", selected)
        self.assertNotIn("Discussion", selected)
        self.assertNotIn("Data availability statement", selected)

    def test_single_case_batch046_paraneoplastic_pet_cohort_defers_table_only_source(self) -> None:
        annotation = self.single_case_annotation(
            text=(
                "Brain 18F-FDG-PET characteristics in patients with paraneoplastic neurological syndrome.\n"
                "A total of 19 patients were analysed in this retrospective cohort.\n"
                "Table 5 Oculomotor findings Patient number Age/sex Antibodies Cancer Clinical PET MRI 1 73/male Anti-Ri cancer.\n"
                "Table 6 Stiff-person syndrome Patient number Age/sex Antibodies Cancer Clinical presentation PET MRI "
                "1 55/female Anti-GAD None Cerebellar degeneration, muscle spasms, type I diabetes - cerebellar stiff-person syndrome Normal.\n"
                "Table 4 Salient findings in patients with paraneoplastic sensory neuropathy Patient number Age/sex Antibody Cancer.\n"
            ),
            paper_id="9154",
        )
        selected = "\n".join(
            str(span.get("selected_text") or "")
            for segment in annotation.get("segments") or []
            for span in segment.get("spans") or []
        )

        self.assertIn("Table 6 Stiff-person syndrome", selected)
        self.assertIn("55/female Anti-GAD", selected)
        self.assertNotIn("Table 5 Oculomotor", selected)
        self.assertNotIn("Table 4 Salient", selected)
        self.assertEqual(annotation.get("annotation_mode"), "single_case_deferred_multi_case_source")
        self.assertIn("not_single_case_for_stage07_singlecase", annotation.get("manual_review_reasons") or [])

    def test_single_case_batch046_aan_abstract_excludes_disclosure_and_navigation(self) -> None:
        selected = self.single_case_selected_text(
            "A 59-year-old patient with GlyR antibody- positive SPSD was treated with immunotherapy including IVIG.\n"
            "The patient underwent aHSCT as a beneficial therapy with improved symptoms.\n"
            "Disclosure: The authors have nothing to disclose.\n"
            "SUBSCRIBERS Sign Up for eAlerts FOLLOW US AAN.COM © 2023 American Academy of Neurology.\n",
            paper_id="9155",
        )

        self.assertIn("A 59-year-old patient", selected)
        self.assertIn("aHSCT", selected)
        self.assertNotIn("Disclosure:", selected)
        self.assertNotIn("SUBSCRIBERS", selected)

    def test_single_case_spot_check_keeps_patient_specific_discussion_follow_up(self) -> None:
        selected = self.single_case_selected_text(
            "Characterization of CD4+ T cells specific for glutamic acid decarboxylase (GAD65) "
            "and proinsulin in a patient with stiff-person syndrome but without type 1 diabetes\n"
            "Abstract\n"
            "Background Glutamic acid decarboxylase is an important autoantigen.\n"
            "Methods In this study, we monitored CD4+ T-cell responses to GAD65 and proinsulin in a "
            "patient with SPS who remained normoglycaemic during the 46-month follow-up.\n"
            "Keywords autoantibodies; tetramers; proinsulin; stiff-person; GADA\n"
            "Introduction Stiff-person syndrome is a rare neurological disorder.\n"
            "The patient\n"
            "The patient is a 33-year-old Caucasian female, previously healthy other than having partial complex epilepsy.\n"
            "Blood glucose levels were monitored every 3-6 months for 42 months and oral glucose tolerance tests were normal.\n"
            "Peripheral blood samples for this study were obtained after informed consent.\n"
            "Results T-cell responses to GAD65 persisted throughout the follow-up.\n"
            "Discussion In this study, we analysed CD4+ T-cell responses and autoantibodies in a series of samples "
            "from a female patient who developed SPS at the age of 29. This patient did not progress to T1D during "
            "the 46-month follow-up.\n"
            "In summary, this longitudinal study of T-cell and antibody reactivity in a patient with SPS suggests "
            "slow or no progression towards clinical manifestation of T1D. Continued follow-up will be needed.\n"
            "Acknowledgements This work was supported by grants.\n"
            "References 1. Duddy ME.\n",
            paper_id="9156",
        )

        self.assertIn("33-year-old Caucasian female", selected)
        self.assertIn("oral glucose tolerance tests were normal", selected)
        self.assertIn("Continued follow-up will be needed", selected)
        self.assertNotIn("GAD65 enzyme activity assay", selected)
        self.assertNotIn("Discussion In this study", selected)
        self.assertNotIn("Acknowledgements", selected)
        self.assertNotIn("References 1.", selected)

    def test_resolve_source_uses_full_text_when_trim_ends_at_footer_interruption(self) -> None:
        trimmed_path = self.write_text_json_at(
            "text_trimmed",
            "9044",
            "A 40-year-old man had stiff-person syndrome. Serum and cerebrospinal fluid were\n"
            "*Dept. of Medicine, Example Hospital.\n"
            "Received : 1.1.1998; Accepted : 2.1.1998",
        )
        full_path = self.write_text_json_at(
            "text",
            "9044",
            "A 40-year-old man had stiff-person syndrome. Serum and cerebrospinal fluid were "
            "positive for GAD antibodies. Treatment with diazepam and baclofen helped.\n"
            + ("Follow-up remained stable. " * 80),
        )
        original_text_dir = core.TEXT_DIR
        try:
            core.TEXT_DIR = self.tmp_path / "text"
            resolved = core.resolve_source_json_path(
                paper_id="9044",
                source_row={},
                stage06_prior=core.Stage06Prior(
                    final_count=1,
                    count_confidence="high",
                    count_basis="test",
                    manual_review_required=False,
                    preferred_text_json_path=str(trimmed_path),
                ),
            )
        finally:
            core.TEXT_DIR = original_text_dir

        self.assertEqual(resolved, full_path)

    def test_resolve_source_uses_full_text_when_trim_is_only_title_fragment(self) -> None:
        trimmed_path = self.write_text_json_at(
            "text_trimmed",
            "9046",
            "Focal stiff-person syndrome\nM. Example\nDepartment of Neurology",
        )
        full_path = self.write_text_json_at(
            "text",
            "9046",
            "Focal stiff-person syndrome\n"
            "Case report\n"
            "A 39-year-old woman developed gait instability, spasms, and stiffness "
            "restricted to both legs. Serum and CSF anti-GAD antibodies were positive.\n"
            + ("Treatment follow-up remained source-backed. " * 80),
        )
        original_text_dir = core.TEXT_DIR
        try:
            core.TEXT_DIR = self.tmp_path / "text"
            resolved = core.resolve_source_json_path(
                paper_id="9046",
                source_row={},
                stage06_prior=core.Stage06Prior(
                    final_count=1,
                    count_confidence="high",
                    count_basis="test",
                    manual_review_required=False,
                    preferred_text_json_path=str(trimmed_path),
                ),
            )
        finally:
            core.TEXT_DIR = original_text_dir

        self.assertEqual(resolved, full_path)

    def test_resolve_source_uses_full_text_for_incomplete_pediatric_sls_trim(self) -> None:
        trimmed_path = self.write_text_json_at(
            "text_trimmed",
            "11903",
            "Pediatric stiff limb syndrome with polyautoimmunity of anti-GAD-65,\n"
            "anti-islet cell, and thyroid peroxidase antibodies: A case report and review\n"
            "of literature\nAuthors and affiliations\nARTICLE INFO\nKeywords:\nStiff limb syndrome",
        )
        full_path = self.write_text_json_at(
            "text",
            "11903",
            "Pediatric stiff limb syndrome with polyautoimmunity of anti-GAD-65,\n"
            "anti-islet cell, and thyroid peroxidase antibodies: A case report and review of literature\n"
            "3. Case presentation\n"
            "An 18-month-old female presented with inability to bear weight, wobbly gait, positive anti-GAD-65 antibodies, IVIG, and clonazepam response.\n"
            + ("Full text case continuation remained available. " * 80),
        )
        original_text_dir = core.TEXT_DIR
        try:
            core.TEXT_DIR = self.tmp_path / "text"
            resolved = core.resolve_source_json_path(
                paper_id="11903",
                source_row={},
                stage06_prior=core.Stage06Prior(
                    final_count=1,
                    count_confidence="high",
                    count_basis="test",
                    manual_review_required=False,
                    preferred_text_json_path=str(trimmed_path),
                ),
            )
        finally:
            core.TEXT_DIR = original_text_dir

        self.assertEqual(resolved, full_path)

    def test_resolve_source_uses_full_text_when_trim_is_only_abstract(self) -> None:
        trimmed_path = self.write_text_json_at(
            "text_trimmed",
            "9063",
            "Case report\n"
            "Anesthetic management of a patient with stiff person syndrome\n"
            "Abstract We describe the successful anesthetic management of a patient "
            "with stiff-person syndrome under conscious sedation.",
        )
        full_path = self.write_text_json_at(
            "text",
            "9063",
            "Case report\n"
            "Anesthetic management of a patient with stiff person syndrome\n"
            "Abstract We describe the successful anesthetic management of a patient "
            "with stiff-person syndrome under conscious sedation.\n"
            "1. Introduction\n"
            "SPS anaesthesia background.\n"
            "2. Case report\n"
            "A 65-year-old man with SPS underwent right inguinal hernia repair. "
            "A somatic paravertebral block was used with conscious sedation.\n"
            + ("Postoperative follow-up remained stable. " * 80),
        )
        original_text_dir = core.TEXT_DIR
        try:
            core.TEXT_DIR = self.tmp_path / "text"
            resolved = core.resolve_source_json_path(
                paper_id="9063",
                source_row={},
                stage06_prior=core.Stage06Prior(
                    final_count=1,
                    count_confidence="high",
                    count_basis="test",
                    manual_review_required=False,
                    preferred_text_json_path=str(trimmed_path),
                ),
            )
        finally:
            core.TEXT_DIR = original_text_dir

        self.assertEqual(resolved, full_path)

    def test_resolve_source_uses_full_text_for_kodama_trimmed_abstract(self) -> None:
        trimmed_path = self.write_text_json_at(
            "text_trimmed",
            "1764",
            "Rituximab improves not only back stiffness but also stiff eyes in stiff person syndrome\n"
            "Objective: We recorded saccade movements in an SPS patient.\n"
            "Methods: We repeatedly conducted saccade eye recordings using video-based eye tracking system "
            "on a 42-year-old male SPS patient with slow saccade.\n"
            "Results: Other neurological symptoms in this patient improved after rituximab.\n"
            "Conclusion: Slow saccade in a stiff eyes patient improved after rituximab administration.\n",
        )
        full_path = self.write_text_json_at(
            "text",
            "1764",
            "Rituximab improves not only back stiffness but also stiff eyes in stiff person syndrome\n"
            "Objective: We recorded saccade movements in an SPS patient.\n"
            "1. Introduction\n"
            "Generic SPS ocular background.\n"
            "2. Methods\n"
            "2. 1. Case presentation\n"
            "The patient was a 42-year-old man with SPS, serum anti-GAD 96,000 IU/mL, "
            "stiff eyes, IVIG and rituximab response.\n"
            + ("Detailed full-text case follow-up remained available. " * 80),
        )
        original_text_dir = core.TEXT_DIR
        try:
            core.TEXT_DIR = self.tmp_path / "text"
            resolved = core.resolve_source_json_path(
                paper_id="1764",
                source_row={},
                stage06_prior=core.Stage06Prior(
                    final_count=1,
                    count_confidence="high",
                    count_basis="test",
                    manual_review_required=False,
                    preferred_text_json_path=str(trimmed_path),
                ),
            )
        finally:
            core.TEXT_DIR = original_text_dir

        self.assertEqual(resolved, full_path)

    def test_resolve_source_uses_full_text_for_incomplete_spasmodic_reflex_trim(self) -> None:
        trimmed_path = self.write_text_json_at(
            "text_trimmed",
            "1918",
            "F59. Spasmodic reflex myoclonus-an characteristic electrophysiological manifestation "
            "for the diagnosis of Stiff-person syndrome\n"
            "Introduction: generic SPS electrophysiology background.\n"
            "Methods: Multichannel surface electromyogram recordings were conducted.",
        )
        full_path = self.write_text_json_at(
            "text",
            "1918",
            "F59. Spasmodic reflex myoclonus-an characteristic electrophysiological manifestation "
            "for the diagnosis of Stiff-person syndrome\n"
            "Introduction: generic SPS electrophysiology background.\n"
            "Methods: Multichannel surface electromyogram recordings were conducted.\n"
            "Results: The results demonstrated spontaneous onset of spasm of the low trunk and legs. "
            "The serum levels of anti-glutamic acid decarboxylase 65 antibodies was 164 IU.\n"
            "Conclusion: The unique EMG pattern can help identify SPS.\n"
            + ("Proceedings continuation was available. " * 90),
        )
        original_text_dir = core.TEXT_DIR
        try:
            core.TEXT_DIR = self.tmp_path / "text"
            resolved = core.resolve_source_json_path(
                paper_id="1918",
                source_row={},
                stage06_prior=core.Stage06Prior(
                    final_count=1,
                    count_confidence="high",
                    count_basis="test",
                    manual_review_required=False,
                    preferred_text_json_path=str(trimmed_path),
                ),
            )
        finally:
            core.TEXT_DIR = original_text_dir

        self.assertEqual(resolved, full_path)

    def test_resolve_source_uses_full_text_for_incomplete_sps_cytoskeleton_trim(self) -> None:
        trimmed_path = self.write_text_json_at(
            "text_trimmed",
            "6796",
            "SC203\n"
            "Clinical and cell biology analysis of stiff person\n"
            "syndrome with eye movement and cerebellar abnormalities.\n"
            "Objective: To investigate structure of muscle and cytoskeleton\n"
            "proteins titin and nebulin in stiff person syndrome (SPS).\n"
            "Background: A 49-year-old lady with stiffness and tension of axial muscles developed diplopia.",
        )
        full_path = self.write_text_json_at(
            "text",
            "6796",
            "SC203\n"
            "Clinical and cell biology analysis of stiff person\n"
            "syndrome with eye movement and cerebellar abnormalities.\n"
            "Objective: To investigate structure of muscle and cytoskeleton\n"
            "proteins titin and nebulin in stiff person syndrome (SPS).\n"
            "Background: A 49-year-old lady with stiffness and tension of axial muscles developed diplopia.\n"
            "Design and methods: Biopsy from erector spinae muscle was analysed.\n"
            "Results: Structure of the muscle tissue was normal and titin and nebulin were decreased.\n"
            "Conclusions: Sustained increase of muscle activity leads to destruction of titin and nebulin.\n"
            + ("Proceedings continuation remained available. " * 60),
        )
        original_text_dir = core.TEXT_DIR
        try:
            core.TEXT_DIR = self.tmp_path / "text"
            resolved = core.resolve_source_json_path(
                paper_id="6796",
                source_row={},
                stage06_prior=core.Stage06Prior(
                    final_count=1,
                    count_confidence="high",
                    count_basis="test",
                    manual_review_required=False,
                    preferred_text_json_path=str(trimmed_path),
                ),
            )
        finally:
            core.TEXT_DIR = original_text_dir

        self.assertEqual(resolved, full_path)

    def test_resolve_source_uses_full_text_when_trim_ends_mid_case(self) -> None:
        trimmed_path = self.write_text_json_at(
            "text_trimmed",
            "9086",
            "Case report\n"
            "A 76-year-old man with stiff-person syndrome underwent thymectomy. "
            "Anesthesia was maintained with sevoflurane and oxygen. "
            + ("The intraoperative course was stable. " * 55)
            + "End-tidal carbon dioxide (CO",
        )
        full_path = self.write_text_json_at(
            "text",
            "9086",
            "Case report\n"
            "A 76-year-old man with stiff-person syndrome underwent thymectomy. "
            "Anesthesia was maintained with sevoflurane and oxygen. "
            + ("The intraoperative course was stable. " * 55)
            + "End-tidal carbon dioxide (CO2) was maintained throughout anesthesia. "
            "The postoperative course was uneventful.\n"
            "Discussion\n"
            "The patient had no postoperative rigidity.\n"
            + ("Additional complete full-text follow-up remained available. " * 45),
        )
        original_text_dir = core.TEXT_DIR
        try:
            core.TEXT_DIR = self.tmp_path / "text"
            resolved = core.resolve_source_json_path(
                paper_id="9086",
                source_row={},
                stage06_prior=core.Stage06Prior(
                    final_count=1,
                    count_confidence="high",
                    count_basis="test",
                    manual_review_required=False,
                    preferred_text_json_path=str(trimmed_path),
                ),
            )
        finally:
            core.TEXT_DIR = original_text_dir

        self.assertEqual(resolved, full_path)

    def test_resolve_source_uses_full_text_for_incomplete_baclofen_poster_ready_text(self) -> None:
        ready_path = self.write_text_json_at(
            "text_proceedings_ready",
            "5808",
            "Severe, Prolonged Baclofen Withdrawal Following a Second\n"
            "Discussion\nGeneric baclofen withdrawal background without the case table.",
        )
        full_path = self.write_text_json_at(
            "text",
            "5808",
            "Clinical Importance\nGeneric poster purpose.\n"
            "Patient Case\n"
            "HPI : A 54-year old female presented with urosepsis.\n"
            "PMH : SPS (anti-GAD 65 Ab+) diagnosed 2004, ITB pump placed 2004.\n"
            + ("Hospital course details remained available. " * 80),
        )
        original_text_dir = core.TEXT_DIR
        original_proceedings_ready_dir = core.TEXT_PROCEEDINGS_READY_DIR
        try:
            core.TEXT_DIR = self.tmp_path / "text"
            core.TEXT_PROCEEDINGS_READY_DIR = self.tmp_path / "text_proceedings_ready"
            resolved = core.resolve_source_json_path(
                paper_id="5808",
                source_row={},
                stage06_prior=core.Stage06Prior(
                    final_count=1,
                    count_confidence="high",
                    count_basis="test",
                    manual_review_required=False,
                    preferred_text_json_path=str(self.tmp_path / "missing" / "5808.json"),
                ),
            )
        finally:
            core.TEXT_DIR = original_text_dir
            core.TEXT_PROCEEDINGS_READY_DIR = original_proceedings_ready_dir

        self.assertEqual(resolved, full_path)

    def test_single_case_case_report_prefers_local_spsd_context_in_embedded_issue(self) -> None:
        source_path = self.write_text_json(
            "9047",
            "Unrelated movement disorders article.\n"
            "Case Report\n"
            "A 64-year-old man had corticobasal degeneration and limb apraxia.\n"
            "Discussion\n"
            "Our patient had CBD.\n"
            "Marked Improvement in a Stiff-Limb Patient\n"
            "Treated With Intravenous Immunoglobulin\n"
            "Stiff-limb syndrome causes stiffness and painful spasms.\n"
            "Case Report\n"
            "A 60-year-old woman had frequent falls, painful spasms, and persistent "
            "rigidity in the left leg. Serum anti-GAD antibodies were present.\n"
            "Discussion\n"
            "Our patient has the clinical findings of stiff-limb syndrome.\n"
            "Carlos Example, MD\n"
            "Department of Neurology\n"
            "References\n1. Brown P.",
        )
        prepared = core.prepare_source(paper_id="9047", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9047",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 60-year-old woman", text)
        self.assertIn("Serum anti-GAD antibodies", text)
        self.assertNotIn("A 64-year-old man", text)
        self.assertNotIn("Department of Neurology", text)

    def test_single_case_excludes_embedded_abstract_boilerplate_inside_case(self) -> None:
        source_path = self.write_text_json(
            "9064",
            "Case report\n"
            "A 49-year-old housewife with stiff person syndrome had abdominal stiffness. "
            "The EMG of the affected regions reported:\n"
            "Abstract The \"Stiff person syndrome\" is a rare dysimmune chronic neurological disorder. "
            "We described an unusual case of autoimmune SPS associated with motor neuropathy. "
            "Parole chiavi: anticorpi anti decarbossilasi dell'acido glutammico, sindrome dell'uomo rigido\n"
            "- persistent muscle activity despite the patient's attempt to relax.\n"
            "Laboratory tests found anti-GAD antibodies in serum.\n"
            "Discussion\nGeneric SPS treatment background.",
        )
        prepared = core.prepare_source(paper_id="9064", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9064",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("49-year-old housewife", text)
        self.assertIn("persistent muscle activity", text)
        self.assertIn("anti-GAD antibodies", text)
        self.assertNotIn("rare dysimmune chronic neurological disorder", text)
        self.assertNotIn("Parole chiavi", text)

    def test_single_case_excludes_inline_page_metadata_without_losing_case_body(self) -> None:
        source_path = self.write_text_json(
            "9065",
            "Case report\n"
            "A 41-year-old female patient with SPS developed spasms and lower back stiff-\n"
            "Neurol Sci (2007) 28:35-37 DOI 10.1007/s10072-007-0745-9 "
            "E. Andreadou Stiff person syndrome: avoiding misdiagnosis CASE REPORT "
            "Abstract Stiff person syndrome is a rare neurological disorder. "
            "Key words Movement disorders. Department of Neurology of Athens National University. "
            "E. Kattoulas Department of Psychiatry Evaggelismos Hospital, Athens, Greece\n"
            "ness and difficulty in walking.\n"
            "KEYWORDS antibodies, anxiety, glutamic acid decarboxylase "
            "CME Example author. Correspondence: Department of Neurology. "
            "doi:10.1038/ncpneuro0259 SUMMARY AUGUST 2006 VOL 2 NO 8 "
            "NATURE CLINICAL PRACTICE NEUROLOGY 455 CASE STUDY 456 "
            "www.nature.com/clinicalpractice/neuro\n"
            "A systems review revealed weight loss and anxiety.\n"
            "However, SPS is a "
            "Downloaded from http://journals.lww.com/cmj by token on 05/31/2023 "
            "Chinese Medical Journal 2006; 119(11):963-965 965 rarely occurring disease.\n"
            "In conclusion, the case illustrates that stiff-person syndrome can precede lymphoma.\n"
            "haematologica online 2006 haematologica/the hematology journal | 2006; 91(online) | 161 | "
            "Bernd Gutmann,1 Example Author 1Department of Internal Medicine. "
            "Correspondence: Example Author.\n"
            "References\n1. Generic reference.",
        )
        prepared = core.prepare_source(paper_id="9065", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9065",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("41-year-old female patient", text)
        self.assertIn("ness and difficulty in walking", text)
        self.assertIn("A systems review revealed", text)
        self.assertIn("rarely occurring disease", text)
        self.assertIn("can precede lymphoma", text)
        self.assertNotIn("Neurol Sci", text)
        self.assertNotIn("KEYWORDS", text)
        self.assertNotIn("Downloaded from", text)
        self.assertNotIn("haematologica online", text)
        self.assertNotIn("Generic reference", text)

    def test_single_case_excludes_inline_journal_metadata_and_page_headers(self) -> None:
        source_path = self.write_text_json(
            "9067",
            "Case report\n"
            "A 65-year-old man with SPS was scheduled for hernia repair. "
            "Past surgical history was remarkable for an uneventful "
            "0952-8180/$ - see front matter D 2006 Elsevier Inc. All rights reserved. "
            "doi:10.1016/j.jclinane.2005.06.009 * Corresponding author. "
            "E-mail address: example@clinic.org. 1 Center for Anesthesiology Education. "
            "Keywords: Regional anesthesia; Stiff person syndrome; Paravertebral block "
            "Journal of Clinical Anesthesia (2006) 18, 218 - 220 "
            "repair of a left inguinal hernia in 1965. "
            "Nature Publishing Group ©2006 CASE STUDY AUGUST 2006 VOL 2 NO 8 "
            "NATURE CLINICAL PRACTICE NEUROLOGY 457 www.nature.com/clinicalpractice/neuro "
            "Anti-GAD antibodies were present and a paravertebral block was used.\n"
            "Discussion\nGeneric anaesthesia background.",
        )
        prepared = core.prepare_source(paper_id="9067", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9067",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("65-year-old man", text)
        self.assertIn("repair of a left inguinal hernia", text)
        self.assertIn("Anti-GAD antibodies", text)
        self.assertNotIn("0952-8180", text)
        self.assertNotIn("Journal of Clinical Anesthesia", text)
        self.assertNotIn("Nature Publishing Group", text)

    def test_single_case_abstract_stops_at_keywords_and_excludes_correspondence_footer(self) -> None:
        source_path = self.write_text_json(
            "9068",
            "ABSTRACT Purpose: To describe a case in a patient with stiff-person syndrome. "
            "Results: A 55-year-old woman with stable stiff-person syndrome developed anterior scleritis. "
            "KEYWORDS Stiff-person syndrome; scleritis INTRODUCTION Generic SPS background.\n"
            "CASE REPORT\n"
            "A 55-year-old woman with stable stiff-person syndrome complained of left eye pain and "
            "Accepted 30 November 2006. Correspondence and reprint requests to: Example Author, "
            "9500 Euclid Avenue. Tel: 216-444-3642; Fax: 216-445-8475; e-mail: lowderc@ccf.org 37 "
            "redness of one-week duration. The patient was started on ibuprofen.\n"
            "M. Taban et al. 38 \nDISCUSSION\n"
            "Generic autoimmune SPS background.",
        )
        prepared = core.prepare_source(paper_id="9068", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9068",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("55-year-old woman", text)
        self.assertIn("redness of one-week duration", text)
        self.assertIn("ibuprofen", text)
        self.assertNotIn("Generic SPS background", text)
        self.assertNotIn("Correspondence and reprint requests", text)
        self.assertNotIn("Taban et al.", text)

    def test_single_case_skips_post_reference_literature_table(self) -> None:
        source_path = self.write_text_json(
            "9066",
            "Case report\n"
            "A 53-year-old man with paraneoplastic SPS had anti-GAD antibodies and renal carcinoma. "
            "Nephrectomy and IVIG improved spasms.\n"
            "Discussion\n"
            "We conclude that renal cell carcinoma should be considered in SPS.\n"
            "References\n1. Example.\n"
            "TABLE 1. Summary of reported cases of paraneoplastic stiff person syndrome\n"
            "Author Cancer Auto-antibody Syndrome Treatment\n"
            "Hagiwara Thymoma GAD SPS benzodiazepines\n"
            "Deep Brain Stimulation in Tourette's Syndrome\n"
            "A 48-year-old man with Tourette's syndrome underwent DBS.",
        )
        prepared = core.prepare_source(paper_id="9066", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9066",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("53-year-old man", text)
        self.assertIn("renal carcinoma", text)
        self.assertNotIn("Summary of reported cases", text)
        self.assertNotIn("Tourette", text)

    def test_single_case_keeps_patient_relevant_patients_with_sps_sentence(self) -> None:
        source_path = self.write_text_json(
            "9069",
            "CASE REPORT\n"
            "A 58-year-old man with SPS had thymoma and underwent anaesthesia.\n"
            "DISCUSSION\n"
            "In our case, The patient did not develop prolonged muscle weakness. "
            "However, SPS is a rarely occurring disease. It is still not clear why some\n"
            "patients with SPS developed prolonged hypotonicity after general anaesthesia.\n"
            "REFERENCES\n1. Example.",
        )
        prepared = core.prepare_source(paper_id="9069", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9069",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("58-year-old man", text)
        self.assertIn("patients with SPS developed prolonged hypotonicity", text)
        self.assertNotIn("REFERENCES", text)

    def test_single_case_literature_review_title_does_not_append_review_discussion(self) -> None:
        source_path = self.write_text_json(
            "9081",
            "ABSTRACT\n"
            "We present a case of a 52-year-old woman with stiff-person syndrome and Graves disease.\n"
            "CASE REPORT AND LITERATURE REVIEW\n"
            "CASE REPORT\n"
            "A 52-year-old woman had stiff-person syndrome, Graves disease, anti-GAD antibodies, "
            "and improved after prednisone and azathioprine.\n"
            "Table 1 Results of serial thyroid function tests in study patient.\n"
            "DISCUSSION\n"
            "Our patient was positive for HLA-DQB1*0201 and HLA-DRB1*03.\n"
            "Immunosuppressive therapy has different effects on the course of Graves disease. "
            "Several published patients are reviewed here.\n"
            "REFERENCES\n1. Generic reference.",
        )
        prepared = core.prepare_source(paper_id="9081", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9081",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("52-year-old woman", text)
        self.assertIn("Table 1 Results", text)
        self.assertNotIn("Immunosuppressive therapy has different effects", text)
        self.assertNotIn("Generic reference", text)

    def test_single_case_discussion_stops_at_patients_with_sps_might_benefit(self) -> None:
        source_path = self.write_text_json(
            "9082",
            "CASE REPORT\n"
            "A 33-year-old man with SPS completed inpatient rehabilitation and gait training.\n"
            "DISCUSSION\n"
            "The patient made functional gains during admission. "
            "Patients with SPS might benefit from longer rehabilitation stays and broader programs.\n"
            "CONCLUSION\n"
            "Generic future research is needed.\n",
        )
        prepared = core.prepare_source(paper_id="9082", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9082",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("33-year-old man", text)
        self.assertIn("made functional gains", text)
        self.assertNotIn("Patients with SPS might benefit", text)
        self.assertNotIn("Generic future research", text)

    def test_single_case_discussion_stops_at_generic_positive_antibody_sentence(self) -> None:
        source_path = self.write_text_json(
            "9087",
            "CASE REPORT\n"
            "A 55-year-old woman with SPS-plus had depression, ataxia, and serum anti-GAD antibodies.\n"
            "DISCUSSION\n"
            "The patient had no other autoimmune disorders and her family history was negative. "
            "Patients with SPS and positive anti-GAD auto-antibodies were found to have additional "
            "autoimmune disorders in prior reports.\n",
        )
        prepared = core.prepare_source(paper_id="9087", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9087",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("55-year-old woman", text)
        self.assertIn("family history was negative", text)
        self.assertNotIn("prior reports", text)

    def test_single_case_discussion_skips_prior_anaesthesia_cases(self) -> None:
        source_path = self.write_text_json(
            "9083",
            "CASE REPORT\n"
            "A 58-year-old man with SPS underwent thymoma resection. Rocuronium was used, "
            "neuromuscular monitoring recovered to 100%, and he was extubated shortly after operation.\n"
            "DISCUSSION\n"
            "Several cases were reported about anesthetic management of patients with SPS. "
            "Johnson and Millar reported a 46-year-old woman with SPS. The patient developed prolonged "
            "hypotonia and was mechanically ventilated overnight. In another case, a 62-year-old woman "
            "with SPS also developed prolonged muscle weakness.\n"
            "REFERENCES\n1. Generic.",
        )
        prepared = core.prepare_source(paper_id="9083", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9083",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("58-year-old man", text)
        self.assertIn("neuromuscular monitoring recovered", text)
        self.assertNotIn("46-year-old woman", text)
        self.assertNotIn("62-year-old woman", text)
        self.assertNotIn("Generic.", text)

    def test_single_case_age_anchor_accepts_yr_old_phrase(self) -> None:
        source_path = self.write_text_json(
            "9057",
            "Stiff Person Syndrome and Anesthesia: Case Report\n"
            "Case Report\n"
            "A 62-yr-old woman had SPS with stiffness, painful cramps, positive GAD "
            "antibodies, and prolonged weakness after anaesthesia.\n"
            "Discussion\nGeneric anaesthesia context.",
        )
        prepared = core.prepare_source(paper_id="9057", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9057",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("62-yr-old woman", text)
        self.assertIn("prolonged weakness", text)

    def test_single_case_age_anchor_accepts_aged_years_phrase_and_appends_results_table(self) -> None:
        source_path = self.write_text_json(
            "9058",
            "Stiff person syndrome does not always occur with maternal passive transfer.\n"
            "Patients and methods. Patient history. A woman aged 31 years developed "
            "stiffness, painful spasms, epilepsy, and SPS. Diazepam gave temporary response.\n"
            "Methods. Anti-GAD65 was detected by immunoprecipitation assay.\n"
            "Results. The profile of anti-GAD65 in the mother and two newborns is "
            "summarized in the table.\n"
            "Discussion. The affected mother had SPS; the newborns remained asymptomatic.\n"
            "References\n1. Example.\n"
            "Table Anti-GAD65 titers before and after pregnancy\n"
            "Evaluation Mother anti-GAD65 titer Firstborn anti-GAD65 titer\n"
            "Before pregnancy >1:100,000\n"
            "24 mo after birth 1:100 1:100\n"
            "DOI 10.1212/example",
        )
        prepared = core.prepare_source(paper_id="9058", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9058",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("woman aged 31 years", text)
        self.assertIn("profile of anti-GAD65", text)
        self.assertIn("Before pregnancy >1:100,000", text)
        self.assertNotIn("immunoprecipitation assay", text)
        self.assertNotIn("References\n1. Example", text)

    def test_single_case_abstract_accepts_at_the_age_of_years_phrase(self) -> None:
        source_path = self.write_text_json(
            "9079",
            "Abstract. We report the case of a female patient, who died at the age of 66 years. "
            "She had developed the clinical symptoms of stiff-man syndrome and harboured "
            "autoantibodies against glutamate-decarboxylase.\n"
            "Results\n"
            "Anamnestic findings\n"
            "The disease of the 66-year-old woman started with neck stiffness and convulsions. "
            "GAD antibodies persisted.\n"
            "Discussion\n"
            "Generic disease discussion.\n",
        )
        prepared = core.prepare_source(paper_id="9079", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9079",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("Abstract. We report the case", text)
        self.assertIn("died at the age of 66 years", text)
        self.assertIn("The disease of the 66-year-old woman", text)

    def test_single_case_embedded_issue_does_not_use_distant_spsd_label_for_phenotype(self) -> None:
        source_path = self.write_text_json(
            "9059",
            "Case Report\n"
            "A 70-year-old man had thalamic haemorrhage and facial spasms.\n"
            "Discussion\n"
            "This was secondary dystonia.\n"
            "Pregnancy in Stiff-Limb Syndrome\n"
            "SLS is a stiff-person spectrum disorder.\n"
            "Case Report\n"
            "This 41-year-old woman was diagnosed with SLS after lower limb spasms. "
            "She improved during pregnancy and relapsed postpartum.\n"
            "Discussion\n"
            "The SLS case shows pregnancy can alter symptoms.",
        )
        prepared = core.prepare_source(paper_id="9059", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9059",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("41-year-old woman", text)
        self.assertIn("relapsed postpartum", text)
        self.assertNotIn("70-year-old man", text)

    def test_single_case_spsd_title_prefers_local_letter_case(self) -> None:
        source_path = self.write_text_json(
            "9086",
            "Cerebellar and Pyramidal Dysfunctions\n"
            "We report the case of a patient with an ataxic-spastic syndrome at the age of 3 years.\n"
            "The patient is a 30-year-old man with parkinsonism, rigidity, and weakness.\n"
            "References\n1. Parkinsonism reference.\n"
            "Stiff-Three Limbs Syndrome\n"
            "Video\n"
            "Stiff-Person syndrome (SPS) is a rare disorder.\n"
            "We report a patient diagnosed with stiff-three limbs syndrome (STLS), without CMUA, "
            "successfully treated with intravenous immunoglobulin.\n"
            "An 11-year-old girl was admitted with a 2-year history of limb paralysis, dysarthria, "
            "painful rigidity in the right upper and both lower limbs, and anti-GAD positivity.\n"
            "Additional Supporting Information may be found in the online\n"
            "version of this article.\n"
            "Published online 24 October 2008 in Wiley InterScience\n"
            "(www.interscience.wiley.com). DOI: 10.1002/mds.22344\n"
            "311LETTERS TO THE EDITOR\n"
            "Movement Disorders, Vol. 24, No. 2, 2009\n"
            " 15318257, 2009, 2, Downloaded from https://movementdisorders.onlinelibrary.wiley.com/doi/10.1002/mds.22344 "
            "by library. See the Terms and Conditions on Wiley Online Library for rules of use; "
            "OA articles are governed by the applicable Creative Commons License\n"
            "limb showed no signs of abnormal tone strength.\n"
            "References\n1. Barker reference.\n"
            "Extrapyramidal Reaction to Ondansetron and Propofol\n"
            "A 26-year-old man had an unrelated reaction.",
        )
        prepared = core.prepare_source(paper_id="9086", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9086",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("Stiff-Three Limbs Syndrome", text)
        self.assertIn("11-year-old girl", text)
        self.assertIn("anti-GAD positivity", text)
        self.assertIn("limb showed no signs", text)
        self.assertNotIn("30-year-old man", text)
        self.assertNotIn("Additional Supporting Information", text)
        self.assertNotIn("Extrapyramidal Reaction", text)

    def test_single_case_skips_design_case_report_label_and_uses_patient_body(self) -> None:
        source_path = self.write_text_json(
            "9060",
            "Downbeating Nystagmus and Muscle Spasms in a Patient with GAD Antibodies\n"
            "DESIGN:Case report.\n"
            "METHODS: A 55-year-old woman developed progressive low back muscle spasms.\n"
            "RESULTS: Serum and cerebrospinal fluid GAD antibodies were detected.\n"
            "CONCLUSIONS: Patients with GAD antibodies may have elements of Stiff-person syndrome.\n"
            "A 55-year-old woman with IDDM presented with lower back muscle spasms, diplopia, "
            "ataxia, GAD antibodies in serum and CSF, and treatment response to diazepam and IVIg.\n"
            "REFERENCES\n1. Example.",
        )
        prepared = core.prepare_source(paper_id="9060", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9060",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("lower back muscle spasms", text)
        self.assertNotEqual(text.strip(), "Case report.")
        self.assertNotIn("REFERENCES", text)

    def test_single_case_skips_journal_page_header_case_report_label(self) -> None:
        source_path = self.write_text_json(
            "9061",
            "Stiff Man Syndrome With Thymoma\n"
            "We treated a 57-year-old woman who had stiff man syndrome.\n"
            "A 57-year-old woman was admitted with continuous muscle stiffness and painful spasms. "
            "Anti-GAD antibody was high and thymectomy improved symptoms.\n"
            "Accepted for publication Feb 10, 2004.\n"
            "Address reprint requests to Dr Tanaka.\n"
            "Fig 1. Computed tomographic scan shows an anterior mediastinal tumor.\n"
            "739Ann Thorac Surg CASE REPORT TANAKA ET AL\n"
            "2005;80:739 - 41 STIFF MAN SYNDROME WITH THYMOMA\n"
            "computed tomography showed an anterior mediastinal tumor and thymectomy was performed.\n"
            "Table 1. Review of Stiff Man Syndrome With a Thymoma\n"
            "Nicholas et al 55 M thymoma.\n"
            "Papillary Carcinoma of the Thymus Gland\n"
            "References\n1. Example.",
        )
        prepared = core.prepare_source(paper_id="9061", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9061",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("57-year-old woman", text)
        self.assertIn("thymectomy improved", text)
        self.assertIn("computed tomography showed", text)
        self.assertNotIn("CASE REPORT TANAKA", text)
        self.assertNotIn("Accepted for publication", text)
        self.assertNotIn("Nicholas et al", text)
        self.assertNotIn("Papillary Carcinoma", text)

    def test_single_case_accepts_ocr_stift_man_label(self) -> None:
        source_path = self.write_text_json(
            "9062",
            "Borrelia myelitis presenting as a partial stift man syndrome\n"
            "Case report\n"
            "A healthy man aged 33 years developed stiffness of one leg and painful jerks "
            "resembling stift man syndrome after a tick bite.\n"
            "References\n1. Example.",
        )
        prepared = core.prepare_source(paper_id="9062", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9062",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("man aged 33 years", text)
        self.assertNotIn("References", text)

    def test_single_case_accepts_conjoined_stiffman_label(self) -> None:
        source_path = self.write_text_json(
            "9073",
            "Sporadic Stiffman Syndrome in a Young Girl\n"
            "Case Report\n"
            "A 14-month-old girl had breath-holding spells, trunk and limb spasms, "
            "continuous motor unit activity, and response to diazepam and baclofen.\n"
            "Discussion\nGeneric Stiffman syndrome background.",
        )
        prepared = core.prepare_source(paper_id="9073", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9073",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("14-month-old girl", text)
        self.assertIn("diazepam and baclofen", text)
        self.assertNotIn("Generic Stiffman", text)

    def test_single_case_age_anchor_accepts_progressive_encephalomyelitis_with_rigidity(self) -> None:
        source_path = self.write_text_json(
            "9048",
            "Unrelated letter\nA 41-year-old man had bronchial asthma.\nReferences\n"
            "Progressive encephalomyelitis\nwith rigidity as refractory asthma\n"
            "We report a 19 year\nold woman with stridor who developed progressive "
            "encephalomyelitis with rigidity (PER).\n"
            "The patient had dyspnoea, board-like rigidity, miosis, stridor, urinary "
            "retention, and continuous motor unit discharges that decreased after diazepam.\n"
            "References\n1. Kasperek S.\n"
            "Impaired cough reflex in patients with recurrent pneumonia\n"
            "A separate letter follows.",
        )
        prepared = core.prepare_source(paper_id="9048", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9048",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("19 year\nold woman", text)
        self.assertIn("continuous motor unit discharges", text)
        self.assertNotIn("41-year-old man", text)
        self.assertNotIn("Impaired cough reflex", text)

    def test_single_case_skips_article_type_case_report_before_abstract(self) -> None:
        source_path = self.write_text_json(
            "9051",
            "Case report\n"
            "Stiff-person syndrome associated with example treatment\n"
            "Example Author, MD\n"
            "Abstract\n"
            "We describe a patient with muscle stiffness.\n"
            "1. Introduction\n"
            "Background on retinoids and SPS.\n"
            "An 18-year-old male patient developed disabling stiffness and painful "
            "spasms 10 days after the onset of treatment. Diazepam improved the spasms.\n"
            "Discussion\n"
            "The patient reported here indicates a possible drug association.",
        )
        prepared = core.prepare_source(paper_id="9051", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9051",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("An 18-year-old male patient", text)
        self.assertNotIn("Example Author", text)
        self.assertNotIn("Background on retinoids", text)

    def test_single_case_abstract_stops_before_following_case_report(self) -> None:
        source_path = self.write_text_json(
            "9053",
            "Abstract\n"
            "The authors report a patient with stiff-person syndrome and pump failure.\n"
            "Stiff-person syndrome background follows.\n"
            "Case report. After a 3-year history of stiffness, this 30-year-old man "
            "was diagnosed with SPS. Antibodies against GAD were present in serum and CSF.\n"
            "References\n1. Example.",
        )
        prepared = core.prepare_source(paper_id="9053", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9053",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("30-year-old man", text)
        self.assertNotIn("Stiff-person syndrome background", text)

    def test_single_case_preserves_patient_abstract_without_age(self) -> None:
        source_path = self.write_text_json(
            "9072",
            "Abstract We describe a patient with stiff-man syndrome whose trunk stiffness "
            "was followed by cerebellar ataxia.\n"
            "Keyords: Anti-GAD autoantibody; Stiff-man syndrome.\n"
            "2. Case report\n"
            "A 55-year-old woman developed trunk stiffness, board-like abdominal rigidity, "
            "anti-GAD antibodies, and later pancerebellar syndrome.\n"
            "4. Discussion\nGeneric antibody background.",
        )
        prepared = core.prepare_source(paper_id="9072", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9072",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("Abstract We describe a patient", text)
        self.assertIn("55-year-old woman", text)
        self.assertNotIn("Generic antibody background", text)

    def test_single_case_no_age_abstract_does_not_block_later_age_case(self) -> None:
        source_path = self.write_text_json(
            "9074",
            "Abstract We describe a patient with severe acne who developed disabling "
            "muscle stiffness and stiff-person syndrome after oral treatment. Keywords: Retinoids.\n"
            "An 18-year-old male patient developed painful spasms of the neck, back, "
            "and upper limbs 10 days after isotretinoin treatment. Diazepam improved symptoms.\n"
            "Discussion\nThe patient reported here indicates a possible drug association.",
        )
        prepared = core.prepare_source(paper_id="9074", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9074",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("18-year-old male patient", text)
        self.assertIn("Diazepam improved symptoms", text)
        self.assertNotIn("Keywords: Retinoids", text)

    def test_single_case_letter_author_department_block_stops_patient_range(self) -> None:
        source_path = self.write_text_json(
            "9054",
            "Progressive encephalomyelitis with rigidity as refractory asthma\n"
            "We report a 19 year old woman who developed progressive encephalomyelitis "
            "with rigidity. Diazepam reduced continuous motor unit discharges.\n"
            "The adducting muscles caused the severe stenosis of the glottic space.\n"
            "N Kikuchi, A Nomura, Y Ishii,\n"
            "K Sekizawa\n"
            "Department of Pulmonary Medicine\n"
            "Correspondence to: Dr K Sekizawa\n"
            "References\n1. Example.",
        )
        prepared = core.prepare_source(paper_id="9054", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9054",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("19 year old woman", text)
        self.assertIn("severe stenosis of the glottic space", text)
        self.assertNotIn("Kikuchi", text)
        self.assertNotIn("Department of Pulmonary Medicine", text)

    def test_single_case_confident_multi_patient_slice_is_deferred(self) -> None:
        source_path = self.write_text_json(
            "9049",
            "Patient 1 was a 47-year-old woman with stiff-person syndrome and breast cancer.\n"
            "Patient 2 was a 42-year-old woman with cerebellar syndrome.\n"
            "References\n1. Cohort reference.",
        )
        prepared = core.prepare_source(paper_id="9049", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9049",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.registry_row["annotation_mode"], "single_case_deferred_multi_case_source")
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertIn("not_single_case_for_stage07_singlecase", result.registry_row["defer_reason"])

    def test_single_case_deferred_when_summary_hides_multi_patient_source(self) -> None:
        source_path = self.write_text_json(
            "9075",
            "Abstract: We reviewed paraneoplastic neurologic syndromes in patients with breast cancer.\n"
            "Patient 1 was a 47-year-old woman with cerebellar syndrome.\n"
            "Patient 2 was a 42-year-old woman with sensory neuropathy.\n",
        )
        prepared = core.prepare_source(paper_id="9075", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9075",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.registry_row["annotation_mode"], "single_case_deferred_multi_case_source")
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")

    def test_single_case_stops_before_bibliografia(self) -> None:
        source_path = self.write_text_json(
            "9050",
            "Caso clinico\n"
            "A 34-year-old woman had stiff-person syndrome with painful spasms. "
            "Diazepam and baclofen improved stiffness.\n"
            "Bibliografia\n1. NIH Conference.",
        )
        prepared = core.prepare_source(paper_id="9050", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9050",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("34-year-old woman", text)
        self.assertNotIn("NIH Conference", text)

    def test_single_case_excludes_minerva_copyright_boilerplate_inside_case(self) -> None:
        source_path = self.write_text_json(
            "9052",
            "Case report\n"
            "An 84- ye ar - old woman was admitted with increased tone, painful spasms, "
            "and suspected stiff-person syndrome.\n"
            "This document is protected by international copyright laws. No additional reproduction is authorized.\n"
            "MINERVA MEDICA COPYRIGHTÂ®\n"
            "THE STIFF-PERSON SYNDROME\n"
            "PIOVANO\n"
            "The patient was intubated, EMG showed continuous motor unit activity, "
            "and CSF GAD-autoantibody testing confirmed the diagnosis.\n"
            "Discussion and conclusions\n"
            "The patient demonstrated the typical finding of SPS.\n"
            "Bibliografia\n1. NIH Conference.",
        )
        prepared = core.prepare_source(paper_id="9052", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9052",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("84- ye ar - old woman", text)
        self.assertIn("continuous motor unit activity", text)
        self.assertNotIn("international copyright laws", text)
        self.assertNotIn("MINERVA MEDICA", text)
        self.assertNotIn("PIOVANO", text)

    def test_single_case_excludes_videotape_received_footer_inside_case(self) -> None:
        source_path = self.write_text_json(
            "9055",
            "Marked Improvement in a Stiff-Limb Patient\n"
            "Case Report\n"
            "A 60-year-old woman had painful spasms and persistent rigidity in the left leg and was\n"
            "A videotape accompanies this article.\n"
            "Received April 19, 1999; Accepted December 17, 1999.\n"
            "Address correspondence and reprint requests to Example Author, MD.\n"
            "CLINICAL/SCIENTIFIC NOTES358\n"
            "restricted to a wheelchair. Serum anti-GAD antibodies were present.\n"
            "Discussion\n"
            "Our patient has the clinical findings of stiff-limb syndrome.",
        )
        prepared = core.prepare_source(paper_id="9055", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9055",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("restricted to a wheelchair", text)
        self.assertNotIn("A videotape accompanies", text)
        self.assertNotIn("Address correspondence", text)

    def test_single_case_excludes_accepted_acknowledgement_before_references(self) -> None:
        source_path = self.write_text_json(
            "9071",
            "REPORT OF A CASE\n"
            "A 54-year-old woman had stiff-man syndrome, diabetes, anti-GAD antibodies, "
            "and improved with corticosteroids.\n"
            "DISCUSSION\n"
            "Our patient had autoimmune features and improved with therapy.\n"
            "Accepted for publication October 1; 1993. Dr Example referred the patient. "
            "Reprints not available. REFERENCES\n1. Generic reference.",
        )
        prepared = core.prepare_source(paper_id="9071", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9071",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("54-year-old woman", text)
        self.assertIn("autoimmune features", text)
        self.assertNotIn("Accepted for publication", text)
        self.assertNotIn("Generic reference", text)

    def test_single_case_excludes_arch_neurol_sidebar_and_author_contributions(self) -> None:
        source_path = self.write_text_json(
            "9077",
            "REPORT OF A CASE\n"
            "A 41-year-old man developed stiff-person syndrome after West Nile fever. "
            "Hyperreflexia was noted in the arms, more on the\n"
            "OBSERVATION\n"
            "From the Department of Neurology, Chaim Sheba Medical Center.\n"
            "(REPRINTED) ARCH NEUROL / VOL 61, JUNE 2004 WWW.ARCHNEUROL.COM\n"
            "938\n"
            "Downloaded From: https://jamanetwork.com/ by a library user on 05/26/2023\n"
            "left than on the right side. Figure 1. IgM and IgG antibodies to West Nile virus "
            "in the patient's serum and cerebrospinal fluid were noted.\n"
            "COMMENT\n"
            "In this report, we describe a patient with SPS following WNF. "
            "Further investigation of the cross-reactivity is required.\n"
            "Accepted for publication December 9, 2003.\n"
            "Author contributions: Study concept and design by the authors.\n"
            "Gene\nGAD65\nWNV\nFigure 3. Amino acid similarity of a viral motif.\n"
            "sition of data by the authors.\n"
            "REFERENCES\n1. Generic reference.",
        )
        prepared = core.prepare_source(paper_id="9077", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9077",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("41-year-old man", text)
        self.assertIn("left than on the right side", text)
        self.assertIn("Figure 1. IgM and IgG antibodies", text)
        self.assertIn("cross-reactivity is required", text)
        self.assertNotIn("From the Department", text)
        self.assertNotIn("Downloaded From", text)
        self.assertNotIn("Accepted for publication", text)
        self.assertNotIn("Author contributions", text)
        self.assertNotIn("Figure 3", text)
        self.assertNotIn("Generic reference", text)

    def test_single_case_excludes_acta_neurol_belg_running_footer(self) -> None:
        source_path = self.write_text_json(
            "9078",
            "Abstract\n"
            "We report a young patient who developed a stiff man syndrome after remission.\n"
            "Case report\n"
            "A 38-year-old man of Indian origin had Hodgkin lymphoma and later developed "
            "stiff man syndrome with anti-GAD65 antibodies. The EMG showed a demyelinating "
            "sensory and motor polyneuropathy\n"
            "in all limbs. MRI of the brain is normal.\n"
            "Multiple neurological syndromes during Hodgkin lymphoma remission\n"
            "Bart WERBROUCK, Veronique MEIRE and Jan L. DE BLEECKER\n"
            "Department of Neurology, Ghent University Hospital, Ghent, Belgium\n"
            "----\n"
            "PARANEOPLASTIC SYNDROME AND HODGKIN 49\n"
            "sequellae of his polyneuropathy. The diagnosis of stiff man syndrome is made.\n"
            "Discussion\n"
            "Our patient responds only partially to the IVIg therapy with diminished abdominal spasms.\n"
            "Acknowledgments\n"
            "We thank colleagues.",
        )
        prepared = core.prepare_source(paper_id="9078", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9078",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("38-year-old man", text)
        self.assertIn("sequellae of his polyneuropathy", text)
        self.assertIn("diminished abdominal spasms", text)
        self.assertNotIn("Bart WERBROUCK", text)
        self.assertNotIn("Department of Neurology, Ghent", text)
        self.assertNotIn("PARANEOPLASTIC SYNDROME AND HODGKIN", text)
        self.assertNotIn("Acknowledgments", text)

    def test_single_case_excludes_elsevier_correspondence_and_running_headers(self) -> None:
        source_path = self.write_text_json(
            "9080",
            "Abstract\n"
            "We describe a patient with type 1 diabetes and stiff-man syndrome.\n"
            "Keywords\n: Stiff man syndrome; Insulin resistance\n"
            "1. Case presentation\n"
            "The patient is a 33-year-old Caucasian woman with severe insulin resistance.\n"
            "* Corresponding author. Tel.: +1 206 5484882; fax: +1 206 5484976.\n"
            "0168-8227:98:$ - see front matter Copyright notice.\n"
            "PII S0168-8227(98)00072-2\n"
            "I.B. Hirsch et al . : Diabetes Research and Clinical Practice 41 (1998) 197-202198\n"
            "of NPH and regular insulin administered prior to breakfast and supper.\n"
            "Table 1 Insulin requirements before and after insulin lispro.\n"
            "Results\n"
            "The patient improved rapidly after insulin lispro and hydrocortisone.\n"
            "I.B. Hirsch et al . : Diabetes Research and Clinical Practice 41 (1998) 197-202200\n"
            "mal counter-regulatory hormone responses were documented.\n"
            "Discussion\n"
            "Our patient had all classic features of SMS except one finding.\n"
            "References\n1. Generic.",
        )
        prepared = core.prepare_source(paper_id="9080", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9080",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("33-year-old Caucasian woman", text)
        self.assertIn("Table 1 Insulin requirements", text)
        self.assertNotIn("Corresponding author", text)
        self.assertNotIn("PII S0168-8227", text)
        self.assertNotIn("Diabetes Research and Clinical Practice 41", text)
        self.assertNotIn("Generic.", text)

    def test_single_case_case_description_heading_avoids_prior_report_age(self) -> None:
        source_path = self.write_text_json(
            "9084",
            "Abstract: We describe a patient with uncontrolled Graves disease and undiagnosed SPS.\n"
            "CASE DESCRIPTION\n"
            "A middle age Chinese woman presented with Graves disease, neck stiffness, backache, "
            "ataxia, anti-GAD antibodies, and stiff person syndrome.\n"
            "Table 1. Thyroid function tests at baseline and after immunotherapy.\n"
            "Discussion\n"
            "SPS was previously reported once in a 52-year-old white woman. "
            "The patient did not have ataxia.\n",
        )
        prepared = core.prepare_source(paper_id="9084", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9084",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("middle age Chinese woman", text)
        self.assertIn("Table 1. Thyroid function tests", text)
        self.assertNotIn("52-year-old white woman", text)

    def test_single_case_excludes_common_publisher_page_blocks(self) -> None:
        source_path = self.write_text_json(
            "9085",
            "CASE REPORT\n"
            "A 50-year-old woman with SPS had progressive stiffness and falls. She was found to have a normal\n"
            "Copyright r 2007 by Lippincott Williams & Wilkins\n"
            "Received for publication October 17, 2006; accepted February 11, 2007.\n"
            "From the Section of Neurology, Example Hospital.\n"
            "Reprints: Example Author, Example Hospital.\n"
            "CASE REPORT\n136 Cog Behav Neurol /C15Volume 20, Number 2, June 2007\n"
            "Downloaded from http://journals.lww.com/cogbehavneurol by token on 06/30/2023\n\n"
            "neurologic examination and later had positive anti-GAD antibodies.\n"
            "Abstract\n"
            "We report the successful management of anesthesia in a patient with stiff-person syndrome.\n"
            "Key words Bispectral index and train-of-four ratio\n"
            "Introduction\n"
            "Stiff-person syndrome is a rare neurologic disease.\n"
            "Address correspondence to: K. Hara\n"
            "Received: February 8, 2007/Accepted: May 17, 2007\n"
            "K. Yamamoto et al.: Stiff-person syndrome and epidural anesthesia 491\n"
            "muscle to train-of-four stimulation was monitored.\n"
            "From the ENT Department and the *Department of Neurology, San Raffaele Hospital, Milan, Italy.\n"
            "Accepted for publication: 5 June 2007. First published online 1 August 2007.\n"
            "The Journal of Laryngology & Otology (2008), 122, 636-638.\n"
            "https://doi.org/10.1017/S0022215107000205 Published online by Cambridge University Press\n\n"
            "caloric vestibular testing showed unilateral weakness.\n"
            "Abbreviations: BMT, bone marrow transplant; GABA, gamma-aminobutyric acid.\n"
            "Published online 17 October 2008 in Wiley InterScience (www.interscience.wiley.com). "
            "DOI 10.1002/mus.21153SPS with Multiple Myeloma MUSCLE & NERVE December 2008 1649\n"
            "fractions and intravenous melphalan were given.\n"
            "Copyright r 2008 by Lippincott Williams & Wilkins\n"
            "Received for publication August 16, 2007; accepted July 2, 2008.\n"
            "From the Department of Psychiatry.\n"
            "Reprints: Example Author.\n"
            "CASE REPORT\n242 Cog Behav Neurol /C15Volume 21, Number 4, December 2008\n"
            "neuropsychiatric symptoms improved with immunosuppression.\n"
            "* Corresponding author.\n"
            "E-mail address: clinician@example.org (Example Author).\n"
            "with dermatitis herpetiformis was present on the trunk.\n"
            "0303-8467/$ - see front matter Copyright 2009 Elsevier B.V. All rights reserved.\n"
            "doi:10.1016/j.clineuro.2009.06.005\n"
            "T. Holmoy et al. / Clinical Neurology and Neurosurgery 111 (2009) 708-712 709\n"
            "possible points at the SPS heightened sensitivity scale.\n"
            "How to cite this article:\n"
            "Example citation.\n"
            "How to cite this URL:\n"
            "Example URL.\n"
            "Available from: https://example.org\n"
            "Full Text\n"
            "| Introduction\n"
            "the intrathecal baclofen dose was adjusted.\n"
            "Stiff Limb Syndrome 595\n"
            "Downloaded from https://academic.oup.com/painmedicine/article/10/3/594/1931041 by user\n"
            "the patient was asymptomatic at follow-up.\n"
            "Key Words\n"
            "Autoimmune GAD65-positive SPS Glutamate decarboxylase Stiff-person syndrome\n"
            "Abstract\n"
            "Generic abstract text.\n"
            "Stiff-Person Syndrome and Pregnancy Gynecol Obstet Invest 2009;67:134-136 135\n"
            "On admission, the patient had walking difficulties due to stiffness.\n"
            "Downloaded from http://karger.com/goi/article-pdf/67/2/134/2868049/000172804.pdf by user\n"
            "Cerimagic /Bilic Gynecol Obstet Invest 2009;67:134-136136\n"
            "In conclusion, caesarean section was chosen.\n"
            "References   1 Moersch FP, Woltman HW: Progressive fluctuating muscular rigidity.\n"
            "Downloaded from http://karger.com/goi/article-pdf/67/2/134/2868049/000172804.pdf by user\n",
        )
        prepared = core.prepare_source(paper_id="9085", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9085",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("50-year-old woman", text)
        self.assertIn("neurologic examination", text)
        self.assertIn("muscle to train-of-four", text)
        self.assertIn("caloric vestibular testing", text)
        self.assertIn("fractions and intravenous melphalan", text)
        self.assertIn("neuropsychiatric symptoms improved", text)
        self.assertIn("with dermatitis herpetiformis", text)
        self.assertIn("possible points at the SPS heightened sensitivity scale", text)
        self.assertIn("the intrathecal baclofen dose was adjusted", text)
        self.assertIn("the patient was asymptomatic at follow-up", text)
        self.assertIn("On admission, the patient had walking difficulties", text)
        self.assertIn("In conclusion, caesarean section was chosen", text)
        self.assertNotIn("Lippincott", text)
        self.assertNotIn("Key words Bispectral", text)
        self.assertNotIn("Cambridge University Press", text)
        self.assertNotIn("MUSCLE & NERVE", text)
        self.assertNotIn("Corresponding author", text)
        self.assertNotIn("Clinical Neurology and Neurosurgery", text)
        self.assertNotIn("How to cite", text)
        self.assertNotIn("academic.oup.com", text)
        self.assertNotIn("Gynecol Obstet Invest", text)
        self.assertNotIn("Moersch FP", text)

    def test_single_case_exclusion_ranges_remove_batch009_review_and_web_noise(self) -> None:
        text = (
            "CASE REPORT\n"
            "A 44-year-old man with stiff limb syndrome had severe spasms. Anti-GAD antibodies were negative.\n"
            " Key Words \n"
            " Spinal cord stimulation  Stiff limb syndrome  Spasms \n"
            " Abstract \n"
            " Generic publisher abstract and correspondence block.\n"
            "Downloaded from http://karger.com/sfn/article-pdf/88/3/183/3535919/000313871.pdf by user\n"
            "Ughratdar/Sivakumar/Basu\n"
            "Stereotact Funct Neurosurg 2010;88:183-186 184\n"
            "During revision the stimulator settings were changed and he could abort spasms within 1 min.\n"
            " Discussion \n"
            " SLS is a rare chronic relapsing remitting disorder. The history of SCS for motor disorders "
            "included other patient series. No underlying \nmechanism was proposed in the study.\n"
            " I n  o u r  r e p o r t  a  n u m b e r  o f  o b s e r v a t i o n s were made. "
            "The effect took approximately 80 s.\n"
            "Control systems\nInhibitory interneurone\nFig. 1. Generic spinal reflex diagram.\n"
            " - The effect was rapid and cumulative.\n"
            "Naturally, the observations noted above have led us to extrapolate a generic mechanism. "
            "The up-regulation in the availability of GABA could explain the anti-spasmodic effect outlasting the "
            "stimulation.\n"
            " Conclusion \n"
            "Though the mechanism is speculative, SCS may become useful for this only case.\n"
            "References \n"
            " 1 Barker RA, Revesz T, Thom M, Marsden CD, Brown P: Review of 23 patients.\n"
            "Downloaded from http://karger.com/sfn/article-pdf/88/3/183/3535919/000313871.pdf by user\n"
            "CASE PRESENTATION\n"
            "A 29-year-old man with SPS had thymoma, chylothorax, negative anti-GAD antibodies, and diazepam response.\n"
            "; oe Tennessee Medicine\n"
            "TABLE 1. Literature Review of All Reported Cases of Patients with Confirmed Thymoma and SPS.\n"
            "Iwata T 79Y/W Severe painful tonic spasm.\n"
            "+ www.tnmed.org * MAY 2010\n"
            "resolution of his thymoma, which responded well to chemotherapy.\n"
            "TABLE 2. Proposed Diagnostic Criteria\nfor SPS.*\n"
            "Evidence of muscular stiffness and axial rigidity.\n"
            "In our patient, sur-\ngical therapy was not an option because\n"
            "GLOSSARY:\nANA: Anti-neutrophilic antibody\n"
            "fe Tennessee Medicine + www.tnmed.org * MAY 2010\n"
            "of the aggressive behavior of the thymoma invading surrounding structures.\n"
            "Miguel Angel Arrabal-Polo\nMD, Francisco Palao-Y ago MD\nand Armando Zuluaga-Gomez MD\n"
            "Urology Department, University of Granada,\nSan Cecilio University Hospital, Granada, Spain\n"
            "arrabalp@ono.com\n"
            "Fig. 1 Urodynamic study in which the alterations in flowmetry can be observed.\n"
            "International Journal of Urology (2010) 17, 587-588 doi: 10.1111/example\n"
            "Copyright 2010 The Japanese Urological Association 587\n"
            "Accepted 5 November 2009\n"
            "1 South Carolina Department of Mental Health, Columbia, South\nCarolina\n"
            "2 Department of Neuropsychiatry and Behavioral Science,\n"
            "University of South Carolina School of Medicine, Columbia,\nSouth Carolina\n"
            "Glutamic acid decarboxylase antibody-positive paraneoplastic stiff limb... "
            "https://www.neurologyindia.com/article.asp?issn=0028-3886;year=2010...\n"
            "2 of 7 26/05/2023, 22:14\n"
            "A 55-year-old lady had right foot spasms, anti-GAD antibodies, breast carcinoma, and improved foot posture.\n"
            " » Discussion  \n"
            "Three distinct subtypes of SPS have been described. The clinical characteristics are given in [Table 1].\n"
            " » References  \n"
            "1. Barker RA, Revesz T, Thom M, Marsden CD, Brown P.\n"
            "CURRENT STATE OF KNOWLEDGE AND\nFUTURE RESEARCH NEEDS\n"
            "Thymoma and SPS can coexist leading to morbidity.\n"
            "The prognosis for patients with SPS is still variable and unpredictable, and clinicians should recognise SPS.\n"
            "In our patient the early recognition and treatment management led to rapid recovery.\n"
            "In particular, the following pivotal is-\nsues may need to be addressed in research studies.\n"
            "Glutamic acid decarboxylase antibody-positive paraneoplastic stiff limb... "
            "https://www.neurologyindia.com/article.asp?issn=0028-3886;year=2010...\n"
            "2 of 7 26/05/2023, 22:14\n"
            "A 55-year-old lady had right foot spasms, anti-GAD antibodies, breast carcinoma, and improved foot posture.\n"
            " Â» Discussion  \n"
            "Three distinct subtypes of SPS have been described. The clinical characteristics are given in [Table 1].\n"
            " Â» References  \n"
            "1. Barker RA, Revesz T, Thom M, Marsden CD, Brown P.\n"
            "DisCussion\n"
            "SPS was first described in 1956 by Moersch and Woltman at the Mayo Clinic.\n"
            "RefeRenCes\n"
            "Ameli R, Snow J, Rakocevic G, Dalakas MC.\n"
            "dIscuss Ion\n"
            "The exact prevalence of SPS is unknown and references follow.\n"
        )

        kept_ranges = core.subtract_source_ranges(
            text,
            [(0, len(text))],
            core.single_case_boilerplate_exclusion_ranges(text),
        )
        cleaned = "\n".join(text[start:end] for start, end in kept_ranges)

        self.assertIn("44-year-old man", cleaned)
        self.assertIn("abort spasms within 1 min", cleaned)
        self.assertIn("approximately 80 s", cleaned)
        self.assertIn("Though the mechanism is speculative", cleaned)
        self.assertIn("29-year-old man with SPS", cleaned)
        self.assertIn("resolution of his thymoma", cleaned)
        self.assertIn("aggressive behavior of the thymoma", cleaned)
        self.assertIn("rapid recovery", cleaned)
        self.assertIn("Fig. 1 Urodynamic study", cleaned)
        self.assertIn("55-year-old lady", cleaned)
        self.assertNotIn("Key Words", cleaned)
        self.assertNotIn("Control systems", cleaned)
        self.assertNotIn("Generic spinal reflex diagram", cleaned)
        self.assertNotIn("generic mechanism", cleaned)
        self.assertNotIn("Stereotact Funct Neurosurg", cleaned)
        self.assertNotIn("Barker RA", cleaned)
        self.assertNotIn("Iwata T", cleaned)
        self.assertNotIn("Proposed Diagnostic Criteria", cleaned)
        self.assertNotIn("GLOSSARY", cleaned)
        self.assertNotIn("pivotal", cleaned)
        self.assertNotIn("Arrabal-Polo", cleaned)
        self.assertNotIn("Japanese Urological Association", cleaned)
        self.assertNotIn("South Carolina Department", cleaned)
        self.assertNotIn("neurologyindia.com", cleaned)
        self.assertNotIn("[Table 1]", cleaned)
        self.assertNotIn("prognosis for patients", cleaned)
        self.assertNotIn("Moersch and Woltman", cleaned)
        self.assertNotIn("exact prevalence", cleaned)

    def test_single_case_exclusions_preserve_jnnp_split_page_continuation(self) -> None:
        text = (
            "Our patient is the first reported case of SPS with MRI striatal abnormalities.\n"
            "Case report\n"
            "A 69-year-old woman came in for consultation with progressive stiffness. "
            "Cerebral MRI showed bright hyperintense changes in both striatal regions "
            "(more intense in the right striatum corresponding to\n"
            "Figure 1 Fundoscopy of gyrate atrophy.\n"
            "Competing interests: None declared.\n"
            "PostScript 657\n"
            "www.jnnp.com\n\n"
            "the more symptomatic left side), and a lesion in the left middle cerebellar peduncle. "
            "The patient improved after diazepam and intravenous immunoglobulin.\n"
            "Discussion\n"
            "The absence of structural MRI changes in most cases suggests a functional disorder.\n"
        )
        start = text.index("Case report")
        end = text.index("Discussion\nThe absence")

        kept_ranges = core.subtract_source_ranges(
            text,
            [(start, end)],
            core.single_case_boilerplate_exclusion_ranges(text),
        )
        cleaned = "\n".join(text[start:end] for start, end in kept_ranges)

        self.assertIn("A 69-year-old woman", cleaned)
        self.assertIn("right striatum corresponding to", cleaned)
        self.assertIn("the more symptomatic left side", cleaned)
        self.assertIn("intravenous immunoglobulin", cleaned)
        self.assertNotIn("Competing interests", cleaned)
        self.assertNotIn("PostScript 657", cleaned)
        self.assertNotIn("www.jnnp.com", cleaned)

    def test_single_case_passthrough_trims_paraneoplastic_sps_review_article(self) -> None:
        source_path = self.write_text_json(
            "9263",
            "Case Report\n"
            "Stiff-person syndrome with paraneoplastic neurological \n"
            "syndrome: a case report and literature review\n"
            "Abstract: Background: Stiff-person syndrome background material. "
            "Case presentation: A 67-year \n"
            "old female patient presented with a 2-year history of progressive stiffness "
            "along with painful spasms in both legs. Treatment with hormones and "
            "gamma-globulin improved her symptoms. In \n"
            "addition, we present a literature review of SPS patients with tumors. "
            "Conclusions: Early SPS detection is critical.\n"
            "Keywords: Muscle stiffness, stiff person syndrome\n"
            "Introduction\n"
            "Stiff-person syndrome is rare generic background with tumor literature.\n"
            "Case report\n"
            "This SPS case report involves a 67-year-old \n"
            "female patient who was admitted with painful muscle contractions in 2018. "
            "She had progressive spasms, positive anti-GAD antibodies, normal spinal MRI, "
            "continuous motor unit activity on EMG, and a lung adenocarcinoma. "
            "The patient's symptoms markedly improved in December 2020.\n"
            "Discussion\n"
            "SPS is an uncommon neurological autoimmune disorder and the references follow.\n"
            "References\n"
            "[1] Generic citation.\n",
        )
        prepared = core.prepare_source(paper_id="9263", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
        selected = "\n".join(span["selected_text"] for span in annotation["segments"][0]["spans"])

        self.assertIn("A 67-year", selected)
        self.assertIn("hormones and gamma-globulin", selected)
        self.assertIn("This SPS case report involves", selected)
        self.assertIn("continuous motor unit activity", selected)
        self.assertNotIn("Introduction", selected)
        self.assertNotIn("generic background", selected)
        self.assertNotIn("literature review of SPS patients", selected)
        self.assertNotIn("Discussion", selected)
        self.assertNotIn("References", selected)

    def test_single_case_passthrough_keeps_complete_repetitive_discharge_case(self) -> None:
        source_path = self.write_text_json(
            "9522",
            "Presentation of a Case With Repetitive Complex Discharges in Stiff Person Syndrome\n"
            "Case Report: A 41-year-old woman with diabetes developed symptoms compatible with SPS.\n"
            "Key Words: stiff person syndrome\n"
            "CASE REPORT\n"
            "A 41-year-old woman had a history of Hashimoto thyroiditis and diabetes mellitus type I. "
            "The patient had symptoms that had evolved over 2 years, consisting of lumbar pain, "
            "axial rigidity, acoustic-triggered spasms, anti-GAD antibodies, and continuous motor unit activity.\n"
            "From the Department of Neurology.\n"
            "Reprints: Pedro Enrique Jimenez Caballero, MD.\n"
            "Copyright \\u00a9 2009 by Lippincott Williams & Wilkins\n"
            "ISSN: 1074-7931/09/1504-0227\n"
            "DOI: 10.1097/NRL.0b013e3181935a29\n"
            "The patient presented with repetitive complex discharges in the form of doublets and triplets.\n"
            "mg Phenytoin per day was not associated with an improvement in the doublets. "
            "Baclofen and clonazepam improved pain, stiffness, muscle spasms, and gait.\n"
            "Jimenez Caballero The Neurologist Volume 15, Number 4, July 2009\n"
            "228 | www.theneurologist.org \\u00a9 2009 Lippincott Williams & Wilkins\n"
            "DISCUSSION\n"
            "Our patient exhibited no clinical or electrophysiological evidence of neuropathic dysfunction, "
            "so the doublets may have reflected alpha motoneurons released from GABAergic inhibition.\n"
            "REFERENCES\n"
            "1. Generic citation.\n",
        )
        prepared = core.prepare_source(paper_id="9522", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)
        selected = "\n".join(span["selected_text"] for span in annotation["segments"][0]["spans"])

        self.assertIn("A 41-year-old woman had a history", selected)
        self.assertIn("symptoms that had evolved over 2 years", selected)
        self.assertIn("repetitive complex discharges", selected)
        self.assertIn("mg Phenytoin per day", selected)
        self.assertNotIn("Key Words", selected)
        self.assertNotIn("Copyright", selected)
        self.assertNotIn("theneurologist", selected)
        self.assertNotIn("Lippincott", selected)
        self.assertNotIn("alpha motoneurons", selected)
        self.assertNotIn("Generic citation", selected)

    def test_single_case_exclusion_ranges_remove_bmj_learning_points(self) -> None:
        text = (
            "CASE PRESENTATION\n"
            "A 41-year-old female patient had stiff-person syndrome with positive anti-GAD antibodies. "
            "Rituximab improved muscle tone but anti-GAD titres continued rising.\n"
            "Learning points\n"
            "SPS is probably an autoimmune disease.\n"
            "Rituximab may be a promising option in its treatment.\n"
        )

        kept_ranges = core.subtract_source_ranges(
            text,
            [(0, len(text))],
            core.single_case_boilerplate_exclusion_ranges(text),
        )
        cleaned = "\n".join(text[start:end] for start, end in kept_ranges)

        self.assertIn("41-year-old female patient", cleaned)
        self.assertIn("anti-GAD titres continued rising", cleaned)
        self.assertNotIn("Learning points", cleaned)
        self.assertNotIn("probably an autoimmune disease", cleaned)

    def test_single_case_exact_case_heading_ignores_prior_literature_cases(self) -> None:
        source_path = self.write_text_json(
            "9087",
            "Only two discussed pregnancy in patients diagnosed with stiff person syndrome.\n"
            "The first case was of a 41-year-old woman who had stiff limb syndrome.\n"
            "The second case depicted a 36-year-old primigravida with stiff person syndrome.\n"
            "CASE\n"
            "A 27-year-old woman, G2A2, presented with respiratory failure and diaphragmatic spasms. "
            "A muscle biopsy showed type 1 fibre atrophy and anti-GAD antibodies were positive. "
            "She was diagnosed with stiff person syndrome, treated with IVIg, gabapentin, diazepam, "
            "prednisone, and later baclofen during pregnancy. She delivered by urgent cesarean section "
            "for nonreassuring fetal heart tones; the infant did well.\n"
            "COMMENT\n"
            "Our patient was on diazepam, gabapentin, and prednisone at conception.\n"
            "Two case reports of three children born to mothers with stiff person syndrome were asymptomatic.\n"
            "Because of\nconcern for our patient, anesthesia services consult was sought.\n"
            "Although our patient had a cesarean delivery, it\nwas secondary to her disease. Weatherby et al reported another mother.\n"
            "Although\nthe antibodies have been reported to pass through the placenta, there was no sequela for the neonate.\n"
            "Both our patient and the patient with stiff limb\nsyndrome were able to wean down medication.\n"
            "In conclusion, our patient had life-threatening diaphragmatic spasms.\n"
            "REFERENCES\n1. Example.\n"
            "Diabetic Papillopathy in Pregnancy\nCASE\nA young primigravid woman had diabetic retinopathy.",
        )
        prepared = core.prepare_source(paper_id="9087", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9087",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("27-year-old woman", text)
        self.assertIn("infant did well", text)
        self.assertNotIn("41-year-old woman", text)
        self.assertNotIn("36-year-old primigravida", text)
        self.assertNotIn("three children born to mothers", text)
        self.assertNotIn("Weatherby et al", text)
        self.assertNotIn("patient with stiff limb", text)
        self.assertNotIn("diabetic retinopathy", text)

    def test_single_case_canadian_journal_split_case_continuation(self) -> None:
        source_path = self.write_text_json(
            "9088",
            "Paraneoplastic Encephalomyelitis, Stiff Person Syndrome\nand Breast Carcinoma\n"
            "CASE REPORT\n\n"
            "A 30-year-old woman presented for involuntary muscle contractions of the legs, "
            "making walking difficult with occasional falls. Spasms were treated with benzodiazepine "
            "with very minimal improvement.\n"
            "790\nhttps://doi.org/10. 1017/S0317167100018011 Published online by Cambridge University Press\n"
            "REFERENCES\n1. Previous letter.\n"
            "but with little effect on limb stiffness. Lumpectomy and axillary dissection were performed. "
            "She received chemotherapy, stiffness improved, and after three and-a-half years she was "
            "without cancer recurrence and able to walk rapidly without any help.\n"
            "DISCUSSION\n"
            "Paraneoplastic syndromes are rare.\n"
            "The case presented here was negative for anti-GAD and anti-amphiphysin antibodies. "
            "Treatment of the neurological symptoms was inefficient until the cancer was treated.\n"
            "Julie Lemieux, Louise Provencher\nQuebec City, QC, Canada\n"
            "TO THE EDITOR\n\n"
            "A Case of Phenytoin-Induced Encephalopathy in a Mathematician with Stage IV NSCLC\n"
            "A 65-year-old mathematician had lung cancer and phenytoin toxicity.",
        )
        prepared = core.prepare_source(paper_id="9088", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9088",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("30-year-old woman", text)
        self.assertIn("without cancer recurrence", text)
        self.assertIn("until the cancer was treated", text)
        self.assertNotIn("Previous letter", text)
        self.assertNotIn("65-year-old mathematician", text)
        self.assertNotIn("Phenytoin-Induced", text)
        self.assertNotIn("Quebec City", text)

    def test_single_case_lowercase_case_report_and_references_are_supported(self) -> None:
        source_path = self.write_text_json(
            "9089",
            "Summary: A 61-year-old man had stiff-person syndrome after tick-borne encephalitis.\n"
            "Key words: stiff-person syndrome\n"
            "CASE REPORT\n"
            "introduction\n"
            "Generic SPS background.\n"
            "case report\n"
            "A 61-year-old man was admitted with muscle hypertonia and episodic painful spasms. "
            "Anti-GAD antibodies were highly elevated, EMG showed continuous motor unit activity, "
            "and therapeutic plasma exchange plus chronic immunosuppression led to stable recovery.\n"
            "discussion\n"
            "In our patient, tick-borne encephalitis could have triggered SPS.\n"
            "references\n1. Example reference.\n",
        )
        prepared = core.prepare_source(paper_id="9089", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9089",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("61-year-old man was admitted", text)
        self.assertIn("stable recovery", text)
        self.assertNotIn("Example reference", text)

    def test_single_case_exclusion_ranges_remove_batch010_publisher_blocks(self) -> None:
        text = (
            "A 58-year-old man had PERM and glycine receptor antibodies.\n"
            "A. Piotrowicz ( &) A. Thumen A. Moser\nNeurochemical Research Group\n"
            "DOI 10.1007/s00415-011-6078-x\n"
            "Stiff-person syndrome (SPS) is a neuroimmunological, and less often, paraneoplastic disease. "
            "Generic background.\n"
            "Thus, as described in our patient, clonazepam ameliorated symptoms.\n"
            "Conflict of interest None.\n"
            "Physical Therapist Management of Stiff Person Syndrome\n"
            "1406 f Physical Therapy Volume 91 Number 9 September 2011\n"
            "Downloaded from https://academic.oup.com/ptj/article/91/9/1403/2735151 by user\n"
            "Jane was able to walk several kilometers by discharge.\n"
            "The author thanks Jane for her willingness to participate.\nDOI: 10.2522/ptj.20100303\n"
            "Editorial, page 414\nAddress correspondence and reprint requests to Dr. Olaf Ansorge.\n"
            "Copyright 2011 by AAN Enterprises, Inc. 439\n"
            "A 28-year-old man had progressive encephalomyelitis with rigidity and myoclonus.\n"
        )

        kept_ranges = core.subtract_source_ranges(
            text,
            [(0, len(text))],
            core.single_case_boilerplate_exclusion_ranges(text),
        )
        cleaned = "\n".join(text[start:end] for start, end in kept_ranges)

        self.assertIn("58-year-old man", cleaned)
        self.assertIn("clonazepam ameliorated symptoms", cleaned)
        self.assertIn("Jane was able to walk", cleaned)
        self.assertIn("28-year-old man", cleaned)
        self.assertNotIn("Piotrowicz", cleaned)
        self.assertNotIn("Generic background", cleaned)
        self.assertNotIn("Conflict of interest", cleaned)
        self.assertNotIn("academic.oup.com", cleaned)
        self.assertNotIn("The author thanks", cleaned)
        self.assertNotIn("AAN Enterprises", cleaned)

    def test_single_case_does_not_stop_at_results_of_routine_laboratory_sentence(self) -> None:
        source_path = self.write_text_json(
            "9056",
            "Case report\n"
            "An 84-year-old woman had stiff-person syndrome with painful spasms.\n"
            "Results of routine laboratory tests were normal. EMG showed continuous "
            "motor unit activity and CSF GAD-autoantibody testing confirmed the diagnosis.\n"
            "Discussion\n"
            "The patient demonstrated typical SPS findings.\n"
            "P ati ents wi th SP S have anti bodi es against GAD-65.",
        )
        prepared = core.prepare_source(paper_id="9056", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9056",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("Results of routine laboratory tests", text)
        self.assertIn("CSF GAD-autoantibody", text)
        self.assertNotIn("GAD-65", text)

    def test_single_case_age_anchor_stops_before_author_department_block(self) -> None:
        source_path = self.write_text_json(
            "9036",
            "A 29-year-old woman had SMS with painful stiffness. Treatment helped.\n"
            "Eckart Lensch, MD\n"
            "Department of Neurology\n"
            "1. Unrelated reference.",
        )
        prepared = core.prepare_source(paper_id="9036", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9036",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 29-year-old woman had SMS", text)
        self.assertNotIn("Department of Neurology", text)
        self.assertNotIn("Unrelated reference", text)

    def test_single_case_age_anchor_stops_before_next_uppercase_article_title(self) -> None:
        source_path = self.write_text_json(
            "9039",
            "A 29-year-old woman had SMS with painful stiffness. Treatment helped.\n"
            "MYASTHENIA GRAVIS AFTER INTERFERON-ALPHA TREATMENT\n"
            "A 47-year-old man had unrelated myasthenia gravis.",
        )
        prepared = core.prepare_source(paper_id="9039", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9039",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("A 29-year-old woman had SMS", text)
        self.assertNotIn("47-year-old man", text)

    def test_single_case_age_anchor_allows_phenotype_when_source_label_is_elsewhere(self) -> None:
        source_path = self.write_text_json(
            "9037",
            "Title: Stiff-man syndrome autopsy report.\n"
            "Results\nThe disease of the 66-year-old woman started with neck stiffness and spasms. "
            "Diazepam helped.\nFigure 1 Pathology image.",
        )
        prepared = core.prepare_source(paper_id="9037", source_path=source_path)
        annotation = core.single_case_passthrough_annotation(prepared_source=prepared)

        result = core.process_paper(
            paper_id="9037",
            source_row={
                "preferred_langextract_mode": "individual",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_eligible": "true",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        text = result.target_view_payloads["p1"]["input_text"]
        self.assertIn("66-year-old woman started", text)
        self.assertIn("Pathology image", text)

    def test_collect_single_case_candidate_ids_uses_stage06_count_not_route(self) -> None:
        rows = {
            "1": {
                "count_eligible": "true",
                "likely_sps_case_count": "1",
                "count_confidence": "high",
                "count_manual_review_required": "false",
            },
            "2": {
                "count_eligible": "true",
                "likely_sps_case_count": "2",
                "count_confidence": "high",
                "count_manual_review_required": "false",
            },
            "3": {
                "count_eligible": "true",
                "likely_sps_case_count": "1",
                "count_confidence": "low",
                "count_manual_review_required": "false",
            },
        }

        self.assertEqual(
            core.collect_single_case_candidate_ids(
                stage06_rows=rows,
                paper_ids=[],
                limit=0,
            ),
            ["1"],
        )

    def test_group_route_can_recover_source_backed_patient_targets(self) -> None:
        text = "Preamble. Case A had axial stiffness.\n\nCase B had startle-provoked spasms."
        source_path = self.write_text_json("9007", text)
        prepared = core.prepare_source(paper_id="9007", source_path=source_path)
        first = prepared.blocks[0]
        second = prepared.blocks[1]
        selected = "Case A had axial stiffness."
        annotation = {
            "targets": [
                {"id": "p1", "kind": "patient", "label": "Case A", "evidence": ""},
                {"id": "p2", "kind": "patient", "label": "Case B", "evidence": ""},
            ],
            "segments": [
                {
                    "targets": ["p1"],
                    "role": "patient_specific",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": first.block_id,
                            "start_offset": 0,
                            "end_offset": len(selected),
                            "selected_text": selected,
                        }
                    ],
                },
                {
                    "targets": ["p2"],
                    "role": "patient_specific",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": second.block_id,
                            "start_offset": 0,
                            "end_offset": len(second.text),
                            "selected_text": second.text,
                        }
                    ],
                },
            ],
        }

        result = core.process_paper(
            paper_id="9007",
            source_row={
                "preferred_langextract_mode": "group",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "2",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.registry_row["route_mode"], "individual_case_split")
        self.assertEqual(result.registry_row["n_declared_patients"], "2")
        self.assertEqual(result.registry_row["n_declared_groups"], "0")
        self.assertEqual(result.registry_row["ready_for_langextract"], "true")
        self.assertEqual(result.registry_row["stage06_diverged"], "true")
        self.assertTrue(result.target_view_payloads["p1"]["ready_for_langextract"])
        self.assertTrue(result.target_view_payloads["p2"]["ready_for_langextract"])
        self.assertIn("route_override:group_to_individual_case_split", " ".join(result.validation_payload["warnings"]))
        self.assertEqual(result.validation_payload["span_adjustments"][0]["relocated_offsets"], {"start": 10, "end": 37})

    def test_group_route_recovers_source_labelled_patient_targets_before_annotation(self) -> None:
        text = (
            "Two SMS patients were studied.\n\n"
            "Patient Be. A 37-year-old man developed episodic stiffness.\n\n"
            "Patient Rm. A 65-year-old man had severe stiffness."
        )
        source_path = self.write_text_json("9015", text)
        prepared = core.prepare_source(paper_id="9015", source_path=source_path)
        be_block = prepared.blocks[1]
        rm_block = prepared.blocks[2]
        annotation = {
            "segments": [
                {
                    "targets": ["p1"],
                    "role": "patient_specific",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": be_block.block_id,
                            "start_offset": 0,
                            "end_offset": len(be_block.text),
                            "selected_text": be_block.text,
                        }
                    ],
                },
                {
                    "targets": ["p2"],
                    "role": "patient_specific",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": rm_block.block_id,
                            "start_offset": 0,
                            "end_offset": len(rm_block.text),
                            "selected_text": rm_block.text,
                        }
                    ],
                },
            ]
        }

        result = core.process_paper(
            paper_id="9015",
            source_row={
                "preferred_langextract_mode": "group",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "2",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

        self.assertEqual(result.registry_row["route_mode"], "individual_case_split")
        self.assertEqual(result.target_view_payloads["p1"]["target_label"], "Patient Be")
        self.assertEqual(result.target_view_payloads["p2"]["target_label"], "Patient Rm")
        self.assertIn("route_override:group_to_individual_case_split:source_labelled_patients", result.validation_payload["warnings"])
        self.assertEqual(result.registry_row["stage06_diverged"], "true")

    def test_group_route_with_label_count_mismatch_requires_review(self) -> None:
        source_path = self.write_text_json(
            "9016",
            "Two SMS patients were studied.\n\n"
            "Patient Be. A 37-year-old man developed episodic stiffness.",
        )

        result = core.process_paper(
            paper_id="9016",
            source_row={
                "preferred_langextract_mode": "group",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "2",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=None,
        )

        self.assertEqual(result.registry_row["route_mode"], "group")
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertIn("ambiguous_route_recovery_label_count:1:2", result.registry_row["manual_review_reasons"])

    def test_lab_heavy_group_without_patient_labels_stays_group(self) -> None:
        source_path = self.write_text_json(
            "9017",
            "We studied serum from 30 SMS patients. All patient sera recognised GAD-65.\n"
            "Methods described laboratory reagents.",
        )

        result = core.process_paper(
            paper_id="9017",
            source_row={
                "preferred_langextract_mode": "group",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "count_confidence": "",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=None,
        )

        self.assertEqual(result.registry_row["route_mode"], "group")
        self.assertEqual(result.target_view_payloads["g1"]["target_label"], "SPSD group")
        self.assertEqual(result.registry_row["ready_for_langextract"], "false")
        self.assertIn("deterministic_group_pass_through_requires_review", result.registry_row["manual_review_reasons"])

    def test_reviewed_annotation_compiles_source_anchors(self) -> None:
        source_path = self.write_text_json(
            "9009",
            "Intro.\n\nCase 1. A patient had SPS.\n\nDiscussion generic.",
        )
        prepared = core.prepare_source(paper_id="9009", source_path=source_path)
        reviewed = {
            "paper_id": "9009",
            "route_mode": "individual",
            "targets": [{"id": "p1", "kind": "patient", "label": "Patient 1", "evidence": "reviewed"}],
            "segments": [
                {
                    "targets": ["p1"],
                    "role": "patient_specific",
                    "confidence": "reviewed",
                    "evidence": "Reviewed case span.",
                    "selections": [{"start_text": "Case 1.", "end_text": "had SPS."}],
                }
            ],
        }

        annotation = core.compile_reviewed_annotation_payload(
            reviewed_payload=reviewed,
            prepared_source=prepared,
        )

        self.assertEqual(annotation["annotation_mode"], "reviewed_gold")
        self.assertEqual(annotation["route_mode"], "individual")
        self.assertEqual(annotation["segments"][0]["spans"][0]["selected_text"], "Case 1. A patient had SPS.")

    def test_reviewed_split_spans_preserve_ocr_interruption(self) -> None:
        source_path = self.write_text_json(
            "9018",
            "Patient Be had been discon-\n\nPage footer.\n\ntinued, the patient was admitted.",
        )
        prepared = core.prepare_source(paper_id="9018", source_path=source_path)
        reviewed = {
            "paper_id": "9018",
            "route_mode": "individual",
            "targets": [{"id": "p1", "kind": "patient", "label": "Patient Be", "evidence": "reviewed"}],
            "segments": [
                {
                    "targets": ["p1"],
                    "role": "patient_specific",
                    "confidence": "reviewed",
                    "evidence": "Reviewed interrupted source span.",
                    "selections": [
                        {"text": "Patient Be had been discon-"},
                        {"text": "tinued, the patient was admitted."},
                    ],
                }
            ],
        }

        annotation = core.compile_reviewed_annotation_payload(
            reviewed_payload=reviewed,
            prepared_source=prepared,
        )
        segments, report = core.validate_annotation_payload(
            annotation_payload=annotation,
            prepared_source=prepared,
            declared_targets=[core.Target("p1", "patient", "Patient Be", "test")],
        )

        self.assertFalse(report.failed)
        self.assertEqual([segment.text for segment in segments], ["Patient Be had been discon-", "tinued, the patient was admitted."])

    def test_table_heuristic_trims_recognisable_rows_to_spsd_ids(self) -> None:
        source_path = self.write_text_json(
            "9010",
            "The final patient (case 2) had stiff-person syndrome.\n\n"
            "TABLE 1\n"
            "Case Diagnosis Age\n"
            "1 irrelevant myoclonus 40\n"
            "2 stiff-person syndrome 62\n"
            "3 irrelevant dystonia 55",
        )
        prepared = core.prepare_source(paper_id="9010", source_path=source_path)
        table_block = prepared.blocks[1]
        annotation = {
            "segments": [
                {
                    "targets": ["g1"],
                    "role": "group_summary",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": table_block.block_id,
                            "start_offset": 0,
                            "end_offset": len(table_block.text),
                            "selected_text": table_block.text,
                        }
                    ],
                }
            ]
        }

        segments, report = core.validate_annotation_payload(
            annotation_payload=annotation,
            prepared_source=prepared,
            declared_targets=[core.Target("g1", "group", "SPSD group", "test")],
        )

        self.assertFalse(report.failed)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "2 stiff-person syndrome 62")
        self.assertIn("trimmed_table_to_relevant_rows:s0001", report.warnings)

    def test_table_heuristic_accepts_direct_spsd_diagnosis_rows(self) -> None:
        source_path = self.write_text_json(
            "9012",
            "The final patient (case 10) had stiff-person syndrome.\n\n"
            "TABLE 1\n"
            "Diagnosis Antibody titre\n"
            "Postanoxic myoclonus 200\n"
            "Stiff-person syndrome 4,800",
        )
        prepared = core.prepare_source(paper_id="9012", source_path=source_path)
        table_block = prepared.blocks[1]
        annotation = {
            "segments": [
                {
                    "targets": ["g1"],
                    "role": "group_summary",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": table_block.block_id,
                            "start_offset": 0,
                            "end_offset": len(table_block.text),
                            "selected_text": table_block.text,
                        }
                    ],
                }
            ]
        }

        segments, report = core.validate_annotation_payload(
            annotation_payload=annotation,
            prepared_source=prepared,
            declared_targets=[core.Target("g1", "group", "SPSD group", "test")],
        )

        self.assertFalse(report.failed)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "Stiff-person syndrome 4,800")
        self.assertIn("trimmed_table_to_relevant_rows:s0001", report.warnings)

    def test_explicit_spsd_case_ids_handles_parenthetical_case_list(self) -> None:
        text = "The final three patients (cases 8, 9, and 10) had stiff-person syndrome."

        self.assertEqual(core.explicit_spsd_case_ids(text), {"8", "9", "10"})

    def test_source_units_do_not_row_split_narrative_blocks_with_a_few_numbers(self) -> None:
        source_path = self.write_text_json(
            "9024",
            "CASE REPORTS\n"
            "Case 1. A 46-year-old woman had stiff-person syndrome in 1992.\n"
            "She had painful spasms and improved with baclofen.\n"
            "Case 2. A 25-year-old man had stiffness in 1987.\n"
            "He had electromyographic evidence and improved with treatment.",
        )
        prepared = core.prepare_source(paper_id="9024", source_path=source_path)

        units = core.build_source_units(prepared, max_unit_chars=300)
        unit_texts = [unit.text for unit in units]

        self.assertNotIn("table_row", {unit.unit_type for unit in units})
        self.assertTrue(any("Case 1." in text and "spasms" in text for text in unit_texts))
        self.assertTrue(any("Case 2." in text and "electromyographic" in text for text in unit_texts))
        self.assertFalse(any("Case 1." in text and "Case 2." in text for text in unit_texts))

    def test_source_units_do_not_rejoin_text_across_patient_headings(self) -> None:
        source_path = self.write_text_json(
            "9025",
            "PATIENT 1\n"
            "The first patient improved after prednisone.\n"
            "PATIENT 2\n"
            "The second patient had gad antibodies in serum and CSF.",
        )
        prepared = core.prepare_source(paper_id="9025", source_path=source_path)

        units = core.build_source_units(prepared, max_unit_chars=300)
        unit_texts = [unit.text for unit in units]

        self.assertTrue(any("PATIENT 1" in text and "first patient" in text for text in unit_texts))
        self.assertTrue(any("PATIENT 2" in text and "second patient" in text for text in unit_texts))
        self.assertFalse(any("first patient" in text and "PATIENT 2" in text for text in unit_texts))

    def test_source_units_do_not_rejoin_text_across_table_headings(self) -> None:
        source_path = self.write_text_json(
            "9026",
            "Both current patients had GAD antibodies.\n"
            "TABLE 1. Summary of previously reported cases\n"
            "The wider literature table is not a current case narrative.",
        )
        prepared = core.prepare_source(paper_id="9026", source_path=source_path)

        units = core.build_source_units(prepared, max_unit_chars=300)
        unit_texts = [unit.text for unit in units]

        self.assertTrue(any("Both current patients" in text for text in unit_texts))
        self.assertTrue(any(unit.unit_type == "heading" and "TABLE 1" in unit.text for unit in units))
        self.assertFalse(any("Both current patients" in text and "wider literature" in text for text in unit_texts))

    def test_source_units_do_not_rejoin_text_across_article_metadata(self) -> None:
        source_path = self.write_text_json(
            "9027",
            "PATIENT 1\n"
            "The first patient had stiff-person syndrome.\n"
            "Reprint requests to Example Author, MD.\n"
            "Her symptoms improved after treatment.",
        )
        prepared = core.prepare_source(paper_id="9027", source_path=source_path)

        units = core.build_source_units(prepared, max_unit_chars=300)
        unit_texts = [unit.text for unit in units]

        self.assertTrue(any(unit.unit_type == "metadata" and "Reprint requests" in unit.text for unit in units))
        self.assertFalse(any("first patient" in text and "symptoms improved" in text for text in unit_texts))

    def test_source_label_detection_does_not_promote_irrelevant_neighbour_case(self) -> None:
        text = "Patient 5 had SPSD whereas Patient 6 had an unrelated diagnosis."

        self.assertEqual(
            [label.label for label in core.source_patient_labels(text, include_headings=False)],
            ["Patient 5"],
        )

    def test_table_heuristic_warns_when_rows_are_ambiguous(self) -> None:
        source_path = self.write_text_json(
            "9011",
            "The final patient (case 2) had stiff-person syndrome.\n\n"
            "TABLE 1\n"
            "Case\n"
            "1\n"
            "2\n"
            "Diagnosis\n"
            "irrelevant myoclonus\n"
            "stiff-person syndrome",
        )
        prepared = core.prepare_source(paper_id="9011", source_path=source_path)
        table_block = prepared.blocks[1]
        annotation = {
            "segments": [
                {
                    "targets": ["g1"],
                    "role": "group_summary",
                    "confidence": "high",
                    "spans": [
                        {
                            "block_id": table_block.block_id,
                            "start_offset": 0,
                            "end_offset": len(table_block.text),
                            "selected_text": table_block.text,
                        }
                    ],
                }
            ]
        }

        _, report = core.validate_annotation_payload(
            annotation_payload=annotation,
            prepared_source=prepared,
            declared_targets=[core.Target("g1", "group", "SPSD group", "test")],
        )

        self.assertIn("ambiguous_table_row_mapping:s0001", report.review_reasons)

    def test_group_route_embedded_single_spsd_case_recovers_individual_route(self) -> None:
        source_path = self.write_text_json(
            "9013",
            "Mixed movement-disorder cohort.\n\n"
            "Case 10 A 62-year-old woman had stiff-person syndrome.\nTreatment helped.\n"
            "Discussion\nThe remaining trial-level summary was not SPSD-specific.",
        )

        result = core.process_paper(
            paper_id="9013",
            source_row={
                "preferred_langextract_mode": "group",
                "langextract_eligible": "true",
            },
            manual_row={},
            stage06_row={
                "preferred_text_json_path": str(source_path),
                "likely_sps_case_count": "1",
                "count_confidence": "high",
            },
            paths=self.output_paths,
            manifest_run_id="test_stage07_xml",
            annotation_model="gpt-5.5",
            annotation_payload=None,
        )

        self.assertEqual(result.registry_row["route_mode"], "individual")
        self.assertEqual(result.registry_row["annotation_mode"], "deterministic_clinical_window")
        self.assertEqual(result.registry_row["stage06_diverged"], "true")
        self.assertEqual(result.registry_row["ready_for_langextract"], "true")
        self.assertIn("Case 10 A 62-year-old woman", result.target_view_payloads["p1"]["input_text"])
        self.assertNotIn("remaining trial-level summary", result.target_view_payloads["p1"]["input_text"])
        self.assertIn("route_override:group_to_individual", " ".join(result.validation_payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
