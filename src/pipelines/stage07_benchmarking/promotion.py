"""Promotion-gate evaluation for Stage 07 benchmark runs.

The benchmark metrics are intentionally granular, but promotion needs a compact
operator-facing decision. This module turns per-paper scores into one row per
matrix configuration, using a small versioned JSON policy that can be copied
into each evaluation run for provenance.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .metrics import f1_score, ratio, truthy


DEFAULT_PROMOTION_GATES_PATH = Path(__file__).with_name("promotion_gates.json")
PROMOTION_GATES_SCHEMA_VERSION = "stage07_promotion_gates_v1"


def load_promotion_gates(path: Path | None = None) -> dict[str, Any]:
    """Load and lightly validate a promotion-gate policy.

    The JSON is deliberately plain so that threshold changes are reviewable in
    normal diffs. Validation stays narrow: the benchmark should reject a wrong
    schema version, but it should not require a large policy framework.
    """

    gates_path = path or DEFAULT_PROMOTION_GATES_PATH
    payload = json.loads(gates_path.read_text(encoding="utf-8"))
    schema_version = str(payload.get("schema_version") or "")
    if schema_version != PROMOTION_GATES_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported promotion gate schema {schema_version!r}; expected {PROMOTION_GATES_SCHEMA_VERSION!r}."
        )
    if not isinstance(payload.get("thresholds"), dict):
        raise ValueError("Promotion gates must contain a thresholds object.")
    if not isinstance(payload.get("warning_thresholds", {}), dict):
        raise ValueError("Promotion gate warning_thresholds must be an object when present.")
    return payload


def _float_threshold(gates: dict[str, Any], key: str, default: float) -> float:
    return float((gates.get("thresholds") or {}).get(key, default))


def _int_threshold(gates: dict[str, Any], key: str, default: int) -> int:
    return int((gates.get("thresholds") or {}).get(key, default))


def _warning_float(gates: dict[str, Any], key: str, default: float) -> float:
    return float((gates.get("warning_thresholds") or {}).get(key, default))


def _warning_int(gates: dict[str, Any], key: str, default: int) -> int:
    return int((gates.get("warning_thresholds") or {}).get(key, default))


def _status_is_failure(status: str) -> bool:
    text = str(status or "").strip().casefold()
    return bool(text and text not in {"passed", "pass", "ok", "not_run"})


def _micro_for_scores(scores: list[dict[str, Any]]) -> dict[str, Any]:
    total_predicted = 0
    total_gold = 0
    total_overlap = 0
    for score in scores:
        micro = score.get("micro") or {}
        total_predicted += int(micro.get("predicted_chars") or 0)
        total_gold += int(micro.get("gold_chars") or 0)
        total_overlap += int(micro.get("overlap_chars") or 0)
    precision = ratio(total_overlap, total_predicted, empty_value=1.0 if total_gold == 0 else 0.0)
    recall = ratio(total_overlap, total_gold, empty_value=1.0 if total_predicted == 0 else 0.0)
    return {
        "predicted_chars": total_predicted,
        "gold_chars": total_gold,
        "overlap_chars": total_overlap,
        "precision": precision,
        "recall": recall,
        "f1": f1_score(precision, recall),
    }


def _paper_ids_with(scores: list[dict[str, Any]], predicate: Any) -> list[str]:
    return sorted(str(score.get("paper_id") or "") for score in scores if predicate(score))


def _gate_message(name: str, observed: int | float, comparator: str, threshold: int | float) -> str:
    return f"{name}:{observed}{comparator}{threshold}"


def evaluate_config_gates(
    *,
    matrix_config_name: str,
    scores: list[dict[str, Any]],
    promotion_gates: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate one matrix configuration against the promotion policy."""

    micro = _micro_for_scores(scores)
    contaminated = _paper_ids_with(scores, lambda score: bool(score.get("contamination_flags")))
    false_ready = _paper_ids_with(scores, lambda score: bool((score.get("readiness_calibration") or {}).get("false_ready")))
    false_not_ready = _paper_ids_with(
        scores,
        lambda score: bool((score.get("readiness_calibration") or {}).get("false_not_ready")),
    )
    target_inventory_errors = _paper_ids_with(scores, lambda score: not bool(score.get("target_inventory_exact")))
    ready_target_inventory_errors = _paper_ids_with(
        scores,
        lambda score: truthy(score.get("ready_for_langextract")) and not bool(score.get("target_inventory_exact")),
    )
    role_errors = _paper_ids_with(scores, lambda score: bool(score.get("role_attribution_errors")))
    xml_failures = _paper_ids_with(scores, lambda score: _status_is_failure(score.get("xml_roundtrip_status", "")))
    json_failures = _paper_ids_with(scores, lambda score: _status_is_failure(score.get("json_validation_status", "")))
    manual_review = _paper_ids_with(scores, lambda score: bool(str(score.get("manual_review_reasons") or "").strip()))

    failures: list[str] = []
    warnings: list[str] = []
    if len(scores) < _int_threshold(promotion_gates, "min_n_papers", 1):
        failures.append(_gate_message("n_papers", len(scores), "<", _int_threshold(promotion_gates, "min_n_papers", 1)))
    if len(contaminated) > _int_threshold(promotion_gates, "max_contaminated_papers", 0):
        failures.append(
            _gate_message(
                "contaminated_papers",
                len(contaminated),
                ">",
                _int_threshold(promotion_gates, "max_contaminated_papers", 0),
            )
        )
    if len(false_ready) > _int_threshold(promotion_gates, "max_false_ready_papers", 0):
        failures.append(
            _gate_message("false_ready_papers", len(false_ready), ">", _int_threshold(promotion_gates, "max_false_ready_papers", 0))
        )
    if len(ready_target_inventory_errors) > _int_threshold(
        promotion_gates,
        "max_ready_target_inventory_error_papers",
        0,
    ):
        failures.append(
            _gate_message(
                "ready_target_inventory_error_papers",
                len(ready_target_inventory_errors),
                ">",
                _int_threshold(promotion_gates, "max_ready_target_inventory_error_papers", 0),
            )
        )
    if len(role_errors) > _int_threshold(promotion_gates, "max_role_error_papers", 0):
        failures.append(_gate_message("role_error_papers", len(role_errors), ">", _int_threshold(promotion_gates, "max_role_error_papers", 0)))
    if len(xml_failures) > _int_threshold(promotion_gates, "max_xml_roundtrip_failures", 0):
        failures.append(
            _gate_message(
                "xml_roundtrip_failures",
                len(xml_failures),
                ">",
                _int_threshold(promotion_gates, "max_xml_roundtrip_failures", 0),
            )
        )
    if len(json_failures) > _int_threshold(promotion_gates, "max_json_validation_failures", 0):
        failures.append(
            _gate_message(
                "json_validation_failures",
                len(json_failures),
                ">",
                _int_threshold(promotion_gates, "max_json_validation_failures", 0),
            )
        )
    if float(micro["precision"]) < _float_threshold(promotion_gates, "min_micro_precision", 0.99):
        failures.append(
            _gate_message(
                "micro_precision",
                round(float(micro["precision"]), 6),
                "<",
                _float_threshold(promotion_gates, "min_micro_precision", 0.99),
            )
        )
    if float(micro["recall"]) < _float_threshold(promotion_gates, "min_micro_recall", 0.95):
        failures.append(
            _gate_message(
                "micro_recall",
                round(float(micro["recall"]), 6),
                "<",
                _float_threshold(promotion_gates, "min_micro_recall", 0.95),
            )
        )

    if len(false_not_ready) > _warning_int(promotion_gates, "max_false_not_ready_papers", 0):
        warnings.append(
            _gate_message(
                "false_not_ready_papers",
                len(false_not_ready),
                ">",
                _warning_int(promotion_gates, "max_false_not_ready_papers", 0),
            )
        )
    max_manual_review_fraction = _warning_float(promotion_gates, "max_manual_review_paper_fraction", 0.5)
    manual_review_fraction = len(manual_review) / max(1, len(scores))
    if manual_review_fraction > max_manual_review_fraction:
        warnings.append(_gate_message("manual_review_paper_fraction", round(manual_review_fraction, 6), ">", max_manual_review_fraction))

    promotion_status = "fail" if failures else "review" if warnings else "pass"
    return {
        "matrix_config_name": matrix_config_name,
        "promotion_gate_profile": str(promotion_gates.get("profile_name") or ""),
        "promotion_status": promotion_status,
        "n_papers": len(scores),
        "micro_precision": micro["precision"],
        "micro_recall": micro["recall"],
        "micro_f1": micro["f1"],
        "contaminated_papers": len(contaminated),
        "contaminated_paper_ids": contaminated,
        "false_ready_papers": len(false_ready),
        "false_ready_paper_ids": false_ready,
        "false_not_ready_papers": len(false_not_ready),
        "false_not_ready_paper_ids": false_not_ready,
        "target_inventory_error_papers": len(target_inventory_errors),
        "target_inventory_error_paper_ids": target_inventory_errors,
        "ready_target_inventory_error_papers": len(ready_target_inventory_errors),
        "ready_target_inventory_error_paper_ids": ready_target_inventory_errors,
        "role_error_papers": len(role_errors),
        "role_error_paper_ids": role_errors,
        "xml_roundtrip_failures": len(xml_failures),
        "xml_roundtrip_failure_paper_ids": xml_failures,
        "json_validation_failures": len(json_failures),
        "json_validation_failure_paper_ids": json_failures,
        "manual_review_papers": len(manual_review),
        "manual_review_paper_ids": manual_review,
        "failed_gates": failures,
        "warning_gates": warnings,
    }


