"""Metric helpers for offline Stage 07 XML benchmarking.

The benchmark compares source character intervals after Stage 07 validation,
not raw model JSON. That choice matters: it measures the text that would reach
LangExtract and lets the normal validator handle relocations, table trimming,
and rejected spans before scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re


IGNORED_ROLES = {"background", "uncertain"}
UNSAFE_SECTION_HEADING_RE = re.compile(
    r"^\s*(?:abstract\s*)?(?:references?|bibliography|materials?\s+and\s+methods?|methods?|acknowledg(?:e)?ments?)(?:\s*[:.\-]\s+|\s*$)",
    re.IGNORECASE,
)
EXTERNAL_REPORT_LABEL_CONTEXT_RE = re.compile(
    r"^\W*in\s+(?:their|his|her|the|this|that)\s+reports?\b",
    re.IGNORECASE,
)
COMPARISON_LABEL_CONTEXT_RE = re.compile(
    r"(?:similar\s+to(?:\s+that\s+of)?|same\s+as|compared\s+(?:with|to)|unlike|as\s+in|that\s+of)\s*$",
    re.IGNORECASE,
)


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


def entity_labels(segments_payload: dict[str, Any]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for item in segments_payload.get("entities") or []:
        target_id = str(item.get("id") or item.get("target_id") or "").strip()
        label = str(item.get("label") or item.get("target_label") or "").strip()
        if target_id and label:
            labels[target_id] = label
    return labels


def looks_like_unsafe_section_text(text: str) -> bool:
    """Return true when text appears to be an extraction-unsafe section.

    The gate is meant to catch actual section leakage, such as abstract
    "Methods." blocks or reference headings. It should not fire on case-report
    prose that merely cites a laboratory method or says "see Methods".
    """

    compact_text = str(text or "").strip()
    return bool(UNSAFE_SECTION_HEADING_RE.search(compact_text))


def label_mentions_other_current_target(text: str, label: str) -> bool:
    """Return true when a target label looks like a current-paper patient leak.

    Numbering can be reused across papers. Phrases such as "Patient 2 in their
    report" identify the numbering in a cited report, not the current paper's
    Patient 2, so they are ignored by this guardrail.
    """

    if len(label.strip()) < 4:
        return False
    label_pattern = r"(?<!\w)" + r"\s+".join(re.escape(part) for part in label.strip().split()) + r"(?!\w)"
    for match in re.finditer(label_pattern, text, flags=re.IGNORECASE):
        preceding_context = text[max(0, match.start() - 64) : match.start()]
        following_context = text[match.end() : match.end() + 64]
        if COMPARISON_LABEL_CONTEXT_RE.search(preceding_context):
            continue
        if EXTERNAL_REPORT_LABEL_CONTEXT_RE.search(following_context):
            continue
        return True
    return False


def validation_value(payload: dict[str, Any], key: str) -> str:
    validation = payload.get("validation") or {}
    return str(validation.get(key) or "")


def logical_segment_id(segment: dict[str, Any]) -> str:
    return str(segment.get("logical_segment_id") or segment.get("segment_id") or "").strip()


def parse_optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def logical_segment_groups(segments_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Group physical spans so contamination audits show complete excerpts.

    Stage 07 can split one logical annotation into several physical spans when
    the evidence crosses OCR page or paragraph boundaries. The flag is attached
    to the logical segment because that is what a reviewer thinks in, but the
    audit row keeps the physical segment IDs for traceability.
    """

    grouped: dict[str, list[dict[str, Any]]] = {}
    for segment in segments_payload.get("segments") or []:
        grouped.setdefault(logical_segment_id(segment), []).append(segment)

    groups: list[dict[str, Any]] = []
    for group_id, segments in grouped.items():
        ordered = sorted(
            segments,
            key=lambda segment: parse_optional_int((segment.get("source_offsets") or {}).get("start")) or 0,
        )
        targets = sorted(
            {
                str(target_id or "").strip()
                for segment in ordered
                for target_id in segment.get("targets") or []
                if str(target_id or "").strip()
            }
        )
        roles = sorted({str(segment.get("role") or "").strip() for segment in ordered if str(segment.get("role") or "").strip()})
        starts = [
            value
            for value in (parse_optional_int((segment.get("source_offsets") or {}).get("start")) for segment in ordered)
            if value is not None
        ]
        ends = [
            value
            for value in (parse_optional_int((segment.get("source_offsets") or {}).get("end")) for segment in ordered)
            if value is not None
        ]
        groups.append(
            {
                "logical_segment_id": group_id,
                "physical_segment_ids": [str(segment.get("segment_id") or "") for segment in ordered],
                "targets": targets,
                "role": roles[0] if len(roles) == 1 else "|".join(roles),
                "roles": roles,
                "source_start": min(starts) if starts else "",
                "source_end": max(ends) if ends else "",
                "text": "\n\n".join(str(segment.get("text") or "") for segment in ordered),
            }
        )
    return sorted(groups, key=lambda group: (int(group["source_start"]) if group["source_start"] != "" else -1, group["logical_segment_id"]))


