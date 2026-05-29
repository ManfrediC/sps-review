from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / "resources" / "stage07_single_case_gold_json_index.csv"
MC_CASE_REPORT_PATH = REPO_ROOT / "examples" / "datasheet_examples_MC_Case_Report_Form.csv"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "validation" / "langextract_example_bootstrap"
DEFAULT_EXAMPLES_OUT_DIR = REPO_ROOT / "examples" / "langextract_bootstrap"
DEFAULT_GEMINI_ENV_FILE = REPO_ROOT / "env" / "gemini.env"
DEFAULT_OPENAI_ENV_FILE = REPO_ROOT / "env" / "openai_api_key.env"
DEFAULT_SPAN_PLAN_PATH = DEFAULT_OUTPUT_ROOT / "pilot_10" / "gold_source_span_plan.csv"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_OPENAI_REASONING_EFFORT = "low"
DEFAULT_OPENAI_MAX_OUTPUT_TOKENS = 8000
SOURCE_SHEET_NAME = "datasheet_examples_MC_Case_Report_Form.csv"

PROVENANCE_FIELDS = {"extractor", "Reference", "case_ID"}
EVIDENCE_MODES = {"exact_quote", "inferred_from_text", "not_found"}

REVIEW_FIELDNAMES = [
    "paper_id",
    "case_id",
    "field_name",
    "spreadsheet_value",
    "model_spreadsheet_value",
    "evidence_mode",
    "extraction_text",
    "char_start",
    "char_end",
    "supporting_snippets_json",
    "supports_manual_value",
    "reasoning_short",
    "validator_status",
    "review_status",
    "review_notes",
    "target_view_json_path",
]


@dataclass(frozen=True)
class PilotRecord:
    paper_id: str
    case_id: str
    target_view_json_path: Path
    source_text: str
    manual_fields: dict[str, str]


@dataclass(frozen=True)
class FieldGrounding:
    field_name: str
    spreadsheet_value: str
    evidence_mode: str
    extraction_text: str
    supporting_snippets: list[str]
    reasoning_short: str
    supports_manual_value: bool


