"""Advisory review helper for uncertain Stage 07 single-case outputs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src" / "pipelines"))
sys.path.insert(0, str(REPO_ROOT / "src" / "pipelines" / "stage07_XML"))

from stage07_XML import core  # noqa: E402

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover - exercised only without optional SDK
    OpenAI = None


DEFAULT_STAGE07_ROOT = REPO_ROOT / "data" / "extraction_json" / "stage07_xml"
DEFAULT_ADVISORY_ROOT = REPO_ROOT / "qa" / "validation" / "stage07_single_case_advisory"
DEFAULT_DEEPSEEK_ENV_FILE = REPO_ROOT / "env" / "deepseek_api_key.env"
DEFAULT_OPENAI_ENV_FILE = REPO_ROOT / "env" / "openai_api_key.env"
ADVISORY_SCHEMA_VERSION = "stage07_single_case_advisory_v1"
OPENAI_FALLBACK_USAGE_PATH = DEFAULT_ADVISORY_ROOT / "openai_fallback_usage.json"


SYSTEM_PROMPT = """You are a source-backed reviewer for Stage 07 single-case SPSD extraction.
Return only a JSON object. Do not include chain-of-thought.
Decide whether the candidate p1 target view correctly captures the single SPSD case material.
Use only the supplied source and candidate text. Do not infer clinical facts absent from the source.
If the source is not a single-case source for this workflow, advise deferral to the multi-case workflow."""


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_env_key(path: Path, variable: str) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped and stripped.startswith(("sk-", "ds-")):
            return stripped
        if stripped.startswith(f"{variable}="):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def resolve_api_key(provider: str, explicit_key: str, env_file: Path | None) -> str:
    if explicit_key.strip():
        return explicit_key.strip()
    variable = "DEEPSEEK_API_KEY" if provider == "deepseek" else "OPENAI_API_KEY"
    env_value = os.environ.get(variable, "").strip()
    if env_value:
        return env_value
    path = env_file or (DEFAULT_DEEPSEEK_ENV_FILE if provider == "deepseek" else DEFAULT_OPENAI_ENV_FILE)
    key = read_env_key(path, variable)
    if key:
        return key
    raise RuntimeError(f"No {variable} found in the environment or {path}.")


def compact_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = max_chars // 2
    tail = max_chars - head
    return text[:head] + "\n\n[...middle omitted for advisory prompt...]\n\n" + text[-tail:]


def load_candidate_package(stage07_root: Path, paper_id: str, max_source_chars: int) -> dict[str, Any]:
    paper_path = stage07_root / "papers" / f"{paper_id}.json"
    view_path = stage07_root / "target_views" / paper_id / "p1.json"
    validation_path = stage07_root / "validation" / f"{paper_id}.validation.json"
    segments_path = stage07_root / "segments" / f"{paper_id}.segments.json"
    paper = json.loads(paper_path.read_text(encoding="utf-8"))
    view = json.loads(view_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    segments = json.loads(segments_path.read_text(encoding="utf-8"))
    source_path = core.repo_path_from_relative(str(paper.get("source", {}).get("source_text_json_path") or ""))
    source_text = ""
    if source_path is not None and source_path.exists():
        prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
        source_text = prepared.source_text
    return {
        "paper_id": paper_id,
        "stage07_annotation": paper.get("annotation", {}),
        "stage06_prior": paper.get("stage06_prior", {}),
        "manual_review": paper.get("manual_review", {}),
        "validation": validation,
        "target_view": {
            "ready_for_langextract": view.get("ready_for_langextract"),
            "manual_review_reasons": view.get("manual_review_reasons", []),
            "input_text": compact_text(str(view.get("input_text") or ""), 20000),
        },
        "segment_count": len(segments.get("segments") or []),
        "source_text_excerpt": compact_text(source_text, max_source_chars),
    }


def build_user_prompt(package: dict[str, Any]) -> str:
    expected = {
        "decision": "accept_ready | defer_multi_case | needs_patch | uncertain",
        "confidence": "high | medium | low",
        "evidence": [
            {
                "quote": "exact short source quote",
                "supports": "why this quote supports the decision",
            }
        ],
        "advice": "brief final advice, no reasoning trace",
    }
    return json.dumps(
        {
            "task": "Review this Stage 07 single-case candidate output.",
            "return_schema": expected,
            "decision_rules": [
                "accept_ready only if p1 contains the relevant single SPSD case material and excludes unrelated patients, cohorts, references, and adjacent articles.",
                "defer_multi_case if the source is not a single-case source for this workflow.",
                "needs_patch if the source appears eligible but the candidate p1 is over-broad, truncated, or missing case material.",
                "uncertain if the provided evidence is insufficient.",
            ],
            "package": package,
        },
        ensure_ascii=False,
    )


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return json.loads(stripped)


def call_deepseek(*, api_key: str, model: str, prompt: str) -> dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("The openai package is not installed.")
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
    )
    content = response.choices[0].message.content or ""
    return extract_json_object(content)


def load_openai_usage(path: Path = OPENAI_FALLBACK_USAGE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": ADVISORY_SCHEMA_VERSION, "calls": []}
    return json.loads(path.read_text(encoding="utf-8"))


def record_openai_usage(model: str, paper_id: str, path: Path = OPENAI_FALLBACK_USAGE_PATH) -> None:
    payload = load_openai_usage(path)
    calls = list(payload.get("calls") or [])
    calls.append({"paper_id": paper_id, "model": model, "called_at_utc": now_utc_iso()})
    payload["calls"] = calls
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def call_openai_fallback(
    *,
    api_key: str,
    model: str,
    prompt: str,
    paper_id: str,
    call_limit: int,
) -> dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("The openai package is not installed.")
    usage = load_openai_usage()
    if len(usage.get("calls") or []) >= call_limit:
        raise RuntimeError(f"OpenAI fallback call limit reached ({call_limit}).")
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        reasoning={"effort": "xhigh"},
        text={"format": {"type": "json_object"}, "verbosity": "low"},
        store=False,
    )
    record_openai_usage(model, paper_id)
    return extract_json_object(response.output_text)


def write_advice(
    *,
    paper_id: str,
    provider: str,
    model: str,
    advice: dict[str, Any],
    advisory_root: Path,
) -> Path:
    payload = {
        "schema_version": ADVISORY_SCHEMA_VERSION,
        "paper_id": paper_id,
        "provider": provider,
        "model": model,
        "created_at_utc": now_utc_iso(),
        "advice": advice,
    }
    path = advisory_root / f"{paper_id}.{provider}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--provider", choices=["deepseek", "openai"], default="deepseek")
    parser.add_argument("--deepseek-model", default="deepseek-v4-pro")
    parser.add_argument("--openai-model", default="gpt-5.5")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-env-file", type=Path, default=None)
    parser.add_argument("--stage07-root", type=Path, default=DEFAULT_STAGE07_ROOT)
    parser.add_argument("--advisory-root", type=Path, default=DEFAULT_ADVISORY_ROOT)
    parser.add_argument("--max-source-chars", type=int, default=40000)
    parser.add_argument("--openai-fallback-call-limit", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    package = load_candidate_package(args.stage07_root, args.paper_id, args.max_source_chars)
    prompt = build_user_prompt(package)
    model = args.deepseek_model if args.provider == "deepseek" else args.openai_model
    api_key = resolve_api_key(args.provider, args.api_key, args.api_key_env_file)
    if args.provider == "deepseek":
        advice = call_deepseek(api_key=api_key, model=model, prompt=prompt)
    else:
        advice = call_openai_fallback(
            api_key=api_key,
            model=model,
            prompt=prompt,
            paper_id=args.paper_id,
            call_limit=args.openai_fallback_call_limit,
        )
    path = write_advice(
        paper_id=args.paper_id,
        provider=args.provider,
        model=model,
        advice=advice,
        advisory_root=args.advisory_root,
    )
    print(f"Wrote advisory advice to {path}")


if __name__ == "__main__":
    main()
