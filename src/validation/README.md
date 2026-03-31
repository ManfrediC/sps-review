# `src` / `validation`

## Purpose
Reusable validation and audit utilities for checking generated registries or artifacts against source content.

These scripts are intentionally separate from `src/pipelines/`:
- pipelines build or transform canonical outputs under `data/`
- validation scripts audit those outputs and report whether they appear consistent with the underlying evidence

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
python src/validation/validate_pdf_source_registry.py --sample-size 20 --output-path results/pdf_source_registry_validation.json
```
