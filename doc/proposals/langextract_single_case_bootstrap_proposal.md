# Proposal: Bootstrap LangExtract Examples From Reviewed Single-Case Gold

## Purpose

Build a reviewable pilot workflow that turns 10 manually reviewed MC case-report rows into high-quality LangExtract examples, then scales to the full 85 reviewed rows once the evidence quality and review workflow are acceptable.

The proposal supersedes the exploratory bottom section of `src/pipelines/09_build_langextract_examples.py`. That script can still be mined for ideas, but it should not be treated as canonical. The new implementation should be explicit, CLI-verifiable, and safe around paid Gemini calls.

## Inputs

- `resources/stage07_single_case_gold_json_index.csv`
  - Use only rows where `manually_reviewed_MC == TRUE`.
  - Use `stage07_target_view_json_path` to load the Stage 07 gold target-view JSON.
  - The text field is expected as `input_text`; accept `text` only as a fallback.
- `examples/datasheet_examples_MC_Case_Report_Form.csv`
  - Treat this as the manual gold standard.
  - Join by `Reference == paper_id`.
  - Preserve `case_ID` as case metadata.
  - Use all non-empty manually extracted data fields as candidate extraction targets.
- `qa/validation/stage07_single_case_codex_gold/.../json/target_views/{paper_id}/p1.json`
  - Use its raw clinical text for grounding.
- `env/gemini.env`
  - Local secret file containing `GEMINI_API_KEY=...`.
  - The script may load this file, but must never print, persist, or commit the key.

## Output Shape

Pilot outputs should be non-canonical review artefacts under:

`qa/validation/langextract_example_bootstrap/pilot_10/`

Planned files:

- `selected_rows.csv`: the 10 selected paper/case rows and source paths.
- `field_candidates.jsonl`: one JSON record per paper/case containing Gemini output for all non-empty manual fields.
- `field_review.csv`: one row per manual field, optimised for human review.
- `run_manifest.json`: model, input hashes, selected IDs, command, and validation summary.

Accepted pilot examples should be compiled into:

`examples/langextract_bootstrap/draft_langextract_examples.json`

Accepted examples should not be written to `config/prompts/examples/` until after review.

## Product Survival Brief

- Primary workflow: convert manual MC spreadsheet rows plus Stage 07 gold text into reviewed LangExtract examples.
- Core data object and owner: one bootstrapped field-level evidence candidate, owned by this repo's review workflow.
- Roles and permissions affected: no app roles; CLI only.
- Lifecycle states: `draft`, `needs_review`, `accepted`, `rejected`.
- External service state: Gemini API call, gated by `--allow-paid-run`.
- Admin/support need: run manifest plus per-field review CSV for repair and reruns.
- Observability need: counts for selected papers, fields requested, fields returned, exact quote matches, inferred fields, not found fields, and validation failures.
- Non-goals: full 85-row production promotion, prompt optimisation, and running Gemini without explicit approval.

## Premortem

Premortem frame: it is 6 months from now and the LangExtract example bootstrap failed. We are working backwards to identify why.

1. The model produced plausible but ungrounded clinical evidence.
   - Mitigation: require exact text snippets for quoteable fields, local substring validation, and explicit `evidence_mode` for inferred fields.
2. The workflow silently dropped manual fields.
   - Mitigation: validate one Gemini result per non-empty manual target field.
3. The pilot confused provenance fields with extraction targets.
   - Mitigation: keep `extractor`, `Reference`, and `case_ID` as metadata; include all other non-empty manual fields as extraction targets.
4. The Stage 07 text did not contain enough evidence for some manual values.
   - Mitigation: allow `not_found` and `inferred_from_text` statuses; do not force exact quotes for inferential fields.
5. The generated examples were promoted too early.
   - Mitigation: write only review packs first; require accepted review rows before writing prompt examples.
6. The model version or SDK behaviour changed.
   - Mitigation: record model ID, SDK version if available, response schema, command, and input hashes in `run_manifest.json`.

