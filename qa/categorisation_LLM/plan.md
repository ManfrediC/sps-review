# PLAN.md — LLM-based source categorisation

## Scope

Implement the **source categorisation** component for the SPS review workflow.

This task covers **only** source categorisation.

Do **not** implement:
- patient or case counting
- subgroup counting
- clinical variable extraction
- case splitting
- deduplication across papers
- multi-paper synthesis

---

## Goal

Build an **LLM-first, rule-validated** pipeline that assigns each paper to exactly one source category.

The system must be:
- conservative — prefer correct abstention over forced classification
- evidence-linked — every classification cites specific textual evidence
- auditable — every decision is logged with reasoning and validator flags
- benchmarkable — evaluated against the existing 30-row gold standard and expanded sets
- compatible — output schema matches what downstream stages already consume

---

## Category definitions

### `conference_abstract`
Conference, meeting, proceedings, poster, or supplement abstract.

### `review_article`
Synthesises prior literature and does not provide clinically useful original SPS-spectrum patient data.

### `single_case_report`
Main original clinical content is one individual SPS-spectrum patient.

### `case_series_or_multi_case`
Multiple original patients with case-oriented or semi-individualised reporting.

**Note:** The existing pipeline and all downstream stages use `case_series_or_multi_case`, not `case_series`. The LLM schema and all outputs must use this label exactly.

### `observational_group_study`
Original grouped clinical data from a non-interventional design such as retrospective, prospective, registry, or cohort work.

### `interventional_study`
Original grouped clinical data from a treatment, intervention, trial, or controlled therapeutic design.

### `lab_heavy_clinical_or_translational`
Primarily assay, biomarker, immunology, or translational work, but still contains clinically relevant original SPS-spectrum human data.

### `non_clinical_basic_science`
Primarily mechanistic or laboratory-based and does not provide clinically useful original SPS-spectrum patient data.

### `incorrect_reference`
The PDF or record does not correspond to a valid or retrievable source for this review. Assigned only via the manual override ledger — the LLM must never emit this category.

### `unclear_manual_review`
Cannot be safely classified from the available evidence.

---

## Known confusion patterns

The current heuristic classifier (66.7% source-category accuracy on the 30-row gold standard) has documented failure modes. The LLM prompt and validators must explicitly address each:

| Predicted | Gold | Count | Root cause |
|---|---|---|---|
| `review_article` | `observational_group_study` | 3 | Papers studying SPS cohorts but without SPS in the title are misread as reviews because they discuss prior literature |
| `observational_group_study` | `conference_abstract` | 2 | Full-length proceedings volumes cause the proceedings signal to be suppressed |
| `interventional_study` | `observational_group_study` | 2 | Keywords like "trial" or "placebo" in treatment-description contexts trigger interventional scoring |
| `single_case_report` | `lab_heavy_clinical_or_translational` | 1 | A single patient mentioned in a translational immunology paper gets overweighted |
| `conference_abstract` | `lab_heavy_clinical_or_translational` | 1 | Short format assumed to be a conference abstract when it is actually a short lab-clinical paper |
| `observational_group_study` | `single_case_report` | 1 | Group-level language in a paper about one SPS patient overwhelms the single-case signal |

---

## Required output schema

Use a strict structured schema (Pydantic model for internal use, JSON Schema for Structured Outputs).

### Primary classification fields
- `paper_id` — string
- `source_type` — enum of the nine categories above (excluding `incorrect_reference`)
- `original_sps_spectrum_data` — enum: `yes` | `no` | `unclear`
- `contains_individual_level_data` — boolean
- `contains_group_level_data` — boolean
- `manual_review_required` — boolean
- `confidence` — enum: `high` | `medium` | `low`
- `reasoning_summary` — string, 1–3 sentence explanation
- `evidence` — array of evidence items (minimum 1)
- `validator_flags` — array of strings (populated by the validation stage, empty from the LLM)

### Evidence item fields
Each evidence item must contain:
- `quote` — verbatim or near-verbatim text from the paper
- `page` — integer, if available (null otherwise)
- `section` — string, if identifiable (null otherwise)
- `supports` — what this evidence supports (e.g. "original cohort data", "single patient")

Do not emit a classification without at least one evidence item.

---

## Stage 1: Input assembly

### Goal
Build one input payload per paper for the LLM call. This is a deterministic packaging step — no classification happens here.

### Approach
Do **not** build a bespoke keyword-retrieval system. Instead, assemble the full available context and truncate only if necessary.

