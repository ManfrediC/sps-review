# `src` / `validation`

## Purpose
Reusable validation and audit utilities for checking generated registries or artifacts against source content.

These scripts are intentionally separate from `src/pipelines/`:
- pipelines build or transform canonical outputs under `data/`
- validation scripts audit those outputs and report whether they appear consistent with the underlying evidence
- non-canonical validation reports, review sheets, and spot checks should be written under `qa/validation/`, not `data/` or `results/`

The retired stage-05 autoresearch bundle is now archived under `legacy/stage_05_autoresearch/`. `src/validation/` keeps the live manual batch-management, review, and feedback utilities for stage 05.

The retired deterministic stage-05 validation bundle now lives under `legacy/stage_05_deterministic/src/validation/`.

## Available scripts

### `validate_pdf_source_registry.py`

Validates sampled rows from `data/references/pdf_source_registry.csv` against source content.

It:
- samples eligible registry rows reproducibly using a configurable random seed
- prefers OCR-backed text from `data/extraction_json/text/{paper_id}.json` when available
- falls back to direct PDF text extraction when no text JSON exists
- checks title, first-author surname tokens, and publication year against the recovered text
- reports per-row validation statuses such as `confirmed_exact`, `confirmed_fuzzy_title`, `title_year_only`, or `no_match`
- can write a machine-readable JSON report

### Run

```bash
python src/validation/validate_pdf_source_registry.py --sample-size 20 --seed 20260331
```

Write a JSON report:

```bash
python src/validation/validate_pdf_source_registry.py --sample-size 20 --output-path qa/validation/pdf_source_registry_validation.json
```

### `validate_text_extraction_quality.py`

Builds a stratified manual-review sample for step 03 extraction QA.

Default scheme for `n=300`:
- `150` baseline random records
- `60` OCR-applied records
- `45` long or proceedings-like records
- `45` text-artifact-risk records

If a high-risk bucket has fewer available records than requested, the remainder is filled from the baseline pool.

The script:
- reads `data/extraction_json/text/{paper_id}.json`
- joins metadata from `data/references/pdf_source_registry.csv`
- oversamples OCR, long/proceedings, and artifact-risk extractions
- writes an optional JSON report and a CSV review sheet for manual audit

Run the default `n=300` audit and write both outputs:

```bash
python src/validation/validate_text_extraction_quality.py --output-path qa/validation/text_extraction_quality_sample.json --review-csv-path qa/validation/text_extraction_quality_review.csv
```

Run a smaller quick check:

```bash
python src/validation/validate_text_extraction_quality.py --sample-size 20 --seed 20260401
```

### `export_text_json_to_txt.py`

Converts `data/extraction_json/text/{paper_id}.json` into human-readable `.txt` files for manual review.

It:
- reads page-level text JSON from `data/extraction_json/text/`
- joins title/author/year metadata from `data/references/pdf_source_registry.csv`
- writes one `{paper_id}.txt` file per exported record
- can export the full corpus or a selected subset via `--paper-id` and `--selection-csv`
- is the utility used to refresh `qa/validation/text_exports/all/` plus the weaker/failure subset folders after cleanup reruns

Export the full corpus:

```bash
python src/validation/export_text_json_to_txt.py --output-dir qa/validation/text_exports/all --force
```

Export a selected subset:

```bash
python src/validation/export_text_json_to_txt.py --selection-csv qa/validation/text_extraction_remainder_likely_failures.csv --output-dir qa/validation/text_exports/likely_failures --force
```

### `build_source_categorisation_review_sample.py`

Builds a stratified manual-review batch for step 04 source categorisation calibration.

Default batch for `n=30`:
- `10` conference-edge rows
- `10` case-series versus group-study boundary rows
- `5` review/lab-boundary rows
- `5` high-confidence controls