## Proposed Implementation

The proposal is to rewrite `src/pipelines/09_build_langextract_examples.py` into a focused bootstrap-and-promote CLI, or create a new module and leave a thin compatibility wrapper in `09_build_langextract_examples.py`. I recommend a rewrite because the existing file already owns stage 09 in `doc/repo_rules.md`, but the current bottom sample is exploratory and mixed with unrelated code.

### 1. Constants And Response Schema

```python
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


# Keep all paths repository-relative where possible so review outputs can be
# compared across machines and worktrees.
REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / "resources" / "stage07_single_case_gold_json_index.csv"
MC_CASE_REPORT_PATH = REPO_ROOT / "examples" / "datasheet_examples_MC_Case_Report_Form.csv"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "validation" / "langextract_example_bootstrap"
DEFAULT_EXAMPLES_OUT_DIR = REPO_ROOT / "examples" / "langextract_bootstrap"
DEFAULT_GEMINI_ENV_FILE = REPO_ROOT / "env" / "gemini.env"


# The user requested Gemini 2.5 Flash. Keep it configurable so the exact
# provider model ID can be corrected without editing code if the SDK exposes a
# slightly different spelling.
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


# These fields identify the manual row and reviewer, but they are not clinical
# facts to ask LangExtract to extract from article text.
PROVENANCE_FIELDS = {"extractor", "Reference", "case_ID"}


class FieldGrounding(BaseModel):
    # The spreadsheet column name. The caller will verify that every requested
    # non-empty field appears exactly once in the response.
    field_name: str = Field(description="Manual spreadsheet column name.")

    # Preserve the exact manual value as the gold standard. The model may not
    # normalise, translate, or silently rewrite it.
    spreadsheet_value: str = Field(description="Exact non-empty value from the manual row.")

    # Exact quotes work for fields such as age, sex wording, treatments, titres,
    # and named diagnoses. Some higher-level fields, such as phenotype, may need
    # inference from several snippets.
    evidence_mode: Literal["exact_quote", "inferred_from_text", "not_found"] = Field(
        description="How the manual value is supported by the source text."
    )

    # For exact_quote, this must be a verbatim substring of source_text. For
    # inferred_from_text, this should be the shortest useful source phrase or
    # sentence that anchors the inference. For not_found, leave it empty.
    extraction_text: str = Field(description="Verbatim supporting text, or empty if not found.")

    # Optional additional verbatim snippets for inferred fields where one text
    # span is not enough. The validator checks each snippet as a substring.
    supporting_snippets: list[str] = Field(default_factory=list)

    # A short explanation for reviewers. This is never promoted into the final
    # LangExtract example unless explicitly chosen later.
    reasoning_short: str = Field(description="Brief reviewer-facing explanation.")

    # The model must mark false if it cannot support the manual value from the
    # supplied text. This gives the validator a simple fail-visible gate.
    supports_manual_value: bool


class BootstrappedCaseExample(BaseModel):
    # Paper and case metadata allow one paper to produce multiple examples when
    # the manual sheet has multiple case rows.
    paper_id: str
    case_id: str
    model_id: str
    field_groundings: list[FieldGrounding]
```

Summary: this block defines the proposed script-level constants and the structured Gemini response schema. The key design choice is to separate quoteable evidence from inferred evidence rather than pretending every spreadsheet value must have a direct quote.

### 2. Load And Join The 10-Paper Pilot

