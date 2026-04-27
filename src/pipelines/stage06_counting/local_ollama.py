from __future__ import annotations

import json
import os
import time
from typing import Any

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover - only used in incomplete environments.
    requests = None  # type: ignore[assignment]
from pydantic import ValidationError

from src.pipelines.stage06_counting.local_models import LocalCountDecisionOutput, LocalModelCallResult
from src.pipelines.stage06_counting.local_prepare import format_candidate_package_for_local_llm
from src.pipelines.stage06_counting.models import CountCandidatePackage


DEFAULT_OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = "gemma4:e4b"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 600.0
DEFAULT_OLLAMA_TEMPERATURE = 0.0

SYSTEM_PROMPT = """\
You extract the most likely count of unique original SPS-spectrum patients from a reviewed evidence pack.
You will receive a compact evidence card. Your only task is to count unique original SPS-spectrum patients in that card.
Ignore broader prevalence framing unless it directly states the SPS-spectrum cohort count.

For this review, stiff person spectrum disorder (SPSD) includes:
- classic stiff person syndrome (SPS)
- partial or focal SPS, including stiff limb syndrome
- SPS-plus
- jerking SPS
- progressive encephalomyelitis with rigidity and myoclonus (PERM)

`Stiff man syndrome (SMS)` is an older designation for SPS.

The source category is fixed. Do not reclassify the paper.
Count only unique original, confirmed or diagnosis-supported SPS-spectrum patients or cohorts reported in this paper.

Return exactly one JSON object with these keys:
{
  "n_spsd_patients": 0,
  "evidence_span": "short direct quote",
  "data_granularity": "individual-level" | "group-level" | "both" | "unclear",
  "confidence": "high" | "medium" | "low",
  "needs_review": true,
  "reasoning_short": "one short sentence",
  "possibilities": [
    {
      "n_spsd_patients": 0,
      "evidence_span": "short direct quote",
      "data_granularity": "individual-level" | "group-level" | "both" | "unclear",
      "confidence": "high" | "medium" | "low",
      "rationale_short": "why this alternative is plausible"
    }
  ]
}

Do not count:
- cited-literature cases
- controls or non-SPSD patients unless an explicit SPS-spectrum subgroup is given
- suspected or referred SPS cohorts without explicit diagnostic support
- donor-material, serum, CSF, assay-source, or specimen-source patients unless the paper also reports clinically extractable original SPSD patient data
- samples, sera, assays, titres, biopsies, visits, or repeated measurements
- overlapping subgroup totals
- background prevalence or historical literature counts
- background trial counts from other papers

Conservatism rules:
- If the SPS-spectrum subset is ambiguous, set `needs_review=true`.
- If the evidence card shows a suspected or referred SPS cohort plus a stricter confirmed or diagnosis-supported subset, prefer the stricter confirmed subset.
- If the evidence card says `original_cohort_provenance_uncertain=true`, set `needs_review=true`.
- If confidence is not high, set `needs_review=true`.
- If the evidence presents more than one plausible count, put the best guess in the top-level fields and record the alternatives in `possibilities`.
- If any alternative in `possibilities` has a different count from the top-level count, set `needs_review=true`.
- If the paper is already routed as `single_case_report` or `single_case_conference_abstract`, default to `1` unless the evidence explicitly reports more than one original SPS-spectrum patient in this paper.
- If an enumerated diagnosis list separately names `SPS` and `PERM` within one broader cohort, count both SPS-spectrum diagnoses unless overlap is explicitly stated.
- If a case-report framing conflicts with a parenthetical suffix count like `SPS (3)`, treat the suffix as suspicious and set `needs_review=true`.
- Never use alias keys such as `count`, `evidence`, `granularity`, or string-only `possibilities`.
- Return JSON only, with no markdown fences or prose outside the JSON object.
"""


