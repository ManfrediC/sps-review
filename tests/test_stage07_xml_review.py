from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.validation import _stage07_xml_review as review


def segment(
    *,
    segment_id: str,
    logical_segment_id: str,
    targets: list[str],
    role: str,
    source_text: str,
    selected_text: str,
    block_id: str = "b0001",
    confidence: str = "high",
) -> dict[str, object]:
    start = source_text.index(selected_text)
    end = start + len(selected_text)
    return {
        "segment_id": segment_id,
        "logical_segment_id": logical_segment_id,
        "targets": targets,
        "role": role,
        "text": selected_text,
        "source_offsets": {"start": start, "end": end},
        "source_block_id": block_id,
        "confidence": confidence,
        "evidence": f"Evidence for {segment_id}",
    }


class TestStage07XmlReview(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.stage07_root = self.tmp_path / "stage07_xml"
        self.registry_path = self.tmp_path / "stage07_xml_registry.csv"
        self.gold_root = self.tmp_path / "qa" / "validation" / "stage07_xml" / "gold_standard"
        self.registry_rows: list[dict[str, str]] = []

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_stage07_output(
        self,
        *,
        paper_id: str,
        source_text: str,
        entities: list[dict[str, str]],
        segments: list[dict[str, object]],
        route_mode: str = "individual_case_split",
        manual_reasons: list[str] | None = None,
    ) -> None:
        manual_reasons = manual_reasons or []
        source_sha = review.sha256_text(source_text)
        paper_json_path = self.stage07_root / "papers" / f"{paper_id}.json"
        segments_json_path = self.stage07_root / "segments" / f"{paper_id}.segments.json"
        annotated_text_path = self.stage07_root / "annotated_text" / f"{paper_id}.annotated.txt"
        validation_json_path = self.stage07_root / "validation" / f"{paper_id}.validation.json"
        for path in (paper_json_path, segments_json_path, annotated_text_path, validation_json_path):
            path.parent.mkdir(parents=True, exist_ok=True)

        paper_json_path.write_text(
            json.dumps(
                {
                    "paper_id": paper_id,
                    "stage07_schema_version": "stage07_xml_v1",
                    "title": f"Paper {paper_id}",
                    "source": {
                        "source_text_sha256": "source-record-sha",
                        "prepared_source_sha256": source_sha,
                    },
                    "source_route": {"resolved_langextract_mode": route_mode},
                    "annotation": {
                        "annotation_mode": "mocked_span_metadata",
                        "validation_status": "failed" if manual_reasons else "passed",
                        "roundtrip_status": "passed",
                    },
                    "entities": entities,
                    "manual_review": {
                        "manual_review_required": bool(manual_reasons),
                        "reasons": manual_reasons,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        segments_json_path.write_text(
            json.dumps(
                {
                    "paper_id": paper_id,
                    "stage07_segments_schema_version": "stage07_xml_segments_v1",
                    "source": {
                        "source_text_sha256": "source-record-sha",
                        "prepared_source_sha256": source_sha,
                        "prepared_source_character_count": len(source_text),
                    },
                    "entities": entities,
                    "source_blocks": [
                        {
                            "block_id": "b0001",
                            "source_offsets": {"start": 0, "end": len(source_text)},
                            "page_index": 0,
                            "text": source_text,
                        }
                    ],
                    "segments": segments,
                    "validation": {"status": "failed" if manual_reasons else "passed"},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        annotated_text_path.write_text(source_text, encoding="utf-8")
        validation_json_path.write_text(
            json.dumps({"status": "failed" if manual_reasons else "passed", "errors": manual_reasons}),
            encoding="utf-8",
        )
        self.registry_rows.append(
            {
                "paper_id": paper_id,
                "paper_json_path": str(paper_json_path),
                "segments_json_path": str(segments_json_path),
                "annotated_text_path": str(annotated_text_path),
                "validation_json_path": str(validation_json_path),
                "route_mode": route_mode,
                "validation_status": "failed" if manual_reasons else "passed",
                "roundtrip_status": "passed",
                "manual_review_required": "true" if manual_reasons else "false",
                "manual_review_reasons": "|".join(manual_reasons),
            }
        )

    def write_registry(self) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with self.registry_path.open("w", encoding="utf-8", newline="") as handle:
            fieldnames = [
                "paper_id",
                "paper_json_path",
                "segments_json_path",
                "annotated_text_path",
                "validation_json_path",
                "route_mode",
                "validation_status",
                "roundtrip_status",
                "manual_review_required",
                "manual_review_reasons",
            ]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.registry_rows)

    def build_fixture_outputs(self) -> None:
        one_patient_text = "A single patient had <SPSD> and axial stiffness."
        self.write_stage07_output(
            paper_id="1001",
            source_text=one_patient_text,
            entities=[{"id": "p1", "kind": "patient", "label": "Patient 1"}],
            segments=[
                segment(
                    segment_id="s0001",
                    logical_segment_id="l0001",
                    targets=["p1"],
                    role="patient_specific",
                    source_text=one_patient_text,
                    selected_text="A single patient had <SPSD> and axial stiffness.",
                )
            ],
            route_mode="individual",
        )

        shared_text = (
            "Patient 1 had axial stiffness.\n\n"
            "Patient 2 had spasms.\n\n"
            "Both patients had anti-GAD antibodies.\n\n"
            "Unclear assignment: family history."
        )
        self.write_stage07_output(
            paper_id="1002",
            source_text=shared_text,
            entities=[
                {"id": "p1", "kind": "patient", "label": "Patient 1"},
                {"id": "p2", "kind": "patient", "label": "Patient 2"},
            ],
            segments=[
                segment(
                    segment_id="s0001",
                    logical_segment_id="l0001",
                    targets=["p1"],
                    role="patient_specific",
                    source_text=shared_text,
                    selected_text="Patient 1 had axial stiffness.",
                ),
                segment(
                    segment_id="s0002",
                    logical_segment_id="l0002",
                    targets=["p2"],
                    role="patient_specific",
                    source_text=shared_text,
                    selected_text="Patient 2 had spasms.",
                ),
                segment(
                    segment_id="s0003",
                    logical_segment_id="l0003",
                    targets=["p1", "p2"],
                    role="shared",
                    source_text=shared_text,
                    selected_text="Both patients had anti-GAD antibodies.",
                ),
                segment(
                    segment_id="s0004",
                    logical_segment_id="l0004",
                    targets=["unknown"],
                    role="uncertain",
                    source_text=shared_text,
                    selected_text="Unclear assignment: family history.",
                    confidence="low",
                ),
            ],
            manual_reasons=["uncertain_segment:s0004"],
        )

        group_text = "The cohort included 6 SPSD patients with stiffness."
        self.write_stage07_output(
            paper_id="1003",
            source_text=group_text,
            entities=[{"id": "g1", "kind": "group", "label": "SPSD group"}],
            segments=[
                segment(
                    segment_id="s0001",
                    logical_segment_id="l0001",
                    targets=["g1"],
                    role="group_summary",
                    source_text=group_text,
                    selected_text=group_text,
                )
            ],
            route_mode="group",
        )

        high_count_parts = [f"P{index} statement." for index in range(1, 22)]
        high_count_text = "\n".join(high_count_parts)
        high_count_entities = [
            {"id": f"p{index}", "kind": "patient", "label": f"Patient {index}"}
            for index in range(1, 22)
        ]
        high_count_segments = [
            segment(
                segment_id=f"s{index:04d}",
                logical_segment_id=f"l{index:04d}",
                targets=[f"p{index}"],
                role="patient_specific",
                source_text=high_count_text,
                selected_text=f"P{index} statement.",
            )
            for index in range(1, 22)
        ]
        self.write_stage07_output(
            paper_id="1004",
            source_text=high_count_text,
            entities=high_count_entities,
            segments=high_count_segments,
        )
        self.write_registry()

    def test_build_review_pack_writes_html_queue_and_responses(self) -> None:
        self.build_fixture_outputs()

        result = review.build_review_pack(
            round_id="2026-04-25_round_01",
            stage07_root=self.stage07_root,
            registry_path=self.registry_path,
            gold_root=self.gold_root,
        )

        index_path = self.gold_root / "2026-04-25_round_01" / "index.html"
        paper_html_path = self.gold_root / "2026-04-25_round_01" / "papers" / "1001.html"
        queue_path = self.gold_root / "2026-04-25_round_01" / "review_queue.csv"
        responses_path = self.gold_root / "2026-04-25_round_01" / "review_responses.csv"
        self.assertEqual(result["paper_count"], "4")
        self.assertTrue(index_path.exists())
        self.assertTrue(paper_html_path.exists())
        self.assertTrue(queue_path.exists())
        self.assertTrue(responses_path.exists())

        paper_html = paper_html_path.read_text(encoding="utf-8")
        self.assertIn("&lt;SPSD&gt;", paper_html)
        self.assertIn("target-chip", paper_html)

        with queue_path.open(encoding="utf-8", newline="") as handle:
            queue_rows = list(csv.DictReader(handle))
        with responses_path.open(encoding="utf-8", newline="") as handle:
            response_rows = list(csv.DictReader(handle))
        self.assertEqual(len(queue_rows), 28)
        self.assertEqual(len(response_rows), 28)
        self.assertIn("paper", {row["row_type"] for row in queue_rows})
        self.assertIn("p1 p2", {row["predicted_targets"] for row in queue_rows})
        self.assertIn("0", {row["source_start"] for row in queue_rows})
        self.assertEqual(response_rows[0]["reviewed_targets"], response_rows[0]["predicted_targets"])

    def test_colour_assignments_cover_high_count_targets_with_labels(self) -> None:
        entities = [
            {"id": f"p{index}", "kind": "patient", "label": f"Patient {index}"}
            for index in range(1, 25)
        ]

        colours = review.target_colour_assignments(entities)
        chips = review.chips_html(["p1", "p21", "p24"], review.target_label_lookup(entities), colours)

        self.assertEqual(len(colours), 24)
        self.assertEqual(colours["p21"]["index"], "21")
        self.assertIn("Patient 21", chips)
        self.assertIn("p24", chips)

    def test_refresh_gold_standard_merges_reviewed_rows_deterministically(self) -> None:
        self.build_fixture_outputs()
        review.build_review_pack(
            round_id="2026-04-25_round_01",
            stage07_root=self.stage07_root,
            registry_path=self.registry_path,
            gold_root=self.gold_root,
        )
        responses_path = self.gold_root / "2026-04-25_round_01" / "review_responses.csv"
        rows = review.load_csv_rows(responses_path)
        rows[0]["prediction_correct"] = "true"
        rows[0]["review_status"] = "reviewed"
        rows[0]["reviewer_notes"] = "Initial review."
        rows[0]["reviewer_id"] = "tester"
        rows[0]["reviewed_at_utc"] = "2026-04-25T10:00:00+00:00"
        review.write_csv_rows(responses_path, rows, review.RESPONSE_FIELDNAMES)

        second_round = self.gold_root / "2026-04-25_round_02"
        second_round.mkdir(parents=True)
        duplicate = dict(rows[0])
        duplicate["round_id"] = "2026-04-25_round_02"
        duplicate["reviewer_notes"] = "Corrected review."
        duplicate["reviewed_at_utc"] = "2026-04-25T11:00:00+00:00"
        review.write_csv_rows(second_round / "review_responses.csv", [duplicate], review.RESPONSE_FIELDNAMES)

        gold_path = review.refresh_gold_standard(gold_root=self.gold_root)

        gold_rows = review.load_csv_rows(gold_path)
        self.assertEqual(len(gold_rows), 1)
        self.assertEqual(gold_rows[0]["reviewer_notes"], "Corrected review.")
        self.assertEqual(gold_rows[0]["review_status"], "reviewed")


if __name__ == "__main__":
    unittest.main()
