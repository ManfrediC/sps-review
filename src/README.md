# `src` Overview

This folder contains the project pipeline scripts. They are designed to be run from the repository root and operate on the data stored under `data/`.

## Pipeline Order

1. `pipelines/00_download_covidence_pdfs.py`
   - Downloads source PDFs from the Covidence extraction view into `data/pdf_original/`.
   - Uses local/browser session state plus Covidence credentials.

2. `pipelines/00_build_pdf_source_registry.py`
   - Builds `data/references/pdf_source_registry.csv`.
   - Links each Covidence reference to its downloaded PDF path and download metadata.

3. `pipelines/01_extract_text.py`
   - Extracts page-level text from the downloaded PDFs.
   - Uses native PDF text first, then falls back to OCR when the extracted text is sparse or corrupted.
   - Writes `data/extraction_json/text/{paper_id}.json`.

4. `pipelines/00_trim_proceedings_text.py`
   - Detects large proceedings or multi-abstract PDFs.
   - Finds the target abstract/publication by fuzzy title and author matching.
   - Writes focused text records to `data/extraction_json/text_trimmed/{paper_id}.json`.

5. `pipelines/02_LangExtract.py`
   - Reads extracted text and runs LangExtract with OpenAI models.
   - Prefers trimmed proceedings text when available.
   - Writes raw extractions to `data/extraction_json/langextract/` and summaries to `data/extraction_json/summary/`.

6. `pipelines/03_quality_assessment.py`
   - Reads extracted text and runs publication-type detection plus dictionary-driven quality extraction.
   - Prefers trimmed proceedings text when available.
   - Writes raw outputs to `data/extraction_json/quality/raw/` and structured records to `data/extraction_json/quality/records/`.

## Registry / Support Scripts

- `pipelines/00_build_paper_artifact_registry.py`
  - Builds `data/references/paper_artifact_registry.csv`.
  - This is the project-wide source-of-truth table linking references, PDFs, extracted text, trimmed text, LangExtract outputs, summaries, and quality records.

- `pipelines/00_screen_text_extraction.py`
  - Screens extracted text for likely issues such as proceedings-like documents, noisy website chrome, or suspicious text-quality patterns.
  - Writes `data/references/text_screening_registry.csv`.

- `pipelines/README.md`
  - More detailed per-script notes and run examples for the pipeline folder.

## Practical Notes

- `paper_id` is the Covidence ID and is the key used across all downstream artifacts.
- The full extracted text is preserved even when a trimmed proceedings version exists.
- Registry builders are meant to keep all generated artifacts traceable from one table.
