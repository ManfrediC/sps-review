# Plan: complete the remaining LLM stage-05 proceedings rollout

## Goal

Run the LLM variant of step 05 on every remaining proceedings paper that is already `confirmed_full` in `data/references/proceedings_text_qc_registry.csv`, excluding papers that already have an active manually checked gold-standard JSON, so the proceedings subset is ready for downstream extraction work.

This plan assumes the current LLM stage-05 flow remains the preferred extraction path:

- `src/pipelines/05_trim_proceedings_text_LLM.py`
- `src/pipelines/05b_validate_proceedings_text_LLM.py`
- `src/validation/review_stage05_llm_app.py`

## Current state

As of `2026-04-13`:

- `106` proceedings papers are currently eligible for a ready-to-use proceedings text:
  - `qc_status == confirmed_full`
  - `trim_status == trimmed_auto`
- `20` have already been run through the LLM workflow and manually checked in the Streamlit reviewer.
- `52` eligible papers already have an active manually checked gold JSON in `qa/trimming/gold_standard/manifest.json`.
- `16` papers are in both sets.
- `56` eligible papers are therefore already ready via either:
  - accepted LLM trim output, or
  - active gold-standard JSON
- `50` remain for LLM rollout.

Remaining workload by source text size:

- `11` papers with `1-2` text pages
- `8` papers with `3-10` text pages
- `9` papers with `11-100` text pages
- `22` papers with `101+` text pages

Gold-standard rule:

- if a paper has an active entry in `qa/trimming/gold_standard/manifest.json`, it does not need to go through the LLM stage-05 path
- treat that gold JSON as already accepted proceedings text for downstream readiness work

Important downstream constraint:

- `src/pipelines/06_extract_sps_case_counts.py`
- `src/pipelines/07_split_case_series.py`
- `src/pipelines/10_langextract.py`
- `src/pipelines/12_build_paper_artifact_registry.py`

still only know about the canonical deterministic `data/extraction_json/text_trimmed/` path. They do not yet consume `data/extraction_json/text_trimmed_llm/`.

That means "run the remaining LLM trims" is not sufficient on its own. A short downstream-routing step is also required before the corpus is truly ready for the next stage.

## Success criteria

The rollout is complete when all of the following are true:

1. Every remaining eligible proceedings paper has:
   - either an active gold-standard JSON entry,
   - or:
     - a candidate package in `data/extraction_json/text_trimmed_llm_candidates/`
     - a final LLM-reviewed trim in `data/extraction_json/text_trimmed_llm/`
     - a row in `data/references/text_trim_llm_candidate_registry.csv`
     - a row in `data/references/text_trim_llm_registry.csv`
2. Any malformed or uncertain output is resolved before moving on:
   - by a heuristic patch,
   - or by a targeted manual override,
   - or by a clearly labelled manual-review hold row
3. Downstream stages prefer accepted gold-standard proceedings text first, then vetted LLM trim, instead of silently falling back to full proceedings text.
4. The remaining proceedings pool reaches `0` for:
   - `qc_status == confirmed_full`
   - `trim_status == trimmed_auto`
   - `paper_id not in text_trim_llm_registry.csv`
   - `paper_id not in qa/trimming/gold_standard/manifest.json`

## Recommended rollout strategy

### Principle 1: process by document size, not by paper ID order

The expensive part is candidate generation on very large proceedings PDFs. Validation calls are comparatively cheap. Processing should therefore move from small texts to large volumes.

### Principle 2: keep the review loop tight

After each batch:

- inspect the batch in `src/validation/review_stage05_llm_app.py`
- check for:
  - trailing references
  - trailing disclosures
  - bleed into the next abstract
  - obvious early truncation
- patch heuristics immediately when a repeated pattern appears
- rerun only the affected paper IDs

### Principle 3: do not overwrite the deterministic baseline during rollout

Keep the deterministic `text_trimmed/` outputs untouched until the full LLM rollout is accepted. Route downstream stages to prefer the LLM path instead of replacing baseline files mid-rollout.

## Execution phases

### Phase 1: quick-win batch completion

Target the remaining `19` papers with `text_n_pages <= 10` and no active gold JSON.

Recommended batch size:

- candidate generation: `8-10` papers per run
- LLM validation: the same `8-10` papers per run

Why first:

- fastest throughput
- cheapest API spend per accepted paper
- best way to surface any remaining prompt or heuristic edge cases before the long-volume runs

Suggested first-wave pool:

- `5286`
- `5371`
- `5573`
- `5600`
- `6452`
- `8009`
- `12623`
- `12630`
- `5315`
- `6680`
- `6732`
- `5362`
- `6691`
- `12536`
- `12594`
- `6257`
- `1675`
- `969`
- `1391`

Operational loop for each batch:

1. Run `05_trim_proceedings_text_LLM.py` on the selected paper IDs.
2. Run `05b_validate_proceedings_text_LLM.py` on the same IDs with `OPENAI_API_KEY` loaded from `env/openai_api_key.env`.
3. Review the batch in the Streamlit app.
4. Fix any repeated boundary issue before opening the next batch.