The script:
- reads `data/references/source_categorisation_registry.csv`
- joins `data/references/source_sps_case_count_registry.csv` when available so review sheets use the separate case-count stage
- excludes already manually reviewed rows by default
- selects rows using explicit bucket signals and a reproducible seed
- writes an optional JSON summary and a compact CSV review sheet
- can export preferred-text TXT packets for the same papers

Build the default batch and export review materials:

```bash
python src/validation/build_source_categorisation_review_sample.py --output-path qa/validation/source_categorisation/source_categorisation_review_sample_n30_seed20260405.json --review-csv-path qa/validation/source_categorisation/source_categorisation_review_sample_n30_seed20260405.csv --text-output-dir qa/validation/source_categorisation/text_packets_n30_seed20260405
```

### `find_missed_proceedings_candidates.py`

Builds a review queue for short proceedings fragments or conference-style abstracts that stage 04 did not currently label `conference_abstract`.

The script:
- reads `data/references/source_categorisation_registry.csv`
- excludes rows already labelled `conference_abstract`
- matches the reference title and authors back to the extracted text
- combines metadata cues such as `conference paper`, `supplement`, `poster`, or `conference abstract` with local proceedings-format cues such as poster-session headers or code-prefixed abstract blocks
- writes a non-canonical JSON summary, review CSV, and optional snippet TXT files under `qa/validation/`
- supports focused testing via repeated `--paper-id` flags so heuristics can be reviewed on a small batch before any wider audit run

Run a focused mixed batch first:

```bash
python src/validation/find_missed_proceedings_candidates.py --paper-id 5753 --paper-id 1597 --paper-id 1935 --paper-id 1017 --output-path qa/validation/missed_proceedings_audit_2026-04-06/focused_batch/report.json --review-csv-path qa/validation/missed_proceedings_audit_2026-04-06/focused_batch/review_queue.csv --snippet-dir qa/validation/missed_proceedings_audit_2026-04-06/focused_batch/snippets
```

After the focused batch looks sensible, run a wider audit:

```bash
python src/validation/find_missed_proceedings_candidates.py --output-path qa/validation/missed_proceedings_audit_2026-04-06/report.json --review-csv-path qa/validation/missed_proceedings_audit_2026-04-06/review_queue.csv --snippet-dir qa/validation/missed_proceedings_audit_2026-04-06/snippets
```

### `manage_trimming_batches.py`

Prepares one proceedings-trimming QA batch at a time for the stage-05 improvement loop.

The script:
- reads the resolved stage-04 conference-abstract pool
- excludes papers already frozen in `qa/trimming/feedback/` or `qa/trimming/regression/`
- resumes an interrupted processing batch instead of starting from scratch
- refuses to open a new batch while an earlier batch is still unresolved
- runs `05_trim_proceedings_text_LLM.py`, `05b_validate_proceedings_text_LLM.py`, and `05c_publish_proceedings_ready.py` incrementally on the selected subset only
- writes a batch manifest under `qa/trimming/batches/`
- writes subset candidate, final, and proceedings-ready artefacts plus a machine-readable batch report under `qa/trimming/reports/<batch_id>/`

Prepare the next default 50-file batch:

```bash
python src/validation/manage_trimming_batches.py
```

Prepare a smaller explicit batch size:

```bash
python src/validation/manage_trimming_batches.py --batch-size 10
```

### `review_stage05_llm_app.py`

Read-only Streamlit inspector for the live LLM-assisted stage-05 proceedings workflow.

It:
- reads the canonical registries by default and can be pointed at batch-local `text_trim_llm_candidate_registry.csv` and `text_trim_llm_registry.csv` files
- joins the source PDF from `data/references/paper_artifact_registry.csv`
- shows the source PDF alongside the current LLM trim decision
- includes page-search jump controls driven by the extracted text
- shows a compact preview of the final LLM-trimmed text when one exists
- displays every heuristic end candidate with its rationale and end index
- lets you inspect the selected candidate boundary and the full overshoot span with candidate-end markers
- is the preferred inspection surface before `05c_publish_proceedings_ready.py` promotes the accepted result into `data/extraction_json/text_proceedings_ready/`

