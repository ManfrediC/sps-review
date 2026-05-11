"""Combined DeepSeek unit selection plus GPT-5.4 reviewer-patcher.

The combined path keeps Stage 07 source-backed: models select stable
``unit_id`` values only, and Python compiles the exact source offsets into the
existing span-metadata contract.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import (
    PreparedSource,
    SourceUnit,
    Target,
    UnitFeatures,
    allowed_roles_for_targets,
    build_unit_features,
    build_source_units,
    compile_unit_selection_payload,
    featured_source_units_payload,
    relative_to_repo,
)
from .deepseek_client import (
    DEFAULT_DEEPSEEK_MAX_OUTPUT_TOKENS,
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_DEEPSEEK_REQUEST_TIMEOUT_SECONDS,
    extract_json_object,
    response_metadata as deepseek_response_metadata,
)
from .openai_client import (
    record_telemetry_row,
    response_metadata as openai_response_metadata,
    sha256_json,
)
from stage07_benchmarking.telemetry import telemetry_row

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover - exercised when OpenAI is not installed
    OpenAI = None


DEFAULT_OPENAI_REVIEW_MODEL = "gpt-5.4"
DEFAULT_OPENAI_REVIEW_REASONING_EFFORT = "medium"
DEFAULT_OPENAI_REVIEW_MAX_OUTPUT_TOKENS = 20000
DEFAULT_REVIEWER_MAX_UNITS = 120
REVIEWER_EXPLANATION_WORD_LIMIT = 20


PRIMARY_SYSTEM_PROMPT = """\
You assign fixed source units to fixed current-paper SPSD targets.

Return JSON only. Do not include reasoning. Select only supplied unit IDs and
target IDs. Python compiles exact source text and offsets.

Current-paper targets are the declared targets only. Do not assign cited-report
patients, controls, normal subjects, comparator cohorts, or previous-paper
patients to current-paper targets. If a unit describes an assay using current
patient serum, CSF, tissue, tumour, or other samples, keep it relevant only to
the current target samples used.

Use patient_specific for exactly one patient target, shared for multiple
patient targets, and group_summary/group_specific for group targets. Exclude
comparator-only, background, references, metadata, and cited-literature units.
Return manual_review_reasons only when extraction needs human review.
""".strip()


REVIEWER_SYSTEM_PROMPT = """\
You review a DeepSeek source-unit selection for Stage 07 SPSD extraction.

Return JSON only. Do not include chain-of-thought. Use only supplied unit ids.
Python compiles exact source text and offsets. Patch by adding or removing unit
ids, approve the candidate, or require manual review. Evidence and reasons must
be 20 words or fewer.

