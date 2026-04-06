# `src` / `validation`

## Purpose
Reusable validation and audit utilities for checking generated registries or artifacts against source content.

These scripts are intentionally separate from `src/pipelines/`:
- pipelines build or transform canonical outputs under `data/`
- validation scripts audit those outputs and report whether they appear consistent with the underlying evidence
- non-canonical validation reports, review sheets, and spot checks should be written under `qa/validation/`, not `data/` or `results/`

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
- refuses to open a new batch while an earlier batch is still awaiting feedback
- runs `05_trim_proceedings_text.py` and `05b_validate_proceedings_text.py` on the selected subset only
- writes a batch manifest under `qa/trimming/batches/`
- writes subset outputs and a machine-readable batch report under `qa/trimming/reports/<batch_id>/`

Prepare the next default 10-file batch:

```bash
python src/validation/manage_trimming_batches.py
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
