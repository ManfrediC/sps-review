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

from stage07_XML import core


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

    def test_single_patient_source_gets_deterministic_pass_through_view(self) -> None:
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
        self.assertEqual(result.registry_row["ready_for_langextract"], "true")
        self.assertTrue(result.target_view_payloads["p1"]["ready_for_langextract"])
        self.assertIn("A 40-year-old woman had SPS.", result.target_view_payloads["p1"]["input_text"])


if __name__ == "__main__":
    unittest.main()

