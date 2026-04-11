from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validation import _stage05_regression as regression


DEFAULT_OUTPUT_ROOT = regression.REPORTS_DIR / "stage05_regression_guard"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate reviewed stage-05 trimming cases in small tranches and verify them "
            "against historical feedback plus frozen historical JSON outputs."
        )
    )
    parser.add_argument(
        "--regression-dir",
        type=Path,
        default=regression.REGRESSION_DIR,
        help="Directory containing frozen reviewed regression fixtures.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=regression.REPORTS_DIR,
        help="Root directory containing historical batch reports.",
    )
    parser.add_argument(
        "--source-registry-path",
        type=Path,
        default=regression.SOURCE_REGISTRY_PATH,
        help="Path to source_categorisation_registry.csv.",
    )
    parser.add_argument(
        "--source-manual-review-path",
        type=Path,
        default=regression.SOURCE_MANUAL_REVIEW_PATH,
        help="Path to source_categorisation_manual_review.csv.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory for regenerated tranche outputs and tranche reports.",
    )
    parser.add_argument(
        "--tranche-size",
        type=int,
        default=10,
        help="Number of reviewed sources to regenerate per tranche.",
    )
    parser.add_argument(
        "--start-tranche",
        type=int,
        default=1,
        help="1-based tranche index to start from.",
    )
    parser.add_argument(
        "--max-tranches",
        type=int,
        default=0,
        help="Maximum number of tranches to run. Zero means run until completion or first failure.",
    )
    parser.add_argument(
        "--continue-on-fail",
        action="store_true",
        help="Continue to later tranches even if an earlier tranche fails.",
    )
    return parser.parse_args()


def write_summary(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    all_cases = regression.load_regression_cases(
        regression_dir=args.regression_dir,
        reports_dir=args.reports_dir,
        source_registry_path=args.source_registry_path,
        source_manual_review_path=args.source_manual_review_path,
    )
    tranches = regression.chunked_cases(all_cases, args.tranche_size)
    if args.start_tranche < 1 or args.start_tranche > max(len(tranches), 1):
        raise ValueError(f"start-tranche must be between 1 and {max(len(tranches), 1)}.")

    summary_results: list[dict[str, object]] = []
    stop_after_fail = not args.continue_on_fail
    stop_reason = ""

    for tranche_index, cases in enumerate(tranches, start=1):
        if tranche_index < args.start_tranche:
            continue
        if args.max_tranches and len(summary_results) >= args.max_tranches:
            break
        tranche_dir = args.output_root / f"tranche_{tranche_index:03d}"
        report = regression.run_regression_tranche(cases, tranche_dir)
        summary_results.append(
            {
                "tranche_index": tranche_index,
                "tranche_id": tranche_dir.name,
                "case_count": report["case_count"],
                "passed_count": report["passed_count"],
                "failed_count": report["failed_count"],
                "paper_ids": report["paper_ids"],
                "report_path": regression.display_path(tranche_dir / "report.json"),
            }
        )
        if report["failed_count"] and stop_after_fail:
            stop_reason = f"Stopped after failing {tranche_dir.name}."
            break

    summary = {
        "generated_at_utc": regression.now_utc_iso(),
        "reviewed_stage05_case_count": len(all_cases),
        "tranche_size": args.tranche_size,
        "start_tranche": args.start_tranche,
        "max_tranches": args.max_tranches,
        "stop_reason": stop_reason,
        "results": summary_results,
    }
    write_summary(args.output_root / "summary.json", summary)

    print(f"Reviewed stage-05 regression cases discovered: {len(all_cases)}")
    print(f"Summary: {regression.display_path(args.output_root / 'summary.json')}")
    if stop_reason:
        print(stop_reason)


if __name__ == "__main__":
    main()
