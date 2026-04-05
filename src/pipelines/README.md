# Pipelines

This folder contains the text extraction pipeline for source PDFs.

## `01_download_covidence_pdfs.py`

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
python src/pipelines/01_download_covidence_pdfs.py
```

Headless rerun:

```bash
python src/pipelines/01_download_covidence_pdfs.py --headless
```

## `02_build_pdf_source_registry.py`

This script builds a reference-to-file registry in `data/references/pdf_source_registry.csv`.

It joins:

- the Covidence export in `data/references/sps_references_export.csv`,
- the downloaded PDFs in `data/pdf_original/`, and
- the Covidence download manifest in `data/extraction_json/covidence/download_manifest.jsonl`.

The output gives each reference its local PDF filename/path plus a `download_status`.

It also refreshes `data/references/pdf_acquisition_queue.csv`, which is the canonical backlog of references that still do not have a local PDF. The queue currently includes only matched references with no local PDF and a non-terminal `download_status` such as `missing`, `failed`, or `paywalled`.

### Run

```bash
python src/pipelines/02_build_pdf_source_registry.py
```

## `12_build_paper_artifact_registry.py`

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
python src/pipelines/12_build_paper_artifact_registry.py
```

## `05_trim_proceedings_text.py`

This script detects likely conference proceedings or other multi-abstract PDFs and trims them down to the one abstract/publication that matches the Covidence reference.

It:

- reads full text JSON files from `data/extraction_json/text`,
- detects proceedings using structural signals (abstract-boundary density, title/author density, and program markers),
- optionally uses index/table-of-contents pages to localise the target abstract page and boundary neighborhood,
- segments the proceedings into abstract blocks,
- finds the best target block using title/author fuzzy matching with boundary guardrails,
- applies completeness checks and spillover checks before auto-accepting,
- writes trimmed JSON files to `data/extraction_json/text_trimmed/{paper_id}.json`, and
- writes a decision registry to `data/references/text_trim_registry.csv`.

Main trim statuses:

- `trimmed_auto`
- `header_only_source`
- `manual_review_required`
- `not_needed`

### Run

```bash
python src/pipelines/05_trim_proceedings_text.py
```

## `06_validate_proceedings_text.py`

This script runs the separate proceedings QC pass that was queued after trimming.

It:

- selects proceedings-like papers from reviewed/heuristic source routing plus the trim registry,
- prefers trimmed proceedings text when it exists,
- checks title and author alignment,
- checks abstract completeness signals (section headings/body size),
- checks for likely spillover into neighboring abstracts,
- scores the best-matching page,
- records whether the proceedings-derived text appears to contain the correct abstract, and
- writes `data/references/proceedings_text_qc_registry.csv`.

Useful statuses:

- `confirmed_full`
- `partial_truncated`
- `spillover_detected`
- `header_only_source`
- `untrimmed_localised`
- `mismatch`

### Run

```bash
python src/pipelines/06_validate_proceedings_text.py
```

## `03_extract_text.py`

Briefly, this script:

- Reads all `*.pdf` files from `data/pdf_original`.
- Derives `paper_id` from each filename (the number before the first underscore).
- Extracts text page-by-page with `pypdf`.
- Computes a SHA-256 checksum for each source PDF.
- Detects low-text or corrupted native text and optionally runs OCR (`ocrmypdf`) before re-extracting text.
- Writes one JSON output per PDF to `data/extraction_json/text/{paper_id}.json`.
- Writes the raw extraction stage only; reviewed text cleanup is a separate downstream stage in `03b_clean_text.py`.

## Output JSON includes

- `paper_id`, `source_filename`, `source_sha256`
- `n_pages`, `page_char_counts`, `pages`
- OCR status fields such as `needs_ocr_before_ocr`, `ocr_trigger_reasons`, `needs_ocr`, `remaining_text_quality_flags`, `ocr_applied`, `ocr_mode`, `ocr_error`

## Run

From repo root:

```bash
python src/pipelines/03_extract_text.py
```

## `03b_clean_text.py`

This script is now the canonical cleanup stage for both the deterministic pass and the reviewed residual rescue pass.

It:

