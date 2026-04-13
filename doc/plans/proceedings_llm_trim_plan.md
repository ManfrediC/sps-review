# Plan: LLM-assisted abstract end selection for proceedings trimming

## Goal

Implement a new two-stage workflow that keeps the current **start-of-abstract recognition**, generates **several end candidates** from strict to permissive, and then uses an OpenAI model to decide whether one candidate is exact or whether the correct end lies inside an overshooting candidate.

Create two new scripts:

- `src/pipelines/05_trim_proceedings_text_LLM.py`
- `src/pipelines/05b_validate_proceedings_text_LLM.py`

Do **not** replace the current scripts yet. Keep the current scripts untouched as baseline.

---

## Design principles

1. **Do not change start recognition logic unless necessary.** Reuse the current proceedings detection, block extraction, index-assisted routing, and start-anchor logic.
2. **Do not commit to a single end too early.** The new stage 05 should generate multiple plausible end candidates.
3. **Guarantee containment.** At least one permissive candidate must overshoot enough that the true end is highly likely to be inside it.
4. **Use the LLM as an adjudicator, not as the primary start detector.**
5. **Keep provenance explicit.** Every output must indicate whether the result came from heuristics only, LLM candidate selection, or LLM trimming within an overshoot.
6. **Make the workflow auditable.** Persist candidate spans, candidate heuristics, LLM request metadata, and LLM decision metadata.

---

## High-level workflow

### Stage 05: `05_trim_proceedings_text_LLM.py`

Purpose:
- detect proceedings as before
- identify the correct abstract **start** as before
- build a **candidate package** containing 3–5 plausible end candidates
- write a candidate record and registry row
- do **not** make the final LLM decision here

### Stage 05b: `05b_validate_proceedings_text_LLM.py`

Purpose:
- load the candidate package from stage 05
- call OpenAI with structured output
- ask the model whether one candidate is exact, or whether the true end lies inside the overshoot candidate
- validate the model’s response against guardrails
- write the final trimmed record and final registry row

---

## Output locations

Use separate output locations so this workflow does not collide with the existing stage-05 outputs.

Recommended new constants:

- `CANDIDATE_OUT_DIR = data/extraction_json/text_trimmed_llm_candidates`
- `FINAL_OUT_DIR = data/extraction_json/text_trimmed_llm`
- `CANDIDATE_REGISTRY_PATH = data/references/text_trim_llm_candidate_registry.csv`
- `FINAL_REGISTRY_PATH = data/references/text_trim_llm_registry.csv`

Keep the existing reference CSV, source categorisation files, manual-review files, and overrides.

---

## Shared data structures

Add new dataclasses in both scripts or, preferably, in a small shared helper module.

### `EndCandidate`

```python
@dataclass
class EndCandidate:
    candidate_id: str
    heuristic_name: str
    rank: int
    start_index: int
    end_index_exclusive: int
    start_page_index: int
    end_page_index: int
    n_lines: int
    body_char_count: int
    contains_next_confirmed_header: bool
    contains_soft_boundary: bool
    contains_tail_metadata: bool
    confidence_class: str  # strict | medium | permissive
    rationale: str
```

### `LLMDecision`

```python
@dataclass
class LLMDecision:
    decision_type: str  # candidate_exact | line_within_overshoot | unable_to_determine
    selected_candidate_id: str
    last_abstract_line_global_index: int | None
    confidence: str  # high | medium | low
    end_reason: str
    explanation_short: str
```

### `CandidatePackage`

```python
@dataclass
class CandidatePackage:
    paper_id: str
    source_text_json_path: str
    reference_title: str
    reference_authors: str
    matched_start_index: int
    matched_start_page_index: int
    matched_block_code: str
    matched_block_title: str
    start_rule: str
    candidate_generation_mode: str
    candidates: list[EndCandidate]
    overshoot_candidate_id: str
    baseline_candidate_id: str
    proceedings_signals: dict[str, Any]
    upstream_match_metadata: dict[str, Any]
```

---

## Required refactor before implementation

The current `05_trim_proceedings_text.py` and `05b_validate_proceedings_text.py` are effectively duplicates. For the new LLM workflow, avoid copying the whole file again without refactoring.

### Refactor plan

