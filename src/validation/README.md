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