- reads the target list from `config/extraction/text_cleanup_overrides.csv`,
- honors the reviewed `source_strategy` for each target (`json_cleanup` or `pdftotext_cleanup`),
- processes only enabled paper IDs (or an explicit `--paper-id` subset),
- stores the original raw JSON snapshot at `data/extraction_json/text_preclean/{paper_id}.json`,
- overwrites the canonical cleaned JSON at `data/extraction_json/text/{paper_id}.json`, and
- refreshes `data/references/paper_artifact_registry.csv` unless `--skip-registry-refresh` is passed.

Cleanup is intentionally conservative and deterministic:

- common mojibake and ligature repair
- a small reviewed substitution layer for corpus-specific glyph damage such as `gamma-aminobutyric` placeholders
- line-break hyphenation repair
- conservative punctuation/spacing normalization
- light repeated header/footer and publisher boilerplate removal

Phase 1 is intentionally limited to deterministic cleanup on a reviewed subset. Proceedings/context localization problems and true source-linkage problems should be handled elsewhere rather than pushed into this script.

With `--stage2`, the same script switches to the reviewed residual-cleanup path. In that mode it:

- reads `config/extraction/text_cleanup_stage2_overrides.csv`,
- applies reviewed per-paper substitutions from `config/extraction/text_cleanup_stage2_substitutions.csv`,
- can rebuild from `pdftotext`, localized OCR, or an alternate in-repo PDF when the attached PDF is known to be wrong, and
- preserves stage-2 backups in `data/extraction_json/text_preclean_stage2/{paper_id}.json`.

### Run

```bash
python src/pipelines/03b_clean_text.py
```

Force a rerun from preserved raw backups:

```bash
python src/pipelines/03b_clean_text.py --force
```

Run the reviewed residual rescue pass explicitly:

```bash
python src/pipelines/03b_clean_text.py --stage2 --paper-id 43 --paper-id 62 --paper-id 155
```

Force a rerun from preserved stage-2 backups:

```bash
python src/pipelines/03b_clean_text.py --stage2 --paper-id 43 --force
```

## `04_source_categorisation.py`

This script classifies each extracted source into a pragmatic downstream category using the reference export, proceedings-trim signals, and preferred text content.

It:

- reads the full text JSON from `data/extraction_json/text`,
- prefers `data/extraction_json/text_trimmed/{paper_id}.json` when available,
- reuses `data/references/text_trim_registry.csv` for proceedings signals,
- assigns categories such as `single_case_report`, `case_series_or_multi_case`, `observational_group_study`, `conference_abstract`, `review_article`, `non_clinical`, or `unclear_manual_review`,
- records whether case-series splitting is a candidate, and
- writes `data/references/source_categorisation_registry.csv`.

This registry is the heuristic first pass. Manual adjudications for papers that required case-by-case review are stored in:

- `data/references/source_categorisation_manual_review.csv`

That manual override ledger records:

- the original heuristic decision
- the final reviewed category and subtype
- short review notes
- a review batch label and timestamp
- `pdf_content_alignment_tag`

Alignment tags currently used:

- `appears_matched`
  - the downloaded PDF/content appears consistent with the reference
- `uncertain`
  - the paper was classifiable, but the local file or extracted text was not fully conclusive
- `likely_wrong_pdf_attached`
  - the PDF/content appears inconsistent with the reference metadata and should be treated cautiously
- `incorrect_reference`
  - the stored reference metadata itself appears to be wrong or points to the wrong paper, so the local PDF/text should not be treated as recoverable by extraction cleanup alone

Category meanings:

- `single_case_report`
  - one patient or one clearly case-level report
  - route to individual-level LangExtract
- `case_series_or_multi_case`
  - more than one individual case with case-level content
  - run case-series splitting before LangExtract
- `observational_group_study`
  - cohort/cross-sectional/group paper without per-patient extraction target
  - route to group-level LangExtract
- `interventional_study`
  - controlled or therapeutic group study
  - route to group-level LangExtract
- `conference_abstract`
  - meeting abstract, supplement, proceedings item, or trimmed proceedings record
  - often needs trimming or manual review before downstream use
- `lab_heavy_clinical_or_translational`
  - clinically relevant group paper dominated by antibody/laboratory/method content
  - usually keep for group-level extraction, not case splitting