```python
@dataclass(frozen=True)
class PilotRecord:
    # A PilotRecord is the smallest unit sent to Gemini: one paper/case row,
    # the Stage 07 text for that paper, and all non-empty manual fields for that
    # case row.
    paper_id: str
    case_id: str
    target_view_json_path: Path
    source_text: str
    manual_fields: dict[str, str]


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    # Use utf-8-sig so a byte-order mark in CSV exports does not become part of
    # the first header name.
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_stage07_text(path: Path) -> str:
    # Stage 07 target-view JSONs currently expose the clinical input text as
    # input_text. The fallback to text is included because the user described
    # the raw text generically as a text field, and older artefacts may differ.
    payload = json.loads(path.read_text(encoding="utf-8"))
    text = (payload.get("input_text") or payload.get("text") or "").strip()
    if not text:
        raise ValueError(f"No Stage 07 input text found in {path}")
    return text


def manual_fields_from_row(row: dict[str, str]) -> dict[str, str]:
    # Keep every non-empty manually extracted data value. Provenance columns are
    # retained elsewhere as metadata, not sent as extraction targets.
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


def select_pilot_records(limit: int, explicit_ids: list[str]) -> list[PilotRecord]:
    # The resource index is the authoritative bridge from Stage 07 gold IDs to
    # target-view JSON paths and the manually_reviewed_MC flag.
    index_rows = load_csv_rows(INDEX_PATH)
    manual_rows = load_csv_rows(MC_CASE_REPORT_PATH)

    manual_by_id: dict[str, list[dict[str, str]]] = {}
    for row in manual_rows:
        paper_id = (row.get("Reference") or "").strip()
        if paper_id:
            manual_by_id.setdefault(paper_id, []).append(row)

    wanted = {paper_id.strip() for paper_id in explicit_ids if paper_id.strip()}
    selected: list[PilotRecord] = []

    for index_row in index_rows:
        paper_id = (index_row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        if index_row.get("manually_reviewed_MC") != "TRUE":
            continue
        if wanted and paper_id not in wanted:
            continue

        target_path = REPO_ROOT / index_row["stage07_target_view_json_path"]
        source_text = load_stage07_text(target_path)

        for manual_row in manual_by_id.get(paper_id, []):
            fields = manual_fields_from_row(manual_row)
            if not fields:
                continue
            selected.append(
                PilotRecord(
                    paper_id=paper_id,
                    case_id=(manual_row.get("case_ID") or "").strip(),
                    target_view_json_path=target_path,
                    source_text=source_text,
                    manual_fields=fields,
                )
            )
            if not wanted and len(selected) >= limit:
                return selected

    return selected
```

Summary: this block proposes the deterministic data join. It selects only `manually_reviewed_MC == TRUE` rows, loads the Stage 07 target-view text, joins to MC manual rows by `Reference`, and keeps all non-empty non-provenance fields for the pilot.

### 3. Build The Gemini Prompt

```python
def build_bootstrap_prompt(record: PilotRecord) -> str:
    # Keep the prompt specific to this single call. Do not mention later stages,
    # future scaling, or unrelated pipeline tasks.
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
```

Summary: this block proposes the per-case prompt. It is deliberately narrow: the model only grounds the manual values against the supplied Stage 07 text and must return one structured item per field.

### 4. Call Gemini 2.5 Flash Behind An Explicit Paid-Run Gate

```python
def require_paid_run_approval(allow_paid_run: bool) -> None:
    # The repo rules forbid starting paid LLM/API runs without explicit user
    # approval. A CLI flag is auditable and keeps dry-runs safe by default.
    if not allow_paid_run:
        raise SystemExit("Refusing to call Gemini without --allow-paid-run.")


def load_env_file(path: Path) -> None:
    # Keep this intentionally tiny: read KEY=VALUE lines, ignore comments and
    # blanks, and never print the loaded values. Existing environment variables
    # win so callers can override locally without editing files.
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def gemini_client(env_file: Path) -> genai.Client:
    # Secrets stay in environment variables or local env files. The script should
    # not print the key or write it into run artefacts.
    load_env_file(env_file)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=api_key)


def run_gemini_bootstrap(
    record: PilotRecord,
    *,
    model_id: str,
    allow_paid_run: bool,
    env_file: Path,
) -> BootstrappedCaseExample:
    require_paid_run_approval(allow_paid_run)
    client = gemini_client(env_file)
    prompt = build_bootstrap_prompt(record)

    # response_schema asks Gemini for JSON that Pydantic can validate. Keep
    # temperature at zero to reduce variation and make reruns easier to compare.
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BootstrappedCaseExample,
            temperature=0.0,
        ),
    )

    # Parse through Pydantic even when the SDK says it returned JSON. Treat model
    # output as untrusted until schema validation succeeds.
    payload = json.loads(response.text or "{}")
    parsed = BootstrappedCaseExample.model_validate(payload)

    # The model should echo these, but the caller owns the truth. Overwrite them
    # so downstream review rows cannot drift because of model formatting.
    return parsed.model_copy(
        update={
            "paper_id": record.paper_id,
            "case_id": record.case_id,
            "model_id": model_id,
        }
    )
```