Run:

```bash
streamlit run src/validation/review_stage05_llm_app.py
```

### `review_stage06_count_app.py`

Streamlit review workflow for the stage-06 SPS case-count pipeline.

It:
- opens a specific `results/stage06_count_runs/<run_id>/` folder or the live `source_sps_case_count_registry.csv`
- joins the source PDF from `data/references/paper_artifact_registry.csv`
- shows the source PDF beside the final stage-06 count decision
- supports PDF-page search using the preferred text JSON selected for stage 06
- displays heuristic candidates, the selected LLM decision, and stored evidence quotes
- lets the reviewer record whether the predicted count is correct and save notes under `qa/validation/stage06_count_review/`
- also syncs reviewed responses into the canonical stage-06 override ledger `data/references/source_sps_case_count_manual_review.csv`

Run:

```bash
streamlit run src/validation/review_stage06_count_app.py
```

### `build_stage06_backfill_campaign.py`

Builds the stage-06 hybrid backfill campaign inventory for papers that are still
neither manual-gold reviewed nor processed by a `hybrid_v2_*` stage-06 run.

It:
- reads active stage-06 gold papers from `qa/validation/source_categorisation/gold_standard/stage06_count_gold/manifest.json`
- reads reviewed rows from `data/references/source_sps_case_count_manual_review.csv`
- scans `results/stage06_count_runs/` for `hybrid_v2_*` result payloads
- writes a campaign manifest, one batch manifest per 50-paper chunk, and a
  running status table under `qa/validation/stage06_llm/backfill_campaign/`
- treats each campaign ID as a frozen target set once created; if the source
  universe changes or a new batch layout is needed, create a new campaign ID
  instead of mutating an existing campaign's membership
- supports an explicit in-place repair mode for a drifted existing campaign;
  this reconstructs the frozen batch partition from the completed batch runs
  already on disk plus the current uncovered remainder

Run:

```bash
python src/validation/build_stage06_backfill_campaign.py
```

Repair an existing campaign in place:

```bash
python src/validation/build_stage06_backfill_campaign.py --campaign-id stage06_backfill_20260418 --repair-existing-campaign
```

### `run_stage06_backfill_batch.py`

Runs or resumes one subset stage-06 hybrid backfill batch from a batch manifest
and then builds the batch QA pack.

It:
  - expands the batch manifest into repeated `--paper-id` flags for `06_extract_sps_case_counts_hybrid.py`
  - runs the same stage-06 dependency preflight as the canonical hybrid entrypoint before a paid batch starts
  - writes raw batch-run CSVs under `qa/validation/stage06_llm/`
  - supports resume batches by appending `_resumeNN` run IDs for remaining papers
  - rebuilds the combined batch CSV, inspection Markdown pack, review-comments CSV,
    and review-notes Markdown scaffold after each successful invocation
  - keeps the batch inspection pack tied to the batch's own run artefacts instead of attaching decision/evidence JSON from unrelated runs
  - refreshes the campaign manifest/status snapshot after the batch completes

Estimate a batch without model calls:

```bash
python src/validation/run_stage06_backfill_batch.py --batch-manifest qa/validation/stage06_llm/backfill_campaign/stage06_backfill_20260418/batches/b001.json --estimate-only
```

Run a paid batch:

```bash
python src/validation/run_stage06_backfill_batch.py --batch-manifest qa/validation/stage06_llm/backfill_campaign/stage06_backfill_20260418/batches/b001.json --allow-paid-run
```

### `benchmark_stage06_hybrid.py`

Benchmarks one or more stage-06 workflow CSV outputs against the reviewed stage-06 gold JSON corpus.

It:
- reads active gold papers from `qa/validation/source_categorisation/gold_standard/stage06_count_gold/`
- can score a focused benchmark selection such as `gold30`, `gold20`, or a curated regression pack
- supports exclusions so the remaining active gold papers can be used as a final untouched acceptance set
- reports exact accuracy, silent wrong auto-accepts, manual-review rows, reviewed overrides, and missing predictions
- can write JSON and Markdown summaries for archived benchmark reports