- `non_clinical_basic_science`
  - mechanistic/basic-science work without useful clinical extraction target
  - usually skip LangExtract
- `review_article`
  - narrative/systematic review style paper
  - usually skip case-level LangExtract
- `unclear_manual_review`
  - signals conflict or confidence is too low
  - manual routing required

The current corpus-level manual review pass has been completed, so all rows that were initially `manual_review_required` now have reviewed decisions in `data/references/source_categorisation_manual_review.csv`.

Practical downstream rule:

- if a paper appears in `source_categorisation_manual_review.csv`, use the reviewed `final_source_category` and `final_source_subtype`
- otherwise, use the heuristic values from `source_categorisation_registry.csv`

After each run, it also refreshes `data/references/paper_artifact_registry.csv` unless `--skip-registry-refresh` is passed.

### Run

```bash
python src/pipelines/04_source_categorisation.py
```

## `07_split_case_series.py`

This script prepares reviewed multi-case papers for individual-level LangExtract.

It:

- reads the reviewed routing decision from `data/references/source_categorisation_manual_review.csv` when available,
- limits automatic splitting to papers that are true case-series candidates,
- requires proceedings conference abstracts to pass the proceedings QC gate first,
- searches for explicit `Case 1` / `Patient 1` style headings,
- writes per-paper split artifacts to `data/extraction_json/text_case_series_split/{paper_id}.json`, and
- writes `data/references/case_series_split_registry.csv`.

It is intentionally conservative. If explicit case boundaries are not stable, the paper stays in manual review.

### Run

```bash
python src/pipelines/07_split_case_series.py
```

## `09_build_langextract_examples.py`

This script rebuilds the few-shot JSON files used by LangExtract and the quality-assessment classifier.

It:

- uses curated rows from `examples/`,
- validates that each example points back to a real curated example row, and
- rewrites the prompt assets in `config/prompts/examples/`.

Outputs:

- `config/prompts/examples/02_individual_examples.json`
- `config/prompts/examples/02_group_examples.json`
- `config/prompts/examples/03_publication_type_examples.json`

### Run

```bash
python src/pipelines/09_build_langextract_examples.py
```

## `10_langextract.py`

This script reads text JSON files from `data/extraction_json/text`, applies reviewed routing by default, prefers `data/extraction_json/text_trimmed/{paper_id}.json` when it exists, uses case-series split artifacts when appropriate, runs LangExtract with an OpenAI model, and writes:

- Raw LangExtract entities to `data/extraction_json/langextract/{paper_id}.json`
- Section summaries + overall summary to `data/extraction_json/summary/{paper_id}.json`

Records reviewed as `incorrect_reference` are explicitly excluded and reported as `skipped_incorrect_reference` in the run summary.

### Requirements

- `langextract[openai]` installed in your virtual environment
- `OPENAI_API_KEY` set in your shell environment

### Run

Dry run (no API calls):

```bash
python src/pipelines/10_langextract.py --dry-run --limit 2
```

Real run:

```bash
python src/pipelines/10_langextract.py
```

Ignore reviewed routing and force explicit CLI mode selection:

```bash
python src/pipelines/10_langextract.py --ignore-routing --include-individual --limit 5
```

## `11_quality_assessment.py`

This script reads text JSON files from `data/extraction_json/text`, prefers `data/extraction_json/text_trimmed/{paper_id}.json` when it exists, and writes:

- Raw quality-assessment LangExtract output to `data/extraction_json/quality/raw/{paper_id}.json`
- Structured quality records to `data/extraction_json/quality/records/{paper_id}.json`

Records reviewed as `incorrect_reference` are explicitly excluded before any downstream model calls.

## Directory Contents Snapshot
- Last updated: `2026-04-05`
- Immediate subdirectories (0): _None_
- Immediate files (15, excluding `README.md`): `01_download_covidence_pdfs.py`, `02_build_pdf_source_registry.py`, `03_extract_text.py`, `03b_clean_text.py`, `04_source_categorisation.py`, `05_trim_proceedings_text.py`, `06_validate_proceedings_text.py`, `07_split_case_series.py`, `09_build_langextract_examples.py`, `10_langextract.py`, `11_quality_assessment.py`, `12_build_paper_artifact_registry.py`, ... (+3 more)
