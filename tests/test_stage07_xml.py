from __future__ import annotations

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
