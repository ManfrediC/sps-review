# Repo-specific rules

## Runtime
- Use `.venv` unless documented otherwise.

## Canonical outputs
- Canonical research artefacts stay under `data/` and `data/references/`.
- `results/` is for canonical pipeline-produced exports, logs, and stage traces.
- `results/overnight/` is for logs, calibration reports, and stage traces only.
- Non-canonical validation packs, review sheets, spot checks, and ad hoc audit outputs belong under `qa/validation/`.
- Test fixtures belong under `tests/` or `tests/fixtures/`.
- Do not move or duplicate canonical registries into `results/overnight/`.
- Do not write non-canonical review or validation material into `data/` or `results/`.

## Pipeline order
1. `01_download_covidence_pdfs.py` when Covidence acquisition is needed; this also refreshes `02_build_pdf_source_registry.py` and `12_build_paper_artifact_registry.py` unless skipped.
2. `02_build_pdf_source_registry.py` after new or manually changed PDFs when the PDF-to-reference registry needs rebuilding; this also refreshes the remaining non-downloaded acquisition queue in `data/references/pdf_acquisition_queue.csv`.
3. `03_extract_text.py`
4. `03b_clean_text.py` on the reviewed subset of extracted text JSONs listed in `config/extraction/text_cleanup_overrides.csv`; this preserves pre-clean backups in `data/extraction_json/text_preclean/` and overwrites canonical cleaned JSONs in `data/extraction_json/text/`.
5. `90_screen_text_extraction.py` as an optional screening pass after extraction/cleanup when triaging residual text-quality issues or likely proceedings PDFs.
6. `04_source_categorisation.py` on extracted text to assign the source category and downstream routing; rerun after proceedings trimming only if the categorisation itself should consume preferred trimmed text.
7. `05_trim_proceedings_text.py` for proceedings / `conference_abstract` candidates.
8. `06_validate_proceedings_text.py` after trimming; required before auto-splitting conference-abstract case series.
9. `04b_extract_sps_case_counts.py` after categorisation and, when available, after proceedings trimming/QC so extractable SPS case counts use the preferred text source.
10. `07_split_case_series.py` for reviewed case-series candidates before LangExtract.
11. `09_build_langextract_examples.py` when curated examples change.
12. `10_langextract.py`
13. `11_quality_assessment.py`
14. `12_build_paper_artifact_registry.py` as the cross-pipeline provenance refresh; most stages call it automatically, but run it directly after manual artefact changes.
15. `99_overnight_run.py` is the orchestration wrapper for staged batch runs, not a separate canonical data-processing stage.

## Stopping conditions
- Stop if host-level install or admin access is required; log blocked status.
- Stop if a calibration gate fails.
- Stop if source/reference linkage is broken; preserve evidence.
- Stop and ask if uncertainty materially affects correctness.

## Metadata and registries
- Treat `data/references/sps_references_export.csv` and `.ris` as upstream metadata.
- Write derived linkage data only to generated registries under `data/references/`.
- Preserve both export metadata and live Covidence card metadata when comparing them.

## Secrets
- Keep secrets in environment variables or local `env/*.env` files.
- Preferred variables: `OPENAI_API_KEY`, `GEMINI_API_KEY`.
- Never write secrets into tracked files, logs, prompts, or artefacts.

## Overnight logging
- Append status updates to `results/overnight/LOG.md`.
- Keep machine-readable stage status at `results/overnight/stage_status.tsv`.
- On failure, capture command, exit code, and log path.
