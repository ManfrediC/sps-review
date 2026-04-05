"""LLM-based source categorisation for SPS systematic review papers.

Alternative to ``04_source_categorisation.py`` (heuristic approach).
Outputs to ``results/source_categorisation_llm/`` to keep results
separate from the canonical heuristic output.

Usage:
    python -m src.pipelines.04_source_categorisation_LLM [--paper-id ID ...] [--limit N]
    python -m src.pipelines.04_source_categorisation_LLM --help
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

from src.pipelines.source_categorisation.controller import (
    process_paper,
    result_to_registry_row,
)
from src.pipelines.source_categorisation.io import load_csv_rows_by_id, write_registry
from src.pipelines.source_categorisation.prepare import load_text_json

REPO_ROOT = Path(__file__).resolve().parents[2]

# Input paths (same as the heuristic pipeline).
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
TEXT_TRIM_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"

# Output directory — separate from the canonical heuristic output.
OUTPUT_DIR = REPO_ROOT / "results" / "source_categorisation_llm"
OUTPUT_PATH = OUTPUT_DIR / "source_categorisation_registry.csv"

DEFAULT_MODEL = "gpt-4.1"
CATEGORISATION_VERSION = "llm_v1_gpt4.1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reference CSV loader
# ---------------------------------------------------------------------------


def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    """Load reference rows keyed by Covidence ID."""
    if not path.exists():
        logger.error("References CSV not found: %s", path)
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            key = (row.get("Covidence") or "").strip()
            if key:
                rows[key] = row
    return rows


# ---------------------------------------------------------------------------
# Text path collection
# ---------------------------------------------------------------------------


def collect_text_paths(
    input_dir: Path,
    paper_ids: list[str],
    limit: int,
) -> list[Path]:
    """Collect text JSON paths, filtered by paper IDs and limit."""
    if paper_ids:
        paths = [input_dir / f"{pid}.json" for pid in paper_ids]
        return [p for p in paths if p.exists()]
    paths = sorted(input_dir.glob("*.json"), key=lambda p: p.stem)
    if limit > 0:
        paths = paths[:limit]
    return paths


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _relative_to_repo(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LLM-based source categorisation for SPS papers."
    )
    parser.add_argument("--references-csv", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--input-dir", type=Path, default=TEXT_DIR)
    parser.add_argument("--trimmed-dir", type=Path, default=TEXT_TRIMMED_DIR)
    parser.add_argument("--trim-registry-path", type=Path, default=TEXT_TRIM_REGISTRY_PATH)
    parser.add_argument("--manual-review-path", type=Path, default=MANUAL_REVIEW_PATH)
    parser.add_argument("--output-path", type=Path, default=OUTPUT_PATH)
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Paper ID(s) to process (repeatable). Omit to process all.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max papers to process (0 = all).")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="OpenAI model ID.")
    parser.add_argument(
        "--skip-manual-overrides",
        action="store_true",
        help="Ignore the manual review ledger (e.g. for benchmarking).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare payloads and report what would be classified, without calling the API.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Load registries.
    reference_rows = load_reference_rows(args.references_csv)
    trim_rows = load_csv_rows_by_id(args.trim_registry_path, "paper_id")
    manual_rows: dict[str, dict[str, str]] = {}
    if not args.skip_manual_overrides:
        manual_rows = load_csv_rows_by_id(args.manual_review_path, "paper_id")

    # Collect papers.
    text_paths = collect_text_paths(args.input_dir, args.paper_id, args.limit)
    if not text_paths:
        logger.warning("No text JSONs found to process.")
        sys.exit(0)

    logger.info(
        "Processing %d papers (model=%s, manual_overrides=%d)",
        len(text_paths),
        args.model,
        len(manual_rows),
    )

    if args.dry_run:
        for tp in text_paths:
            pid = tp.stem
            source = "manual_override" if pid in manual_rows else "llm"
            logger.info("  [dry-run] %s -> %s", pid, source)
        logger.info("Dry run complete — %d papers would be processed.", len(text_paths))
        return

    version = CATEGORISATION_VERSION
    if args.model != DEFAULT_MODEL:
        version = f"llm_v1_{args.model}"

    rows: list[dict[str, str]] = []
    llm_count = 0
    manual_count = 0
    error_count = 0

    for text_path in text_paths:
        paper_id = text_path.stem
        reference_row = reference_rows.get(paper_id, {})
        trim_row = trim_rows.get(paper_id, {})
        manual_row = manual_rows.get(paper_id)

        # Load text records.
        text_record = load_text_json(text_path)
        preferred_path = args.trimmed_dir / text_path.name
        preferred_record = None
        preferred_text_source = "full_text"
        if preferred_path.exists():
            preferred_record = load_text_json(preferred_path)
            preferred_text_source = "trimmed"

        try:
            result = process_paper(
                paper_id=paper_id,
                reference_row=reference_row,
                text_record=text_record,
                preferred_record=preferred_record,
                preferred_text_source=preferred_text_source,
                trim_row=trim_row,
                manual_row=manual_row,
                model=args.model,
            )
        except Exception:
            logger.exception("Failed to classify %s — skipping", paper_id)
            error_count += 1
            continue

        if result.classification_source == "manual_review":
            manual_count += 1
        else:
            llm_count += 1

        # Determine paths for registry row.
        text_json_rel = _relative_to_repo(text_path)
        pref_json_rel = _relative_to_repo(preferred_path if preferred_record else text_path)
        proceedings_detected = (trim_row.get("proceedings_detected") or "").strip().lower() == "true"
        trim_status = (trim_row.get("trim_status") or "").strip()

        row = result_to_registry_row(
            result,
            reference_row=reference_row,
            text_json_path=text_json_rel,
            preferred_text_json_path=pref_json_rel,
            preferred_text_source=preferred_text_source,
            proceedings_detected=proceedings_detected,
            trim_status=trim_status,
            categorisation_version=version,
        )
        rows.append(row)

        logger.info(
            "  %s -> %s (%s, %s)",
            paper_id,
            result.source_type.value,
            result.confidence.value,
            result.classification_source,
        )

    # Write output.
    write_registry(rows, args.output_path)
    logger.info(
        "Wrote %d rows to %s (llm=%d, manual=%d, errors=%d)",
        len(rows),
        args.output_path,
        llm_count,
        manual_count,
        error_count,
    )


if __name__ == "__main__":
    main()