def evaluate_gate_results(
    paper_scores: list[dict[str, Any]],
    promotion_gates: dict[str, Any],
) -> list[dict[str, Any]]:
    """Evaluate all matrix configurations present in one benchmark run."""

    scores_by_config: dict[str, list[dict[str, Any]]] = {}
    for score in paper_scores:
        scores_by_config.setdefault(str(score.get("matrix_config_name") or ""), []).append(score)
    return [
        evaluate_config_gates(
            matrix_config_name=name,
            scores=scores,
            promotion_gates=promotion_gates,
        )
        for name, scores in sorted(scores_by_config.items())
    ]


def write_gate_results_csv(path: Path, gate_results: list[dict[str, Any]]) -> None:
    """Write promotion decisions in a spreadsheet-friendly shape."""

    fieldnames = [
        "matrix_config_name",
        "promotion_gate_profile",
        "promotion_status",
        "n_papers",
        "micro_precision",
        "micro_recall",
        "micro_f1",
        "contaminated_papers",
        "contaminated_paper_ids",
        "false_ready_papers",
        "false_ready_paper_ids",
        "false_not_ready_papers",
        "false_not_ready_paper_ids",
        "target_inventory_error_papers",
        "target_inventory_error_paper_ids",
        "ready_target_inventory_error_papers",
        "ready_target_inventory_error_paper_ids",
        "role_error_papers",
        "role_error_paper_ids",
        "xml_roundtrip_failures",
        "xml_roundtrip_failure_paper_ids",
        "json_validation_failures",
        "json_validation_failure_paper_ids",
        "manual_review_papers",
        "manual_review_paper_ids",
        "failed_gates",
        "warning_gates",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in gate_results:
            writer.writerow(
                {
                    "matrix_config_name": row.get("matrix_config_name", ""),
                    "promotion_gate_profile": row.get("promotion_gate_profile", ""),
                    "promotion_status": row.get("promotion_status", ""),
                    "n_papers": row.get("n_papers", 0),
                    "micro_precision": f"{float(row.get('micro_precision') or 0):.6f}",
                    "micro_recall": f"{float(row.get('micro_recall') or 0):.6f}",
                    "micro_f1": f"{float(row.get('micro_f1') or 0):.6f}",
                    "contaminated_papers": row.get("contaminated_papers", 0),
                    "contaminated_paper_ids": "|".join(row.get("contaminated_paper_ids") or []),
                    "false_ready_papers": row.get("false_ready_papers", 0),
                    "false_ready_paper_ids": "|".join(row.get("false_ready_paper_ids") or []),
                    "false_not_ready_papers": row.get("false_not_ready_papers", 0),
                    "false_not_ready_paper_ids": "|".join(row.get("false_not_ready_paper_ids") or []),
                    "target_inventory_error_papers": row.get("target_inventory_error_papers", 0),
                    "target_inventory_error_paper_ids": "|".join(row.get("target_inventory_error_paper_ids") or []),
                    "ready_target_inventory_error_papers": row.get("ready_target_inventory_error_papers", 0),
                    "ready_target_inventory_error_paper_ids": "|".join(
                        row.get("ready_target_inventory_error_paper_ids") or []
                    ),
                    "role_error_papers": row.get("role_error_papers", 0),
                    "role_error_paper_ids": "|".join(row.get("role_error_paper_ids") or []),
                    "xml_roundtrip_failures": row.get("xml_roundtrip_failures", 0),
                    "xml_roundtrip_failure_paper_ids": "|".join(row.get("xml_roundtrip_failure_paper_ids") or []),
                    "json_validation_failures": row.get("json_validation_failures", 0),
                    "json_validation_failure_paper_ids": "|".join(row.get("json_validation_failure_paper_ids") or []),
                    "manual_review_papers": row.get("manual_review_papers", 0),
                    "manual_review_paper_ids": "|".join(row.get("manual_review_paper_ids") or []),
                    "failed_gates": "|".join(row.get("failed_gates") or []),
                    "warning_gates": "|".join(row.get("warning_gates") or []),
                }
            )


__all__ = [
    "DEFAULT_PROMOTION_GATES_PATH",
    "PROMOTION_GATES_SCHEMA_VERSION",
    "evaluate_gate_results",
    "load_promotion_gates",
    "write_gate_results_csv",
]