Summary: this block proposes the Gemini call. It uses `gemini-2.5-flash` by default, can load `GEMINI_API_KEY` from `env/gemini.env`, requires `--allow-paid-run`, keeps the API key out of logs and artefacts, and validates the response before any output is trusted.

### 5. Validate Grounding And Write The Review Pack

```python
def find_text_span(source_text: str, snippet: str) -> tuple[int, int] | None:
    # Exact offsets are computed locally, not trusted from the model. If the
    # snippet is absent, the review row is marked invalid.
    if not snippet:
        return None
    start = source_text.find(snippet)
    if start < 0:
        return None
    return start, start + len(snippet)


def validate_case_output(
    record: PilotRecord,
    output: BootstrappedCaseExample,
) -> list[dict[str, str]]:
    requested_fields = set(record.manual_fields)
    returned_fields = [item.field_name for item in output.field_groundings]
    returned_field_set = set(returned_fields)

    review_rows: list[dict[str, str]] = []

    # Missing and extra fields are fatal for promotion, but they are still
    # written to the review CSV so the user can see what went wrong.
    missing_fields = sorted(requested_fields - returned_field_set)
    extra_fields = sorted(returned_field_set - requested_fields)

    for item in output.field_groundings:
        expected_value = record.manual_fields.get(item.field_name, "")
        span = find_text_span(record.source_text, item.extraction_text)

        supporting_missing = [
            snippet
            for snippet in item.supporting_snippets
            if snippet and snippet not in record.source_text
        ]

        if item.evidence_mode == "exact_quote":
            validator_status = "passed" if span else "quote_not_found"
        elif item.evidence_mode == "inferred_from_text":
            validator_status = "passed" if item.supporting_snippets and not supporting_missing else "inference_snippet_not_found"
        elif item.evidence_mode == "not_found":
            validator_status = "needs_review"
        else:
            validator_status = "invalid_evidence_mode"

        if expected_value != item.spreadsheet_value:
            validator_status = "manual_value_changed"

        review_rows.append(
            {
                "paper_id": record.paper_id,
                "case_id": record.case_id,
                "field_name": item.field_name,
                "spreadsheet_value": expected_value,
                "model_spreadsheet_value": item.spreadsheet_value,
                "evidence_mode": item.evidence_mode,
                "extraction_text": item.extraction_text,
                "char_start": "" if span is None else str(span[0]),
                "char_end": "" if span is None else str(span[1]),
                "supporting_snippets_json": json.dumps(item.supporting_snippets, ensure_ascii=False),
                "supports_manual_value": str(item.supports_manual_value).upper(),
                "reasoning_short": item.reasoning_short,
                "validator_status": validator_status,
                "review_status": "draft",
                "review_notes": "",
                "target_view_json_path": str(record.target_view_json_path.relative_to(REPO_ROOT)),
            }
        )

    for field_name in missing_fields:
        review_rows.append(
            {
                "paper_id": record.paper_id,
                "case_id": record.case_id,
                "field_name": field_name,
                "spreadsheet_value": record.manual_fields[field_name],
                "model_spreadsheet_value": "",
                "evidence_mode": "",
                "extraction_text": "",
                "char_start": "",
                "char_end": "",
                "supporting_snippets_json": "[]",
                "supports_manual_value": "FALSE",
                "reasoning_short": "",
                "validator_status": "missing_from_model_output",
                "review_status": "draft",
                "review_notes": "",
                "target_view_json_path": str(record.target_view_json_path.relative_to(REPO_ROOT)),
            }
        )

    if extra_fields:
        # Record the unexpected fields once per case. This makes schema drift
        # visible without trying to promote unknown targets.
        review_rows.append(
            {
                "paper_id": record.paper_id,
                "case_id": record.case_id,
                "field_name": "__extra_model_fields__",
                "spreadsheet_value": ";".join(extra_fields),
                "model_spreadsheet_value": "",
                "evidence_mode": "",
                "extraction_text": "",
                "char_start": "",
                "char_end": "",
                "supporting_snippets_json": "[]",
                "supports_manual_value": "FALSE",
                "reasoning_short": "",
                "validator_status": "extra_fields_from_model_output",
                "review_status": "draft",
                "review_notes": "",
                "target_view_json_path": str(record.target_view_json_path.relative_to(REPO_ROOT)),
            }
        )

    return review_rows
```

