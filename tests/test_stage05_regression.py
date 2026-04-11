from __future__ import annotations

import csv
import json
from pathlib import Path

from src.autoresearch.stage_05 import benchmark
from src.autoresearch.stage_05 import gold as stage05_gold


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_trimmed_json(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"paper_id": path.stem, "pages": [{"page_index": 0, "text": "\n".join(lines)}]}),
        encoding="utf-8",
    )


def build_bundle(report_dir: Path, paper_id: str, qc_status: str = "confirmed_full", manual_follow_up: str = "false"):
    write_csv(
        report_dir / "text_trim_registry.csv",
        [{"paper_id": paper_id, "trim_status": "trimmed_auto", "trimmed_text_json_path": ""}],
    )
    write_csv(
        report_dir / "proceedings_text_qc_registry.csv",
        [
            {
                "paper_id": paper_id,
                "qc_status": qc_status,
                "manual_follow_up_required": manual_follow_up,
            }
        ],
    )
    return benchmark.ensure_bundle(report_dir)


def make_case(baseline_path: Path, **case_overrides):
    payload = {
        "paper_id": baseline_path.stem,
        "expected_verdict": "correct",
        "expected_manual_review": False,
    }
    payload.update(case_overrides)
    return benchmark.RegressionCase(
        paper_id=baseline_path.stem,
        regression_set_id="batch_001_feedback",
        batch_id="batch_001",
        workflow_stage="stage05_trimming",
        case_payload=payload,
        baseline_bundle_name=baseline_path.parents[1].name,
        baseline_trimmed_path=baseline_path,
    )


def test_evaluate_regression_case_uses_historical_start_and_end_when_feedback_missing(tmp_path: Path) -> None:
    paper_id = "1245"
    baseline_dir = tmp_path / "batch_003"
    current_dir = tmp_path / "tranche_001"
    baseline_path = baseline_dir / "text_trimmed" / f"{paper_id}.json"
    current_path = current_dir / "text_trimmed" / f"{paper_id}.json"

    lines = [
        "Poster 237",
        "Bilateral Hip Fracture During Hospitalization",
        "Conclusions: Refractory spasms may contribute to significant forces exerted on bony elements leading to fractures.",
    ]
    write_trimmed_json(baseline_path, lines)
    write_trimmed_json(current_path, lines)
    build_bundle(baseline_dir, paper_id)
    current_bundle = build_bundle(current_dir, paper_id)

    result = benchmark.evaluate_regression_case(make_case(baseline_path), current_bundle)

    assert result["passed"] is True
    assert result["start_expectation_source"] == "historical_json"
    assert result["end_expectation_source"] == "historical_json"
    assert any(check["name"] == "matches_historical_text" and check["passed"] for check in result["checks"])


def test_evaluate_regression_case_labels_gold_json_when_gold_baseline_is_used(tmp_path: Path) -> None:
    paper_id = "1246"
    baseline_path = tmp_path / "gold_standard" / "papers" / f"{paper_id}.json"
    current_dir = tmp_path / "tranche_001"
    current_path = current_dir / "text_trimmed" / f"{paper_id}.json"

    lines = [
        "Poster 238",
        "Catatonia associated with SPS",
        "Conclusions: Gold baseline ending.",
    ]
    write_trimmed_json(baseline_path, lines)
    write_trimmed_json(current_path, lines)
    current_bundle = build_bundle(current_dir, paper_id)

    result = benchmark.evaluate_regression_case(
        benchmark.RegressionCase(
            paper_id=paper_id,
            regression_set_id="batch_003_feedback",
            batch_id="batch_003",
            workflow_stage="stage05_trimming",
            case_payload={
                "paper_id": paper_id,
                "expected_verdict": "correct",
                "expected_manual_review": False,
            },
            baseline_bundle_name="gold_standard",
            baseline_trimmed_path=baseline_path,
            baseline_source_kind="gold_standard",
        ),
        current_bundle,
    )

    assert result["passed"] is True
    assert result["baseline_source_kind"] == "gold_standard"
    assert result["start_expectation_source"] == "gold_json"
    assert result["end_expectation_source"] == "gold_json"


def test_evaluate_regression_case_flags_true_regression_when_end_drifts_past_historical_json(tmp_path: Path) -> None:
    paper_id = "1452"
    baseline_dir = tmp_path / "batch_007"
    current_dir = tmp_path / "tranche_001"
    baseline_path = baseline_dir / "text_trimmed" / f"{paper_id}.json"
    current_path = current_dir / "text_trimmed" / f"{paper_id}.json"

    baseline_lines = [
        "Poster 321:",
        "A Stiff Diagnosis",
        "Conclusions: Proper diagnosis and treatment can lead to significant functional improvements.",
    ]
    current_lines = baseline_lines + ["Poster 322:", "Another case begins here"]
    write_trimmed_json(baseline_path, baseline_lines)
    write_trimmed_json(current_path, current_lines)
    build_bundle(baseline_dir, paper_id)
    current_bundle = build_bundle(current_dir, paper_id)

    result = benchmark.evaluate_regression_case(make_case(baseline_path), current_bundle)

    assert result["passed"] is False
    assert result["issue_classification"] == "true_regression"
    assert result["failure_location"] == "abstract_end"
    assert "end_anchor_matches" in result["failure_reason"]


