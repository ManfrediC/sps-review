from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


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
                "text": "Her gait improved after treatment and residual stiffness persisted at long-term review but she regained independent transfers.",
            },
            {"page_index": 0, "line_index": 7, "global_index": 7, "text": "Discussion"},
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


if __name__ == "__main__":
    unittest.main()
