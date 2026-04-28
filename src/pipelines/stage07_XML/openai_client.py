"""OpenAI adapter for Stage 07 XML span annotation.

This module deliberately keeps provider-specific concerns away from the core
Stage 07 compiler. The core pipeline validates offsets, tags source text, and
builds target views; this adapter only prepares the model request, enforces the
expected JSON shape, and records trace metadata that is useful for later
benchmarking.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import PreparedSource, Target, relative_to_repo, source_blocks_payload
from stage07_benchmarking.telemetry import (
    append_telemetry_csv,
    append_telemetry_jsonl,
    telemetry_row,
)

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover - exercised when OpenAI is not installed
    OpenAI = None


DEFAULT_OPENAI_REASONING_EFFORT = "medium"
DEFAULT_OPENAI_MAX_OUTPUT_TOKENS = 25000


# The prompt asks for source-backed spans, not final target-view text. Python
# remains responsible for validating offsets and compiling LangExtract inputs so
# that model output cannot silently rewrite the source.
SYSTEM_PROMPT = """\
You prepare source-backed Stage 07 span metadata for a systematic review of stiff person spectrum disorder.

Return JSON only. Do not rewrite the source text. Do not return XML.

For every useful segment, return paragraph block coordinates:
- block_id
- start_offset
- end_offset
- selected_text