def test_evaluate_regression_case_marks_unresolved_historical_problem_when_baseline_disagrees_with_feedback(tmp_path: Path) -> None:
    paper_id = "1830"
    baseline_dir = tmp_path / "batch_009"
    current_dir = tmp_path / "tranche_001"
    baseline_path = baseline_dir / "text_trimmed" / f"{paper_id}.json"
    current_path = current_dir / "text_trimmed" / f"{paper_id}.json"

    lines = [
        "Poster 263:",
        "Case Report",
        "Conclusions: This historical output still stops too early.",
    ]
    write_trimmed_json(baseline_path, lines)
    write_trimmed_json(current_path, lines)
    build_bundle(baseline_dir, paper_id)
    current_bundle = build_bundle(current_dir, paper_id)

    result = benchmark.evaluate_regression_case(
        make_case(
            baseline_path,
            expected_end_contains="Conclusions: A multidisciplinary approach is critical for this patient.",
        ),
        current_bundle,
    )

    assert result["passed"] is False
    assert result["issue_classification"] == "unresolved_historical_problem"
    assert result["failure_location"] == "abstract_end"
    baseline_end_check = next(check for check in result["baseline_checks"] if check["name"] == "end_anchor_matches")
    assert baseline_end_check["passed"] is False


def test_end_anchor_matches_accepts_leading_ellipsis_and_ocr_merged_tail() -> None:
    trimmed_text = "\n".join(
        [
            "Autologous Hematopoietic Stem Cell Transplantation",
            "timework.ThesepreliminaryfindingssuggestthatAHSCTis",
            "well-toleratedandmaybehighlyeffectivetherapyforselect",
            "pts with treatment-refractory, severe SPS.",
        ]
    )

    matched, variant = benchmark.end_anchor_matches(
        trimmed_text,
        "... These preliminary findings suggest that AHSCT is well-tolerated and may be highly effective therapy for select pts with treatment-refractory, severe SPS.",
    )

    assert matched is True
    assert "These preliminary findings" in variant


def test_overlap_score_is_diagnostic_for_near_miss() -> None:
    score = benchmark.overlap_score(
        "Poster 1 Conclusion: Full accepted abstract ending.",
        "Poster 1 Conclusion: Full accepted abstract",
    )

    assert 0.7 < score < 1.0


def test_compare_gold_result_labels_missing_output(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold_standard" / "papers" / "2001.json"
    write_trimmed_json(gold_path, ["Poster 1", "Body", "Conclusion: Accepted ending."])

    result = benchmark.compare_gold_result(
        paper_id="2001",
        gold_path=gold_path,
        candidate_path=None,
        qc_row={},
    )
    assert result["label"] == "missing_output"


def test_classify_gold_result_labels_truncated() -> None:
    label = benchmark.classify_gold_result(
        gold_text="Poster 1 Abstract body Conclusion: Accepted ending.",
        candidate_text="Poster 1 Abstract body",
        qc_row={"qc_status": "partial_truncated"},
        candidate_present=True,
    )

    assert label == "truncated"


def test_classify_gold_result_labels_spillover() -> None:
    label = benchmark.classify_gold_result(
        gold_text="Poster 1 Abstract body Conclusion: Accepted ending.",
        candidate_text="Poster 1 Abstract body Conclusion: Accepted ending. Poster 2 Another abstract.",
        qc_row={"qc_status": "spillover_detected"},
        candidate_present=True,
    )

    assert label == "spillover"


def test_classify_gold_result_labels_wrong_abstract() -> None:
    label = benchmark.classify_gold_result(
        gold_text="Poster 1 Abstract body Conclusion: Accepted ending.",
        candidate_text="Poster 99 Completely different abstract.",
        qc_row={"qc_status": "confirmed_full"},
        candidate_present=True,
    )

    assert label == "wrong_abstract"


def test_run_gold_benchmark_writes_exact_match_summary_without_running_scripts(tmp_path: Path, monkeypatch) -> None:
    gold_papers_dir = tmp_path / "gold_standard" / "papers"
    gold_path = gold_papers_dir / "3001.json"
    write_trimmed_json(gold_path, ["Poster 1", "Body", "Conclusion: Accepted ending."])
    manifest_path = tmp_path / "gold_standard" / "manifest.json"
    stage05_gold.sync_manifest(gold_papers_dir=gold_papers_dir, manifest_path=manifest_path)

    output_dir = tmp_path / "benchmark_output"
    write_trimmed_json(output_dir / "text_trimmed" / "3001.json", ["Poster 1", "Body", "Conclusion: Accepted ending."])
    write_csv(
        output_dir / "text_trim_registry.csv",
        [{"paper_id": "3001", "trim_status": "trimmed_auto", "trimmed_text_json_path": ""}],
    )
    write_csv(
        output_dir / "proceedings_text_qc_registry.csv",
        [{"paper_id": "3001", "qc_status": "confirmed_full", "manual_follow_up_required": "false"}],
    )

    monkeypatch.setattr(benchmark, "run_command", lambda command: None)

    summary = benchmark.run_gold_benchmark(
        output_dir=output_dir,
        manifest_path=manifest_path,
    )

    assert summary["case_count"] == 1
    assert summary["exact_match_rate"] == 1.0
    assert summary["label_counts"]["exact_match"] == 1
    assert (output_dir / "summary.json").exists()