def target_segment_roles(segments_payload: dict[str, Any]) -> dict[str, list[tuple[Interval, str, str]]]:
    roles: dict[str, list[tuple[Interval, str, str]]] = {}
    for segment in segments_payload.get("segments") or []:
        role = str(segment.get("role") or "").strip()
        if role in IGNORED_ROLES:
            continue
        offsets = segment.get("source_offsets") or {}
        try:
            interval = Interval(int(offsets.get("start")), int(offsets.get("end")))
        except (TypeError, ValueError):
            continue
        if interval.end <= interval.start:
            continue
        segment_id = str(segment.get("logical_segment_id") or segment.get("segment_id") or "").strip()
        for target_id in segment.get("targets") or []:
            target_text = str(target_id or "").strip()
            if target_text and target_text != "unknown":
                roles.setdefault(target_text, []).append((interval, role, segment_id))
    return roles


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


def target_source_units(segments_payload: dict[str, Any]) -> dict[str, set[str]]:
    """Collect selected source-unit IDs by target when the payload carries them."""

    by_target: dict[str, set[str]] = {}
    for segment in segments_payload.get("segments") or []:
        role = str(segment.get("role") or "").strip()
        if role in IGNORED_ROLES:
            continue
        unit_ids = {
            str(unit_id).strip()
            for unit_id in segment.get("source_unit_ids") or []
            if str(unit_id).strip()
        }
        if not unit_ids:
            continue
        for target_id in segment.get("targets") or []:
            target_text = str(target_id or "").strip()
            if target_text and target_text != "unknown":
                by_target.setdefault(target_text, set()).update(unit_ids)
    return by_target


def unit_metrics(predicted_payload: dict[str, Any], gold_payload: dict[str, Any]) -> dict[str, Any]:
    predicted_by_target = target_source_units(predicted_payload)
    gold_by_target = target_source_units(gold_payload)
    target_ids = sorted(set(predicted_by_target) | set(gold_by_target))
    if not target_ids:
        return {
            "available": False,
            "predicted_units": 0,
            "gold_units": 0,
            "overlap_units": 0,
            "precision": "",
            "recall": "",
            "f1": "",
            "target_scores": [],
        }
    total_predicted = 0
    total_gold = 0
    total_overlap = 0
    target_scores: list[dict[str, Any]] = []
    for target_id in target_ids:
        predicted = predicted_by_target.get(target_id, set())
        gold = gold_by_target.get(target_id, set())
        overlap = predicted & gold
        total_predicted += len(predicted)
        total_gold += len(gold)
        total_overlap += len(overlap)
        precision = ratio(len(overlap), len(predicted), empty_value=1.0 if not gold else 0.0)
        recall = ratio(len(overlap), len(gold), empty_value=1.0 if not predicted else 0.0)
        target_scores.append(
            {
                "target_id": target_id,
                "predicted_units": len(predicted),
                "gold_units": len(gold),
                "overlap_units": len(overlap),
                "precision": precision,
                "recall": recall,
                "f1": f1_score(precision, recall),
            }
        )
    precision = ratio(total_overlap, total_predicted, empty_value=1.0 if total_gold == 0 else 0.0)
    recall = ratio(total_overlap, total_gold, empty_value=1.0 if total_predicted == 0 else 0.0)
    return {
        "available": True,
        "predicted_units": total_predicted,
        "gold_units": total_gold,
        "overlap_units": total_overlap,
        "precision": precision,
        "recall": recall,
        "f1": f1_score(precision, recall),
        "target_scores": target_scores,
    }


def contamination_flags(
    *,
    predicted_payload: dict[str, Any],
    gold_target_ids: set[str],
    gold_labels: dict[str, str] | None = None,
) -> list[str]:
    """Return precision-first flags that are not captured by interval F1 alone."""

    return sorted(
        {
            detail["flag"]
            for detail in contamination_details(
                predicted_payload=predicted_payload,
                gold_target_ids=gold_target_ids,
                gold_labels=gold_labels,
            )
        }
    )


