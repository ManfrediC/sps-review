"""Metric helpers for offline Stage 07 XML benchmarking.

The benchmark compares source character intervals after Stage 07 validation,
not raw model JSON. That choice matters: it measures the text that would reach
LangExtract and lets the normal validator handle relocations, table trimming,
and rejected spans before scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


IGNORED_ROLES = {"background", "uncertain"}


@dataclass(frozen=True)
class Interval:
    """Half-open source interval, using Python slice semantics."""

    start: int
    end: int


def normalise_intervals(intervals: list[Interval]) -> list[Interval]:
    """Sort and merge intervals before character-level comparison.

    Stage 07 may split a logical segment into several physical spans, and shared
    segments can overlap with direct patient segments. Normalising first avoids
    double-counting overlapping source characters.
    """

    ordered = sorted((item for item in intervals if item.end > item.start), key=lambda item: item.start)
    merged: list[Interval] = []
    for interval in ordered:
        if not merged or interval.start > merged[-1].end:
            merged.append(interval)
            continue
        previous = merged[-1]
        merged[-1] = Interval(previous.start, max(previous.end, interval.end))
    return merged


def interval_length(intervals: list[Interval]) -> int:
    """Count unique covered characters across possibly overlapping intervals."""

    return sum(interval.end - interval.start for interval in normalise_intervals(intervals))


def intersection_length(left: list[Interval], right: list[Interval]) -> int:
    """Count unique source characters covered by both interval sets."""

    left_norm = normalise_intervals(left)
    right_norm = normalise_intervals(right)
    left_index = 0
    right_index = 0
    total = 0
    while left_index < len(left_norm) and right_index < len(right_norm):
        left_item = left_norm[left_index]
        right_item = right_norm[right_index]
        total += max(0, min(left_item.end, right_item.end) - max(left_item.start, right_item.start))
        if left_item.end <= right_item.end:
            left_index += 1
        else:
            right_index += 1
    return total


def ratio(numerator: int, denominator: int, *, empty_value: float = 1.0) -> float:
    """Return a safe ratio with an explicit empty-set convention."""

    if denominator == 0:
        return empty_value
    return numerator / denominator


def f1_score(precision: float, recall: float) -> float:
    """Return harmonic mean of precision and recall."""

    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def interval_metrics(predicted: list[Interval], gold: list[Interval]) -> dict[str, Any]:
    """Score one target's predicted intervals against reviewed gold."""

    predicted_chars = interval_length(predicted)
    gold_chars = interval_length(gold)
    overlap_chars = intersection_length(predicted, gold)
    precision = ratio(overlap_chars, predicted_chars, empty_value=1.0 if gold_chars == 0 else 0.0)
    recall = ratio(overlap_chars, gold_chars, empty_value=1.0 if predicted_chars == 0 else 0.0)
    return {
        "predicted_chars": predicted_chars,
        "gold_chars": gold_chars,
        "overlap_chars": overlap_chars,
        "precision": precision,
        "recall": recall,
        "f1": f1_score(precision, recall),
    }


def declared_target_ids(segments_payload: dict[str, Any]) -> set[str]:
    """Extract declared target IDs from a Stage 07 segments payload."""

    return {
        str(item.get("id") or item.get("target_id") or "").strip()
        for item in segments_payload.get("entities") or []
        if str(item.get("id") or item.get("target_id") or "").strip()
    }


def target_intervals(segments_payload: dict[str, Any]) -> dict[str, list[Interval]]:
    """Collect scored source intervals by target ID.

    Background and uncertain segments are ignored for precision/recall because
    they should not feed LangExtract target views. They are checked separately as
    contamination signals when they are incorrectly assigned to a target.
    """

    by_target: dict[str, list[Interval]] = {}
    for segment in segments_payload.get("segments") or []:
        role = str(segment.get("role") or "").strip()
        if role in IGNORED_ROLES:
            continue
        offsets = segment.get("source_offsets") or {}
        try:
            interval = Interval(int(offsets.get("start")), int(offsets.get("end")))
        except (TypeError, ValueError):
            continue
        for target_id in segment.get("targets") or []:
            target_text = str(target_id or "").strip()
            if not target_text or target_text == "unknown":
                continue
            by_target.setdefault(target_text, []).append(interval)
    return {target_id: normalise_intervals(intervals) for target_id, intervals in by_target.items()}


