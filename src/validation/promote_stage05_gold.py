from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import src.validation._stage05_gold as gold
import src.validation._stage05_regression as regression


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap and verify the stage-05 gold-standard extracted JSON store."
    )
    parser.add_argument("--batch-id", help="Restrict promotion or verification to a single reviewed batch such as batch_009.")
    parser.add_argument("--paper-id", action="append", default=[], help="Restrict promotion or verification to one or more paper IDs. Repeat as needed.")
    parser.add_argument("--tranche-size", type=int, default=10, help="Number of papers per bootstrap or verification tranche.")
    parser.add_argument("--dry-run", action="store_true", help="Build tranche reports without copying JSONs into the gold directory.")
    parser.add_argument("--verify-only", action="store_true", help="Verify the current gold-backed regression set without promoting new gold JSONs.")
    parser.add_argument("--reports-dir", type=Path, default=gold.REPORTS_DIR, help="Root directory containing per-batch stage-05 reports.")
    parser.add_argument("--regression-dir", type=Path, default=regression.REGRESSION_DIR, help="Directory containing frozen stage-05 regression feedback JSON files.")
    parser.add_argument("--source-registry-path", type=Path, default=regression.SOURCE_REGISTRY_PATH, help="Path to source_categorisation_registry.csv.")
    parser.add_argument("--source-manual-review-path", type=Path, default=regression.SOURCE_MANUAL_REVIEW_PATH, help="Path to source_categorisation_manual_review.csv.")
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def verify_gold(
    *,
    regression_dir: Path,
    reports_dir: Path,
    source_registry_path: Path,
    source_manual_review_path: Path,
    batch_id: str | None,
    paper_ids: list[str],
    tranche_size: int,
) -> dict[str, object]:
    all_cases = regression.load_regression_cases(
        regression_dir=regression_dir,
        reports_dir=reports_dir,
        source_registry_path=source_registry_path,
        source_manual_review_path=source_manual_review_path,
    )
    requested_ids = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
    filtered_cases = [
        case
        for case in all_cases
        if (not batch_id or case.batch_id == batch_id) and (not requested_ids or case.paper_id in requested_ids)
    ]
    tranche_results: list[dict[str, object]] = []
    for tranche_index, cases in enumerate(regression.chunked_cases(filtered_cases, tranche_size), start=1):
        output_dir = gold.TRANCHE_REPORTS_DIR / f"verify_tranche_{tranche_index:03d}"
        report = regression.run_regression_tranche(cases, output_dir)
        tranche_results.append(
            {
                "tranche_id": output_dir.name,
                "case_count": report["case_count"],
                "passed_count": report["passed_count"],
                "failed_count": report["failed_count"],
                "paper_ids": report["paper_ids"],
                "report_path": gold.display_path(output_dir / "report.json"),
            }
        )
    summary = {
        "generated_at_utc": regression.now_utc_iso(),
        "mode": "verify_only",
        "case_count": len(filtered_cases),
        "tranche_size": tranche_size,
        "tranches": tranche_results,
    }
    write_json(gold.tranche_report_path("verify_summary"), summary)
    return summary


def main() -> None:
    args = parse_args()
    if args.verify_only:
        summary = verify_gold(
            regression_dir=args.regression_dir,
            reports_dir=args.reports_dir,
            source_registry_path=args.source_registry_path,
            source_manual_review_path=args.source_manual_review_path,
            batch_id=args.batch_id,
            paper_ids=args.paper_id,
            tranche_size=args.tranche_size,
        )
        print(f"Verified {summary['case_count']} reviewed stage-05 papers across {len(summary['tranches'])} tranches.")
        print(f"Summary: {gold.display_path(gold.tranche_report_path('verify_summary'))}")
        return

    summary = gold.bootstrap_gold_store(
        reports_dir=args.reports_dir,
        regression_dir=args.regression_dir,
        source_registry_path=args.source_registry_path,
        source_manual_review_path=args.source_manual_review_path,
        batch_id=args.batch_id,
        paper_ids=args.paper_id,
        tranche_size=args.tranche_size,
        dry_run=args.dry_run,
    )
    print(f"Processed {summary['candidate_count']} reviewed stage-05 papers into the gold store across {len(summary['tranches'])} tranches.")
    print(f"Manifest: {gold.display_path(gold.MANIFEST_PATH)}")
    print(f"Summary: {gold.display_path(gold.tranche_report_path('bootstrap_summary'))}")


if __name__ == "__main__":
    main()
