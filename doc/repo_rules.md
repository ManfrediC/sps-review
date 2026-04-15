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
6. `04_source_categorisation_LLM.py` on extracted text to assign the source category, checkpoint per-paper run artefacts under `results/stage04_llm_runs/`, and publish the paired SPS case-count registries once the run is complete; rerun after proceedings trimming only if the categorisation itself should consume preferred trimmed text.
7. `05_trim_proceedings_text_LLM.py` for proceedings / `conference_abstract` candidates; this writes the stage-05 candidate layer under `data/extraction_json/text_trimmed_llm_candidates/` and `data/references/text_trim_llm_candidate_registry.csv`.
8. `05b_validate_proceedings_text_LLM.py` after candidate generation; this writes the final LLM-reviewed trim layer under `data/extraction_json/text_trimmed_llm/` and `data/references/text_trim_llm_registry.csv`.
9. `05c_publish_proceedings_ready.py` after validation or approved manual stage-05 overrides; this publishes the canonical downstream proceedings layer under `data/extraction_json/text_proceedings_ready/` and `data/references/text_proceedings_ready_registry.csv`.
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