@dataclass(frozen=True)
class BootstrappedCaseExample:
    paper_id: str
    case_id: str
    model_id: str
    field_groundings: list[FieldGrounding]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_path(path_text: str) -> Path:
    normalised = path_text.replace("\\", "/")
    path = Path(normalised)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_csv_rows_atomic(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    write_csv_rows(tmp_path, rows, fieldnames)
    tmp_path.replace(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_json_atomic(path: Path, payload: Any) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    write_json(tmp_path, payload)
    tmp_path.replace(path)


def load_stage07_text(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    text = (payload.get("input_text") or payload.get("text") or "").strip()
    if not text:
        raise ValueError(f"No Stage 07 input text found in {path}")
    return text


def manual_fields_from_row(row: dict[str, str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key, value in row.items():
        clean_key = (key or "").strip()
        clean_value = (value or "").strip()
        if not clean_key or not clean_value:
            continue
        if clean_key in PROVENANCE_FIELDS:
            continue
        fields[clean_key] = clean_value
    return fields


def manual_rows_by_reference(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    by_id: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        paper_id = (row.get("Reference") or "").strip()
        if paper_id:
            by_id.setdefault(paper_id, []).append(row)
    return by_id


def select_pilot_records(
    *,
    limit: int,
    explicit_ids: list[str],
    excluded_ids: list[str] | None = None,
    index_path: Path | None = None,
    manual_path: Path | None = None,
) -> list[PilotRecord]:
    index_rows = read_csv_rows(index_path or INDEX_PATH)
    manual_by_id = manual_rows_by_reference(read_csv_rows(manual_path or MC_CASE_REPORT_PATH))
    wanted = {paper_id.strip() for paper_id in explicit_ids if paper_id.strip()}
    excluded = {paper_id.strip() for paper_id in (excluded_ids or []) if paper_id.strip()}
    selected: list[PilotRecord] = []

    for index_row in index_rows:
        paper_id = (index_row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        if paper_id in excluded:
            continue
        if (index_row.get("manually_reviewed_MC") or "").strip() != "TRUE":
            continue
        if wanted and paper_id not in wanted:
            continue
        target_view_path = repo_path(index_row.get("stage07_target_view_json_path", ""))
        source_text = load_stage07_text(target_view_path)

        for manual_row in manual_by_id.get(paper_id, []):
            manual_fields = manual_fields_from_row(manual_row)
            if not manual_fields:
                continue
            selected.append(
                PilotRecord(
                    paper_id=paper_id,
                    case_id=(manual_row.get("case_ID") or "").strip(),
                    target_view_json_path=target_view_path,
                    source_text=source_text,
                    manual_fields=manual_fields,
                )
            )
            if not wanted and limit > 0 and len(selected) >= limit:
                return selected
    return selected


def build_bootstrap_prompt(record: PilotRecord) -> str:
    manual_payload = json.dumps(record.manual_fields, ensure_ascii=False, indent=2)
    return f"""
You are building grounded examples for an information extraction system.

You will receive:
1. Source text from one reviewed single-case SPSD paper.
2. A dictionary of manually extracted gold-standard spreadsheet fields.

For every provided field:
- Return exactly one field_groundings item.
- Preserve field_name exactly.
- Preserve spreadsheet_value exactly.
- If the value is directly quoteable, set evidence_mode to exact_quote and put
  the shortest verbatim supporting source phrase or sentence in extraction_text.
- If the value requires clinical inference from the text, set evidence_mode to
  inferred_from_text and provide one or more verbatim supporting snippets.
- If the value cannot be supported from the supplied text, set evidence_mode to
  not_found, set supports_manual_value to false, and leave extraction_text empty.
- Do not invent evidence.
- Do not use outside knowledge.
- Do not change the manual value.

Paper ID: {record.paper_id}
Case ID: {record.case_id}

Manual gold fields:
{manual_payload}

Source text:
\"\"\"
{record.source_text}
\"\"\"
""".strip()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def require_paid_run_approval(allow_paid_run: bool) -> None:
    if not allow_paid_run:
        raise SystemExit("Refusing to call a paid LLM API without --allow-paid-run.")


def response_schema_class() -> type[Any]:
    try:
        from pydantic import BaseModel, ConfigDict, Field
    except ImportError as exc:
        raise SystemExit("pydantic is required for paid response schema validation.") from exc

    class ModelFieldGrounding(BaseModel):
        model_config = ConfigDict(extra="forbid")

        field_name: str = Field(description="Manual spreadsheet column name.")
        spreadsheet_value: str = Field(description="Exact non-empty value from the manual row.")
        evidence_mode: str = Field(description="exact_quote, inferred_from_text, or not_found.")
        extraction_text: str = Field(description="Verbatim supporting text, or empty if not found.")
        supporting_snippets: list[str] = Field(description="Verbatim source snippets supporting inferred values.")
        reasoning_short: str = Field(description="Brief reviewer-facing explanation.")
        supports_manual_value: bool

    class ModelBootstrappedCaseExample(BaseModel):
        model_config = ConfigDict(extra="forbid")

        paper_id: str
        case_id: str
        model_id: str
        field_groundings: list[ModelFieldGrounding]

    return ModelBootstrappedCaseExample


def parse_model_payload(payload: dict[str, Any], *, paper_id: str, case_id: str, model_id: str) -> BootstrappedCaseExample:
    groundings: list[FieldGrounding] = []
    for item in payload.get("field_groundings") or []:
        if not isinstance(item, dict):
            continue
        snippets = item.get("supporting_snippets") or []
        if not isinstance(snippets, list):
            snippets = []
        groundings.append(
            FieldGrounding(
                field_name=str(item.get("field_name") or "").strip(),
                spreadsheet_value=str(item.get("spreadsheet_value") or "").strip(),
                evidence_mode=str(item.get("evidence_mode") or "").strip(),
                extraction_text=str(item.get("extraction_text") or "").strip(),
                supporting_snippets=[str(snippet).strip() for snippet in snippets if str(snippet).strip()],
                reasoning_short=str(item.get("reasoning_short") or "").strip(),
                supports_manual_value=parse_bool(item.get("supports_manual_value")),
            )
        )
    return BootstrappedCaseExample(
        paper_id=paper_id,
        case_id=case_id,
        model_id=model_id,
        field_groundings=groundings,
    )


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def run_gemini_bootstrap(
    record: PilotRecord,
    *,
    model_id: str,
    allow_paid_run: bool,
    env_file: Path,
) -> BootstrappedCaseExample:
    require_paid_run_approval(allow_paid_run)
    load_env_file(env_file)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set.")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise SystemExit("google-genai is required for paid Gemini bootstrapping.") from exc

    prompt = build_bootstrap_prompt(record)
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema_class(),
            temperature=0.0,
        ),
    )
    parsed_text = response.text or "{}"
    return parse_model_payload(
        json.loads(parsed_text),
        paper_id=record.paper_id,
        case_id=record.case_id,
        model_id=model_id,
    )


def run_openai_bootstrap(
    record: PilotRecord,
    *,
    model_id: str,
    allow_paid_run: bool,
    env_file: Path,
    reasoning_effort: str,
    max_output_tokens: int,
) -> BootstrappedCaseExample:
    require_paid_run_approval(allow_paid_run)
    load_env_file(env_file)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(f"OPENAI_API_KEY is not set. Checked environment and {repo_rel(env_file)}.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit("openai is required for paid OpenAI bootstrapping.") from exc

    schema = response_schema_class()
    prompt = build_bootstrap_prompt(record)
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model_id,
        store=False,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a systematic-review extraction auditor. Return only JSON that "
                    "matches the supplied schema. Ground every non-empty manual value in the "
                    "provided source text, and mark unsupported values as not_found."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        reasoning={"effort": reasoning_effort},
        text={
            "format": {
                "type": "json_schema",
                "name": "langextract_bootstrap_case_example",
                "schema": schema.model_json_schema(),
                "strict": True,
            },
            "verbosity": "low",
        },
        max_output_tokens=max_output_tokens,
    )

    if getattr(response, "status", "") == "incomplete":
        details = getattr(response, "incomplete_details", None)
        reason = getattr(details, "reason", "") if details is not None else ""
        raise RuntimeError(
            f"OpenAI response was incomplete for paper {record.paper_id}; "
            f"reason={reason or 'unknown'} max_output_tokens={max_output_tokens}"
        )
    output_text = getattr(response, "output_text", "")
    if not output_text.strip():
        raise RuntimeError(f"OpenAI response did not contain output_text for paper {record.paper_id}.")
    parsed = schema.model_validate_json(output_text)
    actual_model_id = str(getattr(response, "model", "") or model_id)
    return parse_model_payload(
        parsed.model_dump(mode="json"),
        paper_id=record.paper_id,
        case_id=record.case_id,
        model_id=actual_model_id,
    )


def retryable_gemini_error(exc: Exception) -> bool:
    message = str(exc)
    retryable_terms = (
        "503 UNAVAILABLE",
        "temporarily unavailable",
        "high demand",
        "try again later",
    )
    return any(term.lower() in message.lower() for term in retryable_terms)


def retryable_openai_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if any(term in message for term in ("insufficient_quota", "billing", "prepayment", "invalid_api_key")):
        return False
    status_code = getattr(exc, "status_code", None)
    if status_code in {408, 409, 429, 500, 502, 503, 504}:
        return True
    retryable_terms = (
        "temporarily unavailable",
        "rate limit",
        "timeout",
        "timed out",
        "server error",
        "connection",
    )
    return any(term in message for term in retryable_terms)


def retryable_provider_error(exc: Exception, provider: str) -> bool:
    if provider == "openai":
        return retryable_openai_error(exc)
    return retryable_gemini_error(exc)


def run_bootstrap(
    record: PilotRecord,
    *,
    args: argparse.Namespace,
) -> BootstrappedCaseExample:
    if args.provider == "openai":
        return run_openai_bootstrap(
            record,
            model_id=args.model_id,
            allow_paid_run=args.allow_paid_run,
            env_file=args.openai_env_file,
            reasoning_effort=args.openai_reasoning_effort,
            max_output_tokens=args.openai_max_output_tokens,
        )
    if args.provider == "gemini":
        return run_gemini_bootstrap(
            record,
            model_id=args.model_id,
            allow_paid_run=args.allow_paid_run,
            env_file=args.gemini_env_file,
        )
    raise ValueError(f"Unsupported provider: {args.provider}")


def run_gemini_bootstrap_with_retries(
    record: PilotRecord,
    *,
    args: argparse.Namespace,
) -> BootstrappedCaseExample:
    attempts_remaining = args.api_retries
    while True:
        try:
            return run_bootstrap(record, args=args)
        except Exception as exc:
            if attempts_remaining <= 0 or not retryable_provider_error(exc, args.provider):
                raise
            attempts_used = args.api_retries - attempts_remaining + 1
            print(
                f"{args.provider} transient failure for paper {record.paper_id}; "
                f"retry {attempts_used}/{args.api_retries} after "
                f"{args.api_retry_wait_seconds} seconds.",
                flush=True,
            )
            attempts_remaining -= 1
            time.sleep(args.api_retry_wait_seconds)


def find_text_span(source_text: str, snippet: str) -> tuple[int, int] | None:
    if not snippet:
        return None
    start = source_text.find(snippet)
    if start < 0:
        return None
    return start, start + len(snippet)


def support_snippet_failures(source_text: str, snippets: list[str]) -> list[str]:
    return [snippet for snippet in snippets if snippet and snippet not in source_text]


def validator_status_for_grounding(
    *,
    record: PilotRecord,
    item: FieldGrounding,
    expected_value: str,
    duplicate_field: bool,
) -> tuple[str, tuple[int, int] | None]:
    span = find_text_span(record.source_text, item.extraction_text)
    missing_support = support_snippet_failures(record.source_text, item.supporting_snippets)

    if duplicate_field:
        status = "duplicate_field_from_model_output"
    elif expected_value != item.spreadsheet_value:
        status = "manual_value_changed"
    elif item.evidence_mode not in EVIDENCE_MODES:
        status = "invalid_evidence_mode"
    elif item.evidence_mode == "exact_quote":
        status = "passed" if span else "quote_not_found"
    elif item.evidence_mode == "inferred_from_text":
        if span is None and item.extraction_text:
            status = "inference_anchor_not_found"
        elif not item.supporting_snippets:
            status = "inference_missing_supporting_snippets"
        elif missing_support:
            status = "inference_snippet_not_found"
        else:
            status = "passed"
    elif item.supports_manual_value:
        status = "not_found_supports_manual_value_conflict"
    else:
        status = "needs_review"
    return status, span


def review_row(
    *,
    record: PilotRecord,
    field_name: str,
    spreadsheet_value: str,
    model_spreadsheet_value: str,
    evidence_mode: str,
    extraction_text: str,
    span: tuple[int, int] | None,
    supporting_snippets: list[str],
    supports_manual_value: bool,
    reasoning_short: str,
    validator_status: str,
) -> dict[str, str]:
    return {
        "paper_id": record.paper_id,
        "case_id": record.case_id,
        "field_name": field_name,
        "spreadsheet_value": spreadsheet_value,
        "model_spreadsheet_value": model_spreadsheet_value,
        "evidence_mode": evidence_mode,
        "extraction_text": extraction_text,
        "char_start": "" if span is None else str(span[0]),
        "char_end": "" if span is None else str(span[1]),
        "supporting_snippets_json": json.dumps(supporting_snippets, ensure_ascii=False),
        "supports_manual_value": str(supports_manual_value).upper(),
        "reasoning_short": reasoning_short,
        "validator_status": validator_status,
        "review_status": "draft",
        "review_notes": "",
        "target_view_json_path": repo_rel(record.target_view_json_path),
    }


def validate_case_output(record: PilotRecord, output: BootstrappedCaseExample) -> list[dict[str, str]]:
    requested_fields = set(record.manual_fields)
    returned_fields = [item.field_name for item in output.field_groundings]
    returned_field_set = {field for field in returned_fields if field}
    duplicate_fields = {field for field in returned_fields if returned_fields.count(field) > 1}
    review_rows: list[dict[str, str]] = []

    for item in output.field_groundings:
        expected_value = record.manual_fields.get(item.field_name, "")
        if item.field_name not in requested_fields:
            status = "extra_field_from_model_output"
            span = find_text_span(record.source_text, item.extraction_text)
        else:
            status, span = validator_status_for_grounding(
                record=record,
                item=item,
                expected_value=expected_value,
                duplicate_field=item.field_name in duplicate_fields,
            )
        review_rows.append(
            review_row(
                record=record,
                field_name=item.field_name,
                spreadsheet_value=expected_value,
                model_spreadsheet_value=item.spreadsheet_value,
                evidence_mode=item.evidence_mode,
                extraction_text=item.extraction_text,
                span=span,
                supporting_snippets=item.supporting_snippets,
                supports_manual_value=item.supports_manual_value,
                reasoning_short=item.reasoning_short,
                validator_status=status,
            )
        )

    for field_name in sorted(requested_fields - returned_field_set):
        review_rows.append(
            review_row(
                record=record,
                field_name=field_name,
                spreadsheet_value=record.manual_fields[field_name],
                model_spreadsheet_value="",
                evidence_mode="",
                extraction_text="",
                span=None,
                supporting_snippets=[],
                supports_manual_value=False,
                reasoning_short="",
                validator_status="missing_from_model_output",
            )
        )

    extra_fields = sorted(returned_field_set - requested_fields)
    if extra_fields:
        review_rows.append(
            review_row(
                record=record,
                field_name="__extra_model_fields__",
                spreadsheet_value=";".join(extra_fields),
                model_spreadsheet_value="",
                evidence_mode="",
                extraction_text="",
                span=None,
                supporting_snippets=[],
                supports_manual_value=False,
                reasoning_short="",
                validator_status="extra_fields_from_model_output",
            )
        )
    return review_rows


def accepted_promotion_text(row: dict[str, str]) -> str:
    extraction_text = (row.get("extraction_text") or "").strip()
    if extraction_text:
        return extraction_text
    try:
        snippets = json.loads(row.get("supporting_snippets_json") or "[]")
    except json.JSONDecodeError:
        return ""
    if not isinstance(snippets, list):
        return ""
    return str(snippets[0]).strip() if snippets else ""


def build_langextract_examples_from_review(review_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    accepted = [
        row
        for row in review_rows
        if row.get("review_status") == "accepted"
        and row.get("validator_status") == "passed"
        and accepted_promotion_text(row)
    ]

    by_case: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in accepted:
        key = (
            row.get("paper_id", ""),
            row.get("case_id", ""),
            row.get("target_view_json_path", ""),
        )
        if key[0] and key[2]:
            by_case.setdefault(key, []).append(row)

    examples: list[dict[str, object]] = []
    for (paper_id, case_id, target_view_json_path), rows in sorted(by_case.items()):
        payload = json.loads(repo_path(target_view_json_path).read_text(encoding="utf-8"))
        text = normalise_example_text(payload.get("input_text") or payload.get("text") or "")
        extractions = [
            {
                "extraction_class": row["field_name"],
                "extraction_text": normalise_example_text(accepted_promotion_text(row)),
                "attributes": {
                    "value": row["spreadsheet_value"],
                    "case_id": case_id,
                    "evidence_mode": row["evidence_mode"],
                },
            }
            for row in rows
        ]
        examples.append(
            {
                "source_sheet": SOURCE_SHEET_NAME,
                "paper_id": paper_id,
                "case_id": case_id,
                "target_view_json_path": target_view_json_path,
                "text": text,
                "extractions": extractions,
            }
        )
    return examples


def load_support_spans(row: dict[str, str]) -> list[dict[str, object]]:
    try:
        payload = json.loads(row.get("support_spans_json") or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    spans: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        span_text = str(item.get("span_text") or "")
        if not span_text:
            continue
        try:
            char_start = int(item.get("char_start", ""))
            char_end = int(item.get("char_end", ""))
        except (TypeError, ValueError):
            continue
        spans.append(
            {
                "span_text": span_text,
                "char_start": char_start,
                "char_end": char_end,
                "span_role": str(item.get("span_role") or ""),
                "selection_source": str(item.get("selection_source") or ""),
                "match_mode": str(item.get("match_mode") or ""),
            }
        )
    return spans


def langextract_attributes(attributes: dict[str, object]) -> dict[str, str | list[str]]:
    coerced: dict[str, str | list[str]] = {}
    for key, value in attributes.items():
        if isinstance(value, list):
            coerced[key] = [normalise_example_text(str(item)) for item in value]
        else:
            coerced[key] = normalise_example_text(str(value))
    return coerced


def normalise_example_text(text: str) -> str:
    return " ".join(text.split())


def validate_span_plan_rows(span_plan_rows: list[dict[str, str]]) -> dict[str, object]:
    coverage_errors: list[dict[str, object]] = []
    span_count = 0
    by_quality: dict[str, int] = {}
    by_recommendation: dict[str, int] = {}

    for row in span_plan_rows:
        paper_id = row.get("paper_id", "")
        field_name = row.get("field_name", "")
        target_path = row.get("target_view_json_path", "")
        spans = load_support_spans(row)
        by_quality[row.get("coverage_quality", "")] = by_quality.get(row.get("coverage_quality", ""), 0) + 1
        recommendation = row.get("langextract_recommendation", "")
        by_recommendation[recommendation] = by_recommendation.get(recommendation, 0) + 1

        if not spans:
            coverage_errors.append(
                {
                    "paper_id": paper_id,
                    "field_name": field_name,
                    "error": "missing_support_spans",
                }
            )
            continue

        payload = json.loads(repo_path(target_path).read_text(encoding="utf-8"))
        source_text = (payload.get("input_text") or payload.get("text") or "")
        for span in spans:
            span_count += 1
            char_start = int(span["char_start"])
            char_end = int(span["char_end"])
            if source_text[char_start:char_end] != span["span_text"]:
                coverage_errors.append(
                    {
                        "paper_id": paper_id,
                        "field_name": field_name,
                        "error": "span_offset_mismatch",
                        "char_start": char_start,
                        "char_end": char_end,
                    }
                )

    return {
        "field_row_count": len(span_plan_rows),
        "support_span_count": span_count,
        "coverage_error_count": len(coverage_errors),
        "coverage_errors": coverage_errors,
        "coverage_quality_counts": dict(sorted(by_quality.items())),
        "recommendation_counts": dict(sorted(by_recommendation.items())),
    }


def build_langextract_examples_from_span_plan(span_plan_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    by_case: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in span_plan_rows:
        key = (
            row.get("paper_id", ""),
            row.get("case_id", ""),
            row.get("target_view_json_path", ""),
        )
        if key[0] and key[2]:
            by_case.setdefault(key, []).append(row)

    examples: list[dict[str, object]] = []
    for (paper_id, case_id, target_view_json_path), rows in sorted(by_case.items()):
        payload = json.loads(repo_path(target_view_json_path).read_text(encoding="utf-8"))
        text = normalise_example_text(payload.get("input_text") or payload.get("text") or "")
        extraction_pool: list[dict[str, object]] = []
        for row in rows:
            spans = load_support_spans(row)
            for index, span in enumerate(spans, start=1):
                extraction_pool.append(
                    {
                        "extraction_class": row["field_name"],
                        "extraction_text": normalise_example_text(str(span["span_text"])),
                        "attributes": langextract_attributes(
                            {
                                "value": row["spreadsheet_value"],
                                "case_id": case_id,
                                "support_span_index": index,
                                "support_span_count": len(spans),
                                "char_start": span["char_start"],
                                "char_end": span["char_end"],
                                "span_role": span["span_role"],
                                "coverage_quality": row.get("coverage_quality", ""),
                                "langextract_recommendation": row.get("langextract_recommendation", ""),
                                "original_evidence_mode": row.get("original_evidence_mode", ""),
                                "original_validator_status": row.get("original_validator_status", ""),
                            }
                        ),
                    }
                )

        extraction_pool.sort(
            key=lambda item: (
                int(item["attributes"]["char_start"]),
                int(item["attributes"]["char_end"]),
                str(item["extraction_class"]),
            )
        )
        extraction_groups = partition_langextract_extractions(extraction_pool)

        for group_index, extractions in enumerate(extraction_groups, start=1):
            for extraction in extractions:
                extraction["attributes"]["example_part_index"] = str(group_index)
                extraction["attributes"]["example_part_count"] = str(len(extraction_groups))
            examples.append(
                {
                    "source_sheet": SOURCE_SHEET_NAME,
                    "paper_id": paper_id,
                    "case_id": case_id,
                    "example_part_index": group_index,
                    "example_part_count": len(extraction_groups),
                    "target_view_json_path": target_view_json_path,
                    "text": text,
                    "extractions": extractions,
                }
            )
    return examples


def partition_langextract_extractions(extractions: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    groups: list[list[dict[str, object]]] = []
    group_last_end: list[int] = []

    for extraction in extractions:
        char_start = int(extraction["attributes"]["char_start"])
        char_end = int(extraction["attributes"]["char_end"])
        placed = False
        for group_index, last_end in enumerate(group_last_end):
            if char_start >= last_end:
                groups[group_index].append(extraction)
                group_last_end[group_index] = char_end
                placed = True
                break
        if not placed:
            groups.append([extraction])
            group_last_end.append(char_end)

    return groups


def validate_langextract_example_payload(examples: list[dict[str, object]]) -> dict[str, object]:
    try:
        import langextract as lx
        from langextract import prompt_validation as pv
    except ImportError as exc:
        raise SystemExit("langextract is required to validate span-plan examples.") from exc

    attribute_errors: list[dict[str, object]] = []
    example_data: list[Any] = []
    extraction_count = 0

    for example_index, example in enumerate(examples, start=1):
        text = str(example.get("text") or "").strip()
        extraction_rows = example.get("extractions") or []
        if not text or not isinstance(extraction_rows, list):
            continue

        extractions: list[Any] = []
        for extraction_index, row in enumerate(extraction_rows, start=1):
            if not isinstance(row, dict):
                continue

            extraction_class = str(row.get("extraction_class") or "").strip()
            extraction_text = str(row.get("extraction_text") or "").strip()
            attributes: dict[str, str | list[str]] | None = None
            attribute_payload = row.get("attributes")

            if attribute_payload is not None:
                if not isinstance(attribute_payload, dict):
                    attribute_errors.append(
                        {
                            "example_index": example_index,
                            "extraction_index": extraction_index,
                            "key": "__attributes__",
                            "type": type(attribute_payload).__name__,
                        }
                    )
                else:
                    attributes = {}
                    for key, value in attribute_payload.items():
                        clean_key = str(key).strip()
                        if not clean_key:
                            continue
                        if isinstance(value, str):
                            attributes[clean_key] = value
                        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
                            attributes[clean_key] = value
                        else:
                            attribute_errors.append(
                                {
                                    "example_index": example_index,
                                    "extraction_index": extraction_index,
                                    "key": clean_key,
                                    "type": type(value).__name__,
                                }
                            )
                            if isinstance(value, list):
                                attributes[clean_key] = [str(item) for item in value]
                            else:
                                attributes[clean_key] = str(value)
                    attributes = attributes or None

            if extraction_class and extraction_text:
                extractions.append(
                    lx.data.Extraction(
                        extraction_class=extraction_class,
                        extraction_text=extraction_text,
                        attributes=attributes,
                    )
                )
                extraction_count += 1

        if extractions:
            example_data.append(lx.data.ExampleData(text=text, extractions=extractions))

    policy = pv.AlignmentPolicy(enable_fuzzy_alignment=False, accept_match_lesser=False)
    report = pv.validate_prompt_alignment(example_data, policy=policy)
    alignment_issues = [str(issue) for issue in report.issues]

    return {
        "example_count": len(example_data),
        "extraction_count": extraction_count,
        "alignment_issue_count": len(alignment_issues),
        "attribute_error_count": len(attribute_errors),
        "alignment_policy": {
            "enable_fuzzy_alignment": False,
            "accept_match_lesser": False,
        },
        "alignment_issues": alignment_issues[:25],
        "attribute_errors": attribute_errors[:25],
    }


def selected_rows(records: list[PilotRecord]) -> list[dict[str, str]]:
    return [
        {
            "paper_id": record.paper_id,
            "case_id": record.case_id,
            "target_view_json_path": repo_rel(record.target_view_json_path),
            "field_count": str(len(record.manual_fields)),
            "text_sha256": sha256_text(record.source_text),
        }
        for record in records
    ]


def selected_fieldnames() -> list[str]:
    return ["paper_id", "case_id", "target_view_json_path", "field_count", "text_sha256"]


def manifest_payload(
    *,
    args: argparse.Namespace,
    selected_count: int,
    field_review_count: int,
    selected_rows_path: Path,
    field_candidates_path: Path | None = None,
    field_review_path: Path | None = None,
    draft_examples_path: Path | None = None,
    run_status: str = "completed",
    completed_record_count: int | None = None,
    failed_paper_id: str = "",
    failure_type: str = "",
    failure_message: str = "",
) -> dict[str, object]:
    return {
        "generated_at_utc": now_utc_iso(),
        "run_status": run_status,
        "provider": args.provider,
        "model_id": args.model_id,
        "gemini_env_file": repo_rel(args.gemini_env_file),
        "openai_env_file": repo_rel(args.openai_env_file),
        "openai_reasoning_effort": args.openai_reasoning_effort,
        "openai_max_output_tokens": args.openai_max_output_tokens,
        "dry_run": bool(args.dry_run or not args.allow_paid_run),
        "allow_paid_run": bool(args.allow_paid_run),
        "api_retries": args.api_retries,
        "api_retry_wait_seconds": args.api_retry_wait_seconds,
        "selected_record_count": selected_count,
        "completed_record_count": selected_count if completed_record_count is None else completed_record_count,
        "field_review_row_count": field_review_count,
        "selected_rows_path": repo_rel(selected_rows_path),
        "field_candidates_path": "" if field_candidates_path is None else repo_rel(field_candidates_path),
        "field_review_path": "" if field_review_path is None else repo_rel(field_review_path),
        "draft_examples_path": "" if draft_examples_path is None else repo_rel(draft_examples_path),
        "failed_paper_id": failed_paper_id,
        "failure_type": failure_type,
        "failure_message": failure_message,
    }


def write_manifest(path: Path, payload: dict[str, object]) -> None:
    write_json(path, payload)


def checkpoint_paid_run(
    *,
    args: argparse.Namespace,
    records: list[PilotRecord],
    completed: int,
    all_review_rows: list[dict[str, str]],
    selected_path: Path,
    jsonl_path: Path,
    review_path: Path,
    run_status: str,
    failed_paper_id: str = "",
    failure_type: str = "",
    failure_message: str = "",
) -> None:
    write_csv_rows_atomic(review_path, all_review_rows, REVIEW_FIELDNAMES)
    write_json_atomic(
        args.output_dir / "run_manifest.json",
        manifest_payload(
            args=args,
            selected_count=len(records),
            completed_record_count=completed,
            field_review_count=len(all_review_rows),
            selected_rows_path=selected_path,
            field_candidates_path=jsonl_path,
            field_review_path=review_path,
            run_status=run_status,
            failed_paper_id=failed_paper_id,
            failure_type=failure_type,
            failure_message=failure_message,
        ),
    )


def write_dry_run_outputs(args: argparse.Namespace, records: list[PilotRecord]) -> None:
    selected_path = args.output_dir / "selected_rows.csv"
    write_csv_rows(selected_path, selected_rows(records), selected_fieldnames())
    write_manifest(
        args.output_dir / "run_manifest.json",
        manifest_payload(
            args=args,
            selected_count=len(records),
            field_review_count=0,
            selected_rows_path=selected_path,
        ),
    )
    print(f"Dry run selected {len(records)} records. No {args.provider} calls made.")
    print(f"Wrote selected rows to {selected_path}")


def write_paid_run_outputs(args: argparse.Namespace, records: list[PilotRecord]) -> None:
    jsonl_path = args.output_dir / "field_candidates.jsonl"
    review_path = args.output_dir / "field_review.csv"
    selected_path = args.output_dir / "selected_rows.csv"
    all_review_rows: list[dict[str, str]] = []

    write_csv_rows(selected_path, selected_rows(records), selected_fieldnames())
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    completed = 0
    checkpoint_paid_run(
        args=args,
        records=records,
        completed=completed,
        all_review_rows=all_review_rows,
        selected_path=selected_path,
        jsonl_path=jsonl_path,
        review_path=review_path,
        run_status="running",
    )
    try:
        with jsonl_path.open("w", encoding="utf-8") as handle:
            for record in records:
                output = run_gemini_bootstrap_with_retries(record, args=args)
                handle.write(json.dumps(asdict(output), ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                all_review_rows.extend(validate_case_output(record, output))
                completed += 1
                checkpoint_paid_run(
                    args=args,
                    records=records,
                    completed=completed,
                    all_review_rows=all_review_rows,
                    selected_path=selected_path,
                    jsonl_path=jsonl_path,
                    review_path=review_path,
                    run_status="running",
                )
    except Exception as exc:
        checkpoint_paid_run(
            args=args,
            records=records,
            completed=completed,
            all_review_rows=all_review_rows,
            selected_path=selected_path,
            jsonl_path=jsonl_path,
            review_path=review_path,
            run_status="failed",
            failed_paper_id=records[completed].paper_id if completed < len(records) else "",
            failure_type=type(exc).__name__,
            failure_message=str(exc),
        )
        raise

    checkpoint_paid_run(
        args=args,
        records=records,
        completed=completed,
        all_review_rows=all_review_rows,
        selected_path=selected_path,
        jsonl_path=jsonl_path,
        review_path=review_path,
        run_status="completed",
    )
    print(f"Wrote {len(records)} {args.provider} candidate records to {jsonl_path}")
    print(f"Wrote {len(all_review_rows)} review rows to {review_path}")


def promote_from_review(args: argparse.Namespace) -> None:
    review_rows = read_csv_rows(args.promote_from_review)
    examples = build_langextract_examples_from_review(review_rows)
    out_path = args.examples_out_dir / "draft_langextract_examples.json"
    write_json(out_path, examples)
    write_manifest(
        args.output_dir / "run_manifest.json",
        manifest_payload(
            args=args,
            selected_count=len(examples),
            field_review_count=len(review_rows),
            selected_rows_path=args.promote_from_review,
            draft_examples_path=out_path,
        ),
    )
    print(f"Wrote {len(examples)} draft examples to {out_path}")


def build_from_span_plan(args: argparse.Namespace) -> None:
    span_plan_rows = read_csv_rows(args.build_from_span_plan)
    validation = validate_span_plan_rows(span_plan_rows)
    if validation["coverage_error_count"]:
        raise SystemExit(
            f"Span plan has {validation['coverage_error_count']} coverage errors; refusing to build examples."
        )

    examples = build_langextract_examples_from_span_plan(span_plan_rows)
    compatibility = validate_langextract_example_payload(examples)
    if compatibility["alignment_issue_count"] or compatibility["attribute_error_count"]:
        raise SystemExit(
            "LangExtract compatibility validation failed: "
            f"{compatibility['alignment_issue_count']} alignment issues, "
            f"{compatibility['attribute_error_count']} attribute errors."
        )

    out_path = args.examples_out_dir / args.span_plan_examples_name
    manifest_path = args.output_dir / "span_plan_examples_manifest.json"
    source_document_count = len(
        {
            (
                row.get("paper_id", ""),
                row.get("case_id", ""),
                row.get("target_view_json_path", ""),
            )
            for row in span_plan_rows
            if row.get("paper_id") and row.get("target_view_json_path")
        }
    )
    write_json(out_path, examples)
    write_json(
        manifest_path,
        {
            "generated_at_utc": now_utc_iso(),
            "span_plan_path": repo_rel(args.build_from_span_plan),
            "examples_path": repo_rel(out_path),
            "example_count": len(examples),
            "source_document_count": source_document_count,
            "extraction_count": compatibility["extraction_count"],
            "langextract_compatibility": compatibility,
            **validation,
        },
    )
    print(f"Wrote {len(examples)} all-gold draft examples to {out_path}")
    print(f"Wrote span-plan coverage manifest to {manifest_path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap reviewed MC single-case LangExtract examples with a paid LLM provider."
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--paper-id", action="append", default=[])
    parser.add_argument("--exclude-paper-id", action="append", default=[])
    parser.add_argument("--provider", choices=["openai", "gemini"], default="openai")
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--gemini-env-file", type=Path, default=DEFAULT_GEMINI_ENV_FILE)
    parser.add_argument("--openai-env-file", type=Path, default=DEFAULT_OPENAI_ENV_FILE)
    parser.add_argument("--openai-reasoning-effort", default=DEFAULT_OPENAI_REASONING_EFFORT)
    parser.add_argument("--openai-max-output-tokens", type=int, default=DEFAULT_OPENAI_MAX_OUTPUT_TOKENS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT / "pilot_10")
    parser.add_argument("--examples-out-dir", type=Path, default=DEFAULT_EXAMPLES_OUT_DIR)
    parser.add_argument("--allow-paid-run", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--api-retries", type=int, default=2)
    parser.add_argument("--api-retry-wait-seconds", type=float, default=20.0)
    parser.add_argument("--promote-from-review", type=Path, default=None)
    parser.add_argument("--build-from-span-plan", type=Path, default=None)
    parser.add_argument("--span-plan-examples-name", default="draft_langextract_examples_all_gold.json")
    args = parser.parse_args(argv)
    if args.model_id is None:
        args.model_id = DEFAULT_OPENAI_MODEL if args.provider == "openai" else DEFAULT_GEMINI_MODEL
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.promote_from_review:
        promote_from_review(args)
        return

    if args.build_from_span_plan:
        build_from_span_plan(args)
        return

    records = select_pilot_records(
        limit=args.limit,
        explicit_ids=args.paper_id,
        excluded_ids=args.exclude_paper_id,
    )
    if not records:
        raise SystemExit("No manually reviewed MC records selected.")

    if args.dry_run or not args.allow_paid_run:
        write_dry_run_outputs(args, records)
        return

    write_paid_run_outputs(args, records)


if __name__ == "__main__":
    main(sys.argv[1:])