def contamination_flags(
    *,
    predicted_payload: dict[str, Any],
    gold_target_ids: set[str],
) -> list[str]:
    """Return precision-first flags that are not captured by interval F1 alone."""

    flags: list[str] = []
    for segment in predicted_payload.get("segments") or []:
        segment_id = str(segment.get("logical_segment_id") or segment.get("segment_id") or "").strip()
        role = str(segment.get("role") or "").strip()
        targets = {str(item or "").strip() for item in segment.get("targets") or []}
        if role == "background" and targets.intersection(gold_target_ids):
            flags.append(f"targeted_background_segment:{segment_id}")
        for target_id in sorted(targets):
            if target_id and target_id != "unknown" and gold_target_ids and target_id not in gold_target_ids:
                flags.append(f"extra_target_segment:{target_id}:{segment_id}")
    return sorted(set(flags))


def score_segments_payloads(
    *,
    gold_payload: dict[str, Any],
    predicted_payload: dict[str, Any],
    paper_id: str | None = None,
    registry_row: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Score one predicted Stage 07 segments payload against one gold payload.

    The result keeps per-target scores for inspection and micro-averaged scores
    for comparing runs. Missing/extra target lists are based on declared entities
    when available, falling back to targets observed in accepted segments.
    """

    gold_by_target = target_intervals(gold_payload)
    predicted_by_target = target_intervals(predicted_payload)
    gold_ids = declared_target_ids(gold_payload) or set(gold_by_target)
    predicted_ids = declared_target_ids(predicted_payload) or set(predicted_by_target)
    target_ids = sorted(gold_ids | predicted_ids | set(gold_by_target) | set(predicted_by_target))
    target_scores = []
    total_predicted = 0
    total_gold = 0
    total_overlap = 0
    for target_id in target_ids:
        metrics = interval_metrics(
            predicted_by_target.get(target_id, []),
            gold_by_target.get(target_id, []),
        )
        total_predicted += int(metrics["predicted_chars"])
        total_gold += int(metrics["gold_chars"])
        total_overlap += int(metrics["overlap_chars"])
        target_scores.append({"target_id": target_id, **metrics})
    precision = ratio(total_overlap, total_predicted, empty_value=1.0 if total_gold == 0 else 0.0)
    recall = ratio(total_overlap, total_gold, empty_value=1.0 if total_predicted == 0 else 0.0)
    contamination = contamination_flags(predicted_payload=predicted_payload, gold_target_ids=gold_ids)
    return {
        "paper_id": paper_id or str(predicted_payload.get("paper_id") or gold_payload.get("paper_id") or ""),
        "target_scores": target_scores,
        "micro": {
            "predicted_chars": total_predicted,
            "gold_chars": total_gold,
            "overlap_chars": total_overlap,
            "precision": precision,
            "recall": recall,
            "f1": f1_score(precision, recall),
        },
        "missing_targets": sorted(gold_ids - predicted_ids),
        "extra_targets": sorted(predicted_ids - gold_ids),
        "contamination_flags": contamination,
        "ready_for_langextract": (registry_row or {}).get("ready_for_langextract", ""),
        "manual_review_reasons": (registry_row or {}).get("manual_review_reasons", ""),
    }


def summarise_paper_scores(paper_scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-paper benchmark rows into a run-level summary."""

    total_predicted = 0
    total_gold = 0
    total_overlap = 0
    for score in paper_scores:
        micro = score.get("micro") or {}
        total_predicted += int(micro.get("predicted_chars") or 0)
        total_gold += int(micro.get("gold_chars") or 0)
        total_overlap += int(micro.get("overlap_chars") or 0)
    precision = ratio(total_overlap, total_predicted, empty_value=1.0 if total_gold == 0 else 0.0)
    recall = ratio(total_overlap, total_gold, empty_value=1.0 if total_predicted == 0 else 0.0)
    return {
        "n_papers": len(paper_scores),
        "n_contaminated_papers": sum(1 for score in paper_scores if score.get("contamination_flags")),
        "n_missing_target_papers": sum(1 for score in paper_scores if score.get("missing_targets")),
        "micro_predicted_chars": total_predicted,
        "micro_gold_chars": total_gold,
        "micro_overlap_chars": total_overlap,
        "micro_precision": precision,
        "micro_recall": recall,
        "micro_f1": f1_score(precision, recall),
    }