Extract shared deterministic helpers into one helper module, for example:

- `src/pipelines/_proceedings_trim_core.py`

Move these into the helper module:

- argument-independent loading helpers
- proceedings detection
- block extraction
- index-assisted candidate selection
- best-start selection
- record flattening / page trimming helpers
- registry writing helpers where practical

New LLM-specific scripts should import from the shared core instead of duplicating all logic again.

---

## Stage 05 implementation plan

## File: `src/pipelines/05_trim_proceedings_text_LLM.py`

### 1. Keep current start selection logic

Reuse the existing logic up to the point where the best block is chosen:

- `proceedings_signals(...)`
- `extract_blocks(...)`
- `best_matching_block(...)`
- `index_assisted_candidate(...)`
- `local_window_candidate(...)`
- `choose_best_candidate(...)`

However:

- treat the selected block’s **start** as trusted
- treat the selected block’s **end** only as one heuristic candidate, not as final truth

### 2. Add a "confirmed next header" search on the full document

Implement a new helper:

```python
def confirmed_header_start_indices(lines: list[LineRef], pattern: ProceedingsPattern) -> list[int]:
    ...
```

This function should be **more conservative** than `header_start_indices(...)`.

A confirmed header should require one of:

- explicit abstract code / code-like boundary
- strong title-like line followed shortly by author-like or institution-like lines
- strong neighbour-code confirmation from the index when available

The purpose is not to detect every possible start. The purpose is to find starts that are safe enough to terminate the previous abstract.

### 3. Build a full-span search window from the selected start

After choosing the best block:

- take `matched_start_index = block.start_index`
- search forward on the **full flattened line list**, not the local candidate slice
- find the first confirmed next header after that start
- define a hard upper bound window using the earliest of:
  - first confirmed next header after start
  - `max_pages_from_start` guardrail
  - `max_lines_from_start` guardrail
  - `max_chars_from_start` guardrail

Recommended initial defaults:

- `max_pages_from_start = 2`
- `max_lines_from_start = 140`
- `max_chars_from_start = 7000`

This full-span window is the source material for candidate generation.

### 4. Generate 3–5 ordered end candidates

Implement:

```python
def build_end_candidates(
    lines: list[LineRef],
    matched_block: AbstractBlock,
    pattern: ProceedingsPattern,
    next_confirmed_header_index: int | None,
) -> list[EndCandidate]:
    ...
```

Build the candidate list from **strict to permissive**. Use the same `start_index` for all candidates.

#### Candidate 1: `current_selected_end`

Use the selected block’s current end from the existing stage-05 logic.

Purpose:
- preserve the current deterministic behaviour as a baseline

#### Candidate 2: `tail_metadata_trim_end`

Create a candidate that extends from the chosen start up to the next confirmed header (or cap), then run a stricter trailing metadata pass to cut obvious tail sections such as:

- disclosure / disclosures
- correspondence / corresponding author
- doi-only tail
- contact / email-only tail

Purpose:
- catch cases where the abstract ends before the next header because metadata intervenes

#### Candidate 3: `last_non_metadata_end`

Scan backward from the permissive span end and stop at the last line before a run of obvious metadata-like lines.

Use a suffix rule such as:

- at least 2 consecutive metadata-like lines, or
- at least 3 metadata-like lines in the last 5 lines

Purpose:
- generate a medium-strict candidate that is longer than the current pipeline but shorter than the full overshoot

#### Candidate 4: `next_confirmed_header_end`

Take the full span from the matched start to the next confirmed header.

If there is no confirmed next header, use the fixed cap.

Purpose:
- this is the main overshoot candidate
- it should make it very likely that the true end is contained

#### Candidate 5: optional `cap_only_overshoot_end`

Only create this if candidate 4 is still relatively short or if there is no confirmed next header.

This ignores soft boundaries and uses only fixed caps.

Purpose:
- provide one maximal fallback overshoot

### 5. Deduplicate and sort candidates

Implement:

```python
def dedupe_end_candidates(candidates: list[EndCandidate]) -> list[EndCandidate]:
    ...
```

Rules:
- deduplicate by `(start_index, end_index_exclusive)`
- keep the more informative heuristic name if two candidates collapse to the same span
- keep candidates sorted by `end_index_exclusive`
- guarantee at least 2 candidates when possible
- guarantee exactly one `overshoot_candidate_id`