### Phase 2: medium-size proceedings batch completion

Target the remaining `9` papers with `11-100` text pages and no active gold JSON.

Recommended batch size:

- candidate generation: `4-5` papers per run
- LLM validation: the same `4-5` papers per run

Ordering rule:

- sort ascending by `text_n_pages`
- then ascending by `best_match_page_index`

Why:

- this keeps each run predictable
- it avoids mixing a near-trivial 15-page proceedings paper with a 300-page one
- it makes timeout behaviour easier to diagnose

### Phase 3: long-volume proceedings batch completion

Target the remaining `22` papers with `101+` text pages and no active gold JSON.

Recommended batch sizing:

- `101-300` text pages: `2-3` papers per run
- `301-500` text pages: `2` papers per run
- `501+` text pages: `1` paper per run

For this phase, assume candidate generation is the bottleneck and budget generous timeouts.

Known long-volume examples that should be treated as single-paper runs:

- `5970`
- `1605`
- `1838`
- `7503`
- `1237`
- `12387`
- `6204`
- `1416`
- `12301`
- `12473`

Execution notes:

- keep validation separate from generation so a slow candidate run does not hide a clean validation result
- if a candidate JSON already exists and looks valid, do not regenerate it unnecessarily
- when a run times out after writing partial candidate packages, rebuild the candidate registry from the written JSONs before continuing

### Phase 4: outlier handling

Any paper that does not pass cleanly in review should be handled immediately, not deferred to the end.

Allowed fixes:

- shared heuristic patch in `src/pipelines/_proceedings_trim_llm.py`
- targeted proceedings trim override where the problem is paper-specific
- single-paper rerun through both LLM scripts

Avoid:

- silent acceptance of malformed boundaries
- broad manual editing of output JSON without provenance

## Downstream-readiness work

This is the step that makes the corpus genuinely ready for the next stage.

### Recommended approach

Teach downstream consumers to prefer accepted proceedings text from either source:

- active gold-standard JSON when present
- otherwise LLM-vetted proceedings trim when present

Recommended preference order:

- case-series split output when present
- active gold-standard proceedings JSON when present
- `text_trimmed_llm/{paper_id}.json`
- `text_trimmed/{paper_id}.json`
- raw `text/{paper_id}.json`

### Files to update

At minimum:

- `src/pipelines/06_extract_sps_case_counts.py`
- `src/pipelines/07_split_case_series.py`
- `src/pipelines/10_langextract.py`
- `src/pipelines/12_build_paper_artifact_registry.py`

Recommended implementation pattern:

1. Add `TEXT_TRIMMED_LLM_DIR = data/extraction_json/text_trimmed_llm`.
2. Introduce one shared helper that resolves the preferred text path.
3. Reuse that helper in downstream stages instead of hand-rolled path selection.
4. Extend the artifact registry so it records LLM trim presence and path explicitly.

Why this is better than copying files into `text_trimmed/`:

- preserves provenance
- keeps gold, deterministic, and LLM outputs comparable
- avoids destructive replacement of the baseline stage-05 output

## Verification plan

### Batch-level checks

After each batch:

- confirm the expected paper IDs were added to:
  - `data/references/text_trim_llm_candidate_registry.csv`
  - `data/references/text_trim_llm_registry.csv`
- confirm the same IDs exist in:
  - `data/extraction_json/text_trimmed_llm_candidates/`
  - `data/extraction_json/text_trimmed_llm/`
- review the batch in `streamlit run src/validation/review_stage05_llm_app.py`

### Code-level checks

After any heuristic or routing patch:

- run
  - `pytest tests/test_05_trim_proceedings_text.py tests/test_05b_validate_proceedings_text.py tests/test_05_proceedings_text_llm.py`
- run any focused downstream tests covering new preferred-text resolution

### Completion checks

At the end of the rollout:

- confirm `remaining_count == 0` for the eligible proceedings set after excluding active gold JSON entries
- confirm downstream stages resolve to gold JSON first, then `text_trimmed_llm`, where available
- run one small end-to-end dry subset into the next stage to prove the hand-off works

## Practical execution order

Recommended order of work:

1. Finish Phases 1-3 until all `50` non-gold eligible proceedings papers have LLM outputs.
2. Handle any outliers immediately as Phase 4 work.
3. Implement the downstream preferred-text routing for both gold JSON and LLM trims.
4. Rebuild the relevant registries.
5. Run one focused downstream proof batch.
6. Only then treat the proceedings corpus as ready for the next stage.

## Definition of done

The proceedings subset is ready for the next step when:

- all `106` eligible proceedings papers are covered by either:
  - active gold-standard JSON, or
  - accepted LLM stage-05 output
- the reviewer app shows no unresolved malformed boundaries
- downstream stages prefer gold JSON first, then the LLM trim, automatically
- no eligible proceedings paper still relies on full proceedings text when an accepted gold or LLM proceedings text exists
