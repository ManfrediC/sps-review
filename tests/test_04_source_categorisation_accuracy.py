"""Accuracy benchmark for 04_source_categorisation.py against manual review ground truth.

Loads the 291 manually reviewed papers, runs classify_record() on each,
and compares heuristic output against final_source_category after normalisation.

Run:
    python -m unittest discover -s tests -p "test_04_source_categorisation_accuracy.py" -v
    python tests/test_04_source_categorisation_accuracy.py          # standalone report
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CATEGORISATION_SCRIPT = REPO_ROOT / "src" / "pipelines" / "04_source_categorisation.py"
ROUTING_SCRIPT = REPO_ROOT / "src" / "pipelines" / "_source_routing.py"
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
MANUAL_REVIEW_CSV = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
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


def load_modules():
    cat_mod = _load_module("categorisation_module", CATEGORISATION_SCRIPT)
    route_mod = _load_module("source_routing_module", ROUTING_SCRIPT)
    return cat_mod, route_mod


def safe_console_text(text: str) -> str:
    return str(text or "").encode("ascii", "backslashreplace").decode("ascii")


def load_csv_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            key = (row.get(key_column) or "").strip()
            if key:
                rows[key] = row
    return rows


def load_text_record(path: Path) -> dict[str, Any]:
    record = json.loads(path.read_text(encoding="utf-8"))
    record["_path"] = str(path)
    return record


# Map manual-review fine-grained categories to the 8 valid heuristic categories.
# The manual reviewers sometimes use rich subtypes as the category column.
MANUAL_TO_HEURISTIC_CATEGORY = {
    # Already valid heuristic categories (identity):
    "single_case_report": "single_case_report",
    "conference_abstract": "conference_abstract",
    "case_series_or_multi_case": "case_series_or_multi_case",
    "observational_group_study": "observational_group_study",
    "interventional_study": "interventional_study",
    "lab_heavy_clinical_or_translational": "lab_heavy_clinical_or_translational",
    "non_clinical_basic_science": "non_clinical_basic_science",
    "review_article": "review_article",
    "unclear_manual_review": "unclear_manual_review",
    # Subtypes used as category -> map to parent:
    "case_report": "single_case_report",
    "paraneoplastic_case_report": "single_case_report",
    "genetic_case_report": "single_case_report",
    "pediatric_case_report": "single_case_report",
    "imaging_case_report": "single_case_report",
    "neuro_ophthalmology_case_report": "single_case_report",
    "respiratory_case_report": "single_case_report",
    "complex_treatment_case_report": "single_case_report",
    "psychiatric_misdiagnosis_case_report": "single_case_report",
    "drug_triggered_case_report": "single_case_report",
    "immune_checkpoint_case_report": "single_case_report",
    "teaching_case_report": "single_case_report",
    "autoimmune_comorbidity_case_report": "single_case_report",
    # Conference abstract subtypes:
    "single_case_conference_abstract": "conference_abstract",
    "case_series_conference_abstract": "conference_abstract",
    "group_conference_abstract": "conference_abstract",
    "animal_model_pathogenicity_abstract": "conference_abstract",
    # Case series subtypes:
    "small_case_series": "case_series_or_multi_case",
    "prevalence_case_series": "case_series_or_multi_case",
    # Lab/translational subtypes:
    "autoantibody_clinical_cohort": "lab_heavy_clinical_or_translational",
    "autoantigen_assay_study": "lab_heavy_clinical_or_translational",
    "comparative_gad65_immunology_study": "lab_heavy_clinical_or_translational",
    "t_cell_receptor_immunology_study": "lab_heavy_clinical_or_translational",
    "glyr_antibody_clinical_cohort": "lab_heavy_clinical_or_translational",
    "serologic_biomarker_study": "lab_heavy_clinical_or_translational",
    "neurophysiology_study": "lab_heavy_clinical_or_translational",
    # Review subtypes:
    "editorial_review": "review_article",
    "teaching_review": "review_article",
    # Edge cases:
    "unclear": "unclear_manual_review",
    "low": "unclear_manual_review",  # data entry artefact
}


def normalize_manual_category(raw_category: str, raw_subtype: str) -> str:
    """Normalize a manual-review category to one of the 8 valid heuristic categories."""
    cat = (raw_category or "").strip()
    if not cat:
        return "unclear_manual_review"
    if cat in MANUAL_TO_HEURISTIC_CATEGORY:
        return MANUAL_TO_HEURISTIC_CATEGORY[cat]
    # Fallback heuristics for unknown categories
    if "case_report" in cat:
        return "single_case_report"
    if "conference" in cat or "abstract" in cat:
        return "conference_abstract"
    if "review" in cat:
        return "review_article"
    if "cohort" in cat or "study" in cat:
        return "lab_heavy_clinical_or_translational"
    return "unclear_manual_review"


def run_benchmark(*, verbose: bool = False) -> dict[str, Any]:
    """Run classify_record on all manual-review papers and compare results."""
    cat_mod, route_mod = load_modules()

    reference_rows = load_csv_by_id(REFERENCES_CSV, "Covidence")
    manual_rows = load_csv_by_id(MANUAL_REVIEW_CSV, "paper_id")
    trim_rows = load_csv_by_id(TRIM_REGISTRY_CSV, "paper_id")

    correct = 0
    total = 0
    skipped = 0
    mismatches: list[dict[str, str]] = []
    category_tp: Counter[str] = Counter()
    category_fp: Counter[str] = Counter()
    category_fn: Counter[str] = Counter()
    confusion: dict[str, Counter[str]] = defaultdict(Counter)

    for paper_id, manual_row in sorted(manual_rows.items()):
        text_path = TEXT_DIR / f"{paper_id}.json"
        if not text_path.exists():
            skipped += 1
            continue

        # Build inputs for classify_record
        ref_row = reference_rows.get(paper_id, {})
        trim_row = trim_rows.get(paper_id, {})

        preferred_path = TEXT_TRIMMED_DIR / f"{paper_id}.json"
        if not preferred_path.exists():
            preferred_path = text_path

        text_record = load_text_record(text_path)
        preferred_record = load_text_record(preferred_path)

        result = cat_mod.classify_record(
            reference_row=ref_row,
            text_record=text_record,
            preferred_record=preferred_record,
            preferred_path=preferred_path,
            trim_row=trim_row,
        )

        heuristic_cat = result["source_category"]
        heuristic_sub = result["source_subtype"]

        # Normalise both sides to the 8 valid heuristic categories for comparison.
        manual_cat_raw = (manual_row.get("final_source_category") or "").strip()
        manual_sub_raw = (manual_row.get("final_source_subtype") or "").strip()
        expected_cat = normalize_manual_category(manual_cat_raw, manual_sub_raw)
        expected_sub = manual_sub_raw

        norm_heuristic_cat = heuristic_cat
        norm_heuristic_sub = heuristic_sub

        total += 1
        match = norm_heuristic_cat == expected_cat
        if match:
            correct += 1
            category_tp[expected_cat] += 1
        else:
            category_fp[norm_heuristic_cat] += 1
            category_fn[expected_cat] += 1
            confusion[expected_cat][norm_heuristic_cat] += 1
            mismatches.append({
                "paper_id": paper_id,
                "title": (ref_row.get("Title") or "")[:80],
                "expected": expected_cat,
                "expected_sub": expected_sub,
                "got": norm_heuristic_cat,
                "got_sub": norm_heuristic_sub,
                "confidence": result.get("classification_confidence", ""),
            })

    # Build per-category metrics
    all_categories = sorted(set(category_tp) | set(category_fp) | set(category_fn))
    per_category: dict[str, dict[str, Any]] = {}
    for cat in all_categories:
        tp = category_tp[cat]
        fp = category_fp[cat]
        fn = category_fn[cat]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        per_category[cat] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1,
        }

    accuracy = correct / total if total > 0 else 0.0
    return {
        "total": total,
        "correct": correct,
        "skipped": skipped,
        "accuracy": accuracy,
        "per_category": per_category,
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "mismatches": mismatches,
    }


def print_report(results: dict[str, Any]) -> None:
    total = results["total"]
    correct = results["correct"]
    accuracy = results["accuracy"]
    skipped = results["skipped"]

    print(f"\n{'='*70}")
    print(f"CATEGORISATION ACCURACY BENCHMARK")
    print(f"{'='*70}")
    print(f"Total evaluated: {total}  |  Correct: {correct}  |  Accuracy: {accuracy:.1%}")
    if skipped:
        print(f"Skipped (no text JSON): {skipped}")

    print(f"\n{'-'*70}")
    print(f"PER-CATEGORY METRICS")
    print(f"{'-'*70}")
    print(f"{'Category':<45} {'Prec':>6} {'Rec':>6} {'F1':>6} {'TP':>4} {'FP':>4} {'FN':>4}")
    print(f"{'-'*45} {'-'*6} {'-'*6} {'-'*6} {'-'*4} {'-'*4} {'-'*4}")
    for cat, m in sorted(results["per_category"].items(), key=lambda x: -x[1]["f1"]):
        print(f"{cat:<45} {m['precision']:>5.0%} {m['recall']:>5.0%} {m['f1']:>5.0%} {m['tp']:>4} {m['fp']:>4} {m['fn']:>4}")

    confusion = results["confusion"]
    if confusion:
        print(f"\n{'-'*70}")
        print(f"CONFUSION (expected -> got)")
        print(f"{'-'*70}")
        for expected, got_counts in sorted(confusion.items()):
            for got, count in sorted(got_counts.items(), key=lambda x: -x[1]):
                print(f"  {expected} -> {got}: {count}")

    mismatches = results["mismatches"]
    if mismatches:
        print(f"\n{'-'*70}")
        print(f"MISMATCHES ({len(mismatches)} total)")
        print(f"{'-'*70}")
        for m in mismatches[:30]:
            safe_title = safe_console_text(m["title"])
            print(
                f"  [{m['paper_id']}] expected={m['expected']} got={m['got']} "
                f"conf={m['confidence']}  \"{safe_title}\""
            )
        if len(mismatches) > 30:
            print(f"  ... and {len(mismatches) - 30} more")


class TestCategorisationAccuracy(unittest.TestCase):
    """Accuracy gate: heuristic must agree with manual review on >50% of papers."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.results = run_benchmark()

    def test_benchmark_has_papers(self):
        self.assertGreater(self.results["total"], 200,
                           "Expected at least 200 evaluable papers")

    def test_accuracy_above_threshold(self):
        accuracy = self.results["accuracy"]
        print_report(self.results)
        self.assertGreater(accuracy, 0.50,
                           f"Accuracy {accuracy:.1%} below 50% threshold")


if __name__ == "__main__":
    results = run_benchmark(verbose=True)
    print_report(results)
