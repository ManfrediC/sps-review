from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipelines._sps_case_count_registry import write_count_rows
from src.pipelines.stage06_counting.overrides import (
    MANUAL_REVIEW_LEDGER_PATH,
    apply_reviewed_overrides_to_rows,
    reviewed_override_rows_by_id,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def refresh_artifact_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply reviewed stage-06 manual overrides to the canonical SPS case-count registry "
            "without rerunning model extraction."
        )
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=REGISTRY_PATH,
        help="Canonical stage-06 registry to rewrite in place.",
    )
    parser.add_argument(
        "--manual-review-path",
        type=Path,
        default=MANUAL_REVIEW_LEDGER_PATH,
        help="Reviewed override ledger to apply.",
    )
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after rewriting the canonical stage-06 registry.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_csv_rows(args.registry_path)
    override_rows = reviewed_override_rows_by_id(args.manual_review_path)
    updated_rows, applied_paper_ids = apply_reviewed_overrides_to_rows(rows, override_rows)

    if not applied_paper_ids:
        raise SystemExit(
            "No reviewed stage-06 overrides matched rows in the target registry. "
            "Check the registry path and manual-review ledger."
        )

    write_count_rows(updated_rows, args.registry_path)
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Applied {len(applied_paper_ids)} reviewed overrides to {args.registry_path}")
    print("Paper IDs: " + ", ".join(applied_paper_ids))


if __name__ == "__main__":
    main()
