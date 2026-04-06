from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.validation.stage04_model_benchmark import _shared as shared


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score stage-04 benchmark predictions across cached gpt-4.1 and newly run models."
    )
    parser.add_argument(
        "--benchmark-id",
        default=shared.DEFAULT_BENCHMARK_ID,
        help="Benchmark set identifier under qa/validation/source_categorisation/model_benchmark/.",
    )
    return parser.parse_args()


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def normalise_bool_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes"}:
        return "true"
    if text in {"false", "0", "no"}:
        return "false"
    return ""


def cached_gpt41_prediction(row: dict[str, str]) -> dict[str, Any]:
    return {
        "paper_id": (row.get("paper_id") or "").strip(),
        "model_name": shared.CACHED_BASELINE_MODEL,
        "result": {
            "source_type": (row.get("cached_gpt41_source_category") or "").strip(),
            "confidence": (row.get("cached_gpt41_confidence") or "").strip(),
            "manual_review_required": normalise_bool_text(row.get("cached_gpt41_manual_review_required")),
            "contains_individual_level_data": normalise_bool_text(
                row.get("cached_gpt41_contains_individual_level_data")
            ),
            "contains_group_level_data": normalise_bool_text(
                row.get("cached_gpt41_contains_group_level_data")
            ),
            "count_manual_review_required": normalise_bool_text(
                row.get("cached_gpt41_count_manual_review_required")
            ),
            "original_sps_spectrum_data": (row.get("cached_gpt41_original_sps_data") or "").strip(),
            "evidence": None,
        },
    }


def model_predictions_by_name(paths: shared.BenchmarkPaths) -> dict[str, dict[str, dict[str, Any]]]:
    predictions: dict[str, dict[str, dict[str, Any]]] = {}
    for model_name in shared.BENCHMARK_MODELS:
        rows = load_jsonl_rows(paths.model_output_root / model_name / "predictions.jsonl")
        if rows:
            predictions[model_name] = {
                str(row.get("paper_id") or "").strip(): row
                for row in rows
                if str(row.get("paper_id") or "").strip()
            }
    return predictions


def evidence_quality_components(evidence: list[dict[str, Any]] | None, *, confidence: str) -> dict[str, float] | None:
    if not evidence:
        return None
    quote_lengths = [len(str(item.get("quote") or "").strip()) for item in evidence]
    page_count = sum(1 for item in evidence if item.get("page") is not None)
    high_confidence_ok = 1.0
    if confidence == "high":
        high_confidence_ok = 1.0 if len(evidence) >= 2 else 0.0
    short_quote_only = 1.0 if quote_lengths and max(quote_lengths) < 10 else 0.0
    return {
        "evidence_present": 1.0,
        "mean_evidence_items": float(len(evidence)),
        "page_coverage_rate": page_count / len(evidence),
        "high_confidence_min_two_evidence_rate": high_confidence_ok,
        "short_quote_only_rate": short_quote_only,
        "evidence_quality_score": (
            1.0
            + (page_count / len(evidence))
            + high_confidence_ok
            + (1.0 - short_quote_only)
        )
        / 4.0,
    }


