"""DeepSeek adapter for compact Stage 07 unit-id selection."""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import (
    PreparedSource,
    Target,
    allowed_roles_for_targets,
    build_unit_features,
    build_source_units,
    compile_unit_selection_payload,
    featured_source_units_payload,
    relative_to_repo,
)
from .openai_client import record_telemetry_row, sha256_json
from stage07_benchmarking.telemetry import telemetry_row

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover - exercised when OpenAI is not installed
    OpenAI = None


DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"
DEFAULT_DEEPSEEK_MAX_OUTPUT_TOKENS = 24000
DEFAULT_DEEPSEEK_REQUEST_TIMEOUT_SECONDS = 3600.0


SYSTEM_PROMPT = """\
You assign fixed source units to fixed current-paper SPSD targets.

Return JSON only. Do not include reasoning. Do not rewrite source text.
Select only supplied unit IDs and target IDs. Python compiles exact source text
and offsets, so never invent offsets, quotes, patients, groups, or facts.

Rules:
- Current-paper targets are the declared targets only.
- Do not assign cited-report patients, controls, normal subjects, comparator cohorts, or previous-paper patients to current targets.
- Include demographic, clinical, diagnostic, laboratory, imaging, pathology, treatment, outcome, sample, specimen, assay, or follow-up units about current targets.
- If a unit describes an assay using current-patient serum, CSF, tissue, tumour, or other samples, it may remain relevant even when controls are mentioned. Assign only the current target samples used.
- Use patient_specific for exactly one patient target; shared for multiple patient targets; group_summary or group_specific for group targets.
- Exclude comparator-only, control-only, background-only, reference, metadata, and cited-literature units.
- OCR variants such as "Patient |" may mean "Patient 1"; pronouns may continue the most recent current target.
- Do not infer individual-level facts from aggregate wording.
- Return manual_review_reasons only when the extraction itself needs human review.
""".strip()


UNIT_SELECTION_RESPONSE_SCHEMA: dict[str, Any] = {
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


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return json.loads(stripped)


def response_metadata(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if hasattr(usage, "model_dump"):
        try:
            usage_payload = usage.model_dump(mode="json")
        except TypeError:
            usage_payload = usage.model_dump()
    elif isinstance(usage, dict):
        usage_payload = usage
    else:
        usage_payload = None
    return {
        "id": getattr(response, "id", ""),
        "model": getattr(response, "model", ""),
        "usage": usage_payload,
    }


def invalid_response_annotation(reason: str) -> dict[str, Any]:
    return {
        "annotation_mode": "deepseek_unit_id_selection_invalid_json",
        "route_mode": "",
        "targets": [],
        "segments": [],
        "validation_warnings": [reason],
        "manual_review_reasons": [reason],
    }


def build_user_payload(
    *,
    prepared_source: PreparedSource,
    targets: list[Target],
) -> dict[str, Any]:
    # Source units are the token-saving abstraction for the cheap path: the
    # model selects IDs, then Python reconstructs exact offsets and text.
    units = build_source_units(prepared_source)
    features = build_unit_features(units, targets)
    return {
        "paper_id": prepared_source.paper_id,
        "declared_targets": [
            {
                "id": target.target_id,
                "kind": target.target_kind,
                "label": target.label,
            }
            for target in targets
        ],
        "allowed_roles": allowed_roles_for_targets(targets),
        "source_units": featured_source_units_payload(units, features),
        "required_output_shape": UNIT_SELECTION_RESPONSE_SCHEMA,
    }


def annotate_with_deepseek_units(
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
    retry_count: int = 0,
    retry_reason: str = "",
) -> dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("The openai package is not installed.")

    user_payload = build_user_payload(prepared_source=prepared_source, targets=targets)
    request_trace_path = ""
    response_trace_path = ""
    meta_trace_path = ""
    if trace_dir is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)
        request_path = trace_dir / f"{prepared_source.paper_id}.unit_selection.request.json"
        request_path.write_text(
            json.dumps(
                {
                    "model": model,
                    "max_output_tokens": max_output_tokens,
                    "request_timeout_seconds": request_timeout_seconds,
                    "system_prompt": SYSTEM_PROMPT,
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
        # DeepSeek uses the OpenAI-compatible chat endpoint here. We request a
        # JSON object and discard hidden reasoning; only selected unit IDs are
        # compiled into downstream artefacts.
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            max_tokens=max_output_tokens,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
    except Exception as exc:
        finished_at = now_utc_iso()
        latency_ms = round((time.perf_counter() - started_counter) * 1000)
        context = telemetry_context or {}
        row = telemetry_row(
            benchmark_run_id=str(context.get("benchmark_run_id") or ""),
            matrix_config_name=str(context.get("matrix_config_name") or ""),
            paper_id=prepared_source.paper_id,
            provider="deepseek",
            model=model,
            endpoint="chat_completions",
            architecture_variant=str(context.get("architecture_variant") or "unit_ids"),
            reasoning_effort="high",
            max_output_tokens=max_output_tokens,
            prompt_hash=hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            schema_hash=sha256_json(UNIT_SELECTION_RESPONSE_SCHEMA),
            started_at_utc=started_at,
            finished_at_utc=finished_at,
            latency_ms=latency_ms,
            response_status=f"exception:{type(exc).__name__}",
            retry_count=retry_count,
            retry_reason=retry_reason,
            trace_request_path=request_trace_path,
        )
        record_telemetry_row(
            row,
            telemetry_rows=telemetry_rows,
            telemetry_jsonl_path=telemetry_jsonl_path,
            telemetry_csv_path=telemetry_csv_path,
        )
        raise

    finished_at = now_utc_iso()
    latency_ms = round((time.perf_counter() - started_counter) * 1000)
    content = response.choices[0].message.content or ""
    if trace_dir is not None:
        response_path = trace_dir / f"{prepared_source.paper_id}.unit_selection.response.txt"
        response_path.write_text(content, encoding="utf-8")
        meta_path = trace_dir / f"{prepared_source.paper_id}.unit_selection.response.meta.json"
        meta_path.write_text(
            json.dumps(response_metadata(response), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        response_trace_path = relative_to_repo(response_path)
        meta_trace_path = relative_to_repo(meta_path)

    context = telemetry_context or {}
    row = telemetry_row(
        benchmark_run_id=str(context.get("benchmark_run_id") or ""),
        matrix_config_name=str(context.get("matrix_config_name") or ""),
        paper_id=prepared_source.paper_id,
        provider="deepseek",
        model=model,
        endpoint="chat_completions",
        architecture_variant=str(context.get("architecture_variant") or "unit_ids"),
        reasoning_effort="high",
        max_output_tokens=max_output_tokens,
        prompt_hash=hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        schema_hash=sha256_json(UNIT_SELECTION_RESPONSE_SCHEMA),
        started_at_utc=started_at,
        finished_at_utc=finished_at,
        latency_ms=latency_ms,
        response_status="completed",
        usage=getattr(response, "usage", None),
        retry_count=retry_count,
        retry_reason=retry_reason,
        trace_request_path=request_trace_path,
        trace_response_path=response_trace_path,
        trace_meta_path=meta_trace_path,
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
        return invalid_response_annotation(reason)
    record_telemetry_row(
        row,
        telemetry_rows=telemetry_rows,
        telemetry_jsonl_path=telemetry_jsonl_path,
        telemetry_csv_path=telemetry_csv_path,
    )
    selection_payload["annotation_mode"] = str(selection_payload.get("annotation_mode") or "deepseek_unit_id_selection")
    return compile_unit_selection_payload(
        selection_payload=selection_payload,
        prepared_source=prepared_source,
    )