Run against the frozen 30-paper benchmark:

```bash
python src/validation/benchmark_stage06_hybrid.py --selection-path qa/validation/stage06_llm/stage06_gold30_balanced_20260416.selection.json --workflow legacy=qa/validation/stage06_llm/stage06_gold30_current_iter1_20260416.csv --workflow llm=qa/validation/stage06_llm/stage06_gold30_llm_iter2_20260416.csv
```

### `bootstrap_stage06_gold_json.py`

Builds a stage-06 per-paper gold JSON corpus from the reviewed cumulative gold CSV.

It:
- reads reviewed rows from `qa/validation/source_categorisation/gold_standard/04_categorisation_gold_standard.csv`
- writes one reviewed stage-06-style JSON per active paper under `qa/validation/source_categorisation/gold_standard/stage06_count_gold/papers/`
- writes a manifest with active, excluded, and conflict statuses
- embeds the reviewed truth together with registry snapshots and any attached historical stage-06 run artefacts that can still be resolved

Run:

```bash
python src/validation/bootstrap_stage06_gold_json.py
```

Preview the manifest summary without writing files:

```bash
python src/validation/bootstrap_stage06_gold_json.py --dry-run
```

### `update_trimming_review_outputs.py`

Refreshes stage-05 review artefacts after a general code patch and rerun of the batch outputs.

It:
- rebuilds `review_queue.csv` from the latest batch-local trim/QC registries
- recompiles `feedback.json` from `responses.csv`
- refreshes `manual_overrides.csv`
- rewrites the batch acceptance report
- rewrites the combined regression-plus-batch evaluation report

Run:

```bash
python src/validation/update_trimming_review_outputs.py --batch-id batch_009
```

### `apply_trimming_manual_overrides.py`

Applies fallback per-paper manual overrides for residual failures after the preferred general stage-05 LLM patch path has been tried.

It:
- reads enabled rows from `manual_overrides.csv`
- extracts the reviewed start/end span directly from the full text JSON
- overwrites the batch-local final LLM-trimmed JSON for that paper
- updates the batch-local `text_trim_llm_registry.csv`
- republishes the affected batch-local proceedings-ready JSONs through `05c_publish_proceedings_ready.py`

Run:

```bash
python src/validation/apply_trimming_manual_overrides.py --batch-id batch_009 --only-enabled
```

### `build_stage04_gold_batch.py`

Builds a reproducible `n=10` gold-standard review batch for stage 04.

Default scheme:
- `2` conference-edge rows
- `2` case-series versus group-study boundary rows
- `2` review/lab-boundary rows
- `2` count-ambiguity rows
- `2` high-confidence controls

The script:
- reads the live stage-04 source and count registries
- excludes papers already present in `examples/datasheet_examples_MC_Case_Report_Form.csv`
- excludes papers already adjudicated in `data/references/source_categorisation_manual_review.csv` by default
- excludes papers already used in earlier gold rounds by default
- requires a local PDF plus extracted text JSON
- writes a round folder under `qa/validation/source_categorisation/gold_standard/` containing:
  - `selection_manifest.json`
  - `selection_queue.csv`
  - `responses.csv`
  - `gold_standard_stage04_<round_id>.csv`

Canonical cumulative reviewed file:
- `qa/validation/source_categorisation/gold_standard/04_categorisation_gold_standard.csv`

Build the default 10-paper batch:

```bash
python src/validation/build_stage04_gold_batch.py
```

Build a larger 20-paper batch with balanced quotas:

```bash
python src/validation/build_stage04_gold_batch.py --conference-edge-size 4 --case-group-boundary-size 4 --review-lab-edge-size 4 --count-ambiguity-size 4 --high-confidence-control-size 4
```

### `review_stage04_gold_app.py`