Only use role "shared" when the same source statement cleanly applies to every
listed target. If a unit gives different facts for different patient labels,
add patient-specific segments or require manual review. Remove duplicate
abstract/background/metadata units when body, table, or discussion units provide
the same evidence more precisely. Preserve current-patient assay context even
when controls or comparator samples are mentioned.
""".strip()


UNIT_SELECTION_RESPONSE_SHAPE: dict[str, Any] = {
    "targets": [],
    "segments": [
        {
            "targets": ["<declared_target_id>"],
            "role": "patient_specific",
            "confidence": "high",
            "evidence": "Brief source-backed reason",
            "unit_ids": ["<unit_id>"],
        }
    ],
    "manual_review_reasons": ["only when the extraction itself needs human review"],
}


REVIEW_PATCH_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["approve", "patch", "manual_review"]},
        "target_additions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "kind": {"type": "string", "enum": ["patient", "group"]},
                    "label": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["id", "kind", "label", "evidence"],
                "additionalProperties": False,
            },
        },
        "additions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "targets": {"type": "array", "items": {"type": "string"}},
                    "role": {
                        "type": "string",
                        "enum": [
                            "patient_specific",
                            "shared",
                            "group_summary",
                            "group_specific",
                            "uncertain",
                            "background",
                        ],
                    },
                    "confidence": {"type": "string"},
                    "evidence": {"type": "string"},
                    "unit_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["targets", "role", "confidence", "evidence", "unit_ids"],
                "additionalProperties": False,
            },
        },
        "removals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "unit_ids": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                "required": ["unit_ids", "reason"],
                "additionalProperties": False,
            },
        },
        "manual_review_reasons": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "decision",
        "target_additions",
        "additions",
        "removals",
        "manual_review_reasons",
    ],
    "additionalProperties": False,
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_source_units_payload(units: list[SourceUnit]) -> list[dict[str, Any]]:
    return [
        {
            "id": unit.unit_id,
            "type": unit.unit_type,
            "p": unit.page_index,
            "text": unit.text,
        }
        for unit in units
    ]


def primary_user_payload(*, prepared_source: PreparedSource, targets: list[Target]) -> dict[str, Any]:
    units = build_source_units(prepared_source)
    features = build_unit_features(units, targets)
    return {
        "paper_id": prepared_source.paper_id,
        "declared_targets": [
            {"id": target.target_id, "kind": target.target_kind, "label": target.label}
            for target in targets
        ],
        "allowed_roles": allowed_roles_for_targets(targets),
        "source_units": featured_source_units_payload(units, features),
        "required_output_shape": UNIT_SELECTION_RESPONSE_SHAPE,
    }


def invalid_primary_selection(reason: str) -> dict[str, Any]:
    return {
        "annotation_mode": "deepseek_unit_id_selection_invalid_json",
        "targets": [],
        "segments": [],
        "manual_review_reasons": [reason],
    }


def request_deepseek_primary_selection(
    *,
    prepared_source: PreparedSource,
    targets: list[Target],
    model: str = DEFAULT_DEEPSEEK_MODEL,
    api_key: str,
    trace_dir: Path | None = None,
    max_output_tokens: int = DEFAULT_DEEPSEEK_MAX_OUTPUT_TOKENS,
    telemetry_rows: list[dict[str, str]] | None = None,
    telemetry_jsonl_path: Path | None = None,
    telemetry_csv_path: Path | None = None,
    telemetry_context: dict[str, Any] | None = None,
    request_timeout_seconds: float | None = DEFAULT_DEEPSEEK_REQUEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("The openai package is not installed.")

    user_payload = primary_user_payload(prepared_source=prepared_source, targets=targets)
    request_trace_path = ""
    response_trace_path = ""
    meta_trace_path = ""
    if trace_dir is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)
        request_path = trace_dir / f"{prepared_source.paper_id}.reviewed_primary.request.json"
        request_path.write_text(
            json.dumps(
                {
                    "model": model,
                    "max_output_tokens": max_output_tokens,
                    "request_timeout_seconds": request_timeout_seconds,
                    "system_prompt": PRIMARY_SYSTEM_PROMPT,
                    "user_payload": user_payload,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        request_trace_path = relative_to_repo(request_path)

    client_kwargs: dict[str, Any] = {"api_key": api_key, "base_url": "https://api.deepseek.com"}
    if request_timeout_seconds and request_timeout_seconds > 0:
        client_kwargs["timeout"] = request_timeout_seconds
    client = OpenAI(**client_kwargs)
    started_at = now_utc_iso()
    started_counter = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PRIMARY_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            max_tokens=max_output_tokens,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
    except Exception as exc:
        row = primary_telemetry_row(
            prepared_source=prepared_source,
            model=model,
            max_output_tokens=max_output_tokens,
            telemetry_context=telemetry_context,
            started_at=started_at,
            started_counter=started_counter,
            response_status=f"exception:{type(exc).__name__}",
            request_trace_path=request_trace_path,
        )
        record_telemetry_row(
            row,
            telemetry_rows=telemetry_rows,
            telemetry_jsonl_path=telemetry_jsonl_path,
            telemetry_csv_path=telemetry_csv_path,
        )
        raise

    content = response.choices[0].message.content or ""
    if trace_dir is not None:
        response_path = trace_dir / f"{prepared_source.paper_id}.reviewed_primary.response.txt"
        response_path.write_text(content, encoding="utf-8")
        meta_path = trace_dir / f"{prepared_source.paper_id}.reviewed_primary.response.meta.json"
        meta_path.write_text(
            json.dumps(deepseek_response_metadata(response), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        response_trace_path = relative_to_repo(response_path)
        meta_trace_path = relative_to_repo(meta_path)

    row = primary_telemetry_row(
        prepared_source=prepared_source,
        model=model,
        max_output_tokens=max_output_tokens,
        telemetry_context=telemetry_context,
        started_at=started_at,
        started_counter=started_counter,
        response_status="completed",
        usage=getattr(response, "usage", None),
        request_trace_path=request_trace_path,
        response_trace_path=response_trace_path,
        meta_trace_path=meta_trace_path,
    )
    try:
        selection_payload = extract_json_object(content)
    except json.JSONDecodeError as exc:
        reason = "deepseek_unit_selection_empty_response" if not content.strip() else "deepseek_unit_selection_invalid_json"
        row["response_status"] = f"invalid_json:{type(exc).__name__}"
        row["validation_status"] = "manual_review_required"
        row["validation_errors"] = reason
        row["manual_review_reasons"] = reason
        record_telemetry_row(
            row,
            telemetry_rows=telemetry_rows,
            telemetry_jsonl_path=telemetry_jsonl_path,
            telemetry_csv_path=telemetry_csv_path,
        )
        return invalid_primary_selection(reason)

    record_telemetry_row(
        row,
        telemetry_rows=telemetry_rows,
        telemetry_jsonl_path=telemetry_jsonl_path,
        telemetry_csv_path=telemetry_csv_path,
    )
    selection_payload["annotation_mode"] = str(
        selection_payload.get("annotation_mode") or "deepseek_unit_id_selection"
    )
    return selection_payload


def primary_telemetry_row(
    *,
    prepared_source: PreparedSource,
    model: str,
    max_output_tokens: int,
    telemetry_context: dict[str, Any] | None,
    started_at: str,
    started_counter: float,
    response_status: str,
    usage: Any = None,
    request_trace_path: str = "",
    response_trace_path: str = "",
    meta_trace_path: str = "",
) -> dict[str, str]:
    context = telemetry_context or {}
    return telemetry_row(
        benchmark_run_id=str(context.get("benchmark_run_id") or ""),
        matrix_config_name=str(context.get("matrix_config_name") or ""),
        paper_id=prepared_source.paper_id,
        provider="deepseek",
        model=model,
        endpoint="chat_completions",
        architecture_variant=str(context.get("architecture_variant") or "unit_ids_reviewed_primary"),
        reasoning_effort="high",
        max_output_tokens=max_output_tokens,
        prompt_hash=hashlib.sha256(PRIMARY_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        schema_hash=sha256_json(UNIT_SELECTION_RESPONSE_SHAPE),
        started_at_utc=started_at,
        finished_at_utc=now_utc_iso(),
        latency_ms=round((time.perf_counter() - started_counter) * 1000),
        response_status=response_status,
        usage=usage,
        trace_request_path=request_trace_path,
        trace_response_path=response_trace_path,
        trace_meta_path=meta_trace_path,
    )


def unit_tags(unit: SourceUnit, targets: list[Target], feature: UnitFeatures | None = None) -> list[str]:
    text = unit.text
    lower = text.casefold()
    tags: set[str] = {unit.unit_type}
    if feature is not None:
        tags.update(feature.reason_codes)
        tags.update(feature.risk_flags)
        if feature.candidate_targets:
            tags.add("candidate_target")
    if re.search(r"\b(?:patient|case|subject)\s*(?:no\.?|number)?\s*\d+\b", text, flags=re.IGNORECASE):
        tags.add("target_label")
    for target in targets:
        label = target.label.strip()
        if label and re.search(rf"\b{re.escape(label)}\b", text, flags=re.IGNORECASE):
            tags.add("target_label")
    if re.search(r"\b(?:discussion|conclusion|comment)\b", lower):
        tags.add("discussion")
    if re.search(r"\b(?:method|patients and methods|materials|serum|csf|assay|elisa|immuno|antibod)", lower):
        tags.add("methods_assay")
    if re.search(r"\b(?:result|finding|table|fig(?:ure)?)\b", lower) or unit.unit_type == "table_row":
        tags.add("results_table")
    if re.search(r"\b(?:stiff[- ]?(?:person|man|limb)|spsd?|sms|perm|gad|glyr|amphiphysin)\b", lower):
        tags.add("spsd")
    if re.search(r"\b(?:diagnos|criteria|autoimmune|diabetes|thyroid|rta|cancer|tumou?r)\b", lower):
        tags.add("diagnosis_context")
    if re.search(r"\b(?:treat|baclofen|diazepam|clonazepam|ivig|steroid|plasma|outcome|improv|follow[- ]?up)\b", lower):
        tags.add("treatment_outcome")
    if re.search(r"\b(?:both|all|series|cohort|patients|subjects|group)\b", lower):
        tags.add("shared_or_group")
    if unit.unit_type == "metadata" or re.search(r"\b(?:references|copyright|downloaded|correspondence)\b", lower):
        tags.add("low_value")
    return sorted(tags)


def selected_unit_ids(selection_payload: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for segment in selection_payload.get("segments") or []:
        ids.update(str(unit_id).strip() for unit_id in segment.get("unit_ids") or [] if str(unit_id).strip())
    return ids


def selected_segment_payloads(selection_payload: dict[str, Any]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for segment in selection_payload.get("segments") or []:
        compact.append(
            {
                "targets": [str(target) for target in segment.get("targets") or []],
                "role": str(segment.get("role") or ""),
                "confidence": str(segment.get("confidence") or ""),
                "evidence": word_limited(str(segment.get("evidence") or "")),
                "unit_ids": [str(unit_id) for unit_id in segment.get("unit_ids") or []],
            }
        )
    return compact


def reviewer_unit_ids(
    *,
    units: list[SourceUnit],
    targets: list[Target],
    features: dict[str, UnitFeatures],
    primary_selection: dict[str, Any],
    max_units: int = DEFAULT_REVIEWER_MAX_UNITS,
) -> set[str]:
    """Choose the compact source-unit window shown to the GPT reviewer.

    The reviewer needs enough surrounding evidence to find misses, but every
    extra unit increases cost. This filter favours selected units, neighbours,
    and clinically tagged units while excluding obvious low-value metadata.
    """

    selected = selected_unit_ids(primary_selection)
    selected_indexes = {
        index
        for index, unit in enumerate(units)
        if unit.unit_id in selected
    }
    review_tags = {
        "target_label",
        "candidate_target",
        "patient_boundary",
        "group_scope",
        "subset_scope",
        "current_patient_sample_context",
        "current_sample_with_comparator_context",
        "external_patient_mention",
        "mixed_patient_labels",
        "group_subset_scope",
        "ocr_patient_label",
        "low_confidence_continuation",
        "diagnosis_context",
        "treatment_outcome",
        "methods_assay",
        "results_table",
    }
    chosen: set[str] = set()
    for index, unit in enumerate(units):
        tags = set(unit_tags(unit, targets, features.get(unit.unit_id)))
        near_selected = any(abs(index - selected_index) <= 1 for selected_index in selected_indexes)
        if unit.unit_id in selected or near_selected or (tags & review_tags and "low_value" not in tags):
            chosen.add(unit.unit_id)
    if len(chosen) <= max_units:
        return chosen
    priority: list[str] = []
    for index, unit in enumerate(units):
        near_selected = any(abs(index - selected_index) <= 1 for selected_index in selected_indexes)
        if unit.unit_id in selected or near_selected:
            priority.append(unit.unit_id)
    for unit in units:
        if unit.unit_id in chosen and unit.unit_id not in priority:
            priority.append(unit.unit_id)
    return set(priority[:max_units])


def reviewer_source_units_payload(
    *,
    units: list[SourceUnit],
    targets: list[Target],
    features: dict[str, UnitFeatures],
    primary_selection: dict[str, Any],
) -> list[dict[str, Any]]:
    selected = selected_unit_ids(primary_selection)
    reviewer_ids = reviewer_unit_ids(
        units=units,
        targets=targets,
        features=features,
        primary_selection=primary_selection,
    )
    tags_by_unit_id = {
        unit.unit_id: unit_tags(unit, targets, features.get(unit.unit_id))
        for unit in units
        if unit.unit_id in reviewer_ids
    }
    visible_units = [unit for unit in units if unit.unit_id in reviewer_ids]
    return featured_source_units_payload(
        visible_units,
        features,
        selected_unit_ids=selected,
        tags_by_unit_id=tags_by_unit_id,
    )


def reviewer_user_payload(
    *,
    prepared_source: PreparedSource,
    targets: list[Target],
    units: list[SourceUnit],
    primary_selection: dict[str, Any],
) -> dict[str, Any]:
    features = build_unit_features(units, targets)
    return {
        "paper_id": prepared_source.paper_id,
        "declared_targets": [
            {"id": target.target_id, "kind": target.target_kind, "label": target.label}
            for target in targets
        ],
        "primary_selection": {
            "targets": primary_selection.get("targets") or [],
            "segments": selected_segment_payloads(primary_selection),
            "manual_review_reasons": primary_selection.get("manual_review_reasons") or [],
        },
        "source_units": reviewer_source_units_payload(
            units=units,
            targets=targets,
            features=features,
            primary_selection=primary_selection,
        ),
        "review_rules": [
            "Approve only when target inventory and selected unit ids are complete and attributable.",
            "Add missed direct patient/group units and missed shared methods/results/discussion units.",
            "Use shared only for the same fact applying cleanly to every listed target.",
            "Do not mark patient-labelled comparative facts as shared.",
            "Prefer body, table, and discussion units over duplicate abstract units.",
            "Remove metadata, references, unrelated comparator cases, and generic background.",
            "Use manual_review_reasons when attribution or source eligibility remains unsafe.",
            "Every evidence or reason string must be 20 words or fewer.",
        ],
    }


def word_limited(value: str, limit: int = REVIEWER_EXPLANATION_WORD_LIMIT) -> str:
    words = str(value or "").strip().split()
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit])


def manual_review_patch(reason: str) -> dict[str, Any]:
    return {
        "decision": "manual_review",
        "target_additions": [],
        "additions": [],
        "removals": [],
        "manual_review_reasons": [reason],
    }


def request_openai_review_patch(
    *,
    prepared_source: PreparedSource,
    targets: list[Target],
    units: list[SourceUnit],
    primary_selection: dict[str, Any],
    model: str = DEFAULT_OPENAI_REVIEW_MODEL,
    api_key: str,
    reasoning_effort: str = DEFAULT_OPENAI_REVIEW_REASONING_EFFORT,
    max_output_tokens: int = DEFAULT_OPENAI_REVIEW_MAX_OUTPUT_TOKENS,
    trace_dir: Path | None = None,
    telemetry_rows: list[dict[str, str]] | None = None,
    telemetry_jsonl_path: Path | None = None,
    telemetry_csv_path: Path | None = None,
    telemetry_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ask GPT-5.4 to approve, patch, or reject the DeepSeek unit selection."""

    if OpenAI is None:
        raise RuntimeError("The openai package is not installed.")

    user_payload = reviewer_user_payload(
        prepared_source=prepared_source,
        targets=targets,
        units=units,
        primary_selection=primary_selection,
    )
    request_trace_path = ""
    response_trace_path = ""
    meta_trace_path = ""
    trace_suffix = f"gpt54_review_{reasoning_effort}"
    if trace_dir is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)
        request_path = trace_dir / f"{prepared_source.paper_id}.{trace_suffix}.request.json"
        request_path.write_text(
            json.dumps(
                {
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "max_output_tokens": max_output_tokens,
                    "system_prompt": REVIEWER_SYSTEM_PROMPT,
                    "user_payload": user_payload,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        request_trace_path = relative_to_repo(request_path)

    client = OpenAI(api_key=api_key)
    started_at = now_utc_iso()
    started_counter = time.perf_counter()
    try:
        response = client.responses.create(
            model=model,
            store=False,
            input=[
                {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            reasoning={"effort": reasoning_effort},
            text={
                "format": {
                    "type": "json_schema",
                    "name": "stage07_unit_review_patch",
                    "schema": REVIEW_PATCH_RESPONSE_SCHEMA,
                    "strict": True,
                },
                "verbosity": "low",
            },
            max_output_tokens=max_output_tokens,
        )
    except Exception as exc:
        row = reviewer_telemetry_row(
            prepared_source=prepared_source,
            model=model,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
            telemetry_context=telemetry_context,
            started_at=started_at,
            started_counter=started_counter,
            response_status=f"exception:{type(exc).__name__}",
            request_trace_path=request_trace_path,
        )
        record_telemetry_row(
            row,
            telemetry_rows=telemetry_rows,
            telemetry_jsonl_path=telemetry_jsonl_path,
            telemetry_csv_path=telemetry_csv_path,
        )
        raise

    output_text = getattr(response, "output_text", "") or ""
    if trace_dir is not None:
        response_path = trace_dir / f"{prepared_source.paper_id}.{trace_suffix}.response.txt"
        response_path.write_text(output_text, encoding="utf-8")
        meta_path = trace_dir / f"{prepared_source.paper_id}.{trace_suffix}.response.meta.json"
        meta_path.write_text(
            json.dumps(openai_response_metadata(response), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        response_trace_path = relative_to_repo(response_path)
        meta_trace_path = relative_to_repo(meta_path)

    row = reviewer_telemetry_row(
        prepared_source=prepared_source,
        model=model,
        reasoning_effort=reasoning_effort,
        max_output_tokens=max_output_tokens,
        telemetry_context=telemetry_context,
        started_at=started_at,
        started_counter=started_counter,
        response_status=str(getattr(response, "status", "") or "completed"),
        incomplete_reason=openai_incomplete_reason(response),
        usage=getattr(response, "usage", None),
        request_trace_path=request_trace_path,
        response_trace_path=response_trace_path,
        meta_trace_path=meta_trace_path,
    )
    if getattr(response, "status", "") == "incomplete":
        reason = f"gpt54_unit_reviewer_incomplete:{openai_incomplete_reason(response) or 'unknown'}"
        row["validation_status"] = "manual_review_required"
        row["manual_review_reasons"] = reason
        record_telemetry_row(
            row,
            telemetry_rows=telemetry_rows,
            telemetry_jsonl_path=telemetry_jsonl_path,
            telemetry_csv_path=telemetry_csv_path,
        )
        return manual_review_patch(reason)
    try:
        patch = extract_json_object(output_text)
    except json.JSONDecodeError as exc:
        reason = "gpt54_unit_reviewer_empty_response" if not output_text.strip() else "gpt54_unit_reviewer_invalid_json"
        row["response_status"] = f"invalid_json:{type(exc).__name__}"
        row["validation_status"] = "manual_review_required"
        row["validation_errors"] = reason
        row["manual_review_reasons"] = reason
        record_telemetry_row(
            row,
            telemetry_rows=telemetry_rows,
            telemetry_jsonl_path=telemetry_jsonl_path,
            telemetry_csv_path=telemetry_csv_path,
        )
        return manual_review_patch(reason)

    record_telemetry_row(
        row,
        telemetry_rows=telemetry_rows,
        telemetry_jsonl_path=telemetry_jsonl_path,
        telemetry_csv_path=telemetry_csv_path,
    )
    return normalise_review_patch(patch)


def openai_incomplete_reason(response: Any) -> str:
    details = getattr(response, "incomplete_details", None)
    if details is None:
        return ""
    if isinstance(details, dict):
        return str(details.get("reason") or "")
    return str(getattr(details, "reason", "") or "")


def reviewer_telemetry_row(
    *,
    prepared_source: PreparedSource,
    model: str,
    reasoning_effort: str,
    max_output_tokens: int,
    telemetry_context: dict[str, Any] | None,
    started_at: str,
    started_counter: float,
    response_status: str,
    incomplete_reason: str = "",
    usage: Any = None,
    request_trace_path: str = "",
    response_trace_path: str = "",
    meta_trace_path: str = "",
) -> dict[str, str]:
    context = telemetry_context or {}
    return telemetry_row(
        benchmark_run_id=str(context.get("benchmark_run_id") or ""),
        matrix_config_name=str(context.get("matrix_config_name") or ""),
        paper_id=prepared_source.paper_id,
        provider="openai",
        model=model,
        endpoint="responses",
        architecture_variant=str(context.get("architecture_variant") or "unit_ids_reviewed_gpt54"),
        reasoning_effort=reasoning_effort,
        max_output_tokens=max_output_tokens,
        strict_json_schema=True,
        prompt_hash=hashlib.sha256(REVIEWER_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        schema_hash=sha256_json(REVIEW_PATCH_RESPONSE_SCHEMA),
        started_at_utc=started_at,
        finished_at_utc=now_utc_iso(),
        latency_ms=round((time.perf_counter() - started_counter) * 1000),
        response_status=response_status,
        incomplete_reason=incomplete_reason,
        usage=usage,
        trace_request_path=request_trace_path,
        trace_response_path=response_trace_path,
        trace_meta_path=meta_trace_path,
    )


def normalise_review_patch(patch: dict[str, Any]) -> dict[str, Any]:
    decision = str(patch.get("decision") or "manual_review")
    if decision not in {"approve", "patch", "manual_review"}:
        decision = "manual_review"
    return {
        "decision": decision,
        "target_additions": [
            {
                "id": str(target.get("id") or "").strip(),
                "kind": str(target.get("kind") or "").strip(),
                "label": str(target.get("label") or "").strip(),
                "evidence": word_limited(str(target.get("evidence") or "")),
            }
            for target in patch.get("target_additions") or []
            if str(target.get("id") or "").strip()
        ],
        "additions": [
            {
                "targets": [str(target).strip() for target in segment.get("targets") or [] if str(target).strip()],
                "role": str(segment.get("role") or "").strip(),
                "confidence": str(segment.get("confidence") or "unspecified").strip(),
                "evidence": word_limited(str(segment.get("evidence") or "")),
                "unit_ids": [str(unit_id).strip() for unit_id in segment.get("unit_ids") or [] if str(unit_id).strip()],
            }
            for segment in patch.get("additions") or []
        ],
        "removals": [
            {
                "unit_ids": [str(unit_id).strip() for unit_id in removal.get("unit_ids") or [] if str(unit_id).strip()],
                "reason": word_limited(str(removal.get("reason") or "")),
            }
            for removal in patch.get("removals") or []
        ],
        "manual_review_reasons": [
            word_limited(str(reason))
            for reason in patch.get("manual_review_reasons") or []
            if str(reason).strip()
        ],
    }


def merge_review_patch(
    *,
    primary_selection: dict[str, Any],
    review_patch: dict[str, Any],
) -> dict[str, Any]:
    """Apply a reviewer patch while preserving the unit-id selection contract."""

    merged = copy.deepcopy(primary_selection)
    merged["annotation_mode"] = "deepseek_unit_id_selection_gpt54_reviewed"
    validation_warnings = [
        str(warning)
        for warning in merged.get("validation_warnings") or []
        if str(warning).strip()
    ]
    validation_warnings.append(f"gpt54_review_decision:{review_patch.get('decision') or 'unknown'}")
    manual_review_reasons = [
        str(reason)
        for reason in merged.get("manual_review_reasons") or []
        if str(reason).strip()
    ]
    manual_review_reasons.extend(str(reason) for reason in review_patch.get("manual_review_reasons") or [])
    if review_patch.get("decision") == "manual_review" and not review_patch.get("manual_review_reasons"):
        manual_review_reasons.append("gpt54_reviewer_manual_review")

    target_ids = {str(target.get("id") or "") for target in merged.get("targets") or [] if isinstance(target, dict)}
    targets = list(merged.get("targets") or [])
    for target in review_patch.get("target_additions") or []:
        target_id = str(target.get("id") or "")
        if target_id and target_id not in target_ids:
            targets.append(target)
            target_ids.add(target_id)

    remove_ids: set[str] = set()
    for removal in review_patch.get("removals") or []:
        remove_ids.update(removal.get("unit_ids") or [])
    segments: list[dict[str, Any]] = []
    occupied: set[str] = set()
    for segment in merged.get("segments") or []:
        kept_ids = [
            str(unit_id).strip()
            for unit_id in segment.get("unit_ids") or []
            if str(unit_id).strip() and str(unit_id).strip() not in remove_ids
        ]
        if not kept_ids:
            continue
        segment = copy.deepcopy(segment)
        segment["unit_ids"] = kept_ids
        segments.append(segment)
        occupied.update(kept_ids)
    for addition in review_patch.get("additions") or []:
        unit_ids = [unit_id for unit_id in addition.get("unit_ids") or [] if unit_id not in occupied]
        if not unit_ids:
            validation_warnings.append("gpt54_reviewer_duplicate_addition_skipped")
            continue
        segment = copy.deepcopy(addition)
        segment["unit_ids"] = unit_ids
        segments.append(segment)
        occupied.update(unit_ids)

    merged["targets"] = targets
    merged["segments"] = segments
    merged["manual_review_reasons"] = sorted(set(manual_review_reasons))
    merged["validation_warnings"] = sorted(set(validation_warnings))
    return merged


def estimated_paid_cost(telemetry_rows: list[dict[str, str]] | None) -> float:
    return sum(float(row.get("estimated_cost_usd") or 0.0) for row in telemetry_rows or [])


def cap_reached(max_cost_usd: float, telemetry_rows: list[dict[str, str]] | None) -> bool:
    return max_cost_usd > 0 and estimated_paid_cost(telemetry_rows) >= max_cost_usd


def annotate_with_deepseek_openai_reviewed_units(
    *,
    prepared_source: PreparedSource,
    targets: list[Target],
    deepseek_model: str = DEFAULT_DEEPSEEK_MODEL,
    deepseek_api_key: str = "",
    openai_model: str = DEFAULT_OPENAI_REVIEW_MODEL,
    openai_api_key: str,
    openai_reasoning_effort: str = DEFAULT_OPENAI_REVIEW_REASONING_EFFORT,
    trace_dir: Path | None = None,
    deepseek_max_output_tokens: int = DEFAULT_DEEPSEEK_MAX_OUTPUT_TOKENS,
    openai_max_output_tokens: int = DEFAULT_OPENAI_REVIEW_MAX_OUTPUT_TOKENS,
    telemetry_rows: list[dict[str, str]] | None = None,
    telemetry_jsonl_path: Path | None = None,
    telemetry_csv_path: Path | None = None,
    telemetry_context: dict[str, Any] | None = None,
    deepseek_request_timeout_seconds: float | None = DEFAULT_DEEPSEEK_REQUEST_TIMEOUT_SECONDS,
    max_paid_api_cost_usd: float = 0.0,
    primary_selection_payload: dict[str, Any] | None = None,
    review_patch_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run or replay the DeepSeek primary plus GPT reviewer architecture."""

    units = build_source_units(prepared_source)
    if primary_selection_payload is None:
        primary_selection_payload = request_deepseek_primary_selection(
            prepared_source=prepared_source,
            targets=targets,
            model=deepseek_model,
            api_key=deepseek_api_key,
            trace_dir=trace_dir,
            max_output_tokens=deepseek_max_output_tokens,
            telemetry_rows=telemetry_rows,
            telemetry_jsonl_path=telemetry_jsonl_path,
            telemetry_csv_path=telemetry_csv_path,
            telemetry_context=telemetry_context,
            request_timeout_seconds=deepseek_request_timeout_seconds,
        )
    if review_patch_payload is None:
        if cap_reached(max_paid_api_cost_usd, telemetry_rows):
            review_patch_payload = manual_review_patch("budget_cap_exceeded_before_gpt54_review")
        else:
            review_patch_payload = request_openai_review_patch(
                prepared_source=prepared_source,
                targets=targets,
                units=units,
                primary_selection=primary_selection_payload,
                model=openai_model,
                api_key=openai_api_key,
                reasoning_effort=openai_reasoning_effort,
                max_output_tokens=openai_max_output_tokens,
                trace_dir=trace_dir,
                telemetry_rows=telemetry_rows,
                telemetry_jsonl_path=telemetry_jsonl_path,
                telemetry_csv_path=telemetry_csv_path,
                telemetry_context=telemetry_context,
            )
    else:
        review_patch_payload = normalise_review_patch(review_patch_payload)
    merged = merge_review_patch(
        primary_selection=primary_selection_payload,
        review_patch=review_patch_payload,
    )
    return compile_unit_selection_payload(
        selection_payload=merged,
        prepared_source=prepared_source,
        units=units,
    )