def ensure_ollama_model_available(
    *,
    model: str = DEFAULT_OLLAMA_MODEL,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    timeout_seconds: float = 20.0,
) -> None:
    if requests is None:
        raise RuntimeError("The 'requests' package is required before Ollama can be checked.")
    response = requests.get(f"{base_url.rstrip('/')}/v1/models", timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    models = {str(item.get("id") or "").strip() for item in payload.get("data") or []}
    if model not in models:
        raise RuntimeError(f"Ollama model '{model}' is not available at {base_url}.")


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _extract_json_object(text: str) -> str:
    in_string = False
    escape = False
    depth = 0
    start_index = -1
    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start_index = index
            depth += 1
        elif char == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start_index >= 0:
                return text[start_index : index + 1]
    raise ValueError("No JSON object found in local-model output.")


def _coerce_count(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _normalise_data_granularity(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unclear"
    mapping = {
        "individual": "individual-level",
        "individual-level": "individual-level",
        "patient-level": "individual-level",
        "group": "group-level",
        "group-level": "group-level",
        "cohort": "group-level",
        "both": "both",
        "mixed": "both",
        "unclear": "unclear",
        "unknown": "unclear",
    }
    return mapping.get(text, "unclear")


def _normalise_confidence(value: object) -> str:
    if isinstance(value, bool):
        return "low"
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric >= 0.85:
            return "high"
        if numeric >= 0.5:
            return "medium"
        return "low"
    text = str(value or "").strip().lower()
    if text in {"high", "medium", "low"}:
        return text
    if text in {"uncertain", "unclear"}:
        return "low"
    return "low"


def _normalise_possibility_payload(
    possibility: object,
    *,
    default_evidence_span: str,
    default_data_granularity: str,
) -> dict[str, Any] | None:
    if isinstance(possibility, dict):
        payload = dict(possibility)
        possibility_count = _coerce_count(payload.get("n_spsd_patients"))
        if possibility_count is None:
            possibility_count = _coerce_count(payload.get("count"))
        if possibility_count is None:
            possibility_count = _coerce_count(payload.get("answer"))
        if possibility_count is None:
            return None
        evidence_span = str(
            payload.get("evidence_span")
            or payload.get("evidence")
            or default_evidence_span
            or "[compact local output omitted evidence span]"
        ).strip()
        data_granularity = _normalise_data_granularity(
            payload.get("data_granularity")
            or payload.get("granularity")
            or default_data_granularity
            or "unclear"
        )
        confidence = _normalise_confidence(payload.get("confidence") or "low")
        rationale_short = str(
            payload.get("rationale_short")
            or payload.get("reasoning_short")
            or payload.get("reason")
            or payload.get("reasoning")
            or payload.get("rationale")
            or "Compact local-model alternative."
        ).strip()
        return {
            "n_spsd_patients": possibility_count,
            "evidence_span": evidence_span,
            "data_granularity": data_granularity,
            "confidence": confidence,
            "rationale_short": rationale_short,
        }

    possibility_count = _coerce_count(possibility)
    if possibility_count is None:
        return None
    return {
        "n_spsd_patients": possibility_count,
        "evidence_span": default_evidence_span or "[compact local output omitted evidence span]",
        "data_granularity": default_data_granularity or "unclear",
        "confidence": "low",
        "rationale_short": "Compact local-model alternative.",
    }


def _normalise_local_count_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("Local-model output must be a JSON object.")

    normalised = dict(payload)
    count = _coerce_count(normalised.get("n_spsd_patients"))
    if count is None:
        count = _coerce_count(normalised.get("count"))
    if count is None:
        count = _coerce_count(normalised.get("answer"))
    if count is None:
        raise ValueError("Local-model output did not include a valid count field.")

    evidence_span = str(
        normalised.get("evidence_span")
        or normalised.get("evidence")
        or normalised.get("span")
        or ""
    ).strip()
    data_granularity = _normalise_data_granularity(
        normalised.get("data_granularity")
        or normalised.get("granularity")
        or ""
    )
    confidence = _normalise_confidence(normalised.get("confidence") or "")
    reasoning_short = str(
        normalised.get("reasoning_short")
        or normalised.get("reason")
        or normalised.get("rationale")
        or normalised.get("reasoning")
        or normalised.get("notes")
        or ""
    ).strip()

    possibilities_payload = normalised.get("possibilities") or []
    default_evidence_span = evidence_span or "[compact local output omitted evidence span]"
    default_data_granularity = data_granularity or "unclear"
    normalised_possibilities = [
        possibility_payload
        for possibility in possibilities_payload
        if (possibility_payload := _normalise_possibility_payload(
            possibility,
            default_evidence_span=default_evidence_span,
            default_data_granularity=default_data_granularity,
        ))
        is not None
    ]

    has_alternative_count = any(
        possibility["n_spsd_patients"] != count for possibility in normalised_possibilities
    )
    missing_structured_fields = not evidence_span or data_granularity == "unclear" or not reasoning_short
    needs_review = bool(normalised.get("needs_review"))
    if has_alternative_count or missing_structured_fields or confidence != "high":
        needs_review = True

    return {
        "n_spsd_patients": count,
        "evidence_span": default_evidence_span,
        "data_granularity": default_data_granularity,
        "confidence": confidence,
        "needs_review": needs_review,
        "reasoning_short": reasoning_short or "Parsed from compact local-model output.",
        "possibilities": normalised_possibilities,
    }


def parse_local_count_output(text: str) -> LocalCountDecisionOutput:
    cleaned = _strip_code_fences(text)
    candidates = [cleaned]
    if "{" in cleaned and "}" in cleaned:
        try:
            candidates.insert(0, _extract_json_object(cleaned))
        except ValueError:
            pass
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
            return LocalCountDecisionOutput.model_validate(_normalise_local_count_payload(payload))
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            last_error = exc
        except ValueError as exc:
            last_error = exc
    raise ValueError(f"Unable to parse local-model JSON output: {last_error}")


def run_local_count_package(
    package: CountCandidatePackage,
    *,
    model: str = DEFAULT_OLLAMA_MODEL,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    timeout_seconds: float = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    temperature: float = DEFAULT_OLLAMA_TEMPERATURE,
) -> LocalModelCallResult:
    prompt = format_candidate_package_for_local_llm(package)
    started = time.monotonic()
    try:
        if requests is None:
            raise RuntimeError("The 'requests' package is required before Ollama can be called.")
        response = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={
                "model": model,
                "stream": False,
                "think": False,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "format": LocalCountDecisionOutput.model_json_schema(),
                "options": {
                    "temperature": temperature,
                },
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        raw_output = str((payload.get("message") or {}).get("content") or "").strip()
        try:
            parsed = parse_local_count_output(raw_output)
            status = "parsed_ok"
            error = ""
        except ValueError as exc:
            parsed = None
            status = "parse_failed"
            error = str(exc)
        return LocalModelCallResult(
            model_id=str(payload.get("model") or model),
            status=status,
            raw_output=raw_output,
            response_payload=payload,
            parsed=parsed,
            error=error,
            duration_seconds=time.monotonic() - started,
        )
    except Exception as exc:
        return LocalModelCallResult(
            model_id=model,
            status="request_failed",
            raw_output="",
            response_payload={},
            parsed=None,
            error=f"{exc.__class__.__name__}: {exc}",
            duration_seconds=time.monotonic() - started,
        )
