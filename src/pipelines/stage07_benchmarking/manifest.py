"""Run-manifest and artefact writers for Stage 07 benchmarking.

All benchmark outputs are non-canonical validation artefacts. Keeping path
construction and writers in this module makes it harder for experiments to
spread into `data/`, `results/`, or new top-level directories.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .matrix import MODEL_MATRIX_SCHEMA_VERSION, load_model_matrix
from .promotion import (
    DEFAULT_PROMOTION_GATES_PATH,
    evaluate_gate_results,
    load_promotion_gates,
    write_gate_results_csv,
)
from .telemetry import (
    DEFAULT_PRICING_TABLE,
    TELEMETRY_FIELDNAMES,
    write_telemetry_csv,
    write_telemetry_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EVALUATION_ROOT = REPO_ROOT / "qa" / "validation" / "stage07_xml" / "evaluation"
RUN_CONFIG_SCHEMA_VERSION = "stage07_benchmark_run_config_v1"


@dataclass(frozen=True)
class BenchmarkPaths:
    """All files written by a single benchmark run."""

    run_dir: Path
    config_path: Path
    paper_scores_path: Path
    target_scores_csv_path: Path
    summary_csv_path: Path
    summary_json_path: Path
    summary_md_path: Path
    pareto_summary_csv_path: Path
    contamination_audit_csv_path: Path
    promotion_gates_path: Path
    gate_results_csv_path: Path
    telemetry_csv_path: Path
    telemetry_jsonl_path: Path
    pricing_table_path: Path


def now_run_id(prefix: str = "stage07_benchmark") -> str:
    """Return a sortable UTC run identifier."""

    return datetime.now(timezone.utc).strftime(f"%Y%m%dT%H%M%SZ_{prefix}")


def benchmark_paths(evaluation_root: Path, run_id: str) -> BenchmarkPaths:
    """Resolve the contained QA output layout for one run."""

    run_dir = evaluation_root / run_id
    return BenchmarkPaths(
        run_dir=run_dir,
        config_path=run_dir / "run_config.json",
        paper_scores_path=run_dir / "paper_scores.jsonl",
        target_scores_csv_path=run_dir / "target_scores.csv",
        summary_csv_path=run_dir / "paper_scores.csv",
        summary_json_path=run_dir / "summary.json",
        summary_md_path=run_dir / "summary.md",
        pareto_summary_csv_path=run_dir / "pareto_summary.csv",
        contamination_audit_csv_path=run_dir / "contamination_audit.csv",
        promotion_gates_path=run_dir / "promotion_gates.json",
        gate_results_csv_path=run_dir / "gate_results.csv",
        telemetry_csv_path=run_dir / "api_telemetry.csv",
        telemetry_jsonl_path=run_dir / "api_telemetry.jsonl",
        pricing_table_path=run_dir / "pricing_table.json",
    )


def ensure_benchmark_paths(paths: BenchmarkPaths) -> None:
    """Create the run directory without touching canonical output roots."""

    paths.run_dir.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    """Write stable UTF-8 JSON with a trailing newline."""

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write per-paper rows as deterministic JSON Lines."""

    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_paper_scores_csv(path: Path, paper_scores: list[dict[str, Any]]) -> None:
    """Write the compact table used for quick spreadsheet inspection."""

    fieldnames = [
        "paper_id",
        "precision",
        "recall",
        "f1",
        "predicted_chars",
        "gold_chars",
        "overlap_chars",
        "unit_precision",
        "unit_recall",
        "unit_f1",
        "missing_targets",
        "extra_targets",
        "contamination_flags",
        "error_taxonomy",
        "ready_for_langextract",
        "manual_review_reasons",
        "target_inventory_exact",
        "role_attribution_errors",
        "xml_roundtrip_status",
        "json_validation_status",
        "false_ready",
        "false_not_ready",
        "matrix_config_name",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for score in paper_scores:
            micro = score.get("micro") or {}
            units = score.get("unit_metrics") or {}
            writer.writerow(
                {
                    "paper_id": score.get("paper_id", ""),
                    "precision": f"{float(micro.get('precision') or 0):.6f}",
                    "recall": f"{float(micro.get('recall') or 0):.6f}",
                    "f1": f"{float(micro.get('f1') or 0):.6f}",
                    "predicted_chars": micro.get("predicted_chars", 0),
                    "gold_chars": micro.get("gold_chars", 0),
                    "overlap_chars": micro.get("overlap_chars", 0),
                    "unit_precision": "" if not units.get("available") else f"{float(units.get('precision') or 0):.6f}",
                    "unit_recall": "" if not units.get("available") else f"{float(units.get('recall') or 0):.6f}",
                    "unit_f1": "" if not units.get("available") else f"{float(units.get('f1') or 0):.6f}",
                    "missing_targets": "|".join(score.get("missing_targets") or []),
                    "extra_targets": "|".join(score.get("extra_targets") or []),
                    "contamination_flags": "|".join(score.get("contamination_flags") or []),
                    "error_taxonomy": "|".join(score.get("error_taxonomy") or []),
                    "ready_for_langextract": score.get("ready_for_langextract", ""),
                    "manual_review_reasons": score.get("manual_review_reasons", ""),
                    "target_inventory_exact": str(score.get("target_inventory_exact", "")).lower(),
                    "role_attribution_errors": "|".join(score.get("role_attribution_errors") or []),
                    "xml_roundtrip_status": score.get("xml_roundtrip_status", ""),
                    "json_validation_status": score.get("json_validation_status", ""),
                    "false_ready": str((score.get("readiness_calibration") or {}).get("false_ready", "")).lower(),
                    "false_not_ready": str((score.get("readiness_calibration") or {}).get("false_not_ready", "")).lower(),
                    "matrix_config_name": score.get("matrix_config_name", ""),
                }
            )


def write_target_scores_csv(path: Path, paper_scores: list[dict[str, Any]]) -> None:
    fieldnames = [
        "paper_id",
        "target_id",
        "precision",
        "recall",
        "f1",
        "predicted_chars",
        "gold_chars",
        "overlap_chars",
        "matrix_config_name",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for score in paper_scores:
            for target_score in score.get("target_scores") or []:
                writer.writerow(
                    {
                        "paper_id": score.get("paper_id", ""),
                        "target_id": target_score.get("target_id", ""),
                        "precision": f"{float(target_score.get('precision') or 0):.6f}",
                        "recall": f"{float(target_score.get('recall') or 0):.6f}",
                        "f1": f"{float(target_score.get('f1') or 0):.6f}",
                        "predicted_chars": target_score.get("predicted_chars", 0),
                        "gold_chars": target_score.get("gold_chars", 0),
                        "overlap_chars": target_score.get("overlap_chars", 0),
                        "matrix_config_name": score.get("matrix_config_name", ""),
                    }
                )


def write_pareto_summary_csv(path: Path, paper_scores: list[dict[str, Any]], telemetry_rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "matrix_config_name",
        "n_papers",
        "mean_precision",
        "mean_recall",
        "mean_f1",
        "n_contaminated_papers",
        "n_false_ready",
        "manual_review_papers",
        "estimated_cost_usd",
        "latency_ms",
    ]
    telemetry_by_config: dict[str, dict[str, float]] = {}
    for row in telemetry_rows:
        name = row.get("matrix_config_name", "")
        telemetry_by_config.setdefault(name, {"cost": 0.0, "latency": 0.0})
        telemetry_by_config[name]["cost"] += float(row.get("estimated_cost_usd") or 0.0)
        telemetry_by_config[name]["latency"] += float(row.get("latency_ms") or 0.0)
    scores_by_config: dict[str, list[dict[str, Any]]] = {}
    for score in paper_scores:
        scores_by_config.setdefault(str(score.get("matrix_config_name") or ""), []).append(score)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for name, scores in sorted(scores_by_config.items()):
            micros = [score.get("micro") or {} for score in scores]
            telemetry = telemetry_by_config.get(name, {})
            writer.writerow(
                {
                    "matrix_config_name": name,
                    "n_papers": len(scores),
                    "mean_precision": f"{sum(float(item.get('precision') or 0) for item in micros) / max(1, len(micros)):.6f}",
                    "mean_recall": f"{sum(float(item.get('recall') or 0) for item in micros) / max(1, len(micros)):.6f}",
                    "mean_f1": f"{sum(float(item.get('f1') or 0) for item in micros) / max(1, len(micros)):.6f}",
                    "n_contaminated_papers": sum(1 for score in scores if score.get("contamination_flags")),
                    "n_false_ready": sum(1 for score in scores if (score.get("readiness_calibration") or {}).get("false_ready")),
                    "manual_review_papers": sum(1 for score in scores if str(score.get("manual_review_reasons") or "")),
                    "estimated_cost_usd": f"{float(telemetry.get('cost') or 0):.8f}",
                    "latency_ms": f"{float(telemetry.get('latency') or 0):.0f}",
                }
            )


def write_contamination_audit_csv(path: Path, paper_scores: list[dict[str, Any]]) -> None:
    """Write exact contamination excerpts for reviewer triage."""

    fieldnames = [
        "matrix_config_name",
        "paper_id",
        "flag",
        "flag_type",
        "target_id",
        "other_target_id",
        "logical_segment_id",
        "physical_segment_ids",
        "role",
        "targets",
        "source_start",
        "source_end",
        "text_excerpt",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for score in paper_scores:
            for detail in score.get("contamination_details") or []:
                writer.writerow(
                    {
                        "matrix_config_name": score.get("matrix_config_name", ""),
                        "paper_id": score.get("paper_id", ""),
                        "flag": detail.get("flag", ""),
                        "flag_type": detail.get("flag_type", ""),
                        "target_id": detail.get("target_id", ""),
                        "other_target_id": detail.get("other_target_id", ""),
                        "logical_segment_id": detail.get("logical_segment_id", ""),
                        "physical_segment_ids": "|".join(detail.get("physical_segment_ids") or []),
                        "role": detail.get("role", ""),
                        "targets": "|".join(detail.get("targets") or []),
                        "source_start": detail.get("source_start", ""),
                        "source_end": detail.get("source_end", ""),
                        "text_excerpt": detail.get("text_excerpt", ""),
                    }
                )


def summary_markdown(summary: dict[str, Any]) -> str:
    """Render a small human-readable benchmark summary."""

    return (
        "# Stage 07 Benchmark Summary\n\n"
        f"- Papers: {summary.get('n_papers', 0)}\n"
        f"- Micro precision: {float(summary.get('micro_precision') or 0):.4f}\n"
        f"- Micro recall: {float(summary.get('micro_recall') or 0):.4f}\n"
        f"- Micro F1: {float(summary.get('micro_f1') or 0):.4f}\n"
        f"- Contaminated papers: {summary.get('n_contaminated_papers', 0)}\n"
        f"- Papers with missing targets: {summary.get('n_missing_target_papers', 0)}\n"
        f"- False-ready papers: {summary.get('n_false_ready_papers', 0)}\n"
        f"- Estimated API cost: ${float(summary.get('estimated_cost_usd') or 0):.4f}\n"
    )


def write_benchmark_artifacts(
    *,
    paths: BenchmarkPaths,
    run_config: dict[str, Any],
    paper_scores: list[dict[str, Any]],
    summary: dict[str, Any],
    telemetry_rows: list[dict[str, str]] | None = None,
    pricing_table: dict[str, Any] | None = None,
    promotion_gates: dict[str, Any] | None = None,
) -> None:
    """Write all benchmark artefacts into the run directory."""

    ensure_benchmark_paths(paths)
    telemetry_payload = telemetry_rows or []
    promotion_payload = promotion_gates or load_promotion_gates(DEFAULT_PROMOTION_GATES_PATH)
    gate_results = evaluate_gate_results(paper_scores, promotion_payload)
    write_json(paths.config_path, run_config)
    write_jsonl(paths.paper_scores_path, paper_scores)
    write_paper_scores_csv(paths.summary_csv_path, paper_scores)
    write_target_scores_csv(paths.target_scores_csv_path, paper_scores)
    write_telemetry_csv(paths.telemetry_csv_path, telemetry_payload)
    write_telemetry_jsonl(paths.telemetry_jsonl_path, telemetry_payload)
    write_pareto_summary_csv(paths.pareto_summary_csv_path, paper_scores, telemetry_payload)
    write_contamination_audit_csv(paths.contamination_audit_csv_path, paper_scores)
    write_json(paths.promotion_gates_path, promotion_payload)
    write_gate_results_csv(paths.gate_results_csv_path, gate_results)
    write_json(paths.pricing_table_path, pricing_table or DEFAULT_PRICING_TABLE)
    write_json(paths.summary_json_path, summary)
    paths.summary_md_path.write_text(summary_markdown(summary), encoding="utf-8")


__all__ = [
    "BenchmarkPaths",
    "DEFAULT_EVALUATION_ROOT",
    "MODEL_MATRIX_SCHEMA_VERSION",
    "RUN_CONFIG_SCHEMA_VERSION",
    "TELEMETRY_FIELDNAMES",
    "benchmark_paths",
    "ensure_benchmark_paths",
    "load_model_matrix",
    "load_promotion_gates",
    "now_run_id",
    "write_benchmark_artifacts",
]
