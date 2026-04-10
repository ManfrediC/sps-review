from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validation import _stage05_review as review


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh stage-05 review queue, feedback, override, and acceptance artefacts for an existing batch."
    )
    parser.add_argument(
        "--batch-id",
        required=True,
        help="Batch identifier such as batch_009.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=review.REPORTS_DIR,
        help="Root directory containing per-batch stage-05 reports.",
    )
    parser.add_argument(
        "--feedback-dir",
        type=Path,
        default=review.FEEDBACK_DIR,
        help="Directory containing frozen human feedback JSON files.",
    )
    parser.add_argument(
        "--regression-dir",
        type=Path,
        default=review.REGRESSION_DIR,
        help="Directory containing frozen regression JSON files.",
    )
    parser.add_argument(
        "--artifact-registry-path",
        type=Path,
        default=review.ARTIFACT_REGISTRY_PATH,
        help="Path to paper_artifact_registry.csv.",
    )
    parser.add_argument(
        "--source-registry-path",
        type=Path,
        default=review.SOURCE_REGISTRY_PATH,
        help="Path to source_categorisation_registry.csv.",
    )
    parser.add_argument(
        "--source-manual-review-path",
        type=Path,
        default=review.SOURCE_MANUAL_REVIEW_PATH,
        help="Path to source_categorisation_manual_review.csv.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_dir = args.reports_dir / args.batch_id
    result = review.refresh_review_materials(
        batch_id=args.batch_id,
        report_dir=report_dir,
        feedback_dir=args.feedback_dir,
        regression_dir=args.regression_dir,
        reports_dir=args.reports_dir,
        artifact_registry_path=args.artifact_registry_path,
        source_registry_path=args.source_registry_path,
        source_manual_review_path=args.source_manual_review_path,
    )
    print(
        f"Updated {args.batch_id}: {result['completed_review_count']} reviewed, "
        f"{result['acceptance_report']['failed_count']} acceptance failures."
    )
    print(f"Feedback: {review.display_path(review.feedback_path(report_dir))}")
    print(f"Acceptance: {review.display_path(review.acceptance_report_path(report_dir))}")


if __name__ == "__main__":
    main()