def contamination_details(
    *,
    predicted_payload: dict[str, Any],
    gold_target_ids: set[str],
    gold_labels: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Return reviewer-facing contamination details with source excerpts."""

    labels = gold_labels or {}
    details: list[dict[str, Any]] = []
    for group in logical_segment_groups(predicted_payload):
        segment_id = str(group.get("logical_segment_id") or "").strip()
        role = str(group.get("role") or "").strip()
        targets = {str(item or "").strip() for item in group.get("targets") or []}
        base_detail = {
            "logical_segment_id": segment_id,
            "physical_segment_ids": list(group.get("physical_segment_ids") or []),
            "role": role,
            "targets": sorted(targets),
            "source_start": group.get("source_start", ""),
            "source_end": group.get("source_end", ""),
            "text_excerpt": " ".join(str(group.get("text") or "").split()),
        }
        if role == "background" and targets.intersection(gold_target_ids):
            details.append(
                {
                    **base_detail,
                    "flag": f"targeted_background_segment:{segment_id}",
                    "flag_type": "targeted_background_segment",
                    "target_id": "|".join(sorted(targets.intersection(gold_target_ids))),
                    "other_target_id": "",
                }
            )
        text = str(group.get("text") or "")
        if role not in IGNORED_ROLES:
            for target_id in sorted(targets):
                if target_id and target_id != "unknown" and gold_target_ids and target_id not in gold_target_ids:
                    details.append(
                        {
                            **base_detail,
                            "flag": f"extra_target_segment:{target_id}:{segment_id}",
                            "flag_type": "extra_target_segment",
                            "target_id": target_id,
                            "other_target_id": "",
                        }
                    )
        if role not in IGNORED_ROLES and looks_like_unsafe_section_text(text):
            details.append(
                {
                    **base_detail,
                    "flag": f"unsafe_section_text:{segment_id}",
                    "flag_type": "unsafe_section_text",
                    "target_id": "|".join(sorted(targets.intersection(gold_target_ids))),
                    "other_target_id": "",
                }
            )
        if role not in IGNORED_ROLES:
            for target_id in sorted(target for target in targets if target in gold_target_ids):
                for other_target, other_label in labels.items():
                    if other_target == target_id:
                        continue
                    if label_mentions_other_current_target(text, other_label):
                        details.append(
                            {
                                **base_detail,
                                "flag": f"cross_target_label_leak:{target_id}:{other_target}:{segment_id}",
                                "flag_type": "cross_target_label_leak",
                                "target_id": target_id,
                                "other_target_id": other_target,
                            }
                        )
    return sorted(
        details,
        key=lambda detail: (
            str(detail.get("flag_type") or ""),
            str(detail.get("target_id") or ""),
            str(detail.get("other_target_id") or ""),
            str(detail.get("logical_segment_id") or ""),
        ),
    )


def role_attribution_errors(gold_payload: dict[str, Any], predicted_payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    gold_roles = target_segment_roles(gold_payload)
    predicted_roles = target_segment_roles(predicted_payload)
    for target_id, predicted_items in predicted_roles.items():
        for predicted_interval, predicted_role, segment_id in predicted_items:
            overlaps = [
                gold_role
                for gold_interval, gold_role, _ in gold_roles.get(target_id, [])
                if intersection_length([predicted_interval], [gold_interval]) > 0
            ]
            if overlaps and predicted_role not in overlaps:
                errors.append(f"role_mismatch:{target_id}:{segment_id}:{predicted_role}:{','.join(sorted(set(overlaps)))}")
    return sorted(set(errors))


def truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y"}


def readiness_calibration(
    *,
    registry_row: dict[str, str] | None,
    gold_registry_row: dict[str, str] | None,
    contamination: list[str],
    missing_targets: list[str],
    extra_targets: list[str],
    role_errors: list[str],
) -> dict[str, bool]:
    predicted_ready = truthy((registry_row or {}).get("ready_for_langextract"))
    if gold_registry_row is None:
        gold_ready = not contamination and not missing_targets and not extra_targets and not role_errors
    else:
        gold_ready = truthy(gold_registry_row.get("ready_for_langextract"))
    semantically_unsafe = bool(contamination or missing_targets or extra_targets or role_errors)
    return {
        "predicted_ready": predicted_ready,
        "gold_ready": gold_ready,
        "false_ready": bool(predicted_ready and (not gold_ready or semantically_unsafe)),
        "false_not_ready": bool((not predicted_ready) and gold_ready and not semantically_unsafe),
    }


def error_taxonomy_codes(
    *,
    precision: float,
    recall: float,
    missing_targets: list[str],
    extra_targets: list[str],
    role_errors: list[str],
    contamination: list[str],
) -> list[str]:
    codes: set[str] = set()
    if missing_targets or extra_targets:
        codes.add("target_inventory_error")
    if role_errors:
        codes.add("role_mismatch")
    if recall < 0.90:
        codes.add("missed_source_evidence")
    if precision < 0.90:
        codes.add("overselected_source_evidence")
    for flag in contamination:
        if flag.startswith("cross_target_label_leak"):
            codes.add("wrong_current_target")
        elif flag.startswith("unsafe_section_text"):
            codes.add("methods_overinclusion")
        elif flag.startswith("comparator_only_leak"):
            codes.add("comparator_only_leak")
        elif flag.startswith("targeted_background_segment"):
            codes.add("role_mismatch")
        elif "external_report" in flag:
            codes.add("external_report_leak")
    return sorted(codes)


def score_segments_payloads(
    *,
    gold_payload: dict[str, Any],
    predicted_payload: dict[str, Any],
    paper_id: str | None = None,
    registry_row: dict[str, str] | None = None,
    gold_registry_row: dict[str, str] | None = None,
    matrix_config_name: str = "",
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
    missing_targets = sorted(gold_ids - predicted_ids)
    extra_targets = sorted(predicted_ids - gold_ids)
    role_errors = role_attribution_errors(gold_payload, predicted_payload)
    contamination_detail_rows = contamination_details(
        predicted_payload=predicted_payload,
        gold_target_ids=gold_ids,
        gold_labels=entity_labels(gold_payload),
    )
    contamination = sorted({detail["flag"] for detail in contamination_detail_rows})
    calibration = readiness_calibration(
        registry_row=registry_row,
        gold_registry_row=gold_registry_row,
        contamination=contamination,
        missing_targets=missing_targets,
        extra_targets=extra_targets,
        role_errors=role_errors,
    )
    return {
        "paper_id": paper_id or str(predicted_payload.get("paper_id") or gold_payload.get("paper_id") or ""),
        "matrix_config_name": matrix_config_name,
        "target_scores": target_scores,
        "micro": {
            "predicted_chars": total_predicted,
            "gold_chars": total_gold,
            "overlap_chars": total_overlap,
            "precision": precision,
            "recall": recall,
            "f1": f1_score(precision, recall),
        },
        "unit_metrics": unit_metrics(predicted_payload, gold_payload),
        "target_inventory_exact": not missing_targets and not extra_targets,
        "missing_targets": missing_targets,
        "extra_targets": extra_targets,
        "role_attribution_errors": role_errors,
        "contamination_flags": contamination,
        "contamination_details": contamination_detail_rows,
        "error_taxonomy": error_taxonomy_codes(
            precision=precision,
            recall=recall,
            missing_targets=missing_targets,
            extra_targets=extra_targets,
            role_errors=role_errors,
            contamination=contamination,
        ),
        "xml_roundtrip_status": validation_value(predicted_payload, "roundtrip_status"),
        "json_validation_status": validation_value(predicted_payload, "status"),
        "ready_for_langextract": (registry_row or {}).get("ready_for_langextract", ""),
        "manual_review_reasons": (registry_row or {}).get("manual_review_reasons", ""),
        "readiness_calibration": calibration,
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
        "n_target_inventory_error_papers": sum(1 for score in paper_scores if not score.get("target_inventory_exact")),
        "n_role_error_papers": sum(1 for score in paper_scores if score.get("role_attribution_errors")),
        "n_false_ready_papers": sum(1 for score in paper_scores if (score.get("readiness_calibration") or {}).get("false_ready")),
        "n_false_not_ready_papers": sum(1 for score in paper_scores if (score.get("readiness_calibration") or {}).get("false_not_ready")),
        "micro_predicted_chars": total_predicted,
        "micro_gold_chars": total_gold,
        "micro_overlap_chars": total_overlap,
        "micro_precision": precision,
        "micro_recall": recall,
        "micro_f1": f1_score(precision, recall),
    }
