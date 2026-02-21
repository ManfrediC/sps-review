# Pipelines

This folder contains the text extraction pipeline for source PDFs.

## `01_extract_text.py`

Briefly, this script:

- Reads all `*.pdf` files from `data/pdf_original`.
- Derives `paper_id` from each filename (the number before the first underscore).
- Extracts text page-by-page with `pypdf`.
- Computes a SHA-256 checksum for each source PDF.
- Detects low-text PDFs and optionally runs OCR (`ocrmypdf`) before re-extracting text.
- Writes one JSON output per PDF to `data/extraction_json/text/{paper_id}.json`.

## Output JSON includes

- `paper_id`, `source_filename`, `source_sha256`
- `n_pages`, `page_char_counts`, `pages`
- OCR status fields such as `needs_ocr_before_ocr`, `needs_ocr`, `ocr_applied`, `ocr_error`

## Run

From repo root:

```bash
python src/pipelines/01_extract_text.py
```

## `02_LangExtract.py`

This script reads text JSON files from `data/extraction_json/text`, runs
LangExtract with an OpenAI model, and writes:

- Raw LangExtract entities to `data/extraction_json/langextract/{paper_id}.json`
- Section summaries + overall summary to `data/extraction_json/summary/{paper_id}.json`

### Requirements

- `langextract[openai]` installed in your virtual environment
- `OPENAI_API_KEY` set in your shell environment

### Run

Dry run (no API calls):

```bash
python src/pipelines/02_LangExtract.py --dry-run --limit 2
```

Real run:

```bash
python src/pipelines/02_LangExtract.py
```
