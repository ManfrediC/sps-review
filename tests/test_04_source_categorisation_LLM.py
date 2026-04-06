from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.pipelines.source_categorisation.models import (
    ClassificationResult,
    Confidence,
    EvidenceItem,
    OriginalSpsData,
    SourceCategory,
)
from src.pipelines.source_categorisation.run_state import (
    append_result_record,
    build_run_manifest,
    initialise_run,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
LLM_SCRIPT = REPO_ROOT / "src" / "pipelines" / "04_source_categorisation_LLM.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_result(paper_id: str, *, count: int) -> ClassificationResult:
    result = ClassificationResult(
        paper_id=paper_id,
        source_type=SourceCategory.case_series_or_multi_case,
        original_sps_spectrum_data=OriginalSpsData.yes,
        contains_individual_level_data=True,
        contains_group_level_data=True,
        manual_review_required=False,
        confidence=Confidence.high,
        likely_sps_case_count=count,
        count_confidence=Confidence.high,
        count_manual_review_required=False,
        count_reasoning_summary=f"The paper explicitly describes {count} SPS patients.",
        reasoning_summary="The paper is a multi-case clinical report.",
        evidence=[
            EvidenceItem(
                quote=f"We describe {count} patients with stiff person syndrome who improved after therapy.",
                page=1,
                section="abstract",
                supports="multi-case SPS cohort and patient count",
            )
        ],
        validator_flags=[],
        classification_source="llm",
    )
    result.derive_routing_fields()
    return result


class TestLlMCategorisationPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.llm_mod = _load_module("llm_source_categorisation_module", LLM_SCRIPT)

    def build_workspace(self) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
        tmp_dir = Path(tempfile.mkdtemp())
        references_csv = tmp_dir / "references.csv"
        input_dir = tmp_dir / "text"
        trimmed_dir = tmp_dir / "text_trimmed"
        run_root = tmp_dir / "runs"
        output_path = tmp_dir / "source_registry.csv"
        count_output_path = tmp_dir / "count_registry.csv"
        progress_path = run_root / "placeholder"

        write_csv(
            references_csv,
            [
                {
                    "Covidence": "321",
                    "Title": "Two SPS cases responding to treatment",
                    "Authors": "Example, A",
                    "Abstract": "We describe two patients with stiff person syndrome who improved after therapy.",
                    "Journal": "Neurology",
                    "Published Year": "2024",
                    "Tags": "",
                    "Notes": "",
                },
                {
                    "Covidence": "322",
                    "Title": "Three SPS cases responding to treatment",
                    "Authors": "Example, B",
                    "Abstract": "We describe three patients with stiff person syndrome who improved after therapy.",
                    "Journal": "Neurology",
                    "Published Year": "2024",
                    "Tags": "",
                    "Notes": "",
                },
            ],
            ["Covidence", "Title", "Authors", "Abstract", "Journal", "Published Year", "Tags", "Notes"],
        )
        input_dir.mkdir(parents=True, exist_ok=True)
        trimmed_dir.mkdir(parents=True, exist_ok=True)
        for paper_id, count in (("321", 2), ("322", 3)):
            (input_dir / f"{paper_id}.json").write_text(
                json.dumps(
                    {
                        "paper_id": paper_id,
                        "pages": [
                            {
                                "page_num": 1,
                                "text": f"Case 1 improved after therapy. Total cases reported: {count}.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
        return references_csv, input_dir, trimmed_dir, run_root, output_path, count_output_path, progress_path

    def test_requires_allow_paid_run_before_llm_calls(self) -> None:
        references_csv, input_dir, trimmed_dir, run_root, output_path, count_output_path, _ = self.build_workspace()
        args = argparse.Namespace(
            references_csv=references_csv,
            input_dir=input_dir,
            trimmed_dir=trimmed_dir,
            trim_registry_path=run_root / "trim.csv",
            manual_review_path=run_root / "manual.csv",
            output_path=output_path,
            count_output_path=count_output_path,
            run_root=run_root,
            run_id="approval_gate",
            resume=False,
            publish=False,
            publish_only=False,
            estimate_only=False,
            allow_paid_run=False,
            paper_id=["321"],
            limit=0,
            model=self.llm_mod.DEFAULT_MODEL,
            checkpoint_every=1,
            max_runtime_minutes=0.0,
            skip_manual_overrides=True,
            dry_run=False,
            skip_registry_refresh=True,
        )

        with (
            mock.patch.object(self.llm_mod, "parse_args", return_value=args),
            mock.patch.object(self.llm_mod, "process_paper") as mocked_process,
            self.assertRaises(SystemExit) as raised,
        ):
            self.llm_mod.main()

        self.assertIn("Refusing to start a paid LLM run", str(raised.exception))
        mocked_process.assert_not_called()
        self.assertFalse((run_root / "approval_gate").exists())

    def test_main_checkpoints_and_publishes_complete_run(self) -> None:
        references_csv, input_dir, trimmed_dir, run_root, output_path, count_output_path, _ = self.build_workspace()
        args = argparse.Namespace(
            references_csv=references_csv,
            input_dir=input_dir,
            trimmed_dir=trimmed_dir,
            trim_registry_path=run_root / "trim.csv",
            manual_review_path=run_root / "manual.csv",
            output_path=output_path,
            count_output_path=count_output_path,
            run_root=run_root,
            run_id="checkpointed_run",
            resume=False,
            publish=True,
            publish_only=False,
            estimate_only=False,
            allow_paid_run=True,
            paper_id=["321", "322"],
            limit=0,
            model=self.llm_mod.DEFAULT_MODEL,
            checkpoint_every=1,
            max_runtime_minutes=0.0,
            skip_manual_overrides=True,
            dry_run=False,
            skip_registry_refresh=True,
        )

        with (
            mock.patch.object(self.llm_mod, "parse_args", return_value=args),
            mock.patch.object(
                self.llm_mod,
                "process_paper",
                side_effect=[make_result("321", count=2), make_result("322", count=3)],
            ),
        ):
            self.llm_mod.main()

        with output_path.open(encoding="utf-8", newline="") as source_handle:
            source_rows = list(csv.DictReader(source_handle))
        with count_output_path.open(encoding="utf-8", newline="") as count_handle:
            count_rows = list(csv.DictReader(count_handle))

        run_dir = run_root / "checkpointed_run"
        progress = json.loads((run_dir / "progress.json").read_text(encoding="utf-8"))

        self.assertEqual(len(source_rows), 2)
        self.assertEqual(len(count_rows), 2)
        self.assertTrue((run_dir / "results.jsonl").exists())
        self.assertTrue((run_dir / "source_categorisation_registry_snapshot.csv").exists())
        self.assertTrue((run_dir / "source_sps_case_count_registry_snapshot.csv").exists())
        self.assertEqual(progress["completed_total"], 2)
        self.assertNotEqual(progress["published_at_utc"], "")

    def test_resume_continues_from_existing_checkpoint(self) -> None:
        references_csv, input_dir, trimmed_dir, run_root, output_path, count_output_path, _ = self.build_workspace()
        manifest = build_run_manifest(
            run_id="resume_run",
            paper_ids=["321", "322"],
            references_csv=references_csv,
            input_dir=input_dir,
            trimmed_dir=trimmed_dir,
            trim_registry_path=run_root / "trim.csv",
            manual_review_path=run_root / "manual.csv",
            model=self.llm_mod.DEFAULT_MODEL,
            skip_manual_overrides=True,
            planned_manual_overrides=0,
            planned_llm_calls=2,
        )
        run_dir = initialise_run(run_root, manifest, resume=False)
        existing_source_row = {
            "paper_id": "321",
            "covidence_id": "321",
            "title": "Two SPS cases responding to treatment",
            "authors": "Example, A",
            "published_year": "2024",
            "journal": "Neurology",
            "tags": "",
            "notes": "",
            "text_json_path": "text/321.json",
            "preferred_text_json_path": "text/321.json",
            "preferred_text_source": "full_text",
            "proceedings_detected": "false",
            "trim_status": "",
            "source_category": "case_series_or_multi_case",
            "source_subtype": "case_series",
            "classification_confidence": "high",
            "likely_case_count": "2",
            "contains_individual_level_data": "true",
            "contains_group_level_data": "true",
            "case_series_split_candidate": "true",
            "preferred_langextract_mode": "individual_case_split",
            "langextract_eligible": "true",
            "manual_review_required": "false",
            "recommended_next_action": "split_cases_then_langextract",
            "conference_marker_hits": "",
            "review_marker_hits": "",
            "case_report_marker_hits": "",
            "multi_case_marker_hits": "",
            "observational_marker_hits": "",
            "interventional_marker_hits": "",
            "non_clinical_marker_hits": "",
            "translational_marker_hits": "",
            "patient_label_count": "",
            "categorisation_reason": "Existing checkpoint.",
            "categorisation_version": self.llm_mod.CATEGORISATION_VERSION,
            "categorised_at_utc": "2026-04-06T09:00:00+00:00",
        }
        existing_count_row = {
            "paper_id": "321",
            "covidence_id": "321",
            "title": "Two SPS cases responding to treatment",
            "authors": "Example, A",
            "source_category": "case_series_or_multi_case",
            "source_subtype": "case_series",
            "preferred_text_json_path": "text/321.json",
            "preferred_text_source": "full_text",
            "count_eligible": "true",
            "likely_sps_case_count": "2",
            "count_confidence": "high",
            "count_basis": "llm_joint_extraction",
            "count_manual_review_required": "false",
            "count_reason": "Existing checkpoint.",
            "count_version": self.llm_mod.CATEGORISATION_VERSION,
            "counted_at_utc": "2026-04-06T09:00:00+00:00",
        }
        append_result_record(
            run_dir,
            {
                "paper_id": "321",
                "classification_source": "llm",
                "saved_at_utc": "2026-04-06T09:00:00+00:00",
                "source_row": existing_source_row,
                "count_row": existing_count_row,
            },
        )

        args = argparse.Namespace(
            references_csv=references_csv,
            input_dir=input_dir,
            trimmed_dir=trimmed_dir,
            trim_registry_path=run_root / "trim.csv",
            manual_review_path=run_root / "manual.csv",
            output_path=output_path,
            count_output_path=count_output_path,
            run_root=run_root,
            run_id="resume_run",
            resume=True,
            publish=True,
            publish_only=False,
            estimate_only=False,
            allow_paid_run=True,
            paper_id=[],
            limit=0,
            model=self.llm_mod.DEFAULT_MODEL,
            checkpoint_every=1,
            max_runtime_minutes=0.0,
            skip_manual_overrides=True,
            dry_run=False,
            skip_registry_refresh=True,
        )

        with (
            mock.patch.object(self.llm_mod, "parse_args", return_value=args),
            mock.patch.object(self.llm_mod, "process_paper", return_value=make_result("322", count=3)) as mocked_process,
        ):
            self.llm_mod.main()

        with output_path.open(encoding="utf-8", newline="") as source_handle:
            source_rows = list(csv.DictReader(source_handle))
        self.assertEqual(len(source_rows), 2)
        self.assertEqual([row["paper_id"] for row in source_rows], ["321", "322"])
        mocked_process.assert_called_once()


if __name__ == "__main__":
    unittest.main()
