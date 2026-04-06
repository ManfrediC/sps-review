from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.validation.stage04_model_benchmark import _shared as shared


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a fixed 20-paper stage-04 model benchmark set from reviewed gold rows."
    )
    parser.add_argument(
        "--benchmark-id",
        default=shared.DEFAULT_BENCHMARK_ID,
        help="Benchmark set identifier under qa/validation/source_categorisation/model_benchmark/.",
    )
    parser.add_argument(
        "--benchmark-size",
        type=int,
        default=shared.DEFAULT_BENCHMARK_SIZE,
        help="Total number of benchmark papers to select.",
    )
    parser.add_argument(
        "--ambiguous-target",
        type=int,
        default=shared.DEFAULT_AMBIGUOUS_TARGET,
        help="Target number of ambiguous/boundary papers in the benchmark set.",
    )
    parser.add_argument(
        "--gold-path",
        type=Path,
        default=shared.GOLD_MASTER_PATH,
        help="Reviewed gold CSV used as the benchmark source.",
    )
    return parser.parse_args()


def joined_review_candidates(gold_path: Path) -> list[dict[str, str]]:
    cached_source_rows, cached_count_rows = shared.load_cached_stage04_outputs()
    artifact_rows = shared.load_artifact_rows()
    joined_rows: list[dict[str, str]] = []
    for gold_row in shared.reviewed_gold_rows(gold_path):
        paper_id = (gold_row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        cached_source_row = cached_source_rows.get(paper_id, {})
        if not cached_source_row:
            continue
        artifact_row = artifact_rows.get(paper_id, {})
        pdf_path_relative = shared.gold.first_pipe_separated_value(artifact_row.get("pdf_paths_relative"))
        preferred_text_json_path = (
            (cached_source_row.get("preferred_text_json_path") or "").strip()
            or (artifact_row.get("text_trim_source_text_json_path") or "").strip()
            or (artifact_row.get("text_json_path") or "").strip()
        )
        if not pdf_path_relative or not preferred_text_json_path:
            continue

        gold_category = (gold_row.get("reviewed_source_category") or "").strip()
        gold_individual, gold_group = shared.infer_gold_data_presence(
            category=gold_category,
            cached_source_row=cached_source_row,
        )
        joined_rows.append(
            {
                "paper_id": paper_id,
                "covidence_id": (gold_row.get("covidence_id") or paper_id).strip(),
                "title": (gold_row.get("title") or "").strip(),
                "authors": (gold_row.get("authors") or "").strip(),
                "published_year": (gold_row.get("published_year") or "").strip(),
                "journal": (gold_row.get("journal") or "").strip(),
                "source_round_id": (gold_row.get("round_id") or "").strip(),
                "selection_bucket": (gold_row.get("selection_bucket") or "").strip(),
                "selection_signals": (gold_row.get("selection_signals") or "").strip(),
                "pdf_path_relative": pdf_path_relative,
                "preferred_text_json_path": preferred_text_json_path,
                "preferred_text_source": (cached_source_row.get("preferred_text_source") or "").strip(),
                "proceedings_detected": (cached_source_row.get("proceedings_detected") or "").strip(),
                "trim_status": (cached_source_row.get("trim_status") or "").strip(),
                "gold_source_category": gold_category,
                "gold_extractable_sps_case_count": (
                    gold_row.get("reviewed_extractable_sps_case_count") or ""
                ).strip(),
                "gold_original_sps_data": shared.infer_gold_original_data(gold_category),
                "gold_contains_individual_level_data": gold_individual,
                "gold_contains_group_level_data": gold_group,
                "gold_ambiguity_tier": shared.infer_ambiguity_tier(gold_row, cached_source_row),
                "gold_label_status": "seeded",
                "gold_label_notes": "Seeded from reviewed category plus cached gpt-4.1 structural fields.",
                "cached_gpt41_source_category": (cached_source_row.get("source_category") or "").strip(),
                "cached_gpt41_source_subtype": (cached_source_row.get("source_subtype") or "").strip(),
                "cached_gpt41_confidence": (cached_source_row.get("classification_confidence") or "").strip(),
                "cached_gpt41_likely_case_count": (cached_source_row.get("likely_case_count") or "").strip(),
                "cached_gpt41_contains_individual_level_data": (
                    cached_source_row.get("contains_individual_level_data") or ""
                ).strip(),
                "cached_gpt41_contains_group_level_data": (
                    cached_source_row.get("contains_group_level_data") or ""
                ).strip(),
                "cached_gpt41_manual_review_required": (
                    cached_source_row.get("manual_review_required") or ""
                ).strip(),
                "cached_gpt41_count_confidence": (
                    cached_count_rows.get(paper_id, {}).get("count_confidence") or ""
                ).strip(),
                "cached_gpt41_count_manual_review_required": (
                    cached_count_rows.get(paper_id, {}).get("count_manual_review_required") or ""
                ).strip(),
                "cached_gpt41_original_sps_data": "",
                "cached_gpt41_evidence_available": "false",
                "cached_gpt41_categorisation_reason": (
                    cached_source_row.get("categorisation_reason") or ""
                ).strip(),
                "cached_gpt41_count_reason": (cached_count_rows.get(paper_id, {}).get("count_reason") or "").strip(),
                "prediction_correct": (gold_row.get("prediction_correct") or "").strip(),
            }
        )
    return joined_rows


def normalise_manual_review_category(category: str) -> str:
    category = category.strip()
    mapping = {
        "review_article": "review_article",
        "teaching_review": "review_article",
        "editorial_review": "review_article",
        "conference_abstract": "conference_abstract",
        "single_case_conference_abstract": "conference_abstract",
        "group_conference_abstract": "conference_abstract",
        "case_series_conference_abstract": "conference_abstract",
        "single_case_report": "single_case_report",
        "case_report": "single_case_report",
        "paraneoplastic_case_report": "single_case_report",
        "genetic_case_report": "single_case_report",
        "pediatric_case_report": "single_case_report",
        "imaging_case_report": "single_case_report",
        "neuro_ophthalmology_case_report": "single_case_report",
        "respiratory_case_report": "single_case_report",
        "complex_treatment_case_report": "single_case_report",
        "psychiatric_misdiagnosis_case_report": "single_case_report",
        "drug_triggered_case_report": "single_case_report",
        "immune_checkpoint_case_report": "single_case_report",
        "teaching_case_report": "single_case_report",
        "autoimmune_comorbidity_case_report": "single_case_report",
        "case_series_or_multi_case": "case_series_or_multi_case",
        "small_case_series": "case_series_or_multi_case",
        "prevalence_case_series": "case_series_or_multi_case",
        "observational_group_study": "observational_group_study",
        "autoantibody_clinical_cohort": "observational_group_study",
        "glyr_antibody_clinical_cohort": "observational_group_study",
        "lab_heavy_clinical_or_translational": "lab_heavy_clinical_or_translational",
        "serologic_biomarker_study": "lab_heavy_clinical_or_translational",
        "neurophysiology_study": "lab_heavy_clinical_or_translational",
        "non_clinical_basic_science": "non_clinical_basic_science",
        "animal_model_pathogenicity_abstract": "non_clinical_basic_science",
        "t_cell_receptor_immunology_study": "non_clinical_basic_science",
        "autoantigen_assay_study": "non_clinical_basic_science",
        "comparative_gad65_immunology_study": "non_clinical_basic_science",
    }
    return mapping.get(category, "")


def manual_review_fallback_candidates() -> list[dict[str, str]]:
    cached_source_rows, cached_count_rows = shared.load_cached_stage04_outputs()
    artifact_rows = shared.load_artifact_rows()
    fallback_rows: list[dict[str, str]] = []
    for manual_row in shared.load_csv_rows(shared.MANUAL_REVIEW_PATH):
        paper_id = (manual_row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        gold_category = normalise_manual_review_category(
            (manual_row.get("final_source_category") or "").strip()
        )
        if not gold_category:
            continue
        alignment_tag = (manual_row.get("pdf_content_alignment_tag") or "").strip()
        if alignment_tag in {"likely_wrong_pdf_attached", "incorrect_reference"}:
            continue
        cached_source_row = cached_source_rows.get(paper_id, {})
        if not cached_source_row:
            continue
        artifact_row = artifact_rows.get(paper_id, {})
        pdf_path_relative = shared.gold.first_pipe_separated_value(artifact_row.get("pdf_paths_relative"))
        preferred_text_json_path = (
            (cached_source_row.get("preferred_text_json_path") or "").strip()
            or (artifact_row.get("text_json_path") or "").strip()
        )
        if not pdf_path_relative or not preferred_text_json_path:
            continue
        gold_individual, gold_group = shared.infer_gold_data_presence(
            category=gold_category,
            cached_source_row=cached_source_row,
        )
        fallback_rows.append(
            {
                "paper_id": paper_id,
                "covidence_id": (cached_source_row.get("covidence_id") or paper_id).strip(),
                "title": (
                    (manual_row.get("title") or "").strip()
                    or (cached_source_row.get("title") or "").strip()
                ),
                "authors": (cached_source_row.get("authors") or "").strip(),
                "published_year": (cached_source_row.get("published_year") or "").strip(),
                "journal": (cached_source_row.get("journal") or "").strip(),
                "source_round_id": (manual_row.get("review_batch") or "manual_review_ledger").strip(),
                "selection_bucket": "manual_review_clear_seed",
                "selection_signals": (manual_row.get("review_decision_notes") or "").strip(),
                "pdf_path_relative": pdf_path_relative,
                "preferred_text_json_path": preferred_text_json_path,
                "preferred_text_source": (cached_source_row.get("preferred_text_source") or "").strip(),
                "proceedings_detected": (cached_source_row.get("proceedings_detected") or "").strip(),
                "trim_status": (cached_source_row.get("trim_status") or "").strip(),
                "gold_source_category": gold_category,
                "gold_extractable_sps_case_count": "",
                "gold_original_sps_data": shared.infer_gold_original_data(gold_category),
                "gold_contains_individual_level_data": gold_individual,
                "gold_contains_group_level_data": gold_group,
                "gold_ambiguity_tier": "clear",
                "gold_label_status": "seeded",
                "gold_label_notes": "Seeded from manual review ledger plus cached gpt-4.1 structural fields.",
                "cached_gpt41_source_category": (cached_source_row.get("source_category") or "").strip(),
                "cached_gpt41_source_subtype": (cached_source_row.get("source_subtype") or "").strip(),
                "cached_gpt41_confidence": (cached_source_row.get("classification_confidence") or "").strip(),
                "cached_gpt41_likely_case_count": (cached_source_row.get("likely_case_count") or "").strip(),
                "cached_gpt41_contains_individual_level_data": (
                    cached_source_row.get("contains_individual_level_data") or ""
                ).strip(),
                "cached_gpt41_contains_group_level_data": (
                    cached_source_row.get("contains_group_level_data") or ""
                ).strip(),
                "cached_gpt41_manual_review_required": (
                    cached_source_row.get("manual_review_required") or ""
                ).strip(),
                "cached_gpt41_count_confidence": (
                    cached_count_rows.get(paper_id, {}).get("count_confidence") or ""
                ).strip(),
                "cached_gpt41_count_manual_review_required": (
                    cached_count_rows.get(paper_id, {}).get("count_manual_review_required") or ""
                ).strip(),
                "cached_gpt41_original_sps_data": "",
                "cached_gpt41_evidence_available": "false",
                "cached_gpt41_categorisation_reason": (
                    cached_source_row.get("categorisation_reason") or ""
                ).strip(),
                "cached_gpt41_count_reason": (cached_count_rows.get(paper_id, {}).get("count_reason") or "").strip(),
                "prediction_correct": "true",
            }
        )
    return fallback_rows


def sorted_candidates_for_category(
    candidates: list[dict[str, str]],
    *,
    category: str,
    ambiguity_tier: str,
) -> list[dict[str, str]]:
    matching = [
        row
        for row in candidates
        if (row.get("gold_source_category") or "").strip() == category
        and (row.get("gold_ambiguity_tier") or "").strip() == ambiguity_tier
    ]
    return sorted(
        matching,
        key=lambda row: shared.benchmark_selection_priority(
            benchmark_role=f"{ambiguity_tier}_{category}",
            gold_row=row,
            cached_source_row={
                "classification_confidence": row.get("cached_gpt41_confidence", ""),
                "manual_review_required": row.get("cached_gpt41_manual_review_required", ""),
            },
        ),
    )


def sorted_ambiguous_candidates(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    ambiguous = [
        row for row in candidates if (row.get("gold_ambiguity_tier") or "").strip() == "ambiguous"
    ]
    return sorted(
        ambiguous,
        key=lambda row: (
            0
            if any(
                (row.get("selection_bucket") or "").strip().startswith(prefix)
                for prefix in shared.AMBIGUOUS_BUCKET_PREFIXES
            )
            else 1,
            shared.parse_int(row.get("paper_id"), default=10**9),
        ),
    )


def sorted_control_candidates(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        candidates,
        key=lambda row: (
            0 if (row.get("gold_ambiguity_tier") or "").strip() == "clear" else 1,
            0 if (row.get("selection_bucket") or "").strip() == "high_confidence_control" else 1,
            shared.parse_int(row.get("paper_id"), default=10**9),
        ),
    )


def category_counts(rows: list[dict[str, str]]) -> Counter[str]:
    return Counter((row.get("gold_source_category") or "").strip() for row in rows)


def build_benchmark_rows(
    candidates: list[dict[str, str]],
    *,
    benchmark_id: str,
    benchmark_size: int,
    ambiguous_target: int,
) -> tuple[list[dict[str, str]], list[str]]:
    selected_ids: set[str] = set()
    selected_rows: list[dict[str, str]] = []
    missing_clear_categories: list[str] = []

    for benchmark_role, category in shared.CLEAR_CATEGORY_TARGETS:
        clear_candidates = sorted_candidates_for_category(candidates, category=category, ambiguity_tier="clear")
        candidate = clear_candidates[0] if clear_candidates else None
        if candidate is None:
            fallback_candidates = sorted_candidates_for_category(
                candidates,
                category=category,
                ambiguity_tier="ambiguous",
            )
            candidate = fallback_candidates[0] if fallback_candidates else None
        if candidate is None:
            missing_clear_categories.append(category)
            continue
        paper_id = (candidate.get("paper_id") or "").strip()
        if paper_id in selected_ids:
            continue
        selected_ids.add(paper_id)
        selected_rows.append(
            {
                "benchmark_id": benchmark_id,
                "benchmark_role": benchmark_role,
                "benchmark_bucket": "clear_category_anchor",
                "selection_priority": str(len(selected_rows) + 1),
                "selection_reason": (
                    f"Selected as the benchmark anchor for {category} from reviewed rows."
                ),
                "selection_created_at_utc": shared.now_utc_iso(),
                **{key: value for key, value in candidate.items() if key != "prediction_correct"},
            }
        )

    for candidate in sorted_ambiguous_candidates(candidates):
        ambiguous_selected = [
            row for row in selected_rows if (row.get("gold_ambiguity_tier") or "").strip() == "ambiguous"
        ]
        if len(ambiguous_selected) >= ambiguous_target:
            break
        paper_id = (candidate.get("paper_id") or "").strip()
        if paper_id in selected_ids:
            continue
        selected_ids.add(paper_id)
        selected_rows.append(
            {
                "benchmark_id": benchmark_id,
                "benchmark_role": "ambiguous_boundary",
                "benchmark_bucket": "ambiguous_boundary",
                "selection_priority": str(len(selected_rows) + 1),
                "selection_reason": (
                    f"Selected as an ambiguous benchmark paper from {candidate.get('selection_bucket') or 'reviewed_gold'}."
                ),
                "selection_created_at_utc": shared.now_utc_iso(),
                **{key: value for key, value in candidate.items() if key != "prediction_correct"},
            }
        )

    remaining_controls = [
        candidate
        for candidate in sorted_control_candidates(candidates)
        if (candidate.get("paper_id") or "").strip() not in selected_ids
    ]
    while len(selected_rows) < benchmark_size and remaining_controls:
        selected_category_counts = category_counts(selected_rows)
        remaining_controls.sort(
            key=lambda row: (
                selected_category_counts.get((row.get("gold_source_category") or "").strip(), 0),
                0 if (row.get("gold_ambiguity_tier") or "").strip() == "clear" else 1,
                0 if (row.get("selection_bucket") or "").strip() == "high_confidence_control" else 1,
                shared.parse_int(row.get("paper_id"), default=10**9),
            )
        )
        candidate = remaining_controls.pop(0)
        paper_id = (candidate.get("paper_id") or "").strip()
        selected_ids.add(paper_id)
        selected_rows.append(
            {
                "benchmark_id": benchmark_id,
                "benchmark_role": "mixed_control",
                "benchmark_bucket": "mixed_control",
                "selection_priority": str(len(selected_rows) + 1),
                "selection_reason": "Selected to complete the mixed 20-paper benchmark set with category balancing.",
                "selection_created_at_utc": shared.now_utc_iso(),
                **{key: value for key, value in candidate.items() if key != "prediction_correct"},
            }
        )

    return selected_rows[:benchmark_size], missing_clear_categories


def main() -> None:
    args = parse_args()
    paths = shared.benchmark_paths(args.benchmark_id)
    candidates = joined_review_candidates(args.gold_path)
    existing_ids = {(row.get("paper_id") or "").strip() for row in candidates}
    for row in manual_review_fallback_candidates():
        paper_id = (row.get("paper_id") or "").strip()
        if paper_id and paper_id not in existing_ids:
            candidates.append(row)
            existing_ids.add(paper_id)
    benchmark_rows, missing_categories = build_benchmark_rows(
        candidates,
        benchmark_id=args.benchmark_id,
        benchmark_size=args.benchmark_size,
        ambiguous_target=args.ambiguous_target,
    )

    shared.write_csv_rows(paths.benchmark_set_path, benchmark_rows, shared.benchmark_fieldnames())
    manifest = shared.benchmark_manifest_payload(
        benchmark_id=args.benchmark_id,
        benchmark_rows=benchmark_rows,
        requested_categories=[category for _, category in shared.CLEAR_CATEGORY_TARGETS],
        missing_requested_categories=missing_categories,
        default_ambiguous_target=args.ambiguous_target,
    )
    shared.write_json(paths.manifest_path, manifest)

    print(f"benchmark_id={args.benchmark_id}")
    print(f"benchmark_set_path={shared.relative_repo_path(paths.benchmark_set_path)}")
    print(f"manifest_path={shared.relative_repo_path(paths.manifest_path)}")
    print(f"selected_rows={len(benchmark_rows)}")
    print(f"selected_category_counts={dict(Counter(row['gold_source_category'] for row in benchmark_rows))}")
    print(f"selected_ambiguity_counts={dict(Counter(row['gold_ambiguity_tier'] for row in benchmark_rows))}")
    if missing_categories:
        print(f"missing_requested_clear_categories={missing_categories}")


if __name__ == "__main__":
    main()