The selected_text must exactly equal block_text[start_offset:end_offset].
Prefer coherent sentence or paragraph spans. Do not invent patients, groups, findings, or targets.
Use the declared target labels as the paper's native patient labels.
For statements that apply to multiple declared patients, use all relevant patient IDs with role "shared".
Do not create a group target merely for all-patient context in an individual case split.
Use only declared target IDs unless an explicit source-backed group target is needed, or a group-routed paper has explicit source-backed individual case units.
Return an empty top-level targets array when no extra source-backed targets are needed.
For single-patient papers, exclude front matter, library coversheets, references, author bios, and generic disease-context sections unless they contain facts about the patient.
For tables in mixed cohorts, use prose to identify which case/patient rows are SPSD-relevant, and select only those rows when the source text makes row boundaries clear.
Split spans around OCR page headers, footers, figure legends, and interrupted words instead of fabricating continuous text.
For lab-heavy group papers without declared patient units, return sparse clinical/sample-population and clinically relevant group findings only.
""".strip()


STAGE07_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "targets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "kind": {"type": "string"},
                    "label": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["id", "kind", "label", "evidence"],
                "additionalProperties": False,
            },
        },
        "segments": {
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
                    "spans": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "block_id": {"type": "string"},
                                "start_offset": {"type": "integer"},
                                "end_offset": {"type": "integer"},
                                "selected_text": {"type": "string"},
                            },
                            "required": [
                                "block_id",
                                "start_offset",
                                "end_offset",
                                "selected_text",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["targets", "role", "confidence", "evidence", "spans"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["targets", "segments"],
    "additionalProperties": False,
}


def response_metadata(response: Any) -> dict[str, Any]:
    """Return a compact, JSON-serialisable response summary for trace files.

    Raw response traces can be useful during failure analysis, but the benchmark
    loop mostly needs status, truncation details, and token accounting. Keeping
    those fields in a small sidecar file makes later comparisons less dependent
    on the OpenAI SDK's full response object shape.
    """

    usage = getattr(response, "usage", None)
    incomplete_details = getattr(response, "incomplete_details", None)
    if hasattr(usage, "model_dump"):
        try:
            usage_payload = usage.model_dump(mode="json")
        except TypeError:
            usage_payload = usage.model_dump()
    elif isinstance(usage, dict):
        usage_payload = usage
    else:
        usage_payload = None
    if hasattr(incomplete_details, "model_dump"):
        try:
            incomplete_payload = incomplete_details.model_dump(mode="json")
        except TypeError:
            incomplete_payload = incomplete_details.model_dump()
    elif isinstance(incomplete_details, dict):
        incomplete_payload = incomplete_details
    else:
        incomplete_payload = None
    return {
        "id": getattr(response, "id", ""),
        "model": getattr(response, "model", ""),
        "status": getattr(response, "status", ""),
        "incomplete_details": incomplete_payload,
        "usage": usage_payload,
    }


def incomplete_reason(response: Any) -> str:
    """Extract the SDK-independent reason for an incomplete response."""

    details = getattr(response, "incomplete_details", None)
    if details is None:
        return ""
    if isinstance(details, dict):
        return str(details.get("reason") or "")
    return str(getattr(details, "reason", "") or "")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def build_user_payload(
    *,
    prepared_source: PreparedSource,
    targets: list[Target],
) -> dict[str, Any]:
    """Build the model-visible source and schema example.

    The payload exposes already-numbered paragraph blocks and declared targets.
    It does not include downstream registry paths or local file locations, which
    keeps the model focused on the attribution task and avoids leaking machine
    specific details into traces.
    """

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
        "allowed_roles": [
            "patient_specific",
            "shared",
            "group_summary",
            "group_specific",
            "uncertain",
            "background",
        ],
        "blocks": source_blocks_payload(prepared_source.blocks),
        "required_output_shape": {
            "targets": [
                {
                    "id": "g2",
                    "kind": "group",
                    "label": "Only if explicitly source-backed",
                    "evidence": "Exact text justifying the extra group target",
                }
            ],
            "segments": [
                {
                    "targets": ["p1"],
                    "role": "patient_specific",
                    "confidence": "high",
                    "evidence": "Brief source-backed reason",
                    "spans": [
                        {
                            "block_id": "b0001",
                            "start_offset": 0,
                            "end_offset": 12,
                            "selected_text": "Exact source",
                        }
                    ],
                }
            ],
        },
    }


def annotate_with_openai(
    *,
    prepared_source: PreparedSource,
    targets: list[Target],
    model: str,
    api_key: str,
    trace_dir: Path | None = None,
    max_output_tokens: int = DEFAULT_OPENAI_MAX_OUTPUT_TOKENS,
    reasoning_effort: str = DEFAULT_OPENAI_REASONING_EFFORT,
    strict_json_schema: bool = True,
    telemetry_rows: list[dict[str, str]] | None = None,
    telemetry_jsonl_path: Path | None = None,
    telemetry_csv_path: Path | None = None,
    telemetry_context: dict[str, Any] | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    retry_count: int = 0,
    retry_reason: str = "",
) -> dict[str, Any]:
    """Request Stage 07 span metadata from OpenAI and return parsed JSON.

    The defaults favour reliability over speed: strict schema output, medium
    reasoning effort, and enough output budget to cover hidden reasoning tokens.
    Paid execution is gated by the caller; this function assumes the caller has
    already resolved that policy decision.
    """

    if OpenAI is None:
        raise RuntimeError("The openai package is not installed.")
    user_payload = build_user_payload(prepared_source=prepared_source, targets=targets)
    request_trace_path = ""
    response_trace_path = ""
    meta_trace_path = ""
    if trace_dir is not None:
        # Trace requests include source text by design because Stage 07 debugging
        # needs exact provenance. API keys are never written here.
        trace_dir.mkdir(parents=True, exist_ok=True)
        request_path = trace_dir / f"{prepared_source.paper_id}.request.json"
        request_path.write_text(
            json.dumps(
                {
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "max_output_tokens": max_output_tokens,
                    "strict_json_schema": strict_json_schema,
                    "system_prompt": SYSTEM_PROMPT,
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
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            reasoning={"effort": reasoning_effort},
            text={
                "format": {
                    "type": "json_schema",
                    "name": "stage07_span_metadata",
                    "schema": STAGE07_RESPONSE_SCHEMA,
                    "strict": strict_json_schema,
                },
                "verbosity": "low",
            },
            max_output_tokens=max_output_tokens,
        )
    except Exception as exc:
        finished_at = now_utc_iso()
        latency_ms = round((time.perf_counter() - started_counter) * 1000)
        context = telemetry_context or {}
        row = telemetry_row(
            benchmark_run_id=str(context.get("benchmark_run_id") or ""),
            matrix_config_name=str(context.get("matrix_config_name") or ""),
            paper_id=prepared_source.paper_id,
            provider="openai",
            model=model,
            endpoint="responses",
            architecture_variant=str(context.get("architecture_variant") or "block_offsets"),
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            top_p=top_p,
            strict_json_schema=strict_json_schema,
            prompt_hash=hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            schema_hash=sha256_json(STAGE07_RESPONSE_SCHEMA),
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
    output_text = getattr(response, "output_text", "")
    if trace_dir is not None:
        # Keep both the raw response and a small metadata sidecar. The sidecar is
        # what benchmark summaries should usually consume.
        response_path = trace_dir / f"{prepared_source.paper_id}.response.raw.json"
        response_path.write_text(
            response.model_dump_json(indent=2),
            encoding="utf-8",
        )
        (trace_dir / f"{prepared_source.paper_id}.response.txt").write_text(
            output_text,
            encoding="utf-8",
        )
        meta_path = trace_dir / f"{prepared_source.paper_id}.response.meta.json"
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
        provider="openai",
        model=model,
        endpoint="responses",
        architecture_variant=str(context.get("architecture_variant") or "block_offsets"),
        reasoning_effort=reasoning_effort,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        top_p=top_p,
        strict_json_schema=strict_json_schema,
        prompt_hash=hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        schema_hash=sha256_json(STAGE07_RESPONSE_SCHEMA),
        started_at_utc=started_at,
        finished_at_utc=finished_at,
        latency_ms=latency_ms,
        response_status=str(getattr(response, "status", "") or ""),
        incomplete_reason=incomplete_reason(response),
        usage=getattr(response, "usage", None),
        retry_count=retry_count,
        retry_reason=retry_reason,
        trace_request_path=request_trace_path,
        trace_response_path=response_trace_path,
        trace_meta_path=meta_trace_path,
    )
    record_telemetry_row(
        row,
        telemetry_rows=telemetry_rows,
        telemetry_jsonl_path=telemetry_jsonl_path,
        telemetry_csv_path=telemetry_csv_path,
    )
    if getattr(response, "status", "") == "incomplete":
        # Treat truncation as a hard failure rather than trying to parse partial
        # JSON; hidden reasoning tokens can exhaust the cap before visible output
        # is complete.
        reason = incomplete_reason(response)
        raise RuntimeError(
            f"OpenAI response was incomplete; reason={reason or 'unknown'} "
            f"max_output_tokens={max_output_tokens}"
        )
    if not output_text.strip():
        status = getattr(response, "status", "")
        incomplete_details = getattr(response, "incomplete_details", None)
        raise RuntimeError(
            f"OpenAI response did not contain output_text; status={status} "
            f"incomplete_details={incomplete_details}"
        )
    return json.loads(output_text)


def record_telemetry_row(
    row: dict[str, str],
    *,
    telemetry_rows: list[dict[str, str]] | None,
    telemetry_jsonl_path: Path | None,
    telemetry_csv_path: Path | None,
) -> None:
    if telemetry_rows is not None:
        telemetry_rows.append(row)
    if telemetry_jsonl_path is not None:
        append_telemetry_jsonl(telemetry_jsonl_path, row)
    if telemetry_csv_path is not None:
        append_telemetry_csv(telemetry_csv_path, row)