Summary: this block proposes the local validator. It checks that Gemini returned every requested field, did not change manual values, and supplied snippets that are actually present in the Stage 07 text.

### 6. Convert Accepted Review Rows To LangExtract Examples

```python
def build_langextract_examples_from_review(review_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    # Only accepted rows become prompt examples. This prevents draft model output
    # from becoming canonical few-shot material.
    accepted = [
        row
        for row in review_rows
        if row.get("review_status") == "accepted"
        and row.get("validator_status") == "passed"
        and row.get("extraction_text")
    ]

    by_case: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in accepted:
        key = (
            row["paper_id"],
            row.get("case_id", ""),
            row["target_view_json_path"],
        )
        by_case.setdefault(key, []).append(row)

    examples: list[dict[str, object]] = []
    for (paper_id, case_id, target_view_json_path), rows in by_case.items():
        source_payload = json.loads((REPO_ROOT / target_view_json_path).read_text(encoding="utf-8"))
        text = (source_payload.get("input_text") or source_payload.get("text") or "").strip()

        extractions = []
        for row in rows:
            # extraction_class is the manual spreadsheet field name. The gold
            # value is stored in attributes so LangExtract examples can teach
            # both the evidence span and the structured target value.
            extractions.append(
                {
                    "extraction_class": row["field_name"],
                    "extraction_text": row["extraction_text"],
                    "attributes": {
                        "value": row["spreadsheet_value"],
                        "case_id": case_id,
                        "evidence_mode": row["evidence_mode"],
                    },
                }
            )

        examples.append(
            {
                "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
                "paper_id": paper_id,
                "case_id": case_id,
                "target_view_json_path": target_view_json_path,
                "text": text,
                "extractions": extractions,
            }
        )

    return examples
```

Summary: this block proposes the promotion compiler. It groups accepted field rows by paper/case and creates LangExtract-compatible examples with spreadsheet field names as extraction classes and manual values in attributes.

### 7. CLI Orchestration

