from __future__ import annotations

import json
import os
import time
from typing import Any

import requests
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

The source category is fixed. Do not reclassify the paper.
Count only unique original SPS-spectrum patients or cohorts reported in this paper.

Do not count:
- cited-literature cases
- controls or non-SPSD patients unless an explicit SPS-spectrum subgroup is given
- samples, sera, assays, titres, biopsies, visits, or repeated measurements
- overlapping subgroup totals
- background prevalence or historical literature counts

Conservatism rules:
- If the SPS-spectrum subset is ambiguous, set `needs_review=true`.
- If confidence is not high, set `needs_review=true`.
- If the evidence presents more than one plausible count, put the best guess in the top-level fields and record the alternatives in `possibilities`.
- Return JSON only, with no markdown fences or prose outside the JSON object.
"""


def ensure_ollama_model_available(
    *,
    model: str = DEFAULT_OLLAMA_MODEL,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    timeout_seconds: float = 20.0,
) -> None:
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
            return LocalCountDecisionOutput.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
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