### 6. Candidate package output

Write a **candidate package JSON** for each processed paper.

Recommended file content:

```json
{
  "paper_id": "...",
  "trim_workflow_version": "proceedings_llm_v1",
  "trim_workflow_stage": "candidate_generation",
  "source_text_json_path": "...",
  "reference_title": "...",
  "reference_authors": "...",
  "matched_start_index": 123,
  "matched_start_page_index": 5,
  "matched_block_code": "A-123",
  "matched_block_title": "...",
  "start_rule": "...",
  "baseline_candidate_id": "cand_01_current_selected_end",
  "overshoot_candidate_id": "cand_04_next_confirmed_header_end",
  "candidate_generation_mode": "strict_to_permissive_v1",
  "candidates": [...],
  "proceedings_metadata": {...},
  "upstream_match_metadata": {...}
}
```

### 7. Stage-05 registry metadata

Add candidate-level metadata to the new candidate registry.

Required fields:

- `trim_workflow_version`
- `trim_workflow_stage`
- `candidate_count`
- `baseline_candidate_id`
- `overshoot_candidate_id`
- `candidate_ids`
- `candidate_heuristics`
- `candidate_end_indices`
- `candidate_end_pages`
- `llm_routing_recommended`
- `llm_routing_reason`

### 8. Routing recommendation flag

Stage 05 should set a routing recommendation for stage 05b.

Implement:

```python
def llm_routing_recommendation(package: CandidatePackage) -> tuple[bool, str]:
    ...
```

Route to LLM when one or more of these are true:

- candidate count >= 2
- current deterministic end is much shorter than overshoot
- current candidate ended by a soft rule or `window_extent_cap` / `page_span_cap`
- trailing metadata is detected near the permissive end
- current pipeline would otherwise return `manual_review_required`

For the first implementation, it is acceptable to route **all** candidate packages to stage 05b.

---

## Stage 05b implementation plan

## File: `src/pipelines/05b_validate_proceedings_text_LLM.py`

### 1. Input

Read the stage-05 candidate package JSONs, not the original trimmed outputs.

### 2. LLM input format

Build a compact, deterministic prompt.

Provide:

- paper ID
- reference title
- reference authors
- matched abstract code if present
- numbered candidate summaries
- one **numbered line list** covering the permissive span from the matched start to the overshoot candidate end
- clear marking of candidate end positions inside the numbered line list

Recommended layout:

```text
Paper ID: ...
Reference title: ...
Reference authors: ...
Matched code: ...

Candidates:
- cand_01 current_selected_end -> ends at line 38
- cand_02 tail_metadata_trim_end -> ends at line 41
- cand_03 last_non_metadata_end -> ends at line 46
- cand_04 next_confirmed_header_end -> ends at line 55 (overshoot candidate)

Line list:
[001] ...
[002] ...
...
[055] ...
```

Do not send the whole paper. Send only the permissive span.

### 3. LLM question

Ask the model to decide among three possibilities:

1. one candidate already ends exactly at the last abstract line
2. none of the candidates is exact, but the last abstract line lies inside the overshoot candidate
3. the model cannot determine the boundary confidently

### 4. Use structured output only

Use the OpenAI Responses API with Structured Outputs and a strict JSON schema.

Recommended schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "decision_type": {
      "type": "string",
      "enum": ["candidate_exact", "line_within_overshoot", "unable_to_determine"]
    },
    "selected_candidate_id": {
      "type": ["string", "null"]
    },
    "last_abstract_line_number": {
      "type": ["integer", "null"]
    },
    "confidence": {
      "type": "string",
      "enum": ["high", "medium", "low"]
    },
    "end_reason": {
      "type": "string",
      "enum": [
        "candidate_is_exact",
        "next_header_starts",
        "metadata_starts",
        "disclosure_starts",
        "correspondence_starts",
        "doi_tail",
        "other",
        "uncertain"
      ]
    },
    "explanation_short": {
      "type": "string"
    }
  },
  "required": [
    "decision_type",
    "selected_candidate_id",
    "last_abstract_line_number",
    "confidence",
    "end_reason",
    "explanation_short"
  ]
}
```

### 5. OpenAI client implementation

Use the official Python SDK and the **Responses API**.

Implementation requirements:

- model default: `gpt-5-mini`
- endpoint: `client.responses.create(...)`
- structured output via `text={"format": {...}}`
- `store=False`
- small output budget
- configurable retry count and timeout
- clear handling for refusal / timeout / malformed output

### 6. Add a small wrapper around API calls

Implement:

```python
def call_llm_for_end_decision(package: CandidatePackage, client: OpenAI, ...) -> LLMDecision:
    ...