### Inputs (in priority order)
1. **Metadata from `sps_references_export.csv`**: title, abstract, journal, year, pages, tags, notes, DOI
2. **Preferred text JSON** (trimmed if available, else full): first N pages of extracted text
3. **Proceedings / trim metadata** from `text_trim_registry.csv`: `proceedings_detected`, `trim_status`

### Assembly rules
- Include all metadata fields verbatim — do not normalise or pre-filter
- Include extracted text from the preferred source, truncated to a token budget (target: ~6,000 tokens of text content, roughly 10–12 pages). Prioritise early pages.
- If the paper has a trimmed version, use it; note the trim status in the payload
- Include `proceedings_detected` and `trim_status` as structured metadata fields — these are cheap high-signal inputs
- If the abstract is empty, note this explicitly (it affects the LLM's available evidence)

### Output
A dictionary or dataclass per paper containing:
- `paper_id`
- `metadata` block (title, abstract, journal, year, pages, tags, notes, DOI, authors)
- `text_content` — the assembled text string
- `text_source` — `"trimmed"` or `"full_text"`
- `proceedings_detected` — boolean
- `trim_status` — string
- `text_page_count` — integer

### What this stage must NOT do
- Classify or score the paper
- Select snippets by keyword relevance (the LLM can find its own evidence)
- Count patients or cases

---

## Stage 2: LLM categorisation

### Goal
Produce one structured source categorisation from the assembled input.

### API requirements
Use the OpenAI **Responses API** with **Structured Outputs** (JSON Schema mode).

Model: start with `gpt-4.1` (best structured-output compliance and reasoning for the cost). Evaluate `gpt-4.1-mini` as a cheaper alternative once accuracy is established. Record the model ID in every output row.

### Call parameters
- `temperature`: 0 — deterministic output for reproducibility
- `max_output_tokens`: 2048 (ample for the schema)
- Structured output schema derived from the Pydantic model

### Prompt structure

The system prompt must:
1. Define the task: classify this paper into exactly one source category
2. Provide category definitions (from above) with explicit boundary guidance for each known confusion pair
3. State the decision policy: conservative, evidence-linked, prefer abstention
4. Specify that `incorrect_reference` is never a valid LLM output
5. Instruct the model to distinguish:
   - Original patient data vs. discussion/review of prior literature
   - Individual-level vs. group-level reporting
   - Hybrid translational papers (lab-heavy but with clinical SPS data)
   - Conference abstracts vs. short full articles (use metadata: pages, supplement markers, DOI patterns)
6. Require quoted evidence for every classification

The user message provides the assembled input payload.

### Prompt anti-patterns to avoid
- Do not embed complex scoring heuristics in the prompt — let the LLM reason
- Do not over-constrain the reasoning format — the structured output schema is sufficient
- Do not include few-shot examples in the initial version; add them only after evaluating where the LLM fails without them

---

## Stage 3: Deterministic validation

### Goal
Reject or flag weak, inconsistent, or poorly supported outputs using checks that are tractable in deterministic code.

### Structural validators
- Schema compliance (all required fields present, valid enum values)
- At least one evidence item with a non-empty `quote`
- `source_type` is not `incorrect_reference`
- If `confidence` is `high`, at least 2 evidence items

### Cross-field consistency validators
- If `source_type` is `review_article` or `non_clinical_basic_science`, then `original_sps_spectrum_data` should not be `yes` (flag if so)
- If `source_type` is `single_case_report`, then `contains_individual_level_data` must be true
- If `source_type` is `observational_group_study` or `interventional_study`, then `contains_group_level_data` must be true
- If `source_type` is `conference_abstract`, check that at least one of these metadata signals is present: proceedings detected, supplement page, supplement issue, conference DOI, short page span (≤2), or abstract word count ≤450. If none are present and the paper has ≥4 pages, flag with `CONF_NO_METADATA_SUPPORT`.
- If `proceedings_detected` is true and `trim_status` is `manual_review_required`, force `manual_review_required = true` regardless of source type

### Evidence-plausibility validators
- If a quoted evidence snippet is shorter than 10 characters, flag as `EVIDENCE_TOO_SHORT`
- If all evidence items have null pages, flag as `EVIDENCE_NO_PAGES` (warning only, not blocking)

### Confidence-calibration validators
- If the paper has no abstract and no extracted text, downgrade confidence to `low` and flag as `INSUFFICIENT_INPUT`
- If the model returns `high` confidence with only 1 evidence item, downgrade to `medium`

### Validator actions
Each validator returns one of:
- `pass` — no issues
- `warning` — flag is appended to `validator_flags` but result is accepted
- `downgrade` — confidence is lowered and/or `manual_review_required` is set to true
- `reject` — force `source_type = unclear_manual_review` and `manual_review_required = true`

Do not attempt fuzzy semantic checks like "evidence actually supports the assigned category" — these are LLM-level tasks and will produce unreliable deterministic results.

---

## Stage 4: Adjudication (conditional)

### When to trigger
Run a single adjudication pass **only** when:
- A validator returned `reject`, **and**
- The original LLM response was not already `unclear_manual_review`

If the original response was `unclear_manual_review` or validators returned only warnings/downgrades, skip adjudication — the validators have already applied their corrections.

### Adjudication call
A second LLM call with:
- The original input payload
- The original LLM classification (full structured output)
- The list of validator flags and actions

The adjudication prompt instructs the model to:
- Consider the validator concerns
- Revise conservatively — only change the classification if the flags identify a genuine error
- Return the same output schema

### Post-adjudication
- Re-run the structural and cross-field validators (not a full re-adjudication loop)
- If the output still has `reject`-level issues, force `unclear_manual_review`
- Do **not** loop further

### Cost control
Most papers should not need adjudication. If adjudication rate exceeds 15% on a batch, review the prompt and validators rather than relying on the adjudication pass.

---

## Integration with existing pipeline

### Relationship to `04_source_categorisation_heuristic.py`
The LLM classifier does **not** replace the existing heuristic script immediately. Instead:

1. Build the LLM pipeline as a new module at `src/pipelines/source_categorisation/`
2. Write output to the same `source_categorisation_registry.csv` schema so downstream stages work unchanged
3. Run both classifiers on the gold standard and compare
4. Once the LLM classifier demonstrably outperforms the heuristic, update `04_source_categorisation_heuristic.py` to call the LLM pipeline (with the heuristic as a fallback when the API is unavailable)

### Manual override precedence
The existing `source_categorisation_manual_review.csv` (291 reviewed rows) takes precedence over any automated classification. The controller must:
1. Check the manual review ledger before running the LLM
2. If a paper has a reviewed `final_source_category`, use that and skip the LLM call
3. Record `classification_source = "manual_review"` in the output

### Registry output compatibility
The final output must include at minimum these columns (matching the existing registry):
- `paper_id`, `covidence_id`, `title`, `authors`, `published_year`, `journal`
- `tags`, `notes`
- `text_json_path`, `preferred_text_json_path`, `preferred_text_source`
- `proceedings_detected`, `trim_status`
- `source_category`, `source_subtype`
- `classification_confidence`
- `contains_individual_level_data`, `contains_group_level_data`
- `case_series_split_candidate`
- `preferred_langextract_mode`, `langextract_eligible`
- `manual_review_required`, `recommended_next_action`
- `categorisation_reason` — validator flags + LLM reasoning summary
- `categorisation_version` — e.g. `llm_v1_gpt4.1`
- `categorised_at_utc`
- `classification_source` — `"llm"` | `"manual_review"` | `"heuristic_fallback"`

The `source_subtype`, `preferred_langextract_mode`, `langextract_eligible`, `case_series_split_candidate`, and `recommended_next_action` fields can be derived deterministically from `source_category` + `contains_individual_level_data` + `contains_group_level_data` + `proceedings_detected` + `trim_status` using the existing routing logic. Do not ask the LLM to populate these.

---

## Suggested module layout

```
src/pipelines/source_categorisation/
    __init__.py
    models.py          # Pydantic schema and derived routing logic
    prepare.py         # Stage 1: input assembly
    classify.py        # Stage 2: LLM call
    validate.py        # Stage 3: deterministic validators
    adjudicate.py      # Stage 4: conditional adjudication
    controller.py      # Orchestrator: prepare → classify → validate → adjudicate → output
    io.py              # Registry CSV reader/writer

tests/
    test_source_categorisation_models.py
    test_source_categorisation_validate.py
    test_source_categorisation_controller.py
```

---

## Benchmarking

### Existing gold standard
Use the 30-row gold set at `qa/validation/source_categorisation/gold_standard/04_categorisation_gold_standard.csv` as the primary benchmark. The key columns are:
- `paper_id`
- `predicted_source_category` (current heuristic output)
- `reviewed_source_category` (human-reviewed ground truth)
- `reviewed_extractable_sps_case_count` (for reference, not scored here)

Current heuristic baseline: **20/30 = 66.7%** source-category accuracy.

### Evaluation metrics
Track per batch:
- Source-category accuracy (exact match)
- Source-category accuracy excluding `unclear_manual_review` (how often it gets it right when it commits)
- Abstention rate (proportion routed to `unclear_manual_review`)
- Per-category precision and recall
- Confusion matrix (to detect whether the known error patterns are resolved)
- Adjudication rate (should be <15%)
- Mean evidence items per classification

### Error analysis
After each benchmark run, produce a row-level comparison CSV:
- `paper_id`, `gold_category`, `llm_category`, `heuristic_category`, `match_llm`, `match_heuristic`, `llm_confidence`, `validator_flags`

### Expansion
After the first benchmark on the existing 30 rows:
1. Identify remaining error patterns
2. Expand the gold set with papers that stress the weak areas (target 50–80 total)
3. Re-benchmark after prompt or validator changes

---

## Implementation order

1. **Schema** (`models.py`)
   - Pydantic models for the LLM output schema and evidence items
   - Deterministic routing-field derivation (subtype, langextract mode, etc.)
   - JSON Schema export for Structured Outputs

2. **Input assembly** (`prepare.py`)
   - Build one function that reads metadata + text artefacts and returns a typed payload
   - Token-budget truncation of text content

3. **LLM categorisation** (`classify.py`)
   - Build one function that submits the payload and returns a parsed Pydantic model
   - System prompt with category definitions and confusion-pattern guidance

4. **Validation** (`validate.py`)
   - Deterministic validator functions returning pass/warning/downgrade/reject

5. **Adjudication** (`adjudicate.py`)
   - Conditional second LLM call with original output + validator flags

6. **Controller** (`controller.py`)
   - `process_paper()`: manual-override check → prepare → classify → validate → adjudicate if needed → validate again → derive routing fields → return final result
   - `process_batch()`: iterate over papers, write registry output

7. **Registry output** (`io.py`)
   - Write CSV matching the existing `source_categorisation_registry.csv` schema

8. **Benchmark harness**
   - Script to run the LLM pipeline on the gold set and produce the comparison CSV

---

## API failure and cost management

### Fallback
If the OpenAI API is unreachable or returns a non-retryable error for a paper:
- Log the failure
- Fall back to the heuristic classifier for that paper
- Record `classification_source = "heuristic_fallback"` and `validator_flags = ["API_UNAVAILABLE"]`

### Rate limiting
Use basic retry with exponential backoff (3 retries, starting at 1s). Do not retry indefinitely.

### Cost estimate
At ~6,000 input tokens + ~500 output tokens per paper with `gpt-4.1`:
- ~$0.016 per paper (primary call only)
- ~$0.032 per paper if adjudication is triggered
- Full corpus (~290 papers): ~$5–10 for a complete run

This is low enough to re-run freely during development.

---

## Testing requirements

### Unit tests
- `models.py`: schema round-trip, routing-field derivation for each category
- `validate.py`: each validator catches its target inconsistency and passes clean inputs
- `prepare.py`: stable output structure from known fixtures

### Integration tests (on gold standard)
The benchmark harness serves as the integration test. Target:
- Source-category accuracy ≥ 85% on the 30-row gold set (vs. 66.7% heuristic baseline)
- No regressions on the 20 papers the heuristic already gets right

### Regression tests
Add a test case for each new failure mode discovered during benchmarking.

---

## Decision policy

When uncertain:
- Lower confidence
- Require manual review
- Prefer `unclear_manual_review`

Do not optimise for forced coverage.
A false confident categorisation is worse than a correct abstention.

---

## Coding requirements

- British English in prompts, comments, and documentation.
- Small, reviewable changes.
- Functions narrow in scope.
- Reproducibility and auditability preserved.
- No hidden heuristics in prompt-building code.
- Validator decisions logged in machine-readable form.
- Do not silently coerce weak outputs into confident labels.
- `temperature = 0` for all LLM calls.
- Record model ID, timestamp, and token usage in every output row.

---

## Deliverable definition

This task is complete only when:

1. Strict categorisation schema exists and exports valid JSON Schema
2. Input assembly builds payloads from existing artefacts
3. LLM categorisation call returns schema-conforming output
4. Deterministic validators catch known inconsistencies
5. Conditional adjudication pass works
6. Controller orchestrates the full flow for a single paper
7. Benchmark harness runs on the 30-row gold set and reports accuracy
8. LLM pipeline achieves ≥85% source-category accuracy on the gold set
9. Registry output is compatible with downstream stages
10. Manual-override precedence is respected

The pipeline must run end-to-end on the full gold set before being considered complete.

---

## Immediate next step

1. Define the Pydantic schema (`models.py`) with JSON Schema export
2. Implement input assembly (`prepare.py`)
3. Write the system prompt and LLM call (`classify.py`)
4. Run on 5 representative papers from the gold set (mix of correct and incorrect heuristic predictions)
5. Inspect outputs before building validators
