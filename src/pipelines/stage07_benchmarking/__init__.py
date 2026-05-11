"""Contained Stage 07 XML benchmarking helpers."""

from .metrics import (
    interval_metrics,
    score_segments_payloads,
    summarise_paper_scores,
)
from .promotion import evaluate_gate_results, load_promotion_gates
from .telemetry import telemetry_row

__all__ = [
    "evaluate_gate_results",
    "interval_metrics",
    "load_promotion_gates",
    "score_segments_payloads",
    "summarise_paper_scores",
    "telemetry_row",
]
