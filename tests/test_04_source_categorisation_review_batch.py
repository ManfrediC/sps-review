from __future__ import annotations

import csv
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CATEGORISATION_SCRIPT = REPO_ROOT / "src" / "pipelines" / "04_source_categorisation.py"
CASE_COUNT_SCRIPT = REPO_ROOT / "src" / "pipelines" / "04b_extract_sps_case_counts.py"
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TRIM_REGISTRY_CSV = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
REVIEW_BATCH_CSV = (
    REPO_ROOT
    / "qa"
    / "validation"
    / "source_categorisation"
    / "source_categorisation_review_sample_n30_seed20260405_compact.csv"
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_csv_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    rows = {}
    for row in load_csv_rows(path):
        key = (row.get(key_column) or "").strip()
        if key:
            rows[key] = row
    return rows


def load_text_record(path: Path) -> dict[str, Any]:
    record = json.loads(path.read_text(encoding="utf-8"))
    record["_path"] = str(path)
    return record


def expected_value(row: dict[str, str], *, predicted_key: str, reviewer_key: str) -> str:
    reviewed = (row.get(reviewer_key) or "").strip()
    if reviewed:
        return reviewed
    return (row.get(predicted_key) or "").strip()


def run_review_batch_benchmark() -> dict[str, Any]:
    cat_mod = _load_module("categorisation_module_review_batch", CATEGORISATION_SCRIPT)
    count_mod = _load_module("case_count_module_review_batch", CASE_COUNT_SCRIPT)
    reference_rows = load_csv_by_id(REFERENCES_CSV, "Covidence")
    trim_rows = load_csv_by_id(TRIM_REGISTRY_CSV, "paper_id")
    review_rows = load_csv_rows(REVIEW_BATCH_CSV)

    category_correct = 0
    subtype_correct = 0
    count_correct = 0
    count_total = 0
    total = 0
    mismatches: list[dict[str, str]] = []

    for review_row in review_rows:
        paper_id = (review_row.get("ID") or "").strip()
        if not paper_id:
            continue
        text_path = TEXT_DIR / f"{paper_id}.json"
        preferred_path = TEXT_TRIMMED_DIR / f"{paper_id}.json"
        if not preferred_path.exists():
            preferred_path = text_path

        text_record = load_text_record(text_path)
        preferred_record = load_text_record(preferred_path)
        category_result = cat_mod.classify_record(
            reference_row=reference_rows.get(paper_id, {}),
            text_record=text_record,
            preferred_record=preferred_record,
            preferred_path=preferred_path,
            trim_row=trim_rows.get(paper_id, {}),
        )
        count_result = count_mod.build_case_count_record(
            reference_row=reference_rows.get(paper_id, {}),
            text_record=text_record,
            preferred_record=preferred_record,
            preferred_path=preferred_path,
            source_row=category_result,
        )

        expected_category = expected_value(
            review_row,
            predicted_key="predicted_source_category",
            reviewer_key="reviewer_final_category",
        )
        expected_subtype = expected_value(
            review_row,
            predicted_key="predicted_source_subtype",
            reviewer_key="reviewer_final_subtype",
        )
        expected_count = (review_row.get("reviewer_correct_sps_patient_count") or "").strip()

        total += 1
        category_match = category_result["source_category"] == expected_category
        subtype_match = category_result["source_subtype"] == expected_subtype
        count_match = True
        if expected_count:
            count_total += 1
            count_match = (count_result.get("likely_sps_case_count") or "").strip() == expected_count

        if category_match:
            category_correct += 1
        if subtype_match:
            subtype_correct += 1
        if expected_count and count_match:
            count_correct += 1

        if not (category_match and subtype_match and count_match):
            mismatches.append(
                {
                    "paper_id": paper_id,
                    "expected_category": expected_category,
                    "got_category": category_result["source_category"],
                    "expected_subtype": expected_subtype,
                    "got_subtype": category_result["source_subtype"],
                    "expected_count": expected_count,
                    "got_count": count_result.get("likely_sps_case_count", ""),
                    "title": (review_row.get("title") or "").strip(),
                }
            )

    return {
        "total": total,
        "category_accuracy": category_correct / total if total else 0.0,
        "subtype_accuracy": subtype_correct / total if total else 0.0,
        "count_accuracy": count_correct / count_total if count_total else 0.0,
        "count_total": count_total,
        "mismatches": mismatches,
    }


def print_report(results: dict[str, Any]) -> None:
    print("\n" + "=" * 70)
    print("REVIEW-BATCH ACCURACY BENCHMARK")
    print("=" * 70)
    print(f"Rows evaluated: {results['total']}")
    print(f"Category accuracy: {results['category_accuracy']:.1%}")
    print(f"Subtype accuracy: {results['subtype_accuracy']:.1%}")
    print(f"Count accuracy on explicitly reviewed rows ({results['count_total']}): {results['count_accuracy']:.1%}")

    mismatches = results["mismatches"]
    if mismatches:
        print("-" * 70)
        print(f"MISMATCHES ({len(mismatches)} total)")
        print("-" * 70)
        for mismatch in mismatches[:20]:
            print(
                f"[{mismatch['paper_id']}] cat {mismatch['got_category']} -> {mismatch['expected_category']} | "
                f"sub {mismatch['got_subtype']} -> {mismatch['expected_subtype']} | "
                f"count {mismatch['got_count']} -> {mismatch['expected_count']} | "
                f"{mismatch['title'][:70]}"
            )


class TestCategorisationReviewBatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.results = run_review_batch_benchmark()

    def test_review_batch_has_expected_rows(self) -> None:
        self.assertEqual(self.results["total"], 30)

    def test_review_batch_category_accuracy_above_floor(self) -> None:
        print_report(self.results)
        self.assertGreater(self.results["category_accuracy"], 0.50)

    def test_review_batch_has_explicit_count_reviews(self) -> None:
        self.assertGreaterEqual(self.results["count_total"], 10)


if __name__ == "__main__":
    report = run_review_batch_benchmark()
    print_report(report)