def compute_model_metrics(
    benchmark_rows: list[dict[str, str]],
    prediction_rows_by_paper: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    total_rows = len(benchmark_rows)
    ambiguous_rows = [
        row for row in benchmark_rows if (row.get("gold_ambiguity_tier") or "").strip() == "ambiguous"
    ]

    source_correct = 0
    original_correct = 0
    original_available = 0
    individual_correct = 0
    individual_available = 0
    group_correct = 0
    group_available = 0
    abstention_numerator = 0
    overconfidence_numerator = 0
    overconfidence_denominator = 0
    escalation_numerator = 0
    evidence_component_sums: Counter[str] = Counter()
    evidence_available = 0
    comparison_rows: list[dict[str, Any]] = []

    for row in benchmark_rows:
        paper_id = (row.get("paper_id") or "").strip()
        prediction = prediction_rows_by_paper.get(paper_id)
        if prediction is None:
            comparison_rows.append({"paper_id": paper_id, "missing_prediction": True})
            continue
        result = dict(prediction.get("result") or {})
        predicted_category = (result.get("source_type") or "").strip()
        gold_category = (row.get("gold_source_category") or "").strip()
        source_match = predicted_category == gold_category
        if source_match:
            source_correct += 1

        predicted_original = (result.get("original_sps_spectrum_data") or "").strip()
        gold_original = (row.get("gold_original_sps_data") or "").strip()
        original_match = None
        if predicted_original and gold_original:
            original_available += 1
            original_match = predicted_original == gold_original
            if original_match:
                original_correct += 1

        predicted_individual = normalise_bool_text(result.get("contains_individual_level_data"))
        gold_individual = normalise_bool_text(row.get("gold_contains_individual_level_data"))
        individual_match = None
        if predicted_individual and gold_individual:
            individual_available += 1
            individual_match = predicted_individual == gold_individual
            if individual_match:
                individual_correct += 1

        predicted_group = normalise_bool_text(result.get("contains_group_level_data"))
        gold_group = normalise_bool_text(row.get("gold_contains_group_level_data"))
        group_match = None
        if predicted_group and gold_group:
            group_available += 1
            group_match = predicted_group == gold_group
            if group_match:
                group_correct += 1

        confidence = (result.get("confidence") or "").strip()
        manual_review_required = normalise_bool_text(result.get("manual_review_required")) == "true"
        count_manual_review_required = normalise_bool_text(result.get("count_manual_review_required")) == "true"
        escalated = manual_review_required or count_manual_review_required or predicted_category == "unclear_manual_review"
        if escalated:
            escalation_numerator += 1
        if (row.get("gold_ambiguity_tier") or "").strip() == "ambiguous" and escalated:
            abstention_numerator += 1

        composite_wrong = not source_match
        if original_match is False:
            composite_wrong = True
        if individual_match is False:
            composite_wrong = True
        if group_match is False:
            composite_wrong = True
        if confidence == "high" and not escalated:
            overconfidence_denominator += 1
            if composite_wrong:
                overconfidence_numerator += 1

        evidence_components = evidence_quality_components(result.get("evidence"), confidence=confidence)
        if evidence_components is not None:
            evidence_available += 1
            for key, value in evidence_components.items():
                evidence_component_sums[key] += value

        comparison_rows.append(
            {
                "paper_id": paper_id,
                "predicted_category": predicted_category,
                "gold_category": gold_category,
                "source_match": source_match,
                "predicted_original": predicted_original,
                "gold_original": gold_original,
                "original_match": original_match,
                "predicted_individual": predicted_individual,
                "gold_individual": gold_individual,
                "individual_match": individual_match,
                "predicted_group": predicted_group,
                "gold_group": gold_group,
                "group_match": group_match,
                "confidence": confidence,
                "escalated": escalated,
            }
        )

    evidence_summary = None
    if evidence_available:
        evidence_summary = {
            key: value / evidence_available for key, value in evidence_component_sums.items()
        }

    return {
        "total_rows": total_rows,
        "source_category_accuracy": source_correct / total_rows if total_rows else 0.0,
        "original_data_yes_no_accuracy": (
            original_correct / original_available if original_available else None
        ),
        "original_data_available_rows": original_available,
        "individual_level_accuracy": (
            individual_correct / individual_available if individual_available else None
        ),
        "individual_level_available_rows": individual_available,
        "group_level_accuracy": (group_correct / group_available if group_available else None),
        "group_level_available_rows": group_available,
        "appropriate_abstention_rate": (
            abstention_numerator / len(ambiguous_rows) if ambiguous_rows else None
        ),
        "ambiguous_row_count": len(ambiguous_rows),
        "overconfidence_rate": (
            overconfidence_numerator / overconfidence_denominator
            if overconfidence_denominator
            else None
        ),
        "overconfidence_denominator": overconfidence_denominator,
        "escalation_manual_review_rate": escalation_numerator / total_rows if total_rows else 0.0,
        "evidence_quality": evidence_summary,
        "evidence_available_rows": evidence_available,
        "comparison_rows": comparison_rows,
    }


def write_summary_csv(path: Path, summary_rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(summary_rows[0].keys()) if summary_rows else ["model_name"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)


def markdown_summary(report: dict[str, Any]) -> str:
    lines = ["# Stage-04 Model Benchmark", ""]
    for model_name, metrics in report["models"].items():
        lines.append(f"## {model_name}")
        lines.append(f"- Source-category accuracy: {metrics['source_category_accuracy']:.1%}")
        original_accuracy = metrics["original_data_yes_no_accuracy"]
        lines.append(
            "- Original-data yes/no accuracy: "
            + ("not available" if original_accuracy is None else f"{original_accuracy:.1%}")
        )
        lines.append(
            f"- Individual-level accuracy: "
            + (
                "not available"
                if metrics["individual_level_accuracy"] is None
                else f"{metrics['individual_level_accuracy']:.1%}"
            )
        )
        lines.append(
            f"- Group-level accuracy: "
            + (
                "not available"
                if metrics["group_level_accuracy"] is None
                else f"{metrics['group_level_accuracy']:.1%}"
            )
        )
        lines.append(
            f"- Appropriate abstention rate: "
            + (
                "not available"
                if metrics["appropriate_abstention_rate"] is None
                else f"{metrics['appropriate_abstention_rate']:.1%}"
            )
        )
        lines.append(
            f"- Overconfidence rate: "
            + (
                "not available"
                if metrics["overconfidence_rate"] is None
                else f"{metrics['overconfidence_rate']:.1%}"
            )
        )
        lines.append(f"- Escalation/manual-review rate: {metrics['escalation_manual_review_rate']:.1%}")
        evidence_quality = metrics["evidence_quality"]
        if evidence_quality is None:
            lines.append("- Evidence quality: not available from cached flattened outputs")
        else:
            lines.append(f"- Evidence quality score: {evidence_quality['evidence_quality_score']:.3f}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    paths = shared.benchmark_paths(args.benchmark_id)
    benchmark_rows = shared.load_csv_rows(paths.benchmark_set_path)
    if not benchmark_rows:
        raise SystemExit("Benchmark set not found or empty. Run build_benchmark_set.py first.")

    predictions_by_model = model_predictions_by_name(paths)
    predictions_by_model.setdefault(
        shared.CACHED_BASELINE_MODEL,
        {(row.get("paper_id") or "").strip(): cached_gpt41_prediction(row) for row in benchmark_rows},
    )

    report = {
        "benchmark_id": args.benchmark_id,
        "created_at_utc": shared.now_utc_iso(),
        "benchmark_size": len(benchmark_rows),
        "gold_label_status_counts": dict(
            Counter((row.get("gold_label_status") or "").strip() for row in benchmark_rows)
        ),
        "models": {},
    }
    summary_rows: list[dict[str, str]] = []

    for model_name, prediction_rows in predictions_by_model.items():
        metrics = compute_model_metrics(benchmark_rows, prediction_rows)
        report["models"][model_name] = metrics
        summary_rows.append(
            {
                "model_name": model_name,
                "source_category_accuracy": f"{metrics['source_category_accuracy']:.6f}",
                "original_data_yes_no_accuracy": (
                    "" if metrics["original_data_yes_no_accuracy"] is None else f"{metrics['original_data_yes_no_accuracy']:.6f}"
                ),
                "individual_level_accuracy": (
                    "" if metrics["individual_level_accuracy"] is None else f"{metrics['individual_level_accuracy']:.6f}"
                ),
                "group_level_accuracy": (
                    "" if metrics["group_level_accuracy"] is None else f"{metrics['group_level_accuracy']:.6f}"
                ),
                "appropriate_abstention_rate": (
                    "" if metrics["appropriate_abstention_rate"] is None else f"{metrics['appropriate_abstention_rate']:.6f}"
                ),
                "overconfidence_rate": (
                    "" if metrics["overconfidence_rate"] is None else f"{metrics['overconfidence_rate']:.6f}"
                ),
                "escalation_manual_review_rate": f"{metrics['escalation_manual_review_rate']:.6f}",
                "evidence_quality_score": (
                    ""
                    if metrics["evidence_quality"] is None
                    else f"{metrics['evidence_quality']['evidence_quality_score']:.6f}"
                ),
            }
        )

    shared.write_json(paths.report_root / "model_benchmark_report.json", report)
    write_summary_csv(paths.report_root / "model_benchmark_summary.csv", summary_rows)
    (paths.report_root / "model_benchmark_summary.md").write_text(
        markdown_summary(report),
        encoding="utf-8",
    )

    print(f"benchmark_id={args.benchmark_id}")
    print(f"report_path={shared.relative_repo_path(paths.report_root / 'model_benchmark_report.json')}")
    for row in summary_rows:
        print(
            f"{row['model_name']}: "
            f"source_category_accuracy={row['source_category_accuracy']} "
            f"appropriate_abstention_rate={row['appropriate_abstention_rate'] or 'NA'}"
        )


if __name__ == "__main__":
    main()
