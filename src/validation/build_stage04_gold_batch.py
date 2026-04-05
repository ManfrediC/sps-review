from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validation._stage04_gold import (
    ARTIFACT_REGISTRY_PATH,
    COUNT_REGISTRY_PATH,
    DEFAULT_BUCKET_QUOTAS,
    DEFAULT_SEED,
    GOLD_STANDARD_ROOT,
    ROUND_MANIFEST_FILENAME,
    ROUND_QUEUE_FILENAME,
    SOURCE_REGISTRY_PATH,
    TRIM_REGISTRY_PATH,
    build_selection_manifest,
    build_selection_queue_rows,
    ensure_empty_responses_file,
    load_csv_rows_by_id,
    load_selection_source_rows,
    next_round_directory,
    selection_queue_fieldnames,
    select_gold_rows,
    write_round_outputs,
    write_csv_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a reproducible stage-04 gold-standard review batch."
    )
    parser.add_argument(
        "--source-registry-path",
        type=Path,
        default=SOURCE_REGISTRY_PATH,
        help="Path to source_categorisation_registry.csv.",
    )
    parser.add_argument(
        "--count-registry-path",
        type=Path,
        default=COUNT_REGISTRY_PATH,
        help="Path to source_sps_case_count_registry.csv.",
    )
    parser.add_argument(
        "--artifact-registry-path",
        type=Path,
        default=ARTIFACT_REGISTRY_PATH,
        help="Path to paper_artifact_registry.csv.",
    )
    parser.add_argument(
        "--trim-registry-path",
        type=Path,
        default=TRIM_REGISTRY_PATH,
        help="Path to text_trim_registry.csv for proceedings page anchors.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Round directory. Defaults to the next dated folder under qa/validation/source_categorisation/gold_standard.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Random seed for reproducible within-bucket ordering.",
    )
    parser.add_argument(
        "--conference-edge-size",
        type=int,
        default=DEFAULT_BUCKET_QUOTAS["conference_edge"],
        help="Rows to sample for conference-edge review.",
    )
    parser.add_argument(
        "--case-group-boundary-size",
        type=int,
        default=DEFAULT_BUCKET_QUOTAS["case_group_boundary"],
        help="Rows to sample for case-series versus group-study review.",
    )
    parser.add_argument(
        "--review-lab-edge-size",
        type=int,
        default=DEFAULT_BUCKET_QUOTAS["review_lab_edge"],
        help="Rows to sample for review versus lab-heavy review.",
    )
    parser.add_argument(
        "--count-ambiguity-size",
        type=int,
        default=DEFAULT_BUCKET_QUOTAS["count_ambiguity"],
        help="Rows to sample for extractable-count ambiguity review.",
    )
    parser.add_argument(
        "--high-confidence-control-size",
        type=int,
        default=DEFAULT_BUCKET_QUOTAS["high_confidence_control"],
        help="Rows to sample as high-confidence controls.",
    )
    parser.add_argument(
        "--include-manual-reviewed",
        action="store_true",
        help="Include papers already adjudicated in source_categorisation_manual_review.csv.",
    )
    parser.add_argument(
        "--include-example-ids",
        action="store_true",
        help="Include papers that already appear in the case-report example CSV.",
    )
    parser.add_argument(
        "--include-prior-gold",
        action="store_true",
        help="Include papers already selected in earlier gold rounds.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bucket_quotas = {
        "conference_edge": args.conference_edge_size,
        "case_group_boundary": args.case_group_boundary_size,
        "review_lab_edge": args.review_lab_edge_size,
        "count_ambiguity": args.count_ambiguity_size,
        "high_confidence_control": args.high_confidence_control_size,
    }
    round_dir = args.output_dir or next_round_directory(GOLD_STANDARD_ROOT)
    round_dir.mkdir(parents=True, exist_ok=True)

    selection_rows, _, artifact_rows = load_selection_source_rows(
        source_registry_path=args.source_registry_path,
        count_registry_path=args.count_registry_path,
        artifact_registry_path=args.artifact_registry_path,
        include_manual_reviewed=args.include_manual_reviewed,
        exclude_example_ids=not args.include_example_ids,
        exclude_gold_ids=not args.include_prior_gold,
    )
    selected_rows, available_counts, selected_counts = select_gold_rows(
        selection_rows,
        bucket_quotas=bucket_quotas,
        seed=args.seed,
    )
    trim_rows = load_csv_rows_by_id(args.trim_registry_path, "paper_id")
    queue_rows = build_selection_queue_rows(
        selected_rows,
        artifact_rows=artifact_rows,
        trim_rows=trim_rows,
        round_dir=round_dir,
    )

    write_csv_rows(
        round_dir / ROUND_QUEUE_FILENAME,
        queue_rows,
        selection_queue_fieldnames(),
    )
    ensure_empty_responses_file(round_dir)
    write_round_outputs(
        round_dir=round_dir,
        queue_rows=queue_rows,
        responses_by_id={},
    )

    manifest = build_selection_manifest(
        round_dir=round_dir,
        selected_rows=selected_rows,
        queue_rows=queue_rows,
        bucket_quotas=bucket_quotas,
        available_counts=available_counts,
        selected_counts=selected_counts,
        seed=args.seed,
    )
    (round_dir / ROUND_MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Created stage-04 gold batch in: {round_dir}")
    print(f"Selected {len(queue_rows)} rows with seed {args.seed}")
    print(f"Bucket quotas: {bucket_quotas}")
    print(f"Available bucket counts: {available_counts}")
    print(f"Selected bucket counts: {manifest['selected_bucket_counts']}")


if __name__ == "__main__":
    main()