```python
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap reviewed MC single-case LangExtract examples with Gemini."
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--paper-id", action="append", default=[])
    parser.add_argument("--model-id", default=DEFAULT_GEMINI_MODEL)
    parser.add_argument("--gemini-env-file", type=Path, default=DEFAULT_GEMINI_ENV_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT / "pilot_10")
    parser.add_argument("--examples-out-dir", type=Path, default=DEFAULT_EXAMPLES_OUT_DIR)
    parser.add_argument("--allow-paid-run", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--promote-from-review", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.promote_from_review:
        review_rows = load_csv_rows(args.promote_from_review)
        examples = build_langextract_examples_from_review(review_rows)
        out_path = args.examples_out_dir / "draft_langextract_examples.json"
        out_path.write_text(json.dumps(examples, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {len(examples)} draft examples to {out_path}")
        return

    records = select_pilot_records(limit=args.limit, explicit_ids=args.paper_id)
    if not records:
        raise SystemExit("No manually reviewed MC records selected.")

    selected_path = args.output_dir / "selected_rows.csv"
    with selected_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["paper_id", "case_id", "target_view_json_path", "field_count", "text_sha256"],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "paper_id": record.paper_id,
                    "case_id": record.case_id,
                    "target_view_json_path": str(record.target_view_json_path.relative_to(REPO_ROOT)),
                    "field_count": len(record.manual_fields),
                    "text_sha256": sha256_text(record.source_text),
                }
            )

    if args.dry_run:
        print(f"Dry run selected {len(records)} records. No Gemini calls made.")
        return

    jsonl_path = args.output_dir / "field_candidates.jsonl"
    review_path = args.output_dir / "field_review.csv"
    all_review_rows: list[dict[str, str]] = []

    with jsonl_path.open("w", encoding="utf-8") as jsonl_handle:
        for record in records:
            output = run_gemini_bootstrap(
                record,
                model_id=args.model_id,
                allow_paid_run=args.allow_paid_run,
                env_file=args.gemini_env_file,
            )
            jsonl_handle.write(output.model_dump_json() + "\n")
            all_review_rows.extend(validate_case_output(record, output))

    with review_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_review_rows[0]))
        writer.writeheader()
        writer.writerows(all_review_rows)

    manifest = {
        "generated_at_utc": now_utc_iso(),
        "model_id": args.model_id,
        "gemini_env_file": str(args.gemini_env_file.relative_to(REPO_ROOT)),
        "selected_record_count": len(records),
        "field_review_row_count": len(all_review_rows),
        "selected_rows_path": str(selected_path.relative_to(REPO_ROOT)),
        "field_candidates_path": str(jsonl_path.relative_to(REPO_ROOT)),
        "field_review_path": str(review_path.relative_to(REPO_ROOT)),
    }
    (args.output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

Summary: this block proposes the end-to-end CLI. The dry-run selects the 10 pilot records without API calls. The paid run writes raw model candidates, a review CSV, and a manifest. Promotion is a separate command that only uses reviewed rows.

### 8. Focused Tests

```python
def test_manual_fields_excludes_only_provenance() -> None:
    row = {
        "extractor": "MC",
        "Reference": "75",
        "case_ID": "",
        "age_description": "39",
        "sex": "F",
        "empty_field": "",
    }
    assert manual_fields_from_row(row) == {"age_description": "39", "sex": "F"}


def test_validate_case_output_rejects_missing_quote() -> None:
    record = PilotRecord(
        paper_id="75",
        case_id="",
        target_view_json_path=Path("qa/validation/example.json"),
        source_text="A 39-year-old woman presented with spasms.",
        manual_fields={"age_description": "39"},
    )
    output = BootstrappedCaseExample(
        paper_id="75",
        case_id="",
        model_id="gemini-2.5-flash",
        field_groundings=[
            FieldGrounding(
                field_name="age_description",
                spreadsheet_value="39",
                evidence_mode="exact_quote",
                extraction_text="A 40-year-old woman",
                supporting_snippets=[],
                reasoning_short="Age phrase.",
                supports_manual_value=True,
            )
        ],
    )
    rows = validate_case_output(record, output)
    assert rows[0]["validator_status"] == "quote_not_found"


def test_validate_case_output_flags_missing_field() -> None:
    record = PilotRecord(
        paper_id="75",
        case_id="",
        target_view_json_path=Path("qa/validation/example.json"),
        source_text="A 39-year-old woman presented with spasms.",
        manual_fields={"age_description": "39", "sex": "F"},
    )
    output = BootstrappedCaseExample(
        paper_id="75",
        case_id="",
        model_id="gemini-2.5-flash",
        field_groundings=[
            FieldGrounding(
                field_name="age_description",
                spreadsheet_value="39",
                evidence_mode="exact_quote",
                extraction_text="39-year-old",
                supporting_snippets=[],
                reasoning_short="Age phrase.",
                supports_manual_value=True,
            )
        ],
    )
    rows = validate_case_output(record, output)
    assert any(row["validator_status"] == "missing_from_model_output" for row in rows)