```

Wrapper responsibilities:

- assemble prompt
- submit request
- parse structured output
- catch SDK/API exceptions
- return a normalised `LLMDecision`

### 7. Guardrail validation of LLM output

Implement:

```python
def validate_llm_decision(package: CandidatePackage, decision: LLMDecision) -> tuple[bool, str]:
    ...
```

A decision is valid only if:

- selected candidate ID exists when `decision_type == candidate_exact`
- `last_abstract_line_number` is present and within range when `decision_type == line_within_overshoot`
- final end is not before the matched start
- final end does not exceed the overshoot candidate end
- final span still passes `has_enough_body(...)`
- final span is not implausibly short relative to the start/header

### 8. Apply decision

Implement:

```python
def apply_llm_decision(package: CandidatePackage, decision: LLMDecision, source_lines: list[LineRef]) -> AbstractBlock:
    ...
```

Rules:

- if `candidate_exact`, trim to that candidate’s end
- if `line_within_overshoot`, trim to the returned line number within the permissive span
- if invalid or `unable_to_determine`, fall back to the best deterministic candidate and mark the status accordingly

### 9. Final status values

Use explicit statuses such as:

- `trimmed_auto_llm_candidate_exact`
- `trimmed_auto_llm_line_within_overshoot`
- `trimmed_auto_llm_fallback_heuristic`
- `manual_review_required_llm_uncertain`
- `manual_review_required_llm_invalid_output`

### 10. Final output JSON metadata

The final trimmed JSON must include metadata that makes the workflow provenance obvious.

Required fields:

- `trim_workflow_version`: `proceedings_llm_v1`
- `trim_workflow_stage`: `llm_validated`
- `end_selection_mode`: `heuristic_only | llm_candidate_exact | llm_line_within_overshoot | llm_fallback`
- `candidate_source_json_path`
- `baseline_candidate_id`
- `overshoot_candidate_id`
- `candidate_count`
- `candidate_ids`
- `llm_used`
- `llm_model`
- `llm_api_mode`: `responses_json_schema`
- `llm_prompt_version`
- `llm_decision_type`
- `llm_selected_candidate_id`
- `llm_last_abstract_line_global_index`
- `llm_confidence`
- `llm_end_reason`
- `llm_explanation_short`
- `llm_validation_passed`
- `llm_validation_reason`
- `heuristic_fallback_used`

### 11. Final registry metadata

Add these columns to the final registry:

- `trim_workflow_version`
- `trim_workflow_stage`
- `end_selection_mode`
- `candidate_count`
- `baseline_candidate_id`
- `overshoot_candidate_id`
- `llm_used`
- `llm_model`
- `llm_decision_type`
- `llm_selected_candidate_id`
- `llm_last_abstract_line_global_index`
- `llm_confidence`
- `llm_end_reason`
- `llm_validation_passed`
- `heuristic_fallback_used`

---

## OpenAI API requirements

Use the current OpenAI Python SDK and the Responses API. The Responses API is the recommended API for new projects, and Structured Outputs in Responses should be passed via `text.format` rather than the old `response_format` shape. Structured Outputs can enforce a JSON schema with `strict: true`, which is ideal for the LLM decision payload. `gpt-5-mini` supports both the Responses API and Structured Outputs. Responses are stored by default, so set `store=False` for this pipeline. The Python SDK also automatically retries certain transient failures such as 429 and 5xx errors by default, but the wrapper should still log failures clearly and surface fallback status in the registry. citeturn651794search4turn125689view2turn125689view0turn125689view1turn125689view3

### Recommended request shape

Use a request shape along these lines:

```python
response = client.responses.create(
    model=model_name,
    store=False,
    instructions=developer_instructions,
    input=user_payload,
    text={
        "format": {
            "type": "json_schema",
            "name": "abstract_end_decision",
            "strict": True,
            "schema": END_DECISION_SCHEMA,
        }
    },
)
```

Parse the response into the `LLMDecision` dataclass and treat any refusal / parse failure as non-fatal fallback conditions. Structured Outputs is intended exactly for schema-constrained responses like this. citeturn125689view0turn125689view2turn125689view4

---

## Prompt content requirements

Use short, explicit instructions.

### Developer instructions

The developer instructions should tell the model:

- it is deciding the end of one conference abstract
- it must use only the provided lines
- it must prefer an exact candidate when possible
- otherwise it may choose a line within the overshoot candidate
- it must not invent content outside the provided span
- it must return only schema-compliant output

### User payload

The user payload should include:

- reference title/authors/code
- candidate summary list
- numbered lines
- reminder that the last abstract line is the last line belonging to the target abstract before metadata or the next abstract header begins

---

## Helper functions to implement

### New helper functions in stage 05

- `confirmed_header_start_indices(...)`
- `first_confirmed_header_after_start(...)`
- `candidate_generation_window(...)`
- `build_end_candidates(...)`
- `dedupe_end_candidates(...)`
- `serialise_candidate_package(...)`
- `candidate_registry_row(...)`
- `llm_routing_recommendation(...)`

### New helper functions in stage 05b

- `load_candidate_package(...)`
- `build_llm_prompt(...)`
- `call_llm_for_end_decision(...)`
- `parse_llm_decision(...)`
- `validate_llm_decision(...)`
- `apply_llm_decision(...)`
- `final_registry_row(...)`

---

## CLI arguments to add

### Stage 05

Add:

- `--candidate-output-dir`
- `--candidate-registry-path`
- `--max-pages-from-start`
- `--max-lines-from-start`
- `--max-chars-from-start`
- `--route-all-to-llm`

### Stage 05b

Add:

- `--candidate-input-dir`
- `--output-dir`
- `--registry-path`
- `--openai-model` default `gpt-5-mini`
- `--openai-timeout-seconds`
- `--openai-max-retries`
- `--llm-mode` with values `all | recommended_only`
- `--prompt-version`
- `--dry-run`

Do not require the API key as a CLI argument. Read it from `OPENAI_API_KEY`.

---

## Fallback behaviour

Fallbacks must be explicit and traceable.

### When to fall back

- no candidate package
- LLM request fails
- refusal
- malformed response
- schema parse failure
- invalid line number
- decision fails guardrails

### Fallback target

Preferred fallback order:

1. `tail_metadata_trim_end`
2. `current_selected_end`
3. `next_confirmed_header_end`
4. manual review

Log which fallback path was used.

---

## Acceptance criteria

Implementation is acceptable when all of the following are true:

1. The new scripts run without modifying the current scripts.
2. Stage 05 writes candidate packages and registry rows with 3–5 ordered end candidates whenever proceedings are detected.
3. At least one candidate is clearly marked as the overshoot candidate.
4. Stage 05b can call OpenAI and parse a strict JSON decision.
5. Final trimmed outputs include full provenance metadata showing LLM vs heuristic selection.
6. Invalid or failed LLM outputs degrade gracefully to deterministic fallback.
7. The registry makes it easy to filter outputs by workflow origin and by LLM decision type.
8. Existing manual overrides still work.

---

## First implementation target

For the first version, optimise for simplicity and auditability rather than perfect elegance.

### Minimum viable version

- keep current start recognition unchanged
- generate exactly 4 candidates:
  - `current_selected_end`
  - `tail_metadata_trim_end`
  - `last_non_metadata_end`
  - `next_confirmed_header_end`
- route all candidate packages to stage 05b
- use `gpt-5-mini`
- use one strict JSON schema
- validate and fall back deterministically

Once this works, refine the candidate heuristics and routing strategy using error analysis.

---

## Nice-to-have, but not required in v1

- cache LLM decisions by hash of prompt payload
- batch processing via the Batch API
- prompt compression for very long overshoot windows
- automatic weak-label export for downstream autoresearch
- confidence-based escalation to a stronger model