Streamlit reviewer for the stage-04 gold rounds.

It:
- loads a selected round from `qa/validation/source_categorisation/gold_standard/`
- shows the source PDF alongside the predicted source category and count
- includes a search box that uses extracted page text to jump the embedded PDF viewer to matching pages
- lets the reviewer confirm or edit the prediction
- saves each response immediately to `responses.csv`
- writes a round snapshot `gold_standard_stage04_<round_id>.csv`
- refreshes the canonical cumulative gold file `qa/validation/source_categorisation/gold_standard/04_categorisation_gold_standard.csv` once a round is complete

Run:

```bash
streamlit run src/validation/review_stage04_gold_app.py
```

### `build_stage04_llm_gold_batch.py`

Builds a reproducible `n=10` LLM stage-04 category-and-count review batch.

Default scheme:
- `3` conference-edge rows
- `3` case/group-boundary rows
- `2` review/lab-boundary rows
- `2` high-confidence controls

The script:
- reads `data/references/source_categorisation_registry.csv`
- joins `data/references/source_sps_case_count_registry.csv`
- excludes papers already adjudicated in `data/references/source_categorisation_manual_review.csv` by default
- excludes papers already present in earlier gold-standard rounds by default
- requires a local PDF plus extracted text JSON
- writes a round folder under `qa/validation/source_categorisation/llm_category_review/`
- appends completed reviews into `qa/validation/source_categorisation/gold_standard/04_categorisation_gold_standard.csv`
- carries the joint LLM category and count prediction into the review queue

Build the default 10-paper batch:

```bash
python src/validation/build_stage04_llm_gold_batch.py
```

### `review_stage04_llm_gold_app.py`

Streamlit reviewer for the LLM stage-04 joint category-and-count rounds.

It:
- loads a selected round from `qa/validation/source_categorisation/llm_category_review/`
- shows the source PDF alongside the LLM-predicted source category and count
- includes a search box that uses extracted page text to jump the embedded PDF viewer to matching pages
- lets the reviewer confirm or edit both the category and the extractable SPS case count
- saves each response immediately to `responses.csv`
- writes a round snapshot CSV
- refreshes the canonical cumulative gold file `qa/validation/source_categorisation/gold_standard/04_categorisation_gold_standard.csv` once a round is complete

Run:

```bash
streamlit run src/validation/review_stage04_llm_gold_app.py
```

### `benchmark_stage04_gold.py`

Benchmarks the legacy heuristic stage-04 flow against reviewed gold-standard rows.

It:
- reruns `src/legacy/04_source_categorisation_heuristic.py` and `06_extract_sps_case_counts.py` logic on reviewed rows
- reports category accuracy and exact count accuracy
- breaks accuracy down by selection bucket
- excludes `likely_wrong_pdf_attached` and `incorrect_reference` rows by default

Run against the cumulative master file:

```bash
python src/validation/benchmark_stage04_gold.py
```

The default benchmark input is:
- `qa/validation/source_categorisation/gold_standard/04_categorisation_gold_standard.csv`

### `stage04_model_benchmark/`

Dedicated directory for cross-model stage-04 comparison.

It keeps the benchmark workflow separate from both:
- the heuristic gold benchmark
- the Streamlit review rounds

Main entry points:
- `src/validation/stage04_model_benchmark/build_benchmark_set.py`
- `src/validation/stage04_model_benchmark/freeze_payloads.py`
- `src/validation/stage04_model_benchmark/run_models.py`
- `src/validation/stage04_model_benchmark/score_models.py`

The workflow:
- builds a fixed mixed 20-paper benchmark from already reviewed stage-04 gold rows
- freezes the exact payload bundle for every paper
- records `tiktoken` prompt estimates before any paid run
- reuses cached `gpt-4.1` outputs without regenerating them
- runs only the newly chosen models with the same schema, validators, and adjudication policy
- writes all benchmark artefacts under `qa/validation/source_categorisation/model_benchmark/`
