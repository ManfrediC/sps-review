# Pipelines

This folder contains the text extraction pipeline for source PDFs.

## `00_download_covidence_pdfs.py`

This script automates the Covidence full-text download step from the extraction view.

It:

- opens the Covidence extraction page in Chromium,
- logs in with runtime credentials or a saved browser session,
- finds each reference block with a `View full text` control,
- reveals the PDF link,
- downloads the PDF into `data/pdf_original`, and
- writes a JSONL manifest to `data/extraction_json/covidence/download_manifest.jsonl`.

After each run, it also refreshes `data/references/pdf_source_registry.csv` unless `--skip-registry-refresh` is passed.

### Requirements

- `playwright` installed in the project virtual environment
- Chromium installed via Playwright
- Covidence credentials supplied at runtime or through `COVIDENCE_EMAIL` and `COVIDENCE_PASSWORD`

### Run

First run:

```bash
python src/pipelines/00_download_covidence_pdfs.py
```

Headless rerun:

```bash
python src/pipelines/00_download_covidence_pdfs.py --headless
```

## `00_build_pdf_source_registry.py`

This script builds a reference-to-file registry in `data/references/pdf_source_registry.csv`.

It joins:

- the Covidence export in `data/references/sps_references_export.csv`,
- the downloaded PDFs in `data/pdf_original/`, and
- the Covidence download manifest in `data/extraction_json/covidence/download_manifest.jsonl`.

The output gives each reference its local PDF filename/path plus a `download_status`.

### Run

```bash
python src/pipelines/00_build_pdf_source_registry.py
```

## `00_build_paper_artifact_registry.py`

This is the cross-pipeline source-of-truth registry for the project.

It writes `data/references/paper_artifact_registry.csv` with one row per `paper_id` across the union of:

- the Covidence reference export,
- downloaded PDFs,
- text extraction outputs,
- LangExtract raw outputs,
- summary outputs, and
- quality-assessment outputs.

This makes the reference, local PDF, extracted text, and downstream AI artifacts traceable from one table.

### Run

```bash
python src/pipelines/00_build_paper_artifact_registry.py
```

## `00_trim_proceedings_text.py`

This script detects likely conference proceedings or other multi-abstract PDFs and trims them down to the one abstract/publication that matches the Covidence reference.

It:

- reads full text JSON files from `data/extraction_json/text`,
- detects proceedings using simple structural signals such as many pages, many title-like lines, and many author-like lines,
- segments the proceedings into abstract blocks,
- finds the best target block using fuzzy title and author matching against `data/references/sps_references_export.csv`,
- writes trimmed JSON files to `data/extraction_json/text_trimmed/{paper_id}.json`, and
- writes a decision registry to `data/references/text_trim_registry.csv`.

### Run

```bash
python src/pipelines/00_trim_proceedings_text.py
```

## `01_extract_text.py`

Briefly, this script:

- Reads all `*.pdf` files from `data/pdf_original`.
- Derives `paper_id` from each filename (the number before the first underscore).
- Extracts text page-by-page with `pypdf`.
- Computes a SHA-256 checksum for each source PDF.
- Detects low-text or corrupted native text and optionally runs OCR (`ocrmypdf`) before re-extracting text.
- Writes one JSON output per PDF to `data/extraction_json/text/{paper_id}.json`.
- Runs `00_trim_proceedings_text.py` to generate focused text artifacts for proceedings PDFs when possible.

## Output JSON includes

- `paper_id`, `source_filename`, `source_sha256`
- `n_pages`, `page_char_counts`, `pages`
- OCR status fields such as `needs_ocr_before_ocr`, `ocr_trigger_reasons`, `needs_ocr`, `remaining_text_quality_flags`, `ocr_applied`, `ocr_mode`, `ocr_error`

## Run

From repo root:

```bash
python src/pipelines/01_extract_text.py
```

## `02_LangExtract.py`

This script reads text JSON files from `data/extraction_json/text`, prefers `data/extraction_json/text_trimmed/{paper_id}.json` when it exists, runs
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

## `03_quality_assessment.py`

This script reads text JSON files from `data/extraction_json/text`, prefers `data/extraction_json/text_trimmed/{paper_id}.json` when it exists, and writes:

- Raw quality-assessment LangExtract output to `data/extraction_json/quality/raw/{paper_id}.json`
- Structured quality records to `data/extraction_json/quality/records/{paper_id}.json`
