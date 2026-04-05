from __future__ import annotations

import csv
import importlib.util
import json
import sys
import unittest
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CATEGORISATION_SCRIPT = REPO_ROOT / "src" / "pipelines" / "04_source_categorisation.py"
CASE_COUNT_SCRIPT = REPO_ROOT / "src" / "pipelines" / "06_extract_sps_case_counts.py"
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TRIM_REGISTRY_CSV = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
CASE_REPORT_FORM_CSV = REPO_ROOT / "examples" / "datasheet_examples_MC_Case_Report_Form.csv"


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


def load_text_record(path: Path) -> dict[str, object]:
    record = json.loads(path.read_text(encoding="utf-8"))
    record["_path"] = str(path)
    return record


def load_gold_case_counts() -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in load_csv_rows(CASE_REPORT_FORM_CSV):
        reference_id = (row.get("Reference") or "").strip()
        if reference_id:
            counts[reference_id] += 1
    return counts


def run_case_count_benchmark() -> dict[str, object]:
    cat_mod = _load_module("categorisation_module_case_counts", CATEGORISATION_SCRIPT)
    count_mod = _load_module("case_count_module_case_counts", CASE_COUNT_SCRIPT)
    reference_rows = load_csv_by_id(REFERENCES_CSV, "Covidence")
    trim_rows = load_csv_by_id(TRIM_REGISTRY_CSV, "paper_id")
    gold_counts = load_gold_case_counts()

    total = 0
    exact = 0
    mismatches: list[dict[str, object]] = []

    for paper_id, expected_count in sorted(gold_counts.items()):
        text_path = TEXT_DIR / f"{paper_id}.json"
        if not text_path.exists() or paper_id not in reference_rows:
            continue
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

        total += 1
        got_count = int((count_result.get("likely_sps_case_count") or "0").strip() or 0)
        if got_count == expected_count:
            exact += 1
        else:
            mismatches.append(
                {
                    "paper_id": paper_id,
                    "expected_count": expected_count,
                    "got_count": got_count,
                    "category": category_result["source_category"],
                    "title": (reference_rows[paper_id].get("Title") or "").strip(),
                }
            )

    return {
        "total": total,
        "exact_accuracy": exact / total if total else 0.0,
        "mismatches": mismatches,
    }


def print_report(results: dict[str, object]) -> None:
    print("\n" + "=" * 70)
    print("EXTRACTABLE CASE-COUNT BENCHMARK")
    print("=" * 70)
    print(f"Rows evaluated: {results['total']}")
    print(f"Exact count accuracy: {results['exact_accuracy']:.1%}")

    mismatches = results["mismatches"]
    if mismatches:
        print("-" * 70)
        print(f"MISMATCHES ({len(mismatches)} total)")
        print("-" * 70)
        for mismatch in mismatches[:20]:
            print(
                f"[{mismatch['paper_id']}] {mismatch['got_count']} -> {mismatch['expected_count']} | "
                f"{mismatch['category']} | {str(mismatch['title'])[:70]}"
            )


class TestExtractableCaseCounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.results = run_case_count_benchmark()

    def test_case_count_benchmark_has_expected_rows(self) -> None:
        self.assertGreaterEqual(self.results["total"], 160)

    def test_case_count_accuracy_above_floor(self) -> None:
        print_report(self.results)
        self.assertGreater(self.results["exact_accuracy"], 0.90)

    def test_lab_heavy_stage_rows_are_zeroed_for_extractable_count(self) -> None:
        count_mod = _load_module("case_count_module_lab_heavy_zero", CASE_COUNT_SCRIPT)
        result = count_mod.build_case_count_record(
            reference_row={
                "Covidence": "89",
                "Title": (
                    "Glutamic acid decarboxylase autoantibodies in stiff-man syndrome and insulin-dependent "
                    "diabetes mellitus exhibit similarities and differences in epitope recognition."
                ),
                "Authors": "Example, E",
                "Abstract": (
                    "Our results indicate that individuals with SMS have GAD Abs in 100- to 500-fold higher "
                    "titer than individuals with IDDM."
                ),
            },
            text_record={"paper_id": "89", "_path": "data/extraction_json/text/89.json"},
            preferred_record={"pages": [{"text": "These two regions of the GAD 65 protein are similar ..."}]},
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "89.json",
            source_row={
                "source_category": "lab_heavy_clinical_or_translational",
                "source_subtype": "group_or_frequency_focused_lab_clinical_study",
            },
        )
        self.assertEqual(result["likely_sps_case_count"], "0")
        self.assertEqual(result["count_basis"], "lab_context_no_extractable_count")


if __name__ == "__main__":
    report = run_case_count_benchmark()
    print_report(report)
