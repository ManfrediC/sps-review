from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validation import _stage07_review as review


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_CATEGORISATION_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_CASE_COUNT_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
OUTPUT_ROOT = REPO_ROOT / "qa" / "validation" / "stage07_smoke"
STAGE07_SCRIPT = REPO_ROOT / "src" / "pipelines" / "07_split_case_series.py"
DEFAULT_OPENAI_ENV_FILE = REPO_ROOT / "env" / "openai_api_key.env"


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def select_finalised_split_papers(
    *,
    source_rows: list[dict[str, str]],
    stage06_rows: list[dict[str, str]],
    limit: int,
    minimum_stage06_count: int,
) -> list[str]:
    split_ids = {
        (row.get("paper_id") or "").strip()
        for row in source_rows
        if (row.get("preferred_langextract_mode") or "").strip() == "individual_case_split"
    }
    eligible_rows = [
        row
        for row in stage06_rows
        if (row.get("paper_id") or "").strip() in split_ids
        and (row.get("count_verification_status") or "").strip()
        and (row.get("count_manual_review_required") or "").strip().lower() == "false"
        and int((row.get("likely_sps_case_count") or "0").strip() or "0") >= minimum_stage06_count
    ]
    eligible_rows.sort(key=lambda row: int((row.get("paper_id") or "0").strip() or "0"))
    return [(row.get("paper_id") or "").strip() for row in eligible_rows[:limit]]


def build_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_stage07_smoke")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a stage-07 smoke test on finalised stage-06 split papers."
    )
    parser.add_argument("--limit", type=int, default=10, help="Number of papers to include in the smoke run.")
    parser.add_argument(
        "--minimum-stage06-count",
        type=int,
        default=2,
        help="Minimum finalised stage-06 SPS count for selected smoke papers.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=OUTPUT_ROOT,
        help="Root directory for smoke-run outputs.",
    )
    parser.add_argument(
        "--adjudication-model",
        default="disabled",
        help="Stage-07 adjudication model. Use 'disabled' for heuristics-only smoke runs.",
    )
    parser.add_argument(
        "--allow-paid-run",
        action="store_true",
        help="Required before any paid GPT adjudication call is made.",
    )
    parser.add_argument(
        "--openai-env-file",
        type=Path,
        default=DEFAULT_OPENAI_ENV_FILE,
        help="Env file used to resolve OPENAI_API_KEY for stage-07 adjudication.",
    )
    parser.add_argument(
        "--skip-openai-preflight",
        action="store_true",
        help="Skip the stage-07 OpenAI preflight probe.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_rows = load_csv_rows(SOURCE_CATEGORISATION_PATH)
    stage06_rows = load_csv_rows(SOURCE_CASE_COUNT_PATH)
    paper_ids = select_finalised_split_papers(
        source_rows=source_rows,
        stage06_rows=stage06_rows,
        limit=args.limit,
        minimum_stage06_count=args.minimum_stage06_count,
    )
    if not paper_ids:
        raise SystemExit("No finalised stage-06 split papers matched the requested smoke-test criteria.")
    if args.adjudication_model != "disabled" and not args.allow_paid_run:
        raise SystemExit(
            "Refusing to start a paid stage-07 smoke run without --allow-paid-run."
        )

    run_id = build_run_id()
    run_root = args.output_root / run_id
    units_dir = run_root / "text_case_series_units"
    manifest_dir = run_root / "unit_manifests"
    registry_path = run_root / "case_series_split_registry.csv"
    selection_path = run_root / "selection.json"
    smoke_summary_path = run_root / "smoke_summary.json"
    run_root.mkdir(parents=True, exist_ok=True)

    selection_payload = {
        "run_id": run_id,
        "paper_ids": paper_ids,
        "limit": args.limit,
        "minimum_stage06_count": args.minimum_stage06_count,
    }
    selection_path.write_text(json.dumps(selection_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    stage07_cmd = [
        sys.executable,
        str(STAGE07_SCRIPT),
        "--output-dir",
        str(units_dir),
        "--registry-path",
        str(registry_path),
        "--manifest-dir",
        str(manifest_dir),
        "--manifest-run-id",
        run_id,
        "--skip-registry-refresh",
    ]
    if args.adjudication_model != "disabled":
        stage07_cmd.extend(
            [
                "--adjudication-model",
                args.adjudication_model,
                "--allow-paid-run",
                "--openai-env-file",
                str(args.openai_env_file),
            ]
        )
        if args.skip_openai_preflight:
            stage07_cmd.append("--skip-openai-preflight")
    for paper_id in paper_ids:
        stage07_cmd.extend(["--paper-id", paper_id])
    subprocess.run(stage07_cmd, check=True, cwd=str(REPO_ROOT))

    registry_rows = load_csv_rows(registry_path)
    published_rows = [
        row for row in registry_rows if (row.get("publication_status") or "").strip() != "manual_review_required"
    ]
    qa_paths = review.build_qa_pack(run_root)
    summary_payload = {
        "run_id": run_id,
        "paper_count": len(registry_rows),
        "paper_ids": paper_ids,
        "adjudication_model": args.adjudication_model,
        "published_paper_count": len(published_rows),
        "manual_review_paper_count": len(registry_rows) - len(published_rows),
        "published_unit_count": sum(int((row.get("published_unit_count") or "0").strip() or "0") for row in registry_rows),
        "registry_path": str(registry_path),
        "units_dir": str(units_dir),
        "manifest_dir": str(manifest_dir),
        **qa_paths,
    }
    smoke_summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary_payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
