from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINES_DIR = REPO_ROOT / "src" / "pipelines"
STAGE07_HELPER = PIPELINES_DIR / "_stage07_units.py"


def _load_module(name: str, path: Path):
    sys.path.insert(0, str(PIPELINES_DIR))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if sys.path[0] == str(PIPELINES_DIR):
            sys.path.pop(0)


class TestStage07SplitCaseSeries(unittest.TestCase):
    def test_individual_units_and_shared_context_build_manifest_cleanly(self) -> None:
        mod = _load_module("stage07_units_manifest", STAGE07_HELPER)
        lines = [
            {"page_index": 0, "line_index": 0, "global_index": 0, "text": "Both patients had axial stiffness."},
            {"page_index": 0, "line_index": 1, "global_index": 1, "text": "Patient 1"},
            {
                "page_index": 0,
                "line_index": 2,
                "global_index": 2,
                "text": "Patient 1 had severe axial stiffness and painful spasms with anti-GAD positivity and improvement after diazepam therapy over follow-up.",
            },
            {
                "page_index": 0,
                "line_index": 3,
                "global_index": 3,
                "text": "She required ongoing symptomatic treatment but remained ambulatory with reduced stiffness and fewer spasms than at presentation.",
            },
            {"page_index": 0, "line_index": 4, "global_index": 4, "text": "Patient 2"},
            {
                "page_index": 0,
                "line_index": 5,
                "global_index": 5,
                "text": "Patient 2 developed progressive leg stiffness, startle-provoked spasms, and anti-GAD-positive SPS with a clear response to corticosteroids.",
            },
            {
                "page_index": 0,
                "line_index": 6,
                "global_index": 6,
                "text": "1Department of Neurology, Example University Hospital, London, UK",
            },
            {
                "page_index": 0,
                "line_index": 7,
                "global_index": 7,
                "text": "Her gait improved after treatment and residual stiffness persisted at long-term review but she regained independent transfers.",
            },
            {"page_index": 0, "line_index": 8, "global_index": 8, "text": "Discussion"},
        ]
        stage06_prior = {
            "final_count": 2,
            "count_confidence": "high",
            "granularity": "individual-level",
            "count_verification_status": "manual_review_override",
        }
        source_route = {
            "contains_individual_level_data": True,
            "contains_group_level_data": False,
        }

        units, reason = mod.build_individual_units(
            paper_id="9001",
            lines=lines,
            stage06_prior=stage06_prior,
        )
        self.assertEqual(reason, "")
        self.assertEqual(len(units), 2)
        self.assertNotIn("Example University Hospital", units[1]["unit_text"])

        shared_blocks = mod.build_shared_context_blocks(
            paper_id="9001",
            lines=lines,
            units=units,
        )
        self.assertEqual(len(shared_blocks), 1)
        self.assertEqual(shared_blocks[0]["applies_to_unit_ids"], [units[0]["unit_id"], units[1]["unit_id"]])
        unresolved = mod.build_unresolved_remainder(
            lines=lines,
            units=units,
            shared_context_blocks=shared_blocks,
            publication_status="publish_all_units",
            reason_code="individual_units_match_stage06_count",
            reason="Explicit individual unit headings matched the stage-06 patient-count prior.",
        )
        self.assertFalse(unresolved["present"])

        status, reason_code, _, _, _ = mod.publication_decision(
            stage06_prior=stage06_prior,
            source_route=source_route,
            individual_units=units,
            group_units=[],
        )
        self.assertEqual(status, "publish_all_units")
        self.assertEqual(reason_code, "individual_units_match_stage06_count")

        payload = {
            "paper_id": "9001",
            "source_text_json_path": "data/extraction_json/text/9001.json",
            "source_route": {
                "resolved_source_category": "case_series_or_multi_case",
                "resolved_source_subtype": "case_series",
                "resolved_source_route_source": "source_categorisation_registry",
                "contains_individual_level_data": True,
                "contains_group_level_data": False,
                "preferred_langextract_mode": "individual_case_split",
                "recommended_next_action": "split_cases_then_langextract",
            },
            "stage06_prior": stage06_prior,
            "publication_decision": {"status": status},
            "shared_context_blocks": shared_blocks,
            "units": mod.clean_units_for_output(units),
        }
        manifest_records = mod.derive_manifest_records(
            manifest_run_id="20260419T120000Z_stage07",
            paper_json_path=Path("data/extraction_json/text_case_series_units/9001.json"),
            paper_payload=payload,
        )
        self.assertEqual(len(manifest_records), 2)
        self.assertIn("Both patients had axial stiffness.", manifest_records[0]["langextract_input_text"])
        self.assertEqual(manifest_records[0]["prompt_mode"], "individual")

    def test_group_units_detect_diagnosis_defined_subgroups(self) -> None:
        mod = _load_module("stage07_units_groups", STAGE07_HELPER)
        lines = [
            {
                "page_index": 0,
                "line_index": 0,
                "global_index": 0,
                "text": "The cohort included 10 patients with SPS and 4 patients with PERM treated at the same centre.",
            }
        ]
        units = mod.build_group_units(
            paper_id="9002",
            lines=lines,
            stage06_prior={"granularity": "group-level", "explicit_sps_subgroup_count": 2},
            source_route={"contains_group_level_data": True},
        )
        self.assertEqual(len(units), 2)
        self.assertEqual(units[0]["unit_type"], "group")
        self.assertEqual(units[0]["group_size"], 10)
        self.assertEqual(units[1]["group_size"], 4)

    def test_inline_case_markers_are_recognised(self) -> None:
        mod = _load_module("stage07_units_inline_markers", STAGE07_HELPER)
        lines = [
            {
                "page_index": 0,
                "line_index": 0,
                "global_index": 0,
                "text": "Subjects, methods, and results. Case 1. A 53-year-old man developed episodic right leg stiffness with painful spasms and later improved after IVIg and diazepam therapy.",
            },
            {
                "page_index": 0,
                "line_index": 1,
                "global_index": 1,
                "text": "He had thyroiditis and pernicious anaemia but no truncal rigidity during the early course of illness.",
            },
            {
                "page_index": 0,
                "line_index": 2,
                "global_index": 2,
                "text": "Case 2. His daughter developed recurrent axial opisthotonos with anxiety-provoked spasms and later partial response to baclofen treatment.",
            },
            {
                "page_index": 0,
                "line_index": 3,
                "global_index": 3,
                "text": "Her serum GAD65 antibody remained strongly positive and episodic symptoms persisted at long-term follow-up.",
            },
        ]

        units, reason = mod.build_individual_units(
            paper_id="9003",
            lines=lines,
            stage06_prior={"final_count": 2},
        )

        self.assertEqual(reason, "")
        self.assertEqual([unit["unit_label"] for unit in units], ["Case 1", "Case 2"])

    def test_restrict_to_article_window_discards_neighbouring_articles(self) -> None:
        mod = _load_module("stage07_units_article_window", STAGE07_HELPER)
        lines = [
            {"page_index": 0, "line_index": 0, "global_index": 0, "text": "Unrelated preceding title"},
            {"page_index": 0, "line_index": 1, "global_index": 1, "text": "A. Author, B. Author"},
            {"page_index": 0, "line_index": 2, "global_index": 2, "text": "Stiff-leg syndrome:"},
            {"page_index": 0, "line_index": 3, "global_index": 3, "text": "a focal form of stiff-man syndrome."},
            {"page_index": 0, "line_index": 4, "global_index": 4, "text": "Albert Saiz, MD, Francesc Graus, MD"},
            {"page_index": 0, "line_index": 5, "global_index": 5, "text": "We report on 2 patients with focal SPS-spectrum disease."},
            {"page_index": 0, "line_index": 6, "global_index": 6, "text": "Patient 1"},
            {"page_index": 0, "line_index": 7, "global_index": 7, "text": "Patient 1 had prolonged right-leg rigidity with anti-GAD positivity and clinical improvement after diazepam treatment over follow-up."},
            {"page_index": 0, "line_index": 8, "global_index": 8, "text": "Patient 2"},
            {"page_index": 0, "line_index": 9, "global_index": 9, "text": "Patient 2 had progressive stiffness, startle-induced spasms, and gait impairment with partial benzodiazepine response and later IVIg benefit."},
            {"page_index": 0, "line_index": 10, "global_index": 10, "text": "Primary Position Upbeat"},
            {"page_index": 0, "line_index": 11, "global_index": 11, "text": "Nystagmus due to Unilateral Medial Medullary Infarction"},
            {"page_index": 0, "line_index": 12, "global_index": 12, "text": "Genjiro Hirose, MD, PhD"},
        ]

        article_lines = mod.restrict_to_article_window(
            lines,
            reference_row={
                "Title": "Stiff-leg syndrome: a focal form of stiff-man syndrome.",
                "Authors": "Saiz, A; Graus, F",
            },
        )

        self.assertEqual(article_lines[0]["text"], "Stiff-leg syndrome:")
        self.assertEqual(article_lines[-1]["text"], "Patient 2 had progressive stiffness, startle-induced spasms, and gait impairment with partial benzodiazepine response and later IVIg benefit.")

    def test_process_paper_can_use_adjudication_when_heuristics_fail(self) -> None:
        mod = _load_module("stage07_units_adjudication", STAGE07_HELPER)
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            tmp_path = Path(tmp_dir_text)
            text_dir = tmp_path / "text"
            output_dir = tmp_path / "out"
            text_dir.mkdir()
            output_dir.mkdir()
            (text_dir / "9004.json").write_text(
                json.dumps(
                    {
                        "source_filename": "9004.pdf",
                        "source_sha256": "abc123",
                        "pages": [
                            {
                                "page_index": 0,
                                "text": "\n".join(
                                    [
                                        "Case series of two patients with SPS.",
                                        "A 42-year-old woman developed progressive axial stiffness with painful spasms and frequent falls before treatment.",
                                        "She improved substantially after diazepam and immunotherapy, although residual stiffness persisted at follow-up.",
                                        "A second patient, a 51-year-old man, had startle-provoked spasms with lower-limb rigidity and anti-GAD positivity.",
                                        "He showed partial improvement after diazepam and physiotherapy but still needed walking support.",
                                        "All 2 patients had anti-GAD antibodies and disabling axial stiffness.",
                                        "Discussion",
                                    ]
                                ),
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            adjudication = mod.Stage07AdjudicationOutput(
                decision_type="publish_units",
                decision_summary="Two attribution-safe individual units were recoverable from the narrative text.",
                units=[
                    mod.Stage07AdjudicatedUnit(
                        unit_type="individual",
                        unit_label="Patient 1",
                        line_spans=[mod.Stage07LineSpan(start_global_index=1, end_global_index=2)],
                        evidence_summary="The first two narrative lines describe one woman consistently.",
                    ),
                    mod.Stage07AdjudicatedUnit(
                        unit_type="individual",
                        unit_label="Patient 2",
                        line_spans=[mod.Stage07LineSpan(start_global_index=3, end_global_index=4)],
                        evidence_summary="The next two lines describe a distinct second patient consistently.",
                    ),
                ],
                shared_context_blocks=[
                    mod.Stage07AdjudicatedSharedContext(
                        context_label="Both patients shared anti-GAD positivity and axial stiffness",
                        applies_to_unit_labels=["Patient 1", "Patient 2"],
                        line_spans=[mod.Stage07LineSpan(start_global_index=5, end_global_index=5)],
                        evidence_summary="The paper explicitly states that both patients shared these features.",
                    )
                ],
                unresolved_remainder_reason="",
            )

            old_text_dir = mod.TEXT_DIR
            old_reference_row_for_paper = mod.reference_row_for_paper
            mod.TEXT_DIR = text_dir
            mod.reference_row_for_paper = lambda paper_id: {}
            try:
                with mock.patch.object(
                    mod,
                    "adjudicate_stage07_units",
                    return_value=(adjudication, "gpt-5.4-test"),
                ) as mocked_adjudicator:
                    result = mod.process_paper(
                        paper_id="9004",
                        source_row={
                            "source_category": "case_series_or_multi_case",
                            "source_subtype": "case_series",
                            "classification_confidence": "high",
                            "contains_individual_level_data": "true",
                            "contains_group_level_data": "false",
                            "preferred_langextract_mode": "individual_case_split",
                            "recommended_next_action": "split_cases_then_langextract",
                        },
                        manual_row={},
                        stage06_row={
                            "likely_sps_case_count": "2",
                            "count_confidence": "high",
                            "count_verification_status": "manual_review_override",
                        },
                        paper_output_dir=output_dir,
                        manifest_run_id="20260420T120000Z_stage07",
                        candidate_generation_mode="heuristics_v1",
                        adjudication_model="gpt-5.4",
                        adjudication_api_key="test-key",
                    )
                self.assertEqual(mocked_adjudicator.call_count, 1)
                self.assertEqual(result.paper_payload["publication_decision"]["status"], "publish_all_units")
                self.assertEqual(len(result.paper_payload["units"]), 2)
                self.assertEqual(result.paper_payload["stage07_adjudication"]["validation_status"], "selected")
                self.assertEqual(
                    [unit["unit_label"] for unit in result.paper_payload["units"]],
                    ["Patient 1", "Patient 2"],
                )
                self.assertIn(
                    "All 2 patients had anti-GAD antibodies and disabling axial stiffness.",
                    result.manifest_records[0]["langextract_input_text"],
                )
            finally:
                mod.TEXT_DIR = old_text_dir
                mod.reference_row_for_paper = old_reference_row_for_paper

    def test_build_units_from_adjudication_rejects_generic_patient_mentions(self) -> None:
        mod = _load_module("stage07_units_adjudication_validation", STAGE07_HELPER)
        lines = [
            {
                "page_index": 0,
                "line_index": 0,
                "global_index": 0,
                "text": "One patient was discovered to have renal cell carcinoma and Ma3-antibodies after an extended antibody work-up, but no stable patient-level narrative anchor was provided in the excerpt.",
            },
            {
                "page_index": 0,
                "line_index": 1,
                "global_index": 1,
                "text": "Another patient with LGI1 antibodies showed a good response to immunotherapy, but the paper fragment still reads as a generic mention rather than a self-contained case description.",
            },
        ]
        adjudication = mod.Stage07AdjudicationOutput(
            decision_type="publish_units",
            decision_summary="Two patients were mentioned.",
            units=[
                mod.Stage07AdjudicatedUnit(
                    unit_type="individual",
                    unit_label="patient_1",
                    line_spans=[mod.Stage07LineSpan(start_global_index=0, end_global_index=0)],
                    evidence_summary="A generic patient mention appears in the abstract.",
                )
            ],
            shared_context_blocks=[],
            unresolved_remainder_reason="",
        )

        with self.assertRaisesRegex(ValueError, "not attribution-safe"):
            mod.build_units_from_adjudication(
                paper_id="9999",
                lines=lines,
                stage06_prior={"final_count": 2},
                adjudication=adjudication,
            )


if __name__ == "__main__":
    unittest.main()
