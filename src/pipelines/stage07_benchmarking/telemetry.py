"""API telemetry and cost-estimation helpers for Stage 07 benchmarks.

Telemetry rows are deliberately small and secret-free. They link model calls to
benchmark runs and matrix configurations while keeping API keys, raw reasoning
content, and provider-specific private fields out of persistent artefacts.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TELEMETRY_SCHEMA_VERSION = "stage07_api_telemetry_v1"
PRICING_SCHEMA_VERSION = "stage07_provider_pricing_v1"


TELEMETRY_FIELDNAMES = [
    "schema_version",
    "benchmark_run_id",
    "matrix_config_name",
    "paper_id",
    "provider",
    "model",
    "endpoint",
    "architecture_variant",
    "reasoning_effort",
    "max_output_tokens",
    "temperature",
    "top_p",
    "strict_json_schema",
    "prompt_hash",
    "schema_hash",
    "started_at_utc",
    "finished_at_utc",
    "latency_ms",
    "response_status",
    "incomplete_reason",
    "input_tokens",
    "cached_input_tokens",
    "cache_miss_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "estimated_cost_usd",
    "pricing_version",
    "retry_count",
    "retry_reason",
    "validation_status",
    "validation_errors",
    "manual_review_reasons",
    "trace_request_path",
    "trace_response_path",
    "trace_meta_path",
]


DEFAULT_PRICING_TABLE: dict[str, Any] = {
    "schema_version": PRICING_SCHEMA_VERSION,
    "version": "2026-04-stage07-estimates",
    "currency": "USD",
    "unit": "per_1m_tokens",
    "models": {
        "openai:gpt-5.5": {
            "input": 5.0,
            "cached_input": 0.5,
            "output": 30.0,
        },
        "openai:gpt-5.4": {
            "input": 2.5,
            "cached_input": 0.25,
            "output": 15.0,
        },
        "deepseek:deepseek-v4-flash": {
            "input": 0.14,
            "cached_input": 0.0028,
            "output": 0.28,
        },
        "deepseek:deepseek-v4-pro": {
            "input": 0.435,
            "cached_input": 0.003625,
            "output": 0.87,
        },
    },
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def nested_value(payload: dict[str, Any], path: list[str], default: int = 0) -> int:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    try:
        return int(current or 0)
    except (TypeError, ValueError):
        return default


def normalise_usage(usage: Any) -> dict[str, int]:
    """Return provider-neutral token counts from OpenAI or chat-style usage."""

    if hasattr(usage, "model_dump"):
        try:
            usage = usage.model_dump(mode="json")
        except TypeError:
            usage = usage.model_dump()
    if not isinstance(usage, dict):
        usage = {}
    input_tokens = nested_value(usage, ["input_tokens"]) or nested_value(usage, ["prompt_tokens"])
    output_tokens = nested_value(usage, ["output_tokens"]) or nested_value(usage, ["completion_tokens"])
    reasoning_tokens = (
        nested_value(usage, ["output_tokens_details", "reasoning_tokens"])
        or nested_value(usage, ["completion_tokens_details", "reasoning_tokens"])
        or nested_value(usage, ["reasoning_tokens"])
    )
    cached_input_tokens = (
        nested_value(usage, ["input_tokens_details", "cached_tokens"])
        or nested_value(usage, ["prompt_tokens_details", "cached_tokens"])
        or nested_value(usage, ["prompt_cache_hit_tokens"])
        or nested_value(usage, ["cache_hit_input_tokens"])
    )
    cache_miss_input_tokens = (
        nested_value(usage, ["prompt_cache_miss_tokens"])
        or nested_value(usage, ["cache_miss_input_tokens"])
    )
    if not cache_miss_input_tokens:
        cache_miss_input_tokens = max(0, input_tokens - cached_input_tokens)
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "cache_miss_input_tokens": cache_miss_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


def pricing_key(provider: str, model: str) -> str:
    return f"{provider.strip().casefold()}:{model.strip()}"


def estimate_cost_usd(
    *,
    provider: str,
    model: str,
    usage: dict[str, int],
    pricing_table: dict[str, Any] | None = None,
) -> float:
    """Estimate provider cost from recorded token counts.

    Reasoning tokens are not charged separately here because providers generally
    include them in output/completion tokens. If a future provider bills them
    separately, add a separate pricing field rather than double-counting.
    """

    table = pricing_table or DEFAULT_PRICING_TABLE
    model_prices = (table.get("models") or {}).get(pricing_key(provider, model), {})
    if not model_prices:
        return 0.0
    cached_input = int(usage.get("cached_input_tokens") or 0)
    miss_input = int(usage.get("cache_miss_input_tokens") or 0)
    if not cached_input and not miss_input:
        miss_input = int(usage.get("input_tokens") or 0)
    output = int(usage.get("output_tokens") or 0)
    return (
        miss_input * float(model_prices.get("input") or 0.0)
        + cached_input * float(model_prices.get("cached_input") or model_prices.get("input") or 0.0)
        + output * float(model_prices.get("output") or 0.0)
    ) / 1_000_000


def joined(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    return str(value)


def telemetry_row(
    *,
    benchmark_run_id: str = "",
    matrix_config_name: str = "",
    paper_id: str = "",
    provider: str = "",
    model: str = "",
    endpoint: str = "",
    architecture_variant: str = "",
    reasoning_effort: str = "",
    max_output_tokens: int | str | None = None,
    temperature: float | str | None = None,
    top_p: float | str | None = None,
    strict_json_schema: bool | str | None = None,
    prompt_hash: str = "",
    schema_hash: str = "",
    started_at_utc: str = "",
    finished_at_utc: str = "",
    latency_ms: int | str | None = None,
    response_status: str = "",
    incomplete_reason: str = "",
    usage: Any = None,
    retry_count: int | str = 0,
    retry_reason: str = "",
    validation_status: str = "",
    validation_errors: Any = None,
    manual_review_reasons: Any = None,
    trace_request_path: str = "",
    trace_response_path: str = "",
    trace_meta_path: str = "",
    pricing_table: dict[str, Any] | None = None,
) -> dict[str, str]:
    normalised_usage = normalise_usage(usage)
    estimated_cost = estimate_cost_usd(
        provider=provider,
        model=model,
        usage=normalised_usage,
        pricing_table=pricing_table,
    )
    table = pricing_table or DEFAULT_PRICING_TABLE
    row = {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "benchmark_run_id": benchmark_run_id,
        "matrix_config_name": matrix_config_name,
        "paper_id": paper_id,
        "provider": provider,
        "model": model,
        "endpoint": endpoint,
        "architecture_variant": architecture_variant,
        "reasoning_effort": reasoning_effort,
        "max_output_tokens": "" if max_output_tokens is None else str(max_output_tokens),
        "temperature": "" if temperature is None else str(temperature),
        "top_p": "" if top_p is None else str(top_p),
        "strict_json_schema": "" if strict_json_schema is None else str(strict_json_schema).lower(),
        "prompt_hash": prompt_hash,
        "schema_hash": schema_hash,
        "started_at_utc": started_at_utc,
        "finished_at_utc": finished_at_utc,
        "latency_ms": "" if latency_ms is None else str(latency_ms),
        "response_status": response_status,
        "incomplete_reason": incomplete_reason,
        "input_tokens": str(normalised_usage["input_tokens"]),
        "cached_input_tokens": str(normalised_usage["cached_input_tokens"]),
        "cache_miss_input_tokens": str(normalised_usage["cache_miss_input_tokens"]),
        "output_tokens": str(normalised_usage["output_tokens"]),
        "reasoning_tokens": str(normalised_usage["reasoning_tokens"]),
        "estimated_cost_usd": f"{estimated_cost:.8f}",
        "pricing_version": str(table.get("version") or ""),
        "retry_count": str(retry_count),
        "retry_reason": retry_reason,
        "validation_status": validation_status,
        "validation_errors": joined(validation_errors),
        "manual_review_reasons": joined(manual_review_reasons),
        "trace_request_path": trace_request_path,
        "trace_response_path": trace_response_path,
        "trace_meta_path": trace_meta_path,
    }
    return {fieldname: row.get(fieldname, "") for fieldname in TELEMETRY_FIELDNAMES}


def write_telemetry_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TELEMETRY_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({fieldname: row.get(fieldname, "") for fieldname in TELEMETRY_FIELDNAMES})


def write_telemetry_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def append_telemetry_jsonl(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_telemetry_csv(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TELEMETRY_FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerow({fieldname: row.get(fieldname, "") for fieldname in TELEMETRY_FIELDNAMES})


def load_telemetry_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    if path.suffix.casefold() == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            return [{field: str(row.get(field) or "") for field in TELEMETRY_FIELDNAMES} for row in csv.DictReader(handle)]
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            rows.append({field: str(payload.get(field) or "") for field in TELEMETRY_FIELDNAMES})
    return rows


def telemetry_call_identity(row: dict[str, str]) -> tuple[str, ...] | None:
    """Return a stable cross-format identity for a recorded API call."""

    fields = [
        "provider",
        "model",
        "endpoint",
        "paper_id",
        "started_at_utc",
        "prompt_hash",
        "schema_hash",
        "trace_request_path",
    ]
    identity = tuple(str(row.get(field) or "") for field in fields)
    if any(identity):
        return identity
    return None


def estimated_cost_from_telemetry_paths(paths: list[Path | None]) -> float:
    """Sum telemetry costs once, even when the same rows exist as CSV and JSONL."""

    seen_calls: set[tuple[str, ...]] = set()
    total = 0.0
    for path in paths:
        if path is None or not path.exists():
            continue
        for row in load_telemetry_rows(path):
            identity = telemetry_call_identity(row)
            if identity is not None:
                if identity in seen_calls:
                    continue
                seen_calls.add(identity)
            try:
                total += float(row.get("estimated_cost_usd") or 0.0)
            except ValueError:
                continue
    return total
