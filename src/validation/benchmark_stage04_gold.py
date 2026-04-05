from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validation._stage04_gold import GOLD_MASTER_PATH, reviewed_gold_rows_from_path


REPO_ROOT = Path(__file__).resolve().parents[2]
CATEGORISATION_SCRIPT = REPO_ROOT / "src" / "pipelines" / "04_source_categorisation.py"
CASE_COUNT_SCRIPT = REPO_ROOT / "src" / "pipelines" / "04b_extract_sps_case_counts.py"
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TRIM_REGISTRY_CSV = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark stage-04 heuristics against reviewed stage-04 gold-standard rows."
    )
    parser.add_argument(
        "--gold-path",
        type=Path,
        default=GOLD_MASTER_PATH,
        help="Path to a reviewed gold-standard CSV. Defaults to the cumulative master file.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Optional JSON report path.",
    )
    parser.add_argument(
        "--include-likely-wrong-pdf",
        action="store_true",
        help="Include rows tagged as likely_wrong_pdf_attached in the scored benchmark.",
    )
    parser.add_argument(
        "--include-incorrect-reference",
        action="store_true",
        help="Include rows tagged as incorrect_reference in the scored benchmark.",
    )
    return parser.parse_args()


def load_text_record(path: Path) -> dict[str, Any]:
    record = json.loads(path.read_text(encoding="utf-8"))
    record["_path"] = str(path)
    return record


def load_csv_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    module = _load_module("stage04_gold_cat_loader", CATEGORISATION_SCRIPT)
    return module.load_csv_rows_by_id(path, key_column)


def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    module = _load_module("stage04_gold_reference_loader", CATEGORISATION_SCRIPT)
    return module.load_reference_rows(path)


def safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def summarise_bucket_accuracy(comparisons: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    bucket_totals: Counter[str] = Counter()
    category_correct: Counter[str] = Counter()
    count_correct: Counter[str] = Counter()
    for comparison in comparisons:
        bucket = str(comparison["selection_bucket"])
        bucket_totals[bucket] += 1
        if comparison["category_match"]:
            category_correct[bucket] += 1
        if comparison["count_match"]:
            count_correct[bucket] += 1
    return {
        bucket: {
            "rows": bucket_totals[bucket],
            "category_accuracy": safe_ratio(category_correct[bucket], bucket_totals[bucket]),
            "count_accuracy": safe_ratio(count_correct[bucket], bucket_totals[bucket]),
        }
        for bucket in sorted(bucket_totals)
    }


def run_benchmark(
    *,
    gold_path: Path,
    include_likely_wrong_pdf: bool,
    include_incorrect_reference: bool,
) -> dict[str, Any]:
    cat_mod = _load_module("stage04_gold_cat_module", CATEGORISATION_SCRIPT)
    count_mod = _load_module("stage04_gold_count_module", CASE_COUNT_SCRIPT)
    reference_rows = load_reference_rows(REFERENCES_CSV)
    trim_rows = load_csv_by_id(TRIM_REGISTRY_CSV, "paper_id")
    gold_rows = reviewed_gold_rows_from_path(gold_path)

    evaluated = 0
    category_correct = 0
    count_correct = 0
    excluded_alignment_counts: Counter[str] = Counter()
    alignment_counts: Counter[str] = Counter()
    mismatches: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []

    for row in gold_rows:
        paper_id = (row.get("paper_id") or "").strip()
        if not paper_id:
            continue

        alignment_tag = (row.get("pdf_content_alignment_tag") or "").strip() or "appears_matched"
        alignment_counts[alignment_tag] += 1
        if alignment_tag == "likely_wrong_pdf_attached" and not include_likely_wrong_pdf:
            excluded_alignment_counts[alignment_tag] += 1
            continue
        if alignment_tag == "incorrect_reference" and not include_incorrect_reference:
            excluded_alignment_counts[alignment_tag] += 1
            continue

        text_path = TEXT_DIR / f"{paper_id}.json"
        if not text_path.exists():
            mismatches.append(
                {
                    "paper_id": paper_id,
                    "title": (row.get("title") or "").strip(),
                    "error": f"Missing full-text JSON: {text_path}",
                }
            )
            continue

        preferred_path = REPO_ROOT / (row.get("preferred_text_json_path") or "")
        if not preferred_path.exists():
            preferred_path = TEXT_TRIMMED_DIR / f"{paper_id}.json"
        if not preferred_path.exists():
            preferred_path = text_path

        text_record = load_text_record(text_path)
        preferred_record = load_text_record(preferred_path)
        reference_row = reference_rows.get(paper_id, {})
        trim_row = trim_rows.get(paper_id, {})
        category_result = cat_mod.classify_record(
            reference_row=reference_row,
            text_record=text_record,
            preferred_record=preferred_record,
            preferred_path=preferred_path,
            trim_row=trim_row,
        )
        count_result = count_mod.build_case_count_record(
            reference_row=reference_row,
            text_record=text_record,
            preferred_record=preferred_record,
            preferred_path=preferred_path,
            source_row=category_result,
        )

        expected_category = (row.get("reviewed_source_category") or "").strip()
        expected_count = (row.get("reviewed_extractable_sps_case_count") or "").strip()
        got_category = (category_result.get("source_category") or "").strip()
        got_count = (count_result.get("likely_sps_case_count") or "").strip()
        category_match = got_category == expected_category
        count_match = got_count == expected_count

        evaluated += 1
        if category_match:
            category_correct += 1
        if count_match:
            count_correct += 1

        comparison = {
            "paper_id": paper_id,
            "title": (row.get("title") or "").strip(),
            "selection_bucket": (row.get("selection_bucket") or "").strip(),
            "alignment_tag": alignment_tag,
            "expected_category": expected_category,
            "got_category": got_category,
            "expected_count": expected_count,
            "got_count": got_count,
            "category_match": category_match,
            "count_match": count_match,
            "categorisation_reason": (category_result.get("categorisation_reason") or "").strip(),
            "count_reason": (count_result.get("count_reason") or "").strip(),
        }
        comparisons.append(comparison)
        if not (category_match and count_match):
            mismatches.append(comparison)

    return {
        "gold_path": str(gold_path),
        "reviewed_rows_available": len(gold_rows),
        "evaluated_rows": evaluated,
        "excluded_alignment_counts": dict(excluded_alignment_counts),
        "alignment_counts": dict(alignment_counts),
        "category_accuracy": safe_ratio(category_correct, evaluated),
        "count_accuracy": safe_ratio(count_correct, evaluated),
        "bucket_accuracy": summarise_bucket_accuracy(comparisons),
        "mismatches": mismatches,
    }


def print_report(results: dict[str, Any]) -> None:
    print("\n" + "=" * 70)
    print("STAGE-04 GOLD BENCHMARK")
    print("=" * 70)
    print(f"Gold file: {results['gold_path']}")
    print(f"Reviewed rows available: {results['reviewed_rows_available']}")
    print(f"Rows evaluated: {results['evaluated_rows']}")
    if results["excluded_alignment_counts"]:
        print(f"Excluded alignment rows: {results['excluded_alignment_counts']}")
    print(f"Category accuracy: {results['category_accuracy']:.1%}")
    print(f"Count accuracy: {results['count_accuracy']:.1%}")

    bucket_accuracy = results["bucket_accuracy"]
    if bucket_accuracy:
        print("-" * 70)
        print("Bucket accuracy")
        print("-" * 70)
        for bucket, metrics in bucket_accuracy.items():
            print(
                f"{bucket:<26} rows={metrics['rows']:<3} "
                f"category={metrics['category_accuracy']:.1%} count={metrics['count_accuracy']:.1%}"
            )

    mismatches = results["mismatches"]
    if mismatches:
        print("-" * 70)
        print(f"MISMATCHES ({len(mismatches)} total)")
        print("-" * 70)
        for mismatch in mismatches[:20]:
            if "error" in mismatch:
                print(f"[{mismatch['paper_id']}] {mismatch['error']}")
                continue
            print(
                f"[{mismatch['paper_id']}] cat {mismatch['got_category']} -> {mismatch['expected_category']} | "
                f"count {mismatch['got_count']} -> {mismatch['expected_count']} | "
                f"{mismatch['title'][:60]}"
            )


def main() -> None:
    args = parse_args()
    results = run_benchmark(
        gold_path=args.gold_path,
        include_likely_wrong_pdf=args.include_likely_wrong_pdf,
        include_incorrect_reference=args.include_incorrect_reference,
    )
    print_report(results)
    if args.output_path is not None:
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