```

Summary: this block proposes focused regression tests for the highest-risk behaviour: preserving all non-empty manual targets, rejecting non-verbatim quotes, and detecting dropped fields.

## Pilot Selection

Start with the first 10 `manually_reviewed_MC == TRUE` IDs in `resources/stage07_single_case_gold_json_index.csv`, unless explicit IDs are supplied:

`75, 92, 155, 162, 187, 197, 395, 427, 439, 512`

This gives a small but realistic spread of older case reports and variable text lengths.

## Review Rules

For each field in `field_review.csv`:

- `accepted`: evidence is clinically and textually acceptable for a LangExtract example.
- `rejected`: evidence is wrong, over-inferred, not useful, or model changed the manual value.
- `needs_review`: evidence may be inferential, ambiguous, or absent from the Stage 07 text.

Recommended first-pass acceptance rules:

- Accept `exact_quote` only when the quote is a verbatim substring and supports the manual value.
- Accept `inferred_from_text` only when the supporting snippets make the inference clear to a human reviewer.
- Reject `not_found` for promotion, but keep it in the review pack as evidence of missingness.
- Do not promote fields where Gemini changed the spreadsheet value.

## Verification Plan

Before any Gemini call:

```powershell
.\\.venv\\Scripts\\python.exe src\\pipelines\\09_build_langextract_examples.py --dry-run --limit 10
```

Expected evidence:

- 10 selected records.
- No Gemini calls.
- `selected_rows.csv` exists.
- Every selected row has a Stage 07 target-view JSON path and at least one manual field.

For the paid pilot, after explicit approval:

```powershell
.\\.venv\\Scripts\\python.exe src\\pipelines\\09_build_langextract_examples.py --limit 10 --allow-paid-run --model-id gemini-2.5-flash
```

Expected evidence:

- `field_candidates.jsonl` has 10 records.
- `field_review.csv` has one row per non-empty manual target field, plus any explicit validator rows.
- `run_manifest.json` records model ID and counts.
- Validator summary reports missing fields, quote failures, inferred fields, and not-found fields.

After manual review:

```powershell
.\\.venv\\Scripts\\python.exe src\\pipelines\\09_build_langextract_examples.py --promote-from-review qa\\validation\\langextract_example_bootstrap\\pilot_10\\field_review.csv
```

Expected evidence:

- `draft_langextract_examples.json` contains only accepted rows.
- No draft, rejected, not-found, or validator-failed fields are promoted.

## Answered Design Decisions For The Implementation Patch

1. `case_ID` is part of the example grouping key. Blank `case_ID` values are valid and group as `(paper_id, "")`.
2. Semicolon-delimited manual values are preserved as the original manual string for the pilot. Splitting can be reconsidered after review.
3. Inferred fields may be promoted into draft examples only after human acceptance in the review CSV.
4. Accepted pilot examples are compiled into `examples/langextract_bootstrap/draft_langextract_examples.json`; they do not replace `config/prompts/examples/02_individual_examples.json` during the 10-row pilot.

## Done Criteria For The First Patch

- `src/pipelines/09_build_langextract_examples.py` is cleaned or replaced with the proposed CLI.
- `--dry-run --limit 10` works without API credentials.
- Tests cover field preservation, quote validation, missing-field detection, and promotion filtering.
- No Gemini calls occur without `--allow-paid-run`.
- Pilot outputs are written only under `qa/validation/langextract_example_bootstrap/pilot_10/`.
- The final report states all commands run, checks passed or skipped, and the exact number of selected records and manual fields.
