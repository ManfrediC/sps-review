## 21.02.2026

Initialized the reproducible SPS-review repository structure and added source reference exports for downstream extraction and verification.
Then implemented and iteratively improved the PDF-to-JSON text extraction pipeline in `src/pipelines/01_extract_text.py`.

Key progress on this date (from commit history):
- Repository bootstrap and folder structure (`ab90651`).
- Reference files added (`417f639`).
- First extraction implementation and JSON output draft (`3acec10`).
- Refactor for clearer function structure and maintainability (`85064fc`).
- OCR support integrated into extraction flow and README updates (`f597040`).
- Initial LangExtract pipeline script scaffold and top-level README update (`1d942d1`).
- Column/quality dictionaries added and aligned with JSON configs (`0ce5d7c`, `14cb64e`).

Session progress completed today:
- Validated extraction end-to-end on current PDF set.
- Confirmed OCR auto-detection and fallback using a non-OCR test PDF (`118492_...`), with post-OCR extraction marked successful in output JSON.
- Installed and configured OCR dependencies (Python + system tools):
  - `pypdf`, `tqdm`, `ocrmypdf`
  - Tesseract OCR
  - Ghostscript
- Configured both Git Bash and PowerShell environments so OCR tooling resolves by command.
- Added `src/pipelines/README.md` documenting the extraction script behavior and outputs.
- Installed OpenAI-ready LangExtract stack in `.venv`:
  - `langextract[openai]`
  - verified imports for `langextract` and `openai`.

## 28.02.2026

Added a browser-based Covidence full-text acquisition workflow and started building the project-wide provenance layer linking references, PDFs, and downstream extraction artifacts.

### Covidence Download Workflow

- Implemented `src/pipelines/00_download_covidence_pdfs.py` using Playwright against the Covidence extraction view.
- Validated the live workflow end-to-end on Covidence with a successful single-reference test for `#13799`.
- Validated the workflow further with a successful batch download of `5020`, `816`, `800`, `5029`, and `12807`.
- Standardized saved filenames as `<Covidence_ID>_<original_filename>.pdf` in `data/pdf_original/`.
- Added Covidence operator documentation in `doc/COVIDENCE_DOWNLOAD_AGENT.md`.
- Updated `src/pipelines/README.md` and the top-level `README.md` with Covidence download documentation.

### Registries And Provenance

- Built `src/pipelines/00_build_pdf_source_registry.py` and generated `data/references/pdf_source_registry.csv` to link Covidence references to local PDF files and download status.
- Built `src/pipelines/00_build_paper_artifact_registry.py` and generated `data/references/paper_artifact_registry.csv` as the cross-pipeline source-of-truth table.
- The master artifact registry now links reference metadata, local PDFs, extracted text JSON, LangExtract raw/summary outputs, and quality raw/record outputs.
- Wired automatic registry refresh so `src/pipelines/00_download_covidence_pdfs.py`, `src/pipelines/01_extract_text.py`, `src/pipelines/02_LangExtract.py`, and `src/pipelines/03_quality_assessment.py` rebuild the artifact registry after successful runs.

### Clean Validation Run

- Reset the downloaded PDF set and reran a clean 10-paper batch from Covidence to validate the workflow from scratch.
- Re-ran `src/pipelines/01_extract_text.py` on the clean batch and confirmed successful text extraction for all 10 downloaded PDFs.

### OCR And Text Screening

- Improved OCR handling in `src/pipelines/01_extract_text.py`.
- Native extraction remains the default.
- OCR is now triggered not only for low-text PDFs but also for corrupted native text.
- Paper `669` was validated as a concrete example where OCR materially improved extraction quality.
- Added `src/pipelines/00_screen_text_extraction.py` to flag likely proceedings/program PDFs and other extraction-quality issues before downstream AI extraction.

### Proceedings Trimming

- Added `src/pipelines/00_trim_proceedings_text.py` as a separate focused-trimming step for large proceedings PDFs.
- Implemented automatic proceedings trimming based on many pages, many title-like lines, many author-like lines, and fuzzy matching of the reference title and author block against abstract blocks in the extracted text.
- Validated automatic trimming on known proceedings cases.
- `5029` matched abstract block `419`.
- `12807` matched abstract block `M207`.
- Extended `data/references/paper_artifact_registry.csv` so it now records trimmed-text artifacts and trim metadata alongside the full extracted text.
- Updated `src/pipelines/02_LangExtract.py` to prefer trimmed proceedings text when available.
- Updated `src/pipelines/03_quality_assessment.py` to prefer trimmed proceedings text when available.

### Credentials And Repo Hygiene

- Added local Covidence credential support through `env/covidence_login.env`.
- Updated `src/pipelines/00_download_covidence_pdfs.py` to load credentials from that file as a fallback.
- Tightened `.gitignore` so Covidence authentication/session files and local Covidence credential env files are explicitly excluded from Git/GitHub.

### Documentation

- Added a concise script-level overview in `src/README.md` describing the purpose and order of all pipeline scripts under `src/`.

### Bulk Covidence Run

- Hardened `src/pipelines/00_download_covidence_pdfs.py` for large runs by improving lazy-list traversal.
- Added progressive scrolling so the downloader waits for newly hydrated study cards instead of assuming the first rendered slice is the full list.
- Added support for Covidence's `Load more` button when scrolling alone no longer reveals additional references.
- Increased the wait time after clicking `Load more` because Covidence can take several seconds to render the next section of the list.
- Added Unicode-safe manifest logging so long runs do not crash on non-ASCII author or title characters.
- Ran the downloader across the full review and reached the end of the available Covidence list.
- Re-ran targeted retries for the unresolved references after the full pass.
- Rebuilt both registries after the bulk run:
- `data/references/pdf_source_registry.csv`
- `data/references/paper_artifact_registry.csv`

### Remaining Manual PDF Queue

- Most references now have a local PDF in `data/pdf_original/`.
- A small unresolved set remains where Covidence either did not expose a PDF link or repeated timeouts occurred during link reveal.
- Created `data/references/missing_pdf_manual_queue.csv` as the handoff list for manual PDF acquisition.
- That queue contains the remaining unresolved Covidence IDs, titles, authors, and the intended filename prefix for manual placement into `data/pdf_original/`.

### Notes

- Covidence study cards do not hydrate immediately after page load; explicit wait logic was needed before scanning for `View full text`.
- The artifact registry was initially populated mainly for reference, PDF, and text stages; LangExtract and quality columns will fill as those pipelines are run on the downloaded PDFs.

## 01.03.2026

Reviewed the results of the large Covidence acquisition run and performed a first quality pass on extracted text and proceedings trimming.

### Extraction And Trimming Batch Review

- Ran `src/pipelines/01_extract_text.py` with OCR fallback on a first batch of 50 PDFs.
- Ran `src/pipelines/00_trim_proceedings_text.py` on the same batch via the extraction pipeline.
- Generated `data/references/text_trim_registry.csv` for that batch and refreshed `data/references/paper_artifact_registry.csv`.
- Created `data/references/first_50_quality_review.csv` to classify the first 50 papers as:
- `ok`
- `proceedings_manual_review`
- `proceedings_trimmed_auto`
- `pdf_reference_mismatch_suspected`

### Quality Findings

- OCR fallback behaved as intended on the first 50-PDF batch.
- Proceedings detection also behaved conservatively as intended.
- One proceedings record was trimmed automatically with acceptable confidence.
- Several large proceedings PDFs were flagged for manual review rather than auto-trimmed.
- The main issue in the batch was not extraction failure but apparent mismatch between downloaded PDF assignment and reference metadata.

### Key Conclusion

- The current Covidence ID extraction in `src/pipelines/00_download_covidence_pdfs.py` is faulty.
- Manual checking showed cases where:
- the PDF title matched the PDF content,
- the paper itself belongs to the reference set,
- but the numeric Covidence ID prefixed to the filename was incorrect.
- This means the bug is at the download/acquisition layer rather than in OCR, text extraction, or proceedings trimming.

### Implications

- The current filename prefix cannot be treated as a fully reliable source of truth for all downloaded PDFs.
- Suspect files need manual or semi-automated reconciliation against the reference export before downstream extraction results can be trusted at scale.
- The downloader will need a stricter Covidence card-to-ID binding strategy before future bulk download runs.

### Covidence ID Repair

- Inspected a saved Covidence HTML example and confirmed that the correct scoping unit for each study card is the enclosing `article` element.
- Patched `src/pipelines/00_download_covidence_pdfs.py` to stop climbing arbitrary DOM ancestors when extracting IDs.
- Replaced the old logic with article-scoped extraction of:
- `covidence_id`
- `card_identifier_text`
- `card_first_author`
- `card_year`
- `card_authors_full`
- `card_publication_title`
- Tightened PDF-link discovery so the downloader now looks inside the local uploaded-documents section within the same article card.

### Registry Enrichment

- Extended `src/pipelines/00_build_pdf_source_registry.py` and `src/pipelines/00_build_paper_artifact_registry.py` to carry the live Covidence card metadata alongside the exported reference metadata.
- Added comparison flags between the reference export and the live Covidence card metadata so mismatches are easier to spot in downstream QA.

### Tainted Artifact Reset

- Deleted the generated artifacts that depended on the faulty Covidence ID extraction:
- `data/extraction_json/covidence/download_manifest.jsonl`
- `data/references/pdf_source_registry.csv`
- `data/references/paper_artifact_registry.csv`
- `data/references/text_trim_registry.csv`
- `data/references/first_50_quality_review.csv`
- `data/references/missing_pdf_manual_queue.csv`
- all generated JSON files under `data/extraction_json/text/`
- all generated JSON files under `data/extraction_json/text_trimmed/`
- Kept the source reference exports:
- `data/references/sps_references_export.csv`
- `data/references/sps_references_export.ris`

### Clean Validation

- Re-ran a clean 10-PDF Covidence batch with the patched downloader and manually verified the card-to-PDF mapping.
- Extended the validation to a second clean 10-PDF batch and again confirmed that the ID-to-PDF mapping was correct.
- This established that the article-scoped Covidence ID extraction was behaving correctly before scaling up.

### Full Clean Covidence Run

- Re-ran the downloader across the full Covidence review with the patched ID extraction logic.
- Completed a clean full download with:
- `1027` downloaded PDFs
- `5` failed references
- `7` missing references
- Regenerated:
- `data/references/pdf_source_registry.csv`
- `data/references/paper_artifact_registry.csv`
- Confirmed that the old wrong-ID prefix issue was not seen in the manual spot-checks after the repair.

### Full Text Extraction

- Ran `src/pipelines/01_extract_text.py` across the clean full PDF set.
- Completed extraction for all `1027` downloaded PDFs.
- Regenerated:
- `data/references/text_trim_registry.csv`
- `data/references/paper_artifact_registry.csv`
- OCR fallback triggered on `52` files.
- Proceedings auto-trimming succeeded on `15` files.
- `102` proceedings-like files remained flagged as `manual_review_required`.

### Extraction Quality Review

- Spot-checked a diagnostic subset of extracted outputs across:
- OCR-triggered files
- generic-filename PDFs
- auto-trimmed proceedings files
- large proceedings/program PDFs
- Findings:
- OCR rescue cases were materially improved and readable.
- Generic-filename PDFs such as `1610_1610.pdf` still mapped to the correct reference and extracted correctly.
- Auto-trimmed proceedings outputs were usable when confidence was high, though some conference-entry cases contained only title/author blocks and little or no abstract body text.
- The main remaining downstream risk is not basic extraction failure but the `102` large proceedings/program PDFs that still require manual review or further trimming refinement.

### Proceedings Manual Review Queue

- Created `data/references/proceedings_manual_review_queue.csv`.
- The queue contains the `102` proceedings records still marked `manual_review_required`.
- It links each paper to:
- reference metadata
- source PDF/text JSON paths
- trimming diagnostics and match scores
- blank `manual_status` and `manual_notes` columns for manual adjudication.

## 03.03.2026

Completed the manual source-categorisation review pass and documented the reviewed override layer for downstream routing.

### Manual Source Categorisation Review

- Worked through all `287` papers that had been flagged `manual_review_required` by `src/pipelines/01a_source_categorisation.py`.
- Reviewed them case by case against the extracted text and, where needed, the PDF content.
- Used title/author search rather than full-document reading for proceedings and supplement records.
- Recorded every adjudication in `data/references/source_categorisation_manual_review.csv`.

### Review Ledger

- The manual review ledger stores:
- heuristic category/subtype/confidence from the automatic pass
- final reviewed category/subtype
- short decision notes
- review batch and timestamp
- `pdf_content_alignment_tag`

### Alignment Tagging

- Used explicit alignment tags to separate routing uncertainty from attachment-quality concerns:
- `appears_matched`
- `uncertain`
- `likely_wrong_pdf_attached`
- This preserves suspected PDF/reference attachment problems as a separate signal instead of hiding them inside the source-category decision.

### Categorisation Outcome

- The manual source-categorisation queue is now exhausted:
- `287` reviewed
- `0` remaining
- The reviewed override file now covers the full set of papers that originally required manual adjudication.
- Many of the ambiguous heuristic cases resolved into:
- `single_case_report`
- `conference_abstract`
- `lab_heavy_clinical_or_translational`
- `observational_group_study`
- `case_series_or_multi_case`
- A small number remained explicitly uncertain because the local file was only an index sheet or otherwise incomplete.

### Documentation

- Updated `src/README.md` to document the reviewed override layer and the meaning of the categorisation outputs.
- Updated `src/pipelines/README.md` to document:
- the distinction between heuristic categorisation and manual overrides
- the meaning of `pdf_content_alignment_tag`
- the rule that reviewed categories should override heuristic routing when present

### Queued Follow-Up

- Deferred a separate proceedings QC pass until after categorisation:
- search each proceedings-derived extracted text by title and/or authors
- confirm that the correct abstract block was captured
- flag any incorrect or incomplete trimmed extractions for correction

### Proceedings Text QC

- Implemented `src/pipelines/00_validate_proceedings_text.py`.
- Added a separate proceedings QC layer that searches proceedings-derived text by title and author surnames rather than relying on trimming output alone.
- Generated `data/references/proceedings_text_qc_registry.csv`.
- Current QC distribution:
- `2` `trimmed_match_confirmed`
- `13` `trimmed_partial_match`
- `194` `full_text_partial_match`
- `25` `not_localised`
- This makes the proceedings follow-up explicit and auditable instead of leaving it implicit in the trim registry.

### Case-Series Splitting

- Implemented `src/pipelines/01b_split_case_series.py`.
- Integrated reviewed routing into the splitter so only reviewed/eligible multi-case sources are considered.
- Tightened the splitter after live inspection:
- generic `patients` / `cases` headings are no longer accepted as case boundaries
- a split now requires the first detected heading to represent the first case
- Generated:
- `data/references/case_series_split_registry.csv`
- `data/extraction_json/text_case_series_split/`
- Current split distribution:
- `37` `split_auto`
- `79` `manual_review_required`
- This keeps the splitter conservative enough for downstream individual extraction.

### LangExtract Example Builder

- Implemented `src/pipelines/00_build_langextract_examples.py`.
- Rebuilt the prompt example JSON files from curated project examples in `examples/`.
- Added provenance into the example payloads via `source_sheet`, `paper_id`, and `case_id` where relevant.
- Current prompt example counts:
- `7` individual examples
- `5` group examples
- `5` publication-type examples

### Routing Integration

- Added a shared routing helper in `src/pipelines/_source_routing.py` and normalised subtype-like manual category values.
- Updated `src/pipelines/00_build_paper_artifact_registry.py` so the master registry now carries:
- resolved reviewed routing
- proceedings QC fields
- case-series split fields
- Updated `src/pipelines/02_LangExtract.py` so it now:
- respects reviewed routing by default
- skips ineligible/manual-review papers unless explicitly overridden
- uses case-series split artifacts for reviewed multi-case papers

### Controlled LangExtract Pilot

- Ran a controlled real LangExtract pilot on:
- `12013` as a reviewed individual paper
- `3139` as a reviewed group paper
- `1097` as an auto-split case series
- The route-aware pilot completed successfully with `processed=3`, `failed=0`.
- Verified that:
- `12013` ran only the individual extraction mode
- `3139` ran only the group extraction mode
- `1097` used the new case-series split artifact and produced per-case extraction output

### Documentation

- Updated `src/README.md` and `src/pipelines/README.md` to document:
- proceedings QC
- case-series splitting
- example rebuilding from curated sheets
- route-aware LangExtract behavior
- updated overnight-stage coverage in `src/pipelines/99_overnight_run.py`

## 04.03.2026

Refactored pipeline numbering and repaired the interrupted proceedings-trimming flow so stage sequencing is consistent and execution-safe.

### Pipeline Renumbering And Reference Updates

- Renamed pipeline scripts to the new canonical numbering:
- `00_download_covidence_pdfs.py` -> `01_download_covidence_pdfs.py`
- `00_build_pdf_source_registry.py` -> `02_build_pdf_source_registry.py`
- `01_extract_text.py` -> `03_extract_text.py`
- `01a_source_categorisation.py` -> `04_source_categorisation_LLM.py`
- `00_trim_proceedings_text.py` -> `05_trim_proceedings_text.py`
- `00_validate_proceedings_text.py` -> `05b_validate_proceedings_text.py`
- `01b_split_case_series.py` -> `07_split_case_series.py`
- `00_build_langextract_examples.py` -> `09_build_langextract_examples.py`
- `02_LangExtract.py` -> `10_langextract.py`
- `03_quality_assessment.py` -> `11_quality_assessment.py`
- `00_build_paper_artifact_registry.py` -> `12_build_paper_artifact_registry.py`
- `00_screen_text_extraction.py` -> `90_screen_text_extraction.py`
- Updated internal script-path references across pipeline scripts to the new names.

### Workflow Sequencing Fixes

- Updated `src/pipelines/03_extract_text.py` to perform extraction only (removed auto-trigger of proceedings trimming).
- Kept artifact-registry refresh in extraction, now pointing to `12_build_paper_artifact_registry.py`.
- Updated `src/pipelines/99_overnight_run.py` stage map and order to include:
- extraction -> source categorisation -> proceedings trim -> proceedings QC -> SPS case counts -> case-series split -> LangExtract stages.

### Proceedings Trimming Repair

- Fixed `src/pipelines/05_trim_proceedings_text.py` main-call mismatch after refactor:
- restored required arguments for proceedings candidate filtering (`existing_trim_registry_path`, `include_already_trimmed`).
- Updated proceedings candidate filtering behavior to remain scoped to proceedings candidates (no fallback to all papers when filtered set is empty).
- Confirmed the script runs cleanly after patching.

### Documentation Sync

- Updated operational docs to new script names and stage order:
- `AGENTS.md`
- `README.md`
- `src/README.md`
- `src/pipelines/README.md`
- `config/prompts/README.md`
- `doc/COVIDENCE_DOWNLOAD_AGENT.md`
- `doc/LANGEXTRACT_EXAMPLE_PLAN.md`
- `doc/codex_plans/windows_native_setup_checklist.md`

### Validation

- Ran CLI smoke checks (`--help`) for renamed and touched scripts.
- Ran a no-op trim execution to verify repaired argument wiring in `05_trim_proceedings_text.py`.

## 05.03.2026

Patched proceedings abstract localisation, refreshed trial/spot-check outputs, added concise pipeline code comments, and expanded directory-level documentation coverage across the repository.

### Proceedings Abstract Extractor Patch And Validation Run

- Patched proceedings localisation behaviour and ran a validation/trial pass (`ef4d9ad`).
- Updated:
- `src/pipelines/05_trim_proceedings_text.py`
- `src/pipelines/05b_validate_proceedings_text.py`
- `src/pipelines/07_split_case_series.py`
- `src/pipelines/README.md`
- Refreshed core registries:
- `data/references/text_trim_registry.csv`
- `data/references/proceedings_text_qc_registry.csv`
- `data/references/source_categorisation_registry.csv`
- `data/references/case_series_split_registry.csv`
- `data/references/paper_artifact_registry.csv`
- Added trial and spot-check artifacts:
- `data/references/proceedings_accuracy_spotcheck_10.csv`
- `data/references/proceedings_accuracy_spotcheck_10_manual.csv`
- `data/references/proceedings_accuracy_spotcheck_10_report.txt`
- `data/references/proceedings_text_qc_registry_trial_index_patch.csv`
- `data/references/text_trim_registry_trial_index_patch.csv`
- `data/references/text_trim_registry_trial_index_patch_single.csv`
- Added planning note:
- `doc/codex_plans/83_column_master_table_plan.md`

### Pipeline Readability Pass

- Added concise, block-level comments across all pipeline scripts (`b54714e`):
- `src/pipelines/01_download_covidence_pdfs.py`
- `src/pipelines/02_build_pdf_source_registry.py`
- `src/pipelines/03_extract_text.py`
- `src/pipelines/04_source_categorisation_LLM.py`
- `src/pipelines/05_trim_proceedings_text.py`
- `src/pipelines/05b_validate_proceedings_text.py`
- `src/pipelines/07_split_case_series.py`
- `src/pipelines/09_build_langextract_examples.py`
- `src/pipelines/10_langextract.py`
- `src/pipelines/11_quality_assessment.py`
- `src/pipelines/12_build_paper_artifact_registry.py`
- `src/pipelines/90_screen_text_extraction.py`
- `src/pipelines/99_overnight_run.py`
- `src/pipelines/_source_routing.py`
- Added trial registry snapshots from this pass:
- `data/references/text_trim_registry_trial_2026_03_05_b.csv`
- `data/references/proceedings_text_qc_registry_trial_2026_03_05_b.csv`

### Repository Documentation Coverage

- Added README coverage for previously undocumented directories (`861d7fe`), including:
- `.codex/`, `.codex/rules/`, `.github/`, `.github/workflows/`
- `config/dictionaries/`, `config/prompts/examples/`, `config/schema/`
- `data/`, `data/references/`
- `doc/`, `doc/codex_plans/`, `doc/methods/`, `doc/protocols/`
- `env/`, `examples/`, `resources/`, `tests/`
- `src/lib/`, `src/notebooks/`
- Updated existing README files with directory snapshots:
- `README.md`
- `config/README.md`
- `config/prompts/README.md`
- `src/README.md`
- `src/pipelines/README.md`

## 31.03.2026

Reviewed and grouped the current uncommitted worktree changes. The main themes today were extraction QA, repo output hygiene, and hardening `03_extract_text.py` for known edge cases.

### Suggested Commit Bucket 1

- Git description: `docs: reserve data/results for canonical outputs and document qa validation workflow`
- Updated `AGENTS.md` to keep `data/` and `results/` reserved for canonical pipeline artefacts and to route non-canonical validation and review material into `qa/validation/`.
- Updated top-level and directory READMEs to reflect the new policy and to document the role of `qa/`, `qa/validation/`, and `qa/validation/text_exports/`.
- Added `.gitignore` coverage for generated `qa/**/*.txt` review exports.
- Touched files:
- `AGENTS.md`
- `.gitignore`
- `README.md`
- `config/README.md`
- `src/README.md`
- `src/validation/README.md`
- `tests/README.md`
- `qa/README.md`
- `qa/validation/README.md`
- `qa/validation/text_exports/README.md`

### Suggested Commit Bucket 2

- Git description: `feat(validation): add text extraction QA sampling and TXT export utilities`
- Added `src/validation/validate_text_extraction_quality.py` to build stratified manual-review samples for step `03`, including quota-based oversampling of OCR, proceedings-like, and artifact-risk records.
- Added `src/validation/export_text_json_to_txt.py` to export `data/extraction_json/text/*.json` into human-readable TXT files for manual QA.
- Added automated tests for both new validation utilities.
- Fixed an implementation bug during this work: PowerShell-written CSV selections carried a UTF-8 BOM, so the exporter initially over-selected records. The loader now reads selection CSVs BOM-safely.
- Kept TXT headers readable by displaying repo-relative JSON source paths in the export output.
- Touched files:
- `src/validation/validate_text_extraction_quality.py`
- `src/validation/export_text_json_to_txt.py`
- `tests/test_validate_text_extraction_quality.py`
- `tests/test_export_text_json_to_txt.py`

### Suggested Commit Bucket 3

- Git description: `feat(extraction): harden step 03 and add per-paper extraction overrides`
- Hardened `src/pipelines/03_extract_text.py` so per-PDF failures no longer abort the whole batch immediately.
- Added structured exception capture for native extraction and OCR failures, including exception class plus truncated stdout/stderr details where available.
- Added atomic JSON writes to reduce the risk of partial or corrupt output files during interruption.
- Added a per-paper override table at `config/extraction/text_extraction_overrides.csv`.
- Implemented reviewed override routes for known problem IDs:
- `force_ocr`: `30`, `238`, `386`, `633`, `12247`, `12613`
- `pdftotext`: `637`, `861`
- Expanded `tests/test_03_extract_text.py` to cover override loading, OCR override routing, `pdftotext` fallback routing, structured error capture, and partial-failure handling.
- Reran `03_extract_text.py` on the overridden IDs only and refreshed the corresponding canonical JSON outputs.
- This targeted rerun also refreshed the canonical provenance registry:
- `data/references/paper_artifact_registry.csv`
- Validation run:
- `.\.venv\Scripts\python.exe -m unittest tests.test_03_extract_text -v`
- Result: `17` tests passed.
- Outcome:
- Previously likely-failed extractions for `30`, `238`, `386`, `633`, `637`, `861`, `12247`, and `12613` now look usable after regeneration.
- Remaining unresolved likely failures after override work are `23`, `1421`, and `6268`.
- Touched files:
- `src/pipelines/03_extract_text.py`
- `tests/test_03_extract_text.py`
- `config/extraction/text_extraction_overrides.csv`
- `data/references/paper_artifact_registry.csv`

### Suggested Commit Bucket 4

- Git description: `chore(qa): generate text extraction review packs and reclassify weak cases`
- Ran `validate_pdf_source_registry.py` on larger reproducible samples (`n=20` and `n=30`) and confirmed the sampled PDF-to-reference linkage looked sound.
- Built a full `n=300` step `03` extraction QA pack under `qa/validation/`, including JSON sample summary plus CSV review sheets.
- Triaged the `n=300` sample and used it to identify likely failure patterns:
- NEJM boilerplate-only text layer
- broken font encoding / unusable text layer
- `pypdf` misses where `pdftotext` performs better
- low-quality scan/OCR failure
- proceedings or wrong-document / whole-issue cases
- Exported the full corpus of extraction JSONs to readable TXT files under `qa/validation/text_exports/all/`.
- Built and refreshed focused TXT review directories for:
- `likely_failures/`
- `weaker_cases/`
- `weaker_text_quality_defects/`
- `weaker_proceedings_context/`
- `weaker_metadata_matching_only/`
- Preserved pre-cleanup QA snapshots where early export output was wrong or later superseded:
- `likely_failures_initial_incorrect_export/`
- `likely_failures_before_post_override_cleanup/`
- `weaker_cases_initial_incorrect_export/`
- Reclassified weaker cases into primary-cause buckets using the JSONs as the source of truth:
- `96` text-quality defects
- `22` proceedings/context cases
- `40` metadata/matching-only cases
- Refreshed the likely-failure set so it now contains only the three unresolved cases:
- `23`
- `1421`
- `6268`
- Generated or moved QA artefacts now present under `qa/validation/` include:
- `pdf_source_registry_validation_sample*.json`
- `text_extraction_quality_sample_n300.json`
- `text_extraction_quality_review_n300.csv`
- `text_extraction_quality_review_n300_triaged.csv`
- `text_extraction_full_weaker_cases.csv`
- `text_extraction_full_likely_failures.csv`
- `text_extraction_remainder_weaker_cases.csv`
- `text_extraction_remainder_likely_failures.csv`
- `text_extraction_remainder_triage_summary.json`
- `text_extraction_weaker_cases_classified.csv`
- `text_extraction_weaker_cases_classified_summary.json`
- `text_extraction_weaker_text_quality_defects.csv`
- `text_extraction_weaker_proceedings_context.csv`
- `text_extraction_weaker_metadata_matching_only.csv`

### Notes For Commit Hygiene

- Bucket 1 is a pure docs/policy commit and should stay separate.
- Bucket 2 is code plus tests for new validation utilities.
- Bucket 3 is the extraction-pipeline behavior change plus its tests and the one canonical registry refresh caused by the targeted rerun.
- Bucket 4 is QA output generation only and is best kept separate from code changes.

### Canonical Text Cleanup Stage Follow-Up

- Implemented the canonical phase-1 text-cleanup stage at `src/pipelines/03b_clean_text.py`.
- Added the deterministic cleanup helpers at `src/lib/text_cleanup.py`.
- Added the reviewed cleanup target table at `config/extraction/text_cleanup_overrides.csv`.
- Extended `src/pipelines/12_build_paper_artifact_registry.py` so the master registry now records:
  - `text_preclean` backup presence
  - cleanup-applied status and profile
  - cleanup source strategy
  - source JSON / source PDF provenance
- Updated `src/pipelines/99_overnight_run.py` and pipeline docs so `03b_clean_text.py` is treated as the canonical step between raw extraction and downstream routing.

### Test Coverage And Validation

- Added:
  - `tests/test_text_cleanup.py`
  - `tests/test_03b_clean_text.py`
  - `tests/test_12_build_paper_artifact_registry.py`
- Re-ran the focused cleanup test suite and then full test discovery.
- Current validation result:
  - `49` tests passed under `python -m unittest discover -s tests -p "test_*.py" -v`

### Audit-Adaptation Loop

- Audited the initial `03b` outputs directly against the source PDFs and their pre-clean JSON backups.
- This live audit showed that some born-digital PDFs were better recovered via `pdftotext` than by cleaning already-corrupted `pypdf` text.
- Adapted the cleanup workflow accordingly:
  - added reviewed `source_strategy` support to `03b_clean_text.py`
  - used `pdftotext_cleanup` for cleaner born-digital sources
  - kept `json_cleanup` for OCR-derived or already-best-available sources
- Added a narrow deterministic repair for `gamma-aminobutyric` placeholder corruption (`/H9253...` and `␥...`) after source-PDF inspection confirmed the underlying text.
- Removed `180` from the active cleanup target list after audit showed it was an issue-level / localization problem rather than a text-cleanup problem.

### Full Cleanup Rollout

- Ran `src/pipelines/03b_clean_text.py --force` on the full reviewed cleanup set.
- Result:
  - `23` canonical text JSONs cleaned
  - `data/references/paper_artifact_registry.csv` refreshed
- The canonical text layout is now:
  - cleaned JSONs in `data/extraction_json/text/`
  - preserved pre-clean backups for targeted papers in `data/extraction_json/text_preclean/`

### QA Refresh After 03b

- Refreshed the TXT export views in:
  - `qa/validation/text_exports/all/`
  - `qa/validation/text_exports/weaker_cases/`
  - `qa/validation/text_exports/likely_failures/`
  - `qa/validation/text_exports/weaker_text_quality_defects/`
  - `qa/validation/text_exports/weaker_proceedings_context/`
  - `qa/validation/text_exports/weaker_metadata_matching_only/`
- Added/updated cleanup audit ledgers:
  - `qa/validation/text_cleanup_audit_round1.csv`
  - `qa/validation/text_cleanup_audit_round2.csv`
- Refreshed the weaker-case classification CSVs after the full `03b` rollout.

### Cleanup Outcome

- The phase-1 cleanup stage materially improved the reviewed target set.
- Weaker cases dropped from `158` to `141`.
- Text-quality defects dropped from `96` to `75`.
- The likely-failure set remained:
  - `23`
  - `1421`
  - `6268`
- Cleanup targets that dropped out of the weaker-case set after `03b` included:
  - `25`, `71`, `114`, `116`, `121`, `133`, `139`, `184`, `197`, `223`, `288`, `387`, `821`, `11750`, `11790`, `12502`, `12785`

### Residual Problems After Phase 1

- Residual text-quality defects:
  - `43`
  - `62`
  - `155`
- Residual proceedings/context or localization cases:
  - `11109`
  - `180`
- Residual metadata / matching-only cases:
  - `608`
  - `13177`

### Recommended Next Step

- A second text-correction stage is justified, but only for the residual subset.
- The next stage should stay deterministic and reviewed:
  - targeted per-ID substitution tables for the few remaining corrupted title/body tokens
  - no broad free-form rewriting of canonical text
  - proceedings/context localization handled separately from text correction

## 02.04.2026

Implemented a preliminary stage-2 text-cleanup pipeline, completed a full review pass for the papers outside the original `n=300` sample, and resolved the two large proceedings-localisation cases `1421` and `6268`.

### Repo Rules And Working Conventions

- Added `doc/repo_rules.md` and updated `AGENTS.md` so the repo-level workflow, output placement, runtime expectations, and British-English writing rule are explicit and versioned.

### Stage-2 Text Cleanup Prototype

- Added `src/pipelines/03c_clean_text_stage2.py` as a standalone residual-cleanup stage for papers that still need per-paper source replacement or reviewed token repairs after `03b_clean_text.py`.
- Added reviewed stage-2 control tables:
  - `config/extraction/text_cleanup_stage2_overrides.csv`
  - `config/extraction/text_cleanup_stage2_substitutions.csv`
- Extended `src/pipelines/03_extract_text.py` and `src/pipelines/03c_clean_text_stage2.py` so external PDF tools first stage non-ASCII filenames to temporary ASCII-safe paths on Windows.
- Added and extended test coverage in:
  - `tests/test_03_extract_text.py`
  - `tests/test_03c_clean_text_stage2.py`
- Updated `config/README.md`, `src/README.md`, `src/pipelines/README.md`, and `tests/README.md` to document the new stage-2 workflow.

### Full Review Of The Remainder Corpus

- Completed a detailed review and triage pass for the papers outside the original `n=300` extraction-quality sample.
- Saved the full review and fix-analysis outputs under `qa/validation/`:
  - `text_extraction_remainder_review_full.csv`
  - `text_extraction_remainder_review_full_summary.json`
  - `text_extraction_remainder_fix_analysis.csv`
  - `text_extraction_remainder_fix_analysis_summary.json`
- Promoted a large set of residual weak cases to cleaner stage-2 sources, mainly `pdftotext`-backed re-extraction where the embedded text layer was clearly better than the canonical `pypdf` output.
- Refreshed the live QA ledgers so the current weaker-case and likely-failure CSVs reflect the post-stage-2 state.

### Proceedings And Localization Work

- Resolved `6268` as a proceedings-localisation problem rather than a wrong-PDF problem.
- Confirmed the target abstract is on PDF page `18`.
- Switched stage 2 to OCR the localised page window only, using `psm=3`, and trimmed away neighbouring abstracts via reviewed substitution rules.
- The canonical text now contains the target abstract cleanly and exactly.

- Resolved `1421` as a proceedings-localisation problem rather than a wrong-PDF problem.
- Ran a one-time OCR search across the supplement, saved the search evidence, and confirmed the target abstract is on supplement page `187`.
- Localised stage 2 to that page only and trimmed away spillover from adjacent abstracts.
- The canonical text now contains the correct author block and abstract body.
- The printed supplement page does not show the full title string, so this remains a manually confirmed proceedings match rather than an automatic exact-title match.

- Saved the localisation evidence so the expensive OCR search does not need to be repeated:
  - `qa/validation/proceedings_localization/1421_ocr_search_top_candidates.csv`
  - `qa/validation/proceedings_localization/1421_ocr_search_summary.json`
  - `qa/validation/proceedings_localization/1421_localization_summary.json`
  - `qa/validation/proceedings_localization/6268_localization_summary.json`

- Added final reviewed source-category overrides for both papers in `data/references/source_categorisation_manual_review.csv`:
  - `1421` -> `conference_abstract / single_case_conference_abstract`
  - `6268` -> `conference_abstract / single_case_conference_abstract`

### Current Corpus Status

- All `1000+` extracted sources have now been reviewed at least once:
  - the original `n=300` stratified sample received detailed manual review and triage
  - the remaining corpus received a full review/fix-analysis pass recorded in the new remainder-review outputs
- `1421` and `6268` have been removed from the live likely-failure list.
- The current live likely-failure set is now:
  - `263`
  - `1598`
  - `1841`
  - `9385`
  - `10691`

### Validation

- Re-ran the full test suite:
  - `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`
- Result:
  - `61` tests passed

### Blocker

- `data/references/paper_artifact_registry.csv` remained locked by another process throughout this work.
- Direct runs of `src/pipelines/12_build_paper_artifact_registry.py` still failed with `PermissionError [Errno 13]`.
- Because of that lock, the final artifact-registry refresh could not yet be completed.

## 05.04.2026

Folded the residual rescue path into the canonical cleanup stage, labeled the two remaining unrecoverable extraction items as incorrect references, and extended the artifact-registry schema so stage-2 cleanup provenance can be tracked once the registry file is writable again.

### Cleanup Stage Consolidation

- Moved the stage-2 rescue implementation behind `src/pipelines/03b_clean_text.py --stage2`.
- Added a shared helper module at `src/lib/text_cleanup_stage2.py` so the reviewed stage-2 logic can be reused without drifting.
- Kept `src/pipelines/03c_clean_text_stage2.py` as a compatibility wrapper that now forwards to `03b_clean_text.py --stage2`.
- Added block-level comments to the merged cleanup code so the stage split, provenance handling, and wrapper behavior are easier to follow.

### Incorrect Reference Labels

- Added explicit manual-review rows for:
  - `263`
  - `1841`
- Both now resolve as:
  - `final_source_category = unclear_manual_review`
  - `final_source_subtype = incorrect_reference`
  - `pdf_content_alignment_tag = incorrect_reference`
- Updated the live QA likely-failure ledgers so their reason text now clearly states that these are incorrect-reference problems rather than recoverable text-extraction failures.

### Artifact Registry Schema Extension

- Extended `src/pipelines/12_build_paper_artifact_registry.py` so it now captures stage-2 provenance fields:
  - `text_preclean_stage2_json_present`
  - `text_preclean_stage2_json_path`
  - `text_cleanup_stage2_*` source, page-window, and OCR settings
- Added test coverage for those new fields in `tests/test_12_build_paper_artifact_registry.py`.

### Validation

- Re-ran the full unittest suite:
  - `python -m unittest discover -s tests -p "test_*.py" -v`
- Result:
  - `63` tests passed

### Remaining Blocker

- `src/pipelines/12_build_paper_artifact_registry.py` still cannot overwrite `data/references/paper_artifact_registry.csv`.
- The file remains locked by another process, so the live CSV could not yet be refreshed even though the in-memory row build now resolves:
  - `263` as `incorrect_reference`
  - `1841` as `incorrect_reference`
  - stage-2 provenance for `1421`, `6268`, `1598`, `9385`, and `10691`

### Acquisition Queue And Explicit Incorrect-Reference Exclusions

- Extended `src/pipelines/02_build_pdf_source_registry.py` so it now also writes the canonical remaining acquisition queue at `data/references/pdf_acquisition_queue.csv`.
- The queue is derived directly from the live PDF source registry and currently contains the `12` references with no local PDF:
  - `7` with `download_status = missing`
  - `5` with `download_status = failed`
- Made `incorrect_reference` an explicit downstream routing mode in `src/pipelines/_source_routing.py` rather than letting those rows fall through as generic manual review.
- Updated downstream AI stages so they now exclude those papers explicitly:
  - `src/pipelines/10_langextract.py` reports them as `skipped_incorrect_reference`
  - `src/pipelines/11_quality_assessment.py` reports them as `skipped_incorrect_reference`
- Verified that the live incorrect-reference rows remain:
  - `263`
  - `1841`
- Verified that no LangExtract or quality-assessment artefacts exist for those two papers.

### Validation

- Re-ran the focused regression suite covering the new queue and routing behaviour:
  - `python -m unittest tests.test_02_build_pdf_source_registry tests.test_source_routing tests.test_10_langextract tests.test_11_quality_assessment tests.test_12_build_paper_artifact_registry -v`
- Result:
  - `14` tests passed
- Rebuilt the live PDF registry and acquisition queue:
  - `python src/pipelines/02_build_pdf_source_registry.py`
- Re-ran downstream dry-run checks for the two reviewed incorrect references:
  - `python src/pipelines/10_langextract.py --dry-run --paper-id 263 --paper-id 1841`
  - `python src/pipelines/11_quality_assessment.py --dry-run --paper-id 263 --paper-id 1841`
- Result:
  - both stages now skip those records explicitly without writing downstream artefacts

### Repo Cleanup And Archiving

- Removed the obsolete `src/pipelines/03c_clean_text_stage2.py` compatibility wrapper now that `03b_clean_text.py --stage2` is the only supported entry point for residual cleanup.
- Removed the wrapper-specific test `tests/test_03c_clean_text_stage2.py`.
- Deleted local source-tree `__pycache__` directories to reduce repository noise.
- Moved historical non-canonical proceedings trial and spot-check files out of `data/references/` into `qa/validation/archive/data_references_legacy/`:
  - `proceedings_accuracy_spotcheck_10.csv`
  - `proceedings_accuracy_spotcheck_10_manual.csv`
  - `proceedings_accuracy_spotcheck_10_report.txt`
  - `proceedings_text_qc_registry_trial_2026_03_05_b.csv`
  - `proceedings_text_qc_registry_trial_index_patch.csv`
  - `text_trim_registry_trial_2026_03_05_b.csv`
  - `text_trim_registry_trial_index_patch.csv`
  - `text_trim_registry_trial_index_patch_single.csv`
- Removed stale generated snapshot folders from `qa/validation/text_exports/` so that directory now contains only the live current export sets.
- Updated the README layers so:
  - `data/references/` is described as canonical live registries only
  - `qa/validation/archive/` is the home for preserved historical QA artefacts
  - `03b_clean_text.py` is documented as the sole cleanup entry point

### Validation

- Re-ran the full unittest suite after the cleanup:
  - `python -m unittest discover -s tests -p "test_*.py" -v`
- Result:
  - `55` tests passed

### Top-Level Documentation Close-Out

- Updated the top-level `README.md` so it reflects the current corpus and workflow state rather than the earlier early-project framing.
- The README now states the live step-`01` to step-`03` status explicitly:
  - `1039` tracked references
  - `1027` downloaded PDFs and canonical extracted text JSONs
  - all extracted texts reviewed at least once
  - `12` remaining acquisition-queue items
  - `263` and `1841` marked as `incorrect_reference`
- Clarified in the README that `src/pipelines/03b_clean_text.py` is the sole cleanup entry point, with `--stage2` as the reviewed residual-rescue mode.
- Refreshed the top-level directory snapshot so it matches the repo layout after the cleanup and archive work.
- Prepared and pushed a docs-only sync commit after the latest repo-stewardship pass.

### Source-Categorisation Calibration And Count-Stage Split

- Added a reusable validation sampler at `src/validation/build_source_categorisation_review_sample.py`.
- Generated a first `n=30` review batch with compact CSV and TXT evidence packets under `qa/validation/source_categorisation/`.
- Reviewed that batch against the live stage-`04` heuristics and used it to localise the main failure families in:
  - conference abstract versus full paper routing
  - case series versus group-study routing
  - inflated or missing SPS case counts

### Separate SPS Case-Count Stage

- Split source categorisation and extractable SPS case counting into separate pipeline responsibilities:
  - `src/pipelines/04_source_categorisation_LLM.py` now owns source type and downstream routing
  - `src/pipelines/06_extract_sps_case_counts.py` now owns extractable SPS case counts
- Added the shared count helper `src/pipelines/_sps_case_counting.py`.
- Generated the canonical count registry:
  - `data/references/source_sps_case_count_registry.csv`
- Extended `src/pipelines/12_build_paper_artifact_registry.py` so the master registry now records:
  - separate count-stage presence
  - count eligibility
  - likely SPS case count
  - count confidence and basis
  - count manual-review flag
  - count version and timestamp

### Count-Heuristic Improvement Loop

- Used `examples/datasheet_examples_MC_Case_Report_Form.csv` as the gold-standard count source, interpreting the number of rows per `Reference` as the extractable SPS case count.
- Tightened the count heuristic to:
  - ignore age-like numbers and background prevalence statements
  - down-weight literature-summary counts
  - recognise `participants` / cohort counts
  - suppress score-scale artefacts such as `0-4`
  - keep a narrower single-case fallback without overriding explicit multi-case papers
  - avoid trusting body-derived patient labels from untrimmed proceedings PDFs
- Added focused regression coverage in:
  - `tests/test_sps_case_counting.py`
  - `tests/test_04_source_categorisation_extractable_case_counts.py`
  - `tests/test_04_source_categorisation_review_batch.py`

### Validation

- Re-ran the dedicated count benchmark:
  - `python -m unittest tests.test_04_source_categorisation_extractable_case_counts -v`
  - result: `95.2%` exact count accuracy over `168` evaluable references
- Re-ran the focused split-stage regression coverage:
  - `python -m unittest tests.test_sps_case_counting -v`
  - `python -m unittest tests.test_04_source_categorisation_review_batch -v`
- The review-batch file remains useful for category/subtype edge cases, but its count columns are no longer treated as a canonical benchmark when the reviewer left the count blank.

## 05.04.2026 (continued)

Added a reproducible gold-standard review workflow for source categorisation and extractable SPS case counts, then used two reviewed rounds to calibrate stage `04` and stage `06`.

### Gold-Standard Review Workflow

- Added a dedicated validation workflow under `src/validation/` for stage-`04` / stage-`06` review:
  - `build_stage04_gold_batch.py`
  - `review_stage04_gold_app.py`
  - `benchmark_stage04_gold.py`
  - `_stage04_gold.py`
- Added a Streamlit reviewer so local PDF review can be done inside the repo with:
  - predicted source category
  - predicted extractable SPS count
  - reviewer override fields
  - resumable per-round response saving
  - in-app PDF text search and page-jump navigation
- Generated review rounds under `qa/validation/source_categorisation/gold_standard/`:
  - `2026-04-05_round_01`
  - `2026-04-05_round_02`
  - `2026-04-05_round_03`
- Added the canonical cumulative reviewed gold file:
  - `qa/validation/source_categorisation/gold_standard/04_categorisation_gold_standard.csv`
- Kept `stage04_gold_standard_master.csv` in sync as a compatibility alias.
- Updated the README layers so the gold-standard file and reviewer workflow are explicitly documented.

### Pipeline Ordering And Renames

- Moved proceedings validation and case counting into the intended operational order after source categorisation:
  - `04_source_categorisation_LLM.py`
  - `05_trim_proceedings_text.py`
  - `05b_validate_proceedings_text.py`
  - `06_extract_sps_case_counts.py`
  - `07_split_case_series.py`
- Renamed:
  - `src/pipelines/06_validate_proceedings_text.py` -> `src/pipelines/05b_validate_proceedings_text.py`
  - `src/pipelines/04b_extract_sps_case_counts.py` -> `src/pipelines/06_extract_sps_case_counts.py`
- Updated the overnight orchestrator, validation scripts, tests, and docs so the new naming and order are consistent.

### Round-02 Calibration

- Incorporated the completed `2026-04-05_round_02` review into the canonical cumulative gold file.
- Patched stage `04` and stage `06` against the reviewed errors:
  - better cohort-versus-lab routing
  - diagnosis-specific subgroup counting
  - improved handling of literature-only and titre/protein numbers
  - zeroed extractable counts for genuinely non-extractable lab-heavy studies
- Added regression coverage so the reviewed round remains reproducible and benchmarkable.
- Generated `2026-04-05_round_03` as the next 20-paper review set.

### Round-03 Calibration

- Added the completed `2026-04-05_round_03` responses into:
  - `04_categorisation_gold_standard.csv`
  - `stage04_gold_standard_master.csv`
- Patched the heuristics in:
  - `src/pipelines/04_source_categorisation_LLM.py`
  - `src/pipelines/06_extract_sps_case_counts.py`
  - `src/pipelines/_sps_case_counting.py`
- Main round-03 fixes:
  - proceedings-aware routing using trimmed/title-localised text windows
  - stronger title-only and single-patient therapeutic routing
  - OCR-ligature normalisation for count extraction
  - conference-abstract result-section count capture such as `six girls`
  - SPS subgroup counts from `13 of 17`-style phrasing and table-row signals
  - better suppression of weak non-extractable counts in translational / observational cohorts
  - preservation of explicit single-case counts for rare review-tagged rows
- Added focused regression tests in:
  - `tests/test_sps_case_counting.py`
  - `tests/test_06_extract_sps_case_counts.py`
  - `tests/test_stage04_gold_regressions.py`

### Current Benchmark State

- Round `01` benchmark:
  - `100%` category accuracy
  - `60%` count accuracy
  - the remaining misses are older mixed-cohort / prevalence-style count disagreements that were left visible rather than paper-specific patched
- Round `02` benchmark:
  - `100%` category accuracy
  - `100%` count accuracy
- Round `03` benchmark:
  - `100%` category accuracy
  - `95%` count accuracy
  - the one remaining mismatch is a duplicate milacemide trial-family conflict between paper `12137` and the earlier reviewed paper `22`
- Cumulative gold benchmark over `04_categorisation_gold_standard.csv`:
  - `100%` category accuracy
  - `90%` count accuracy

### Commit Hygiene

- Created small, topic-specific commits for the new workflow and calibration loop, including:
  - `46e6538` `Rename proceedings QC and case count stages`
  - `224a688` `Improve stage 04 routing and SPS subgroup counts`
  - `72e7f7e` `Add searchable PDF navigation to gold review app`
  - `a6c73ee` `Add reviewed stage 04 gold rounds and regression check`
  - `ba30d98` `Calibrate stage 04 against round 02 gold review`
  - `689e0b2` `Add reviewed round 03 gold categorisation labels`
  - `b63601c` `Calibrate stage 04 and 06 against round 03 gold review`

## 06.04.2026

Refactored proceedings trimming and proceedings QC around explicit header-pattern detection, added boundary-aware regression coverage, and regenerated the canonical stage-`05` artefacts.

### Proceedings trimming refactor

- Added shared proceedings helpers in:
  - `src/pipelines/_proceedings_text.py`
- Refactored:
  - `src/pipelines/05_trim_proceedings_text.py`
  - `src/pipelines/05b_validate_proceedings_text.py`
- Main behaviour changes:
  - infer the local proceedings header pattern before localisation
  - support uncoded title-style and uppercase proceedings headers in addition to code-prefixed abstracts
  - trim from the matched source header to the next detected header/delimiter rather than relying on title similarity alone for the end boundary
  - carry start/end global line anchors into trimmed proceedings JSONs and the trim registry
  - validate trimmed proceedings text against the full source span so QC can detect:
    - clean full matches
    - early truncation before the next header
    - spillover into the neighbouring abstract
    - header-only listings

### Test and documentation updates

- Expanded `tests/test_05_trim_proceedings_text.py` with fixture-driven checks for:
  - uncoded uppercase header detection
  - next-header stopping
  - header-only listings
- Added `tests/test_05b_validate_proceedings_text.py` for segmentation-aware proceedings QC.
- Updated README layers in:
  - `README.md`
  - `src/pipelines/README.md`
  - `qa/validation/README.md`
  - `data/references/README.md`

### Validation

- Ran focused automated checks:
  - `python -m pytest tests/test_05_trim_proceedings_text.py tests/test_05b_validate_proceedings_text.py`
  - `python -m ruff check src/pipelines/_proceedings_text.py src/pipelines/05_trim_proceedings_text.py src/pipelines/05b_validate_proceedings_text.py tests/test_05_trim_proceedings_text.py tests/test_05b_validate_proceedings_text.py`
- Built a small real-data validation pack under:
  - `qa/validation/proceedings_stage05_2026-04-06/`
- Subset outcomes:
  - `1229`: `confirmed_full`
  - `12807`: `header_only_source`
  - `1605`: `confirmed_full`
  - `1793`: `confirmed_full`

### Canonical reruns

- Re-ran:
  - `src/pipelines/05_trim_proceedings_text.py --include-already-trimmed --skip-registry-refresh`
  - `src/pipelines/05b_validate_proceedings_text.py --skip-registry-refresh`
  - `src/pipelines/12_build_paper_artifact_registry.py`
- Refreshed canonical outputs:
  - `data/references/text_trim_registry.csv`
  - `data/references/proceedings_text_qc_registry.csv`
  - `data/references/paper_artifact_registry.csv`

### Current proceedings status

- Trim registry:
  - `124` `trimmed_auto`
  - `30` `header_only_source`
  - `41` `manual_review_required`
  - `44` `not_needed`
- Proceedings QC registry:
  - `106` `confirmed_full`
  - `80` `untrimmed_localised`
  - `23` `partial_truncated`
  - `18` `header_only_source`
  - `11` `mismatch`
  - `1` `spillover_detected`

### Missed proceedings audit

- Added `src/validation/find_missed_proceedings_candidates.py` to audit non-conference stage-04 rows for missed proceedings fragments or conference-style abstracts.
- Refactored proceedings fuzzy matching into the shared helper `src/pipelines/_proceedings_text.py` so stage `05`, stage `05b`, and the new audit use the same title/author scoring.
- Added `tests/test_find_missed_proceedings_candidates.py`.
- The audit combines:
  - metadata cues such as `conference paper`, `conference abstract`, `poster`, and `supplement`
  - local proceedings-format cues around the matched title and author block
  - stricter code handling so section numbering like `1. Introduction` is not mistaken for proceedings codes
- Added focused-batch support via repeated `--paper-id` flags and made snippet exports overwrite stale TXT files on rerun.
- Built a focused mixed validation pack under:
  - `qa/validation/missed_proceedings_audit_2026-04-06/focused_batch_mixed/`
- Focused mixed batch outcome after tightening the heuristic:
  - `8` candidates selected from `15` tested papers
  - retained strong or moderate proceedings-style hits such as `5753`, `6271`, `1017`, `1597`, `1784`, `1935`, `8198`, and `8317`
  - dropped the obvious full-article false positives from the same batch such as `101`, `432`, `647`, `828`, and `952`

## 2026-04-10

### Proceedings trimming regression pass

- Reviewed batch `007` feedback and analysed four boundary failures:
  - `1418`: cut off at a proceedings page header/footer before the carried-over conclusion on the next page
  - `1433`: failed to stop at the next spaced abstract code (`CGR 8`)
  - `1439`: body text was misread as author/header text, causing an early cut
  - `1441`: split author/affiliation header handling was too weak and QC treated a disclosure tail as missing abstract text
- Implemented narrow fixes in:
  - `src/pipelines/_proceedings_text.py`
  - `src/pipelines/05_trim_proceedings_text.py`
  - `src/pipelines/05b_validate_proceedings_text.py`
- Added focused regression coverage in:
  - `tests/test_05_trim_proceedings_text.py`
  - `tests/test_05b_validate_proceedings_text.py`
  - `tests/test_evaluate_trimming_feedback.py`

### Follow-on regression handling

- A full replay surfaced three older cases where header disclosures were being treated as trailing disclosure tails (`1011`, `1245`, `1246`) and one QC identity false negative on an OCR-damaged title (`1251`).
- Tightened the trimmer so disclosure-tail removal only fires after abstract body headings have begun.
- Tightened QC page matching so title/author identity also scores against the header slice, not only the whole page.

### Validation

- Ran focused automated checks:
  - `.venv\Scripts\python.exe -m pytest tests/test_05_trim_proceedings_text.py tests/test_05b_validate_proceedings_text.py tests/test_evaluate_trimming_feedback.py`
- Result:
  - `45 passed`
- Replayed stage `05` and stage `05b` outputs for:
  - `batch_001`
  - `batch_002`
  - `batch_003`
  - `batch_004`
  - `batch_005`
  - `batch_007`
  - `regression_boundary_review`
- Refreshed batch `007` acceptance:
  - `qa/trimming/reports/batch_007/acceptance_report.json`
  - outcome: `10/10` passed
- Refreshed full trimming regression:
  - `qa/trimming/reports/regression_evaluation_batch_007.json`
  - outcome: `59/59` passed

### Proceedings trimming batch 008 follow-up

- Reviewed batch `008` feedback and analysed the main failure patterns:
  - header-only duplicate listings being chosen instead of the later full abstract (`1662`)
  - wrapped all-caps or soft proceedings boundaries being missed, causing spill-over (`1605`, `1664`)
  - isolated abstract/article pages still being treated as proceedings candidates (`1611`, `1668`)
  - event/session preamble and footer noise leaking into the kept span (`1721`, `1664`)
  - dotted or compact abstract codes not being recognised consistently enough for QC boundary checks (`1437`, `1602`)
- Implemented narrow updates in:
  - `src/pipelines/_proceedings_text.py`
  - `src/pipelines/05_trim_proceedings_text.py`
  - `src/pipelines/05b_validate_proceedings_text.py`
  - `src/validation/evaluate_trimming_feedback.py`
- Added focused regression coverage for:
  - conference footer stripping
  - numbered affiliation lines
  - isolated abstract/article-page rejection
  - dotted-code boundary validation
  - mojibake-tolerant page identity scoring
  - manual-follow-up checks for `stage05_not_needed`

### Batch and regression replay

- Froze the accepted batch `008` feedback in:
  - `qa/trimming/feedback/batch_008_feedback.json`
  - `qa/trimming/regression/batch_008_feedback.json`
- Replayed stage `05` and stage `05b` for `batch_008`, then rebuilt:
  - `qa/trimming/reports/batch_008/batch_report.json`
  - `qa/trimming/reports/batch_008/acceptance_report.json`
- Batch `008` accepted-case outcome:
  - `9/9` passed
  - `1675` remains outside the frozen fixture and still needs human review
- After tightening the evaluator to enforce expected manual-review status for `stage05_not_needed`, older stored QC bundles for `batch_002` and `batch_003` were stale.
- Replayed stage `05` and stage `05b` for `batch_002` and `batch_003`, then refreshed:
  - `qa/trimming/reports/batch_002/acceptance_report.json`
  - `qa/trimming/reports/batch_003/acceptance_report.json`
- Refreshed full trimming regression:
  - `qa/trimming/reports/regression_evaluation_batch_008.json`
  - outcome: `68/68` passed

### Manual follow-up flag

- Measured `manual_follow_up_required` against the accepted human-feedback corpus for stage `05` cases only, excluding routing-gate cases.
- Overall accepted stage `05` corpus:
  - `60/60` correct
  - precision `1.00`
  - recall `1.00`
- Batch `008` accepted subset:
  - `9/9` correct
  - true positives `2`
  - true negatives `7`

### Batch 008 finalisation

- Finalised `1675` as a `stage05_not_needed` case after confirming it behaves like an isolated abstract/article-style page rather than a trim-worthy proceedings bundle.
- Updated:
  - `qa/trimming/feedback/batch_008_feedback.json`
  - `qa/trimming/regression/batch_008_feedback.json`
  - `qa/trimming/batches/batch_008.json`
  - `qa/trimming/reports/batch_008/acceptance_report.json`
- Batch `008` is now fully resolved:
  - accepted-case outcome `10/10`

### Stage 05 50-paper review accelerator

- Implemented a resumable stage-05 review workflow for larger proceedings-trimming rounds, using patched `batch_008` behaviour as the baseline.
- Extended:
  - `src/validation/manage_trimming_batches.py`
  - `src/pipelines/05b_validate_proceedings_text.py`
- Added:
  - `src/validation/_stage05_review.py`
  - `src/validation/review_stage05_app.py`
  - `src/validation/update_trimming_review_outputs.py`
  - `src/validation/apply_trimming_manual_overrides.py`
- Updated documentation in:
  - `qa/trimming/README.md`
  - `src/validation/README.md`

### Workflow changes

- Batch preparation now:
  - defaults to a 50-paper target
  - writes the batch manifest before screening begins
  - resumes interrupted stage `05` and `05b` work instead of restarting
  - excludes papers already frozen in `qa/trimming/feedback/` or `qa/trimming/regression/`
  - blocks opening a new batch while another unresolved batch exists
- Batch manifests now track:
  - `stage05_running`
  - `stage05b_running`
  - `awaiting_review`
  - `feedback_received`
  - `patch_in_progress`
  - `override_in_progress`
  - `resolved`
- Stage `05b` registry writing is now merge-safe for per-paper and limited reruns, so prior QC rows are preserved on resume.

### Review tooling

- Added a dedicated Streamlit reviewer for stage `05` that shows:
  - the source PDF with page jump and extracted-text search
  - current trim and QC status
  - a preview of the current trimmed abstract
  - a single correctness checkbox
  - conditional correction fields for reviewed start anchor, end anchor, and patch comments
- Review responses now persist to `responses.csv` before acceptance artefacts are refreshed, so saves survive UI reruns and crashes.
- Added non-canonical batch artefacts under `qa/trimming/reports/<batch_id>/`:
  - `review_queue.csv`
  - `responses.csv`
  - `feedback.json`
  - `manual_overrides.csv`
  - `acceptance_report.json`
  - `patch_review_summary.json`
- General `05/05b` code patches remain the preferred correction path; `manual_overrides.csv` is a fallback-only mechanism for residual failures.

### Verification

- Added or updated targeted tests in:
  - `tests/test_manage_trimming_batches.py`
  - `tests/test_05b_validate_proceedings_text.py`
  - `tests/test_stage05_review.py`
  - `tests/test_apply_trimming_manual_overrides.py`
- Ran:
  - `.venv\Scripts\python.exe -m pytest tests/test_stage05_review.py tests/test_manage_trimming_batches.py tests/test_apply_trimming_manual_overrides.py tests/test_05b_validate_proceedings_text.py tests/test_evaluate_trimming_feedback.py tests/test_05_trim_proceedings_text.py -q`
  - `.venv\Scripts\python.exe -m py_compile src/validation/_stage05_review.py src/validation/review_stage05_app.py src/validation/manage_trimming_batches.py src/validation/update_trimming_review_outputs.py src/validation/apply_trimming_manual_overrides.py src/pipelines/05b_validate_proceedings_text.py`
- Result:
  - `65 passed in 8.92s`

### Stage 05 early-truncation hardening and batch 011 handover

- Investigated the next reviewed `batch_010` failures against the saved reviewer end anchors rather than relying on QC status alone.
- Localised the dominant root cause to false abstract-boundary detection in proceedings text:
  - body lines such as `from 80 Hz to 1000 Hz.`, `7.0) ...`, `2011.2) ...`, and `1LSU ...` were being mistaken for new abstract headers
  - true proceedings starts such as `Poster 321:`, `OP87 - 3001`, split coded headers (`C32`, `117`), and similar variants were not being recognised consistently enough
  - bare title fragments such as `Case Report` could be misread as real section headings, causing header-only trims
- Tightened proceedings parsing in:
  - `src/pipelines/_proceedings_text.py`
  - `src/pipelines/05_trim_proceedings_text.py`
  - `src/validation/evaluate_trimming_feedback.py`
- Added regression coverage for:
  - dashed session codes and poster-style code starts
  - lowercase spaced-body false positives
  - numeric dotted-code false positives
  - numeric-letter affiliation false positives
  - split coded-title boundaries
  - retained versus trimmable tail metadata
  - approximate reviewer start anchors and trimmed end anchors without trailing `References` / `Disclosures`
- Adopted trailing `Disclosure` / `References` sections as non-informative abstract-tail signals for trimming and acceptance, while still allowing retained tails such as `Keywords`, `Level of Evidence`, `Final Comments`, and `Informed Consent`.

### Historical regression replay

- Replayed the affected reviewed cases in:
  - `qa/trimming/reports/batch_001/`
  - `qa/trimming/reports/batch_002/`
  - `qa/trimming/reports/batch_003/`
  - `qa/trimming/reports/batch_007/`
  - `qa/trimming/reports/batch_009/`
  - `qa/trimming/reports/batch_010/`
- Specifically repaired the previously failing historical reviewed papers:
  - `1116`
  - `1452`
  - `1453`
  - `1830`
- Refreshed `batch_010` review artefacts after patching.
- Verified reviewed-regression status in `qa/trimming/reports/regression_evaluation_batch_010.json`:
  - `89/89` passed
- Verified the accepted first 10 reviewed papers in `batch_010`:
  - `10/10` passed

### Review app and next batch

- Updated `src/validation/review_stage05_app.py` so the PDF viewer keeps a fixed frame and uses app-level zoom controls, avoiding the earlier resize-only behaviour and the dark text-layer shading artefact.
- Froze the accepted first 10 reviewed papers from `batch_010` into:
  - `qa/trimming/feedback/batch_010_feedback.json`
  - `qa/trimming/regression/batch_010_feedback.json`
- Marked `qa/trimming/batches/batch_010.json` as `superseded` after freezing those accepted cases.
- Generated the next review round as `batch_011` with a 10-paper target using the patched stage-05 baseline.
- `batch_011` paper IDs:
  - `1625`
  - `1932`
  - `1947`
  - `3125`
  - `5029`
  - `5079`
  - `5087`
  - `5158`
  - `5212`
  - `5233`
- `batch_011` initial QC summary:
  - `7` `confirmed_full`
  - `2` `partial_truncated`
  - `1` `header_only_source`
  - `3` marked `manual_follow_up_required=true`

### Verification

- Ran:
  - `.venv\Scripts\python.exe -m pytest tests/test_05_trim_proceedings_text.py tests/test_05b_validate_proceedings_text.py tests/test_evaluate_trimming_feedback.py tests/test_stage05_review.py -q`
  - `.venv\Scripts\python.exe -m py_compile src/pipelines/_proceedings_text.py src/pipelines/05_trim_proceedings_text.py src/validation/evaluate_trimming_feedback.py tests/test_05_trim_proceedings_text.py`
  - `.venv\Scripts\python.exe src/pipelines/05_trim_proceedings_text.py --include-already-trimmed --skip-registry-refresh --output-dir qa/trimming/reports/batch_001/text_trimmed --registry-path qa/trimming/reports/batch_001/text_trim_registry.csv --paper-id 1116`
  - `.venv\Scripts\python.exe src/pipelines/05_trim_proceedings_text.py --include-already-trimmed --skip-registry-refresh --output-dir qa/trimming/reports/batch_007/text_trimmed --registry-path qa/trimming/reports/batch_007/text_trim_registry.csv --paper-id 1452 --paper-id 1453`
  - `.venv\Scripts\python.exe src/pipelines/05_trim_proceedings_text.py --include-already-trimmed --skip-registry-refresh --output-dir qa/trimming/reports/batch_009/text_trimmed --registry-path qa/trimming/reports/batch_009/text_trim_registry.csv --paper-id 1830`
  - `.venv\Scripts\python.exe src/pipelines/05b_validate_proceedings_text.py --skip-registry-refresh --trimmed-dir qa/trimming/reports/batch_001/text_trimmed --text-trim-registry qa/trimming/reports/batch_001/text_trim_registry.csv --output-path qa/trimming/reports/batch_001/proceedings_text_qc_registry.csv --paper-id 1116`
  - `.venv\Scripts\python.exe src/pipelines/05b_validate_proceedings_text.py --skip-registry-refresh --trimmed-dir qa/trimming/reports/batch_007/text_trimmed --text-trim-registry qa/trimming/reports/batch_007/text_trim_registry.csv --output-path qa/trimming/reports/batch_007/proceedings_text_qc_registry.csv --paper-id 1452 --paper-id 1453`
  - `.venv\Scripts\python.exe src/pipelines/05b_validate_proceedings_text.py --skip-registry-refresh --trimmed-dir qa/trimming/reports/batch_009/text_trimmed --text-trim-registry qa/trimming/reports/batch_009/text_trim_registry.csv --output-path qa/trimming/reports/batch_009/proceedings_text_qc_registry.csv --paper-id 1830`
  - `.venv\Scripts\python.exe src/validation/update_trimming_review_outputs.py --batch-id batch_010`
  - `.venv\Scripts\python.exe src/validation/manage_trimming_batches.py --batch-size 10`
- Result:
  - `78 passed in 35.58s`
  - historical reviewed regression green at `89/89`
  - `batch_011` prepared successfully with 10 papers

## 2026-04-11

### Stage-05 reviewed regression guard

- Replayed the frozen reviewed `stage05_trimming` regression set in eight tranches under `qa/trimming/reports/stage05_regression_guard/`.
- Added dedicated regression tooling in:
  - `src/validation/_stage05_regression.py`
  - `src/validation/run_stage05_regression_tranches.py`
- Enforced reviewed-stage expectations in this priority order:
  - explicit historical reviewer feedback for wrong starts
  - explicit historical reviewer feedback for wrong ends
  - otherwise the historical reviewed JSON start/end as the default truth
- Verified the current frozen reviewed pool in the repo:
  - `73` `stage05_trimming` cases
  - `8` `routing_gate` cases
  - `8` `stage05_not_needed` cases
  - `89` total frozen reviewed regression cases

### Compatibility fixes

- Removed the generic stage-05 trailing DOI trim that had regressed historical reviewed proceedings outputs.
- Added reviewed compatibility overrides in `config/extraction/proceedings_trim_overrides.csv` for residual legacy cases that require:
  - exact historical spans
  - or explicit DOI stripping where the reviewed end feedback stops before the DOI
- Patched `src/pipelines/05b_validate_proceedings_text.py` so a solitary DOI-only tail gap is not misclassified as truncation.
- Patched `src/validation/evaluate_trimming_feedback.py` and the stage-05 regression matcher so reviewed end anchors handle:
  - leading reviewer ellipsis such as `...`
  - OCR-merged tail text near the abstract end

### Regression outcome

- Cleared all eight reviewed `stage05_trimming` tranches:
  - tranche 001: `10/10`
  - tranche 002: `10/10`
  - tranche 003: `10/10`
  - tranche 004: `10/10`
  - tranche 005: `10/10`
  - tranche 006: `10/10`
  - tranche 007: `10/10`
  - tranche 008: `3/3`
- Consolidated the tranche artefacts in:
  - `qa/trimming/reports/stage05_regression_guard/full_summary.json`

### Next review batch

- Refreshed `batch_011` on the patched stage-05 baseline instead of opening a duplicate batch.
- `batch_011` remains the current review batch in `qa/trimming/batches/batch_011.json`.
- `batch_011` paper IDs:
  - `1625`
  - `1932`
  - `1947`
  - `3125`
  - `5029`
  - `5079`
  - `5087`
  - `5158`
  - `5212`
  - `5233`

### Verification

- Ran:
  - `.venv\Scripts\python.exe -m pytest tests/test_stage05_regression.py tests/test_05_trim_proceedings_text.py tests/test_05b_validate_proceedings_text.py tests/test_evaluate_trimming_feedback.py -q`
  - `.venv\Scripts\python.exe -m py_compile src/pipelines/05_trim_proceedings_text.py src/pipelines/05b_validate_proceedings_text.py src/validation/evaluate_trimming_feedback.py src/validation/_stage05_regression.py src/validation/run_stage05_regression_tranches.py`
  - `.venv\Scripts\python.exe src/validation/run_stage05_regression_tranches.py --tranche-size 10 --max-tranches 1`
  - `.venv\Scripts\python.exe src/validation/run_stage05_regression_tranches.py --tranche-size 10 --start-tranche 2 --max-tranches 1`
  - `.venv\Scripts\python.exe src/validation/run_stage05_regression_tranches.py --tranche-size 10 --start-tranche 3 --max-tranches 1`
  - `.venv\Scripts\python.exe src/validation/run_stage05_regression_tranches.py --tranche-size 10 --start-tranche 4 --max-tranches 1`
  - `.venv\Scripts\python.exe src/validation/run_stage05_regression_tranches.py --tranche-size 10 --start-tranche 5 --max-tranches 1`
  - `.venv\Scripts\python.exe src/validation/run_stage05_regression_tranches.py --tranche-size 10 --start-tranche 6 --max-tranches 1`
  - `.venv\Scripts\python.exe src/validation/run_stage05_regression_tranches.py --tranche-size 10 --start-tranche 7 --max-tranches 1`
  - `.venv\Scripts\python.exe src/validation/run_stage05_regression_tranches.py --tranche-size 10 --start-tranche 8 --max-tranches 1`
  - `.venv\Scripts\python.exe src/pipelines/05_trim_proceedings_text.py --all-papers --include-already-trimmed --output-dir qa/trimming/reports/batch_011/text_trimmed --registry-path qa/trimming/reports/batch_011/text_trim_registry.csv --skip-registry-refresh --paper-id 1625 --paper-id 1932 --paper-id 1947 --paper-id 3125 --paper-id 5029 --paper-id 5079 --paper-id 5087 --paper-id 5158 --paper-id 5212 --paper-id 5233`
  - `.venv\Scripts\python.exe src/pipelines/05b_validate_proceedings_text.py --trimmed-dir qa/trimming/reports/batch_011/text_trimmed --text-trim-registry qa/trimming/reports/batch_011/text_trim_registry.csv --output-path qa/trimming/reports/batch_011/proceedings_text_qc_registry.csv --skip-registry-refresh --paper-id 1625 --paper-id 1932 --paper-id 1947 --paper-id 3125 --paper-id 5029 --paper-id 5079 --paper-id 5087 --paper-id 5158 --paper-id 5212 --paper-id 5233`
  - `.venv\Scripts\python.exe src/validation/update_trimming_review_outputs.py --batch-id batch_011`
- Result:
  - `85 passed`
  - reviewed `stage05_trimming` regression set green at `73/73`
  - refreshed `batch_011` ready for review

### Stage-05 autoresearch harness

- Added isolated stage-05 `_autoresearch` pipeline copies so optimisation can proceed without touching the canonical production scripts:
  - `src/pipelines/_proceedings_text_autoresearch.py`
  - `src/pipelines/05_trim_proceedings_text_autoresearch.py`
  - `src/pipelines/05b_validate_proceedings_text_autoresearch.py`
- Added the minimal frozen stage-05 autoresearch harness in:
  - `src/autoresearch/stage_05/gold.py`
  - `src/autoresearch/stage_05/benchmark.py`
  - `src/autoresearch/stage_05/program.md`
- The benchmark is now explicitly frozen so the optimisation loop cannot improve the metric by changing:
  - `benchmark.py`
  - the scoring rules
  - the strict normalisation
- Gold manifest entries now capture:
  - `paper_id`
  - `gold_json_path`
  - `source_text_path`
  - `reviewer`
  - `notes`
  - text hashes and first/last-line anchors
- The frozen benchmark now emits fixed per-paper labels:
  - `missing_output`
  - `spillover`
  - `truncated`
  - `exact_match`
  - `wrong_abstract`
- Updated the relevant README files for `src/`, `src/pipelines/`, `src/validation/`, `src/autoresearch/`, `src/autoresearch/stage_05/`, and `qa/trimming/`.

### Verification

- Ran:
  - `.venv\Scripts\python.exe -m pytest tests/test_stage05_gold.py tests/test_stage05_regression.py`
  - `.venv\Scripts\python.exe -m pytest tests/test_05_trim_proceedings_text.py -k AutoresearchSmoke tests/test_05b_validate_proceedings_text.py -k AutoresearchSmoke`
- Did not run the live stage-05 gold benchmark because the gold-standard JSON corpus is still being generated.

### Stage-05 gold-standard completion

- Restored and finalised the stage-05 gold tooling in:
  - `src/validation/_stage05_gold.py`
  - `src/validation/promote_stage05_gold.py`
  - `src/validation/_stage05_regression.py`
  - `src/validation/run_stage05_regression_tranches.py`
- Built the proceedings gold corpus under `qa/trimming/gold_standard/` with:
  - `83` active gold JSONs in `papers/`
  - `manifest.json`
  - tranche verification reports
  - `verify_summary.json`
  - `COMPLETE`
- Verification outcome:
  - older reviewed regression set re-run against the latest code: `73/73` passed
  - additional reviewed `batch_011` gold JSONs checked directly against reviewed anchors: `10/10` passed
  - combined gold verification: `83/83` passed
- Ran:
  - `.venv\Scripts\python.exe -m pytest tests/test_stage05_gold.py tests/test_stage05_regression.py tests/test_evaluate_trimming_feedback.py tests/test_stage05_review.py -q`
  - `.venv\Scripts\python.exe -m py_compile src/validation/_stage05_gold.py src/validation/_stage05_regression.py src/validation/run_stage05_regression_tranches.py src/validation/promote_stage05_gold.py`

### Stage-05 automation runner

- Added the stage-05 outer-loop runner in:
  - `src/autoresearch/stage_05/loop.py`
- Added the gold-completion watcher / launcher in:
  - `src/autoresearch/stage_05/trigger.py`
- Updated the stage-05 autoresearch docs so the stop condition is explicit:
  - stop once every gold paper is `exact_match`
  - and regression failed count is `0`
- The trigger now launches the full stage-05 loop by default after `qa/trimming/gold_standard/COMPLETE` appears, while still supporting the older baseline-only launch mode.
- Added focused tests for:
  - trigger readiness / command construction
  - loop keep/discard and stop-condition logic

### Verification

- Ran:
  - `.venv\Scripts\python.exe -m pytest tests/test_stage05_trigger.py tests/test_stage05_loop.py tests/test_stage05_gold.py tests/test_stage05_regression.py -q`
  - `.venv\Scripts\python.exe src/autoresearch/stage_05/loop.py --help`
  - `.venv\Scripts\python.exe src/autoresearch/stage_05/trigger.py --help`

### Stage-05 autoresearch structure pass

- Simplified the stage-05 autoresearch run structure to align more closely with the `karpathy/autoresearch` style while keeping the SPS-specific benchmark and stop rules:
  - human-readable `run_tag` support
  - recommended branch naming `autoresearch/<run_tag>`
  - a shorter `results.tsv` ledger
  - per-iteration `decision.json` and `candidate.patch` artefacts
  - standard stdout/stderr log paths for agent and benchmark commands
- Tightened the keep/discard rule so a metrics tie can still be kept when the editable diff is a real simplification.
- Added explicit timeout handling for `codex exec` and benchmark subprocesses in both the loop and the trigger.

### Pytest temp/cache stabilisation

- Added repo-level `pytest.ini` so pytest no longer defaults to the user temp root and legacy `.pytest_cache` path:
  - `cache_dir = pytest_cache`
- Updated `.gitignore` to keep the new pytest temp/cache directories untracked.
- Added root `conftest.py` so repo tests use a workspace-local `tmp_path` / `tmp_path_factory` implementation backed by normal `Path.mkdir()` instead of the failing Windows temp-dir behaviour from pytest's built-in tmpdir layer.
- Patched `tempfile.mkdtemp()` inside pytest runs to use the same workspace-local temp root, because `tempfile.TemporaryDirectory()` was hitting the same Windows permission failure.
- Also downgraded the known Windows pytest temp-dir finalisation `PermissionError` to a warning so teardown no longer aborts the session.
- Reason: repeated Windows permission failures were coming from stale inaccessible pytest temp/cache directories rather than from the pytest package install itself.

### Autoresearch

#### Stage-05 live status sidecar

- Added `src/autoresearch/stage_05/status.py` as a read-only sidecar for live or completed stage-05 runs.
- The status sidecar:
  - inspects the latest loop payload or an explicit run root
  - infers the current run phase from the baseline, ledger, and loop summary artefacts
  - records a compact `status_snapshot.json` under the run root and `qa/trimming/gold_standard/autoresearch/latest_status_snapshot.json`
  - keeps chat check-ins lightweight without touching the live autoresearch workers
- Updated `.gitignore` so the top-level `latest_status_snapshot.json` sidecar stays untracked like the other runtime artefacts.
- Added focused coverage in `tests/test_stage05_status.py`.

#### Stage-05 baseline timeout and resume fix

- Removed the nested `--include-regression` call from the loop and trigger harnesses so the gold benchmark no longer tries to run regression internally before the harness launches the standalone regression step.
- Updated `src/autoresearch/stage_05/benchmark.py` to reuse existing non-canonical trim/QC artefacts when their registries already cover the target `paper_id` set:
  - skip trim when the trim registry covers every target paper and each row that should have a trimmed JSON still resolves to an existing file under `text_trimmed/`
  - rebase copied `trimmed_text_json_path` values onto the fresh run root when local reused files are present
  - skip QC when the QC registry already covers every target paper and the trim outputs were reused unchanged
- Reworked `loop.run_logged_command()` to use a `Popen` timeout wrapper that kills the full subprocess tree on timeout, preventing orphan Python workers from continuing after a failed benchmark.
- Increased the default benchmark timeout in both the loop and the trigger from `1800` seconds to `14400` seconds.
- Seeded `qa/trimming/gold_standard/autoresearch/runs/stage05-apr12_04/baseline/gold/` from the completed `stage05-apr12_03` gold trim artefacts and relaunched the loop on branch `autoresearch/stage05-apr12`.
- Added focused tests for:
  - gold benchmark reuse with complete trim/QC artefacts
  - gold benchmark reuse with trim-only artefacts that require a QC rerun
  - loop benchmark commands avoiding nested regression
  - timeout logging for the new subprocess wrapper
  - trigger baseline launch keeping gold and regression as separate steps

#### Verification

- Ran:
  - `.venv\Scripts\python.exe -m py_compile src/autoresearch/stage_05/benchmark.py src/autoresearch/stage_05/loop.py src/autoresearch/stage_05/trigger.py src/autoresearch/stage_05/status.py`
  - `.venv\Scripts\python.exe -m pytest tests/test_stage05_regression.py tests/test_stage05_loop.py tests/test_stage05_trigger.py tests/test_stage05_status.py -q`

### Stage-05 autoresearch retirement

- Retired the live stage-05 autoresearch bundle to `legacy/stage_05_autoresearch/`.
- Moved the following into that archive:
  - `src/autoresearch/stage_05/`
  - the three stage-05 `_autoresearch` pipeline copies
  - the dedicated `tests/test_stage05_*.py` files
  - the saved watcher outputs and benchmark runs from `qa/trimming/gold_standard/autoresearch/`
  - the trigger marker `qa/trimming/gold_standard/COMPLETE`
- Kept the reviewed gold papers and the shared `qa/trimming/gold_standard/manifest.json` in place because they are still used by the live manual stage-05 review flow.
- Updated the active docs and production tests so the default repo workflow no longer points at the retired autoresearch harness.

### LLM proceedings rollout completion

- Completed the remaining live stage-05 LLM proceedings run for the unresolved conference-abstract pool, including the late-discovered holdout tranche that had not yet entered the earlier candidate registry.
- The LLM stage-05 registries now contain:
  - `89` candidate rows in `data/references/text_trim_llm_candidate_registry.csv`
  - `81` final LLM-reviewed rows in `data/references/text_trim_llm_registry.csv`
  - final status mix: `64` `trimmed_auto_llm_candidate_exact`, `13` `trimmed_auto_llm_line_within_overshoot`, `4` `trimmed_auto_llm_fallback_heuristic`
- Added and exercised the canonical proceedings publication layer:
  - `src/pipelines/05c_publish_proceedings_ready.py`
  - `data/extraction_json/text_proceedings_ready/`
  - `data/references/text_proceedings_ready_registry.csv`
- The canonical proceedings-ready layer now covers the full resolved conference-abstract universe (`235` papers) with no missing JSON files.
- Current proceedings-ready source mix:
  - `82` `gold_manual`
  - `61` `llm_validated`
  - `3` `llm_decision_rebuilt`
  - `71` `source_text_passthrough`
  - `18` `legacy_trimmed`
- Patched two publication edge cases discovered during the rollout:
  - rebuilt starts now prioritise title matches over misleading numeric bullet codes and can match wrapped session-title clusters
  - supplement footer metadata without an explicit year now trims cleanly from rebuilt spans
- Downstream consumers now prefer the canonical proceedings-ready layer where available:
  - `src/pipelines/06_extract_sps_case_counts.py`
  - `src/pipelines/07_split_case_series.py`
  - `src/pipelines/10_langextract.py`
  - `src/pipelines/12_build_paper_artifact_registry.py`

### Verification

- Ran live OpenAI validation for the newly discovered stage-05 holdout papers after explicitly loading `OPENAI_API_KEY` from `env/openai_api_key.env`.
- Manual spot-checks looked correct for the rebuilt/publication edge cases and the final holdout trims, including:
  - `12473`
  - `8296`
  - `6219`
  - `6442`
  - `7804`
  - `8303`
  - passthrough check `1217`
- Ran:
  - `.venv\Scripts\python.exe src/pipelines/05c_publish_proceedings_ready.py`
  - `.venv\Scripts\python.exe -m pytest tests/test_05_trim_proceedings_text.py tests/test_05b_validate_proceedings_text.py tests/test_05_proceedings_text_llm.py tests/test_05c_publish_proceedings_ready.py tests/test_06_extract_sps_case_counts.py tests/test_sps_case_counting.py tests/test_04_source_categorisation_review_batch.py`
  - `.venv\Scripts\python.exe -m py_compile src/pipelines/_proceedings_text.py src/pipelines/_proceedings_trim_llm.py src/pipelines/_proceedings_ready.py src/pipelines/05c_publish_proceedings_ready.py src/pipelines/06_extract_sps_case_counts.py src/pipelines/07_split_case_series.py src/pipelines/10_langextract.py src/pipelines/12_build_paper_artifact_registry.py tests/test_05_trim_proceedings_text.py tests/test_05_proceedings_text_llm.py tests/test_05c_publish_proceedings_ready.py`
- Result:
  - `111` pytest checks passed

### Stage-05 proceedings sanity sweep repairs

- Ran a manual sanity sweep over the published `data/extraction_json/text_proceedings_ready/` outputs to look for the concrete boundary failures seen during rollout: trailing references, disclosure tails, journal/footer inserts, download notices, and next-abstract spillover.
- Confirmed and repaired `13` stage-05 outputs with updated gold JSONs:
  - new or rebuilt gold repairs: `11109`, `1422`, `1909`, `5970`, `6723`, `6732`
  - revised older gold trims: `1028`, `1215`, `1511`, `1793`, `1901`, `1921`, `5029`
- The repaired cases included both contiguous span fixes and a few hand-assembled non-contiguous reconstructions where OCR had interleaved neighbouring abstracts.
- Republished the canonical proceedings-ready layer and refreshed the downstream provenance registry:
  - `data/extraction_json/text_proceedings_ready/`
  - `data/references/text_proceedings_ready_registry.csv`
  - `data/references/paper_artifact_registry.csv`
- Current proceedings-ready publication mix after the repair pass:
  - `88` `gold_manual`
  - `70` `llm_validated`
  - `5` `llm_decision_rebuilt`
  - `72` `source_text_passthrough`
  - `0` `legacy_trimmed`
- Coverage remains complete at `235/235` published proceedings-ready JSONs with `0` missing files.

### Verification

- Re-ran `src/pipelines/05c_publish_proceedings_ready.py` after both repair batches.
- Rechecked the repaired outputs directly in the published proceedings-ready layer.
- Re-ran the focused stage-05 test slice:
  - `.venv\Scripts\python.exe -m pytest tests/test_05_trim_proceedings_text.py tests/test_05b_validate_proceedings_text.py tests/test_05_proceedings_text_llm.py tests/test_05c_publish_proceedings_ready.py -q`
- Result:
  - `90` pytest checks passed

### Stage-06 semantic-conflict policy and 10-paper paid evaluation

- Committed the stage-06 hybrid implementation and reviewer workflow as `3c0af67` (`Implement hybrid stage 06 count adjudication`).
- Tightened the stage-06 controller so semantic validator conflicts now preserve the LLM proposal and force manual review instead of silently replacing the answer with a heuristic fallback.
- Ran focused verification on the new policy:
  - `.venv\Scripts\python.exe -m pytest tests/test_stage06_llm_counting.py tests/test_stage06_count_candidates.py tests/test_06_extract_sps_case_counts.py tests/test_sps_case_counting.py -q`
  - `.venv\Scripts\python.exe -m pytest tests/test_stage06_review_workflow.py tests/test_stage06_review_app_helpers.py -q`
- Result:
  - `45` pytest checks passed

#### Paid batch provenance

- First attempted a paid 10-paper stage-06 batch as `stage06_llm_eval_v9`, but every row returned `llm_request_failed_manual_review_required`.
- Root cause: `OPENAI_API_KEY` was not loaded in the shell (`$env:OPENAI_API_KEY.Length` returned `0`).
- Preserved `v9` as the failed no-key trace, then loaded the existing key from `env/openai_api_key.env` and reran successfully as `stage06_llm_eval_v10`.
- Command used for the successful rerun:
  - `.venv\Scripts\python.exe src/pipelines/06_extract_sps_case_counts.py --verification-mode always --allow-paid-run --allow-unresolved-export --skip-registry-refresh --run-id stage06_llm_eval_v10 --output-path qa/validation/stage06_eval/stage06_llm_eval_v10.csv --paper-id 11 --paper-id 29 --paper-id 227 --paper-id 556 --paper-id 710 --paper-id 990 --paper-id 1426 --paper-id 1937 --paper-id 6060 --paper-id 22`
- QA artefacts:
  - CSV: `qa/validation/stage06_eval/stage06_llm_eval_v10.csv`
  - run artefacts: `results/stage06_count_runs/stage06_llm_eval_v10/`

#### Paper-by-paper assessment

- `11 -> 3` correct. The paper explicitly separates `seven patients with myoclonus` from `three patients with the stiff-person syndrome`.
- `22 -> 1` correct. The cohort contains one `stiff-person syndrome` subject (`case 10`); the earlier `three with stiff-person syndrome` mention is background literature about Brown et al.
- `29 -> 1` correct. This is a classic single-case report of one `36-year-old man` with SPS.
- `1426 -> 16` correct. The abstract states that `16` SPS patients consented and `15` had evaluable data; the unique cohort count is `16`.
- `1937 -> 14` correct under the current SPS-spectrum rule. The abstract reports `13` SPS plus `1` PERM within the anti-GAD cohort, so the SPS-spectrum subset is `14`.
- `227 -> 1` numerically looks correct but remains conservatively unresolved. The paper reports a 92-patient mixed paraneoplastic neurology cohort with only `one` explicit stiff-person syndrome case.
- `556 -> 10` wrong. The paper explicitly defines `Group 1` as `seven` SPS patients, so the extractable SPS count should be `7`; the current candidate package did not offer `7`, and the LLM response contradicted itself.
- `6060 -> 1` correct. The abstract describes three immune-mediated movement-disorder cases, but only `case 1` is PERM; cases 2 and 3 are OMS/OFS.
- `710 -> 6` wrong. The paper’s main six-patient cohort is autoimmune encephalitis, not SPS; the SPS mentions occur in broad control/reference groups and should not be finalised as `6` extractable SPS-spectrum cases.
- `990 -> 1` correct. Table 1 lists one `Stiff person syndrome` patient within the 92-case mixed neuroimmunology series.

#### Current readout

- `7/10` clean final counts looked correct against the paper text: `11`, `22`, `29`, `1426`, `1937`, `6060`, `990`
- `1/10` looks like a correct numeric count held in an over-cautious unresolved state: `227`
- `2/10` were clearly wrong: `556`, `710`

#### Follow-up targets

- `556`: add broader subgroup-candidate generation so explicit cohort counts like `Group 1 consisted of seven patients with SPS` enter the candidate list directly.
- `710`: strengthen the non-extractable/lab-heavy filter so mixed assay-control papers do not promote incidental SPS mentions into final case counts.

## 2026-04-14

### Stage-05 officialisation around the LLM workflow

- Retired the old deterministic stage-05 entrypoints to `legacy/stage_05_deterministic/`:
  - `src/pipelines/05_trim_proceedings_text.py`
  - `src/pipelines/05b_validate_proceedings_text.py`
  - the paired deterministic-only validation helpers and tests
- Kept the `_LLM` filenames as the canonical live stage-05 CLI surface:
  - `src/pipelines/05_trim_proceedings_text_LLM.py`
  - `src/pipelines/05b_validate_proceedings_text_LLM.py`
  - `src/pipelines/05c_publish_proceedings_ready.py`
- Repointed the active stage-05 validation tooling so batch preparation, manual overrides, and overnight orchestration now target the LLM candidate, validation, and publication layers rather than the archived deterministic scripts.
- Updated the live Streamlit review app so it can inspect either the canonical LLM registries or batch-local stage-05 registries.
- Updated the active repo docs so the published stage-05 contract is now:
  - candidate layer: `data/extraction_json/text_trimmed_llm_candidates/` plus `data/references/text_trim_llm_candidate_registry.csv`
  - final LLM layer: `data/extraction_json/text_trimmed_llm/` plus `data/references/text_trim_llm_registry.csv`
  - canonical published layer: `data/extraction_json/text_proceedings_ready/` plus `data/references/text_proceedings_ready_registry.csv`

### Verification

- Ran:
  - `.venv\Scripts\python.exe -m pytest tests/test_05_proceedings_text_llm.py tests/test_05c_publish_proceedings_ready.py tests/test_manage_trimming_batches.py tests/test_apply_trimming_manual_overrides.py -q`
- Result:
  - `24 passed`

## 2026-04-15

### Stage-06 hybrid production cutover

- Added the new canonical hybrid stage-06 runner:
  - `src/pipelines/06_extract_sps_case_counts_hybrid.py`
- Added the shared hybrid controller:
  - `src/pipelines/stage06_counting/hybrid.py`
- The hybrid flow now combines:
  - deterministic candidate generation and hard safety rails from the legacy stage-06 path
  - local Ollama-served `gemma4:e4b` advice on every selected paper
  - GPT-5.4 adjudication with a contradiction-focused challenge pass when deterministic or conservative evidence conflicts
  - a tracked reviewed override ledger at `data/references/source_sps_case_count_manual_review.csv`
- Added the shared override support layer:
  - `src/pipelines/stage06_counting/overrides.py`
- Updated the stage-06 review workflow so saved reviewer responses now also sync into the canonical override ledger:
  - `src/validation/_stage06_review.py`
  - `src/validation/review_stage06_count_app.py`
- Added the hybrid benchmark utility and regression-pack support:
  - `src/validation/benchmark_stage06_hybrid.py`
  - `qa/validation/stage06_llm/stage06_historical_regression_papers.json`
- Preserved the earlier stage-06 scripts as non-canonical comparators:
  - `src/pipelines/06_extract_sps_case_counts.py`
  - `src/pipelines/06_extract_sps_case_counts_LLM.py`

### Verification

- Ran:
  - `.venv\Scripts\python.exe -m pytest tests/test_stage06_overrides.py tests/test_stage06_review_workflow.py tests/test_stage06_hybrid_counting.py tests/test_06_extract_sps_case_counts_hybrid.py tests/test_stage06_hybrid_benchmark.py -q`
  - `.venv\Scripts\python.exe -m py_compile src/pipelines/stage06_counting/hybrid.py src/pipelines/06_extract_sps_case_counts_hybrid.py src/validation/benchmark_stage06_hybrid.py`
  - `.venv\Scripts\python.exe src/pipelines/06_extract_sps_case_counts_hybrid.py --estimate-only --limit 3`

### Stage-06 local Gemma calibration runner

- Added a new QA-only alternative stage-06 runner:
  - `src/pipelines/06_extract_sps_case_counts_LLM.py`
- The new runner keeps the existing deterministic stage-06 candidate packaging and safety rails, then adds:
  - a local Ollama first pass using `gemma4:e4b`
  - a GPT-5.4 adjudication pass on every selected row during calibration
- The local model now receives a derived evidence pack rather than the raw OCR JSON so the prompt stays compact and inspectable.
- The GPT adjudicator can now optionally receive advisory notes without changing the existing canonical stage-06 flow:
  - `src/pipelines/stage06_counting/prepare.py`
  - `src/pipelines/stage06_counting/classify.py`
  - `src/pipelines/stage06_counting/controller.py`

### Local-model support modules

- Added the local stage-06 support layer under `src/pipelines/stage06_counting/`:
  - `local_models.py`
  - `local_prepare.py`
  - `local_ollama.py`
  - `local_validate.py`
- The local layer:
  - formats a compact evidence pack for Gemma
  - calls Ollama with `think=false`
  - tolerantly extracts JSON from plain or fenced responses
  - validates the local count against key deterministic guardrails
- Local parse failures and guardrail conflicts are recorded as artefacts rather than silently discarded.

### QA outputs and docs

- Added the stage-06 calibration output guide:
  - `qa/validation/stage06_llm/README.md`
- Updated `src/pipelines/README.md` with a dedicated section for `06_extract_sps_case_counts_LLM.py`.
- The new runner writes:
  - per-run artefacts under `results/stage06_count_llm_runs/{run_id}/`
  - non-canonical comparison CSVs under `qa/validation/stage06_llm/`

### Verification

- Ran:
  - `.venv\Scripts\python.exe -m pytest tests/test_stage06_local_counting.py tests/test_stage06_llm_counting.py tests/test_stage06_count_candidates.py tests/test_06_extract_sps_case_counts_LLM.py -q`
- Result:
  - `38 passed`

## 2026-04-25

### Stage-07 XML/JSON LangExtract preparation

- Added the new Stage-07 XML pipeline under `src/pipelines/stage07_XML/` without modifying the existing `src/pipelines/07_split_case_series.py`.
- The new pipeline prepares deterministic source blocks, asks GPT-style annotators for span metadata only, validates offsets against unchanged source text, and inserts XML-style `<seg>` tags in Python.
- Outputs now include:
  - per-paper JSON under `data/extraction_json/stage07_xml/papers/`
  - annotated source text under `data/extraction_json/stage07_xml/annotated_text/`
  - segment metadata under `data/extraction_json/stage07_xml/segments/`
  - per-patient/group LangExtract-ready target views under `data/extraction_json/stage07_xml/target_views/`
  - validation reports and manifests under the Stage-07 XML output root
- Added `data/references/stage07_xml_registry.csv` indexing support and extended the paper artefact registry so Stage-07 XML readiness, paths, and validation status are discoverable.
- Added hybrid routing safeguards:
  - single-patient sources use deterministic pass-through
  - live GPT-5.5 span annotation is only used for split/group routes when `--allow-paid-run` is supplied
  - mock annotation payloads remain supported for tests and dry validation
- Documented the Stage-07 XML/JSON contract in `doc/plans/stage07_XML_JSON_plan.md`.

### Stage-07 XML human verification pack

- Added a static human-verification workflow:
  - `src/validation/_stage07_xml_review.py`
  - `src/validation/build_stage07_xml_gold_pack.py`
- The workflow writes non-canonical QA material under `qa/validation/stage07_xml/gold_standard/<round_id>/`.
- Review packs include:
  - `index.html`
  - one colour-coded HTML page per paper
  - `review_queue.csv`
  - editable `review_responses.csv`
  - cumulative `07_xml_assignment_gold_standard.csv`
- The visual review design gives every patient/group a target chip and colour, uses neutral shared styling for multi-target segments, and keeps labels visible so high-count papers remain reviewable.
- The gold-standard ledger records reviewed segment assignments but does not rewrite canonical Stage-07 XML outputs.

### Commits

- `4fb0fb1` `Milestone 1: add Stage 07 XML span pipeline`
- `c061f2f` `Milestone 2: index Stage 07 XML artefacts`
- `90265b9` `Milestone 3: document Stage 07 XML contract`
- `ab44f00` `Milestone 4: enforce hybrid Stage 07 XML routing`
- `82948db` `Milestone 5: add Stage 07 XML verification pack`

### Verification

- Ran:
  - `py -3.14 -m pytest tests/test_stage07_xml.py tests/test_12_build_paper_artifact_registry.py tests/test_07_split_case_series.py -q`
  - `py -3.14 src\pipelines\stage07_XML\run_stage07_xml.py --help`
  - `py -3.14 -m pytest tests\test_stage07_xml_review.py tests\test_stage07_xml.py tests\test_stage07_review_workflow.py tests\test_12_build_paper_artifact_registry.py -q`
  - `py -3.14 -m ruff check src\validation\_stage07_xml_review.py src\validation\build_stage07_xml_gold_pack.py tests\test_stage07_xml_review.py`
- Results:
  - Stage-07 XML core and artefact-registry tests passed.
  - Stage-07 XML review-pack tests passed.
  - Ruff passed on the new review-pack code.
- No paid model/API calls were run during this implementation.

## 2026-04-28

### Stage-07 XML optimisation, benchmarking, and reviewer loop

- Evaluated the Stage-07 XML optimisation plan and implemented the first precision-first optimisation pass around measurement, telemetry, and low-risk safety fixes rather than a large source-representation rewrite.
- Added the contained benchmark package under `src/pipelines/stage07_benchmarking/`, keeping all non-canonical evaluation outputs under `qa/validation/stage07_xml/evaluation/{run_id}`.
- Added automatic scoring against reviewed Stage-07 gold annotations:
  - per-paper micro precision, recall, and F1
  - per-target source-character precision, recall, and F1
  - target inventory exactness
  - missing and extra targets
  - role attribution mismatches
  - contamination flags
  - XML roundtrip and JSON validation status
  - readiness calibration, including false-ready and false-not-ready counts
- Added API telemetry support for live Stage-07 calls:
  - provider, model, endpoint, matrix configuration, and architecture variant
  - reasoning effort and output token cap
  - strict schema mode and prompt/schema hashes
  - request timestamps, latency, response status, and truncation reason
  - input, output, reasoning, and cache token accounting where available
  - estimated cost using a local versioned pricing table
  - validation status and manual-review reasons after parsing
  - trace paths without secrets or API keys
- Added the default optimisation matrix definitions for:
  - current deterministic/baseline heuristic candidates
  - OpenAI `gpt-5.5` medium/high/high-64k style configurations
  - DeepSeek benchmark-only placeholders
  - future source-unit architecture variants
- Added import-triggered DOCX rescoring so reviewed DOCX feedback can be imported into reviewed annotations, regenerated gold XML/JSON, and automatically rescored against candidate Stage-07 outputs.
- Added the operator guide at `doc/stage07_xml_benchmark_operator_guide.md`, covering:
  - running saved and live matrix candidates
  - generating DOCX review packs
  - editing and importing DOCX feedback
  - metric, telemetry, and artefact locations
  - promotion-gate interpretation
- Added promotion gates:
  - default policy in `src/pipelines/stage07_benchmarking/promotion_gates.json`
  - `gate_results.csv` in every benchmark run
  - hard failure on any contamination, false-ready output, validation failure, role error, or insufficient precision/recall
  - warning status for review-burden signals such as false-not-ready papers
- Investigated the 10-paper reviewed gold set:
  - reviewed IDs: `10`, `11`, `17`, `19`, `22`, `23`, `25`, `29`, `30`, `34`
  - initial saved-output benchmark had perfect character overlap but failed promotion because contamination guardrails flagged papers `10`, `29`, `30`, and `34`
- Audited the flagged excerpts manually:
  - real risks: paper `10` mixed patient-specific details in a shared segment; paper `30` abstract `Methods/Results` text assigned as shared patient evidence
  - false-positive guardrails: ordinary case text containing `method of ...`, `(see Methods)`, external numbering such as `Patient 2 in their report`, and comparison text such as `similar to that of patient 1`
- Refined the benchmark contamination rules so false-positive method mentions and external/comparison patient labels no longer block promotion, while real section headings and mixed current-paper patient labels remain flagged.
- Added `contamination_audit.csv` to every benchmark run. It records one row per contamination flag with:
  - matrix configuration
  - paper ID
  - flag type
  - target IDs
  - logical and physical segment IDs
  - role
  - source offsets
  - exact flagged excerpt
- Hardened Stage-07 target-view construction:
  - abstract or section-heading `Methods.`/`References`-style text is demoted to `unknown` + `uncertain`
  - shared segments that explicitly mix multiple current-paper patient labels are demoted to `uncertain`
  - audit-only segments remain visible in XML/segment payloads but are excluded from LangExtract target views
  - demotions add manual-review reasons and prevent false readiness
- Reran the 10 reviewed gold papers through the patched Stage-07 path:
  - contamination dropped to zero
  - promotion gates passed for the recompiled reviewed-gold candidate
  - papers `10` and `30` are now correctly held for manual review rather than treated as ready target views
- Identified an unevaluated DOCX review batch:
  - original round: `qa/validation/stage07_xml/docx_review/stage07_xml_live_batch2_20260427`
  - papers: `39`, `43`, `49`, `58`, `62`, `65`, `71`, `80`, `89`, `92`
  - status: DOCX files existed, but there were no imported `reviewed_annotations` or regenerated gold outputs
- Regenerated that 10-paper DOCX review pack with the current code as:
  - `qa/validation/stage07_xml/docx_review/stage07_xml_live_batch2_regenerated_20260428`

### Commits

- `bcad5e0` `Add Stage 07 benchmark telemetry foundations`
- `514eb61` `Add DOCX review benchmark rescoring`
- `bf093f5` `Document Stage 07 benchmark operator workflow`
- `fb1df56` `Add Stage 07 benchmark promotion gates`
- `889c795` `Refine Stage 07 contamination guardrails`
- `e6a6704` `Add Stage 07 contamination audit and safety routing`
- `0e6f74b` `Regenerate Stage 07 DOCX batch 2 review pack`

### Verification

- Ran the focused Stage-07 test slice repeatedly while adding benchmark and safety features:
  - `python -m pytest tests\test_run_stage07_smoke.py tests\test_stage07_review_workflow.py tests\test_stage07_xml.py tests\test_stage07_xml_docx_review.py tests\test_stage07_xml_gold_regression.py tests\test_stage07_xml_review.py tests\test_stage07_xml_openai_client.py tests\test_stage07_benchmarking.py`
- Final focused result before the OpenAI matrix run:
  - `53 passed`
- Ran no-paid benchmark smokes for:
  - saved current Stage-07 outputs against the 10 reviewed gold papers
  - recompiled reviewed-gold annotations through the patched Stage-07 path
  - the regenerated DOCX review pack
- No DeepSeek calls were run. The DeepSeek key was not read.

### Three-paper paid OpenAI matrix smoke

- Ran a staged paid OpenAI matrix on reviewed gold papers `10`, `30`, and `34`.
- Rationale for paper choice:
  - `10`: mixed shared patient-specific discussion and two-patient split
  - `30`: abstract Methods/Results block plus three-patient split
  - `34`: OCR-interrupted patient text and source-labelled patient names
- All candidate Stage-07 outputs and benchmark summaries were kept under `qa/validation/stage07_xml/evaluation/`.
- Raw OpenAI request/response traces were written under `results/stage07_xml_runs/`; API keys were not written to traces.

#### `O0_gpt55_low_25k`

- Run directory:
  - `qa/validation/stage07_xml/evaluation/openai_matrix_3paper_20260428_O0_gpt55_low_25k`
- Completed all three papers.
- Gate result:
  - `fail`
- Metrics:
  - micro precision `0.514076`
  - micro recall `0.772156`
  - micro F1 `0.617225`
  - contaminated papers `0`
  - false-ready papers `2` (`10`, `30`)
- Telemetry:
  - estimated cost `$0.49571`
  - latency `138810` ms
  - input tokens `39430`
  - output tokens `9952`
  - reasoning tokens `2221`
- Interpretation:
  - Low effort was fast and cheap, but far too permissive. It marked unsafe or overbroad outputs ready for `10` and `30` and failed the precision/recall gates.

#### `O1_gpt55_medium_25k`

- Run directory:
  - `qa/validation/stage07_xml/evaluation/openai_matrix_3paper_20260428_O1_gpt55_medium_25k`
- Completed all three papers.
- Gate result:
  - `fail`
- Metrics:
  - micro precision `0.602121`
  - micro recall `0.701646`
  - micro F1 `0.648085`
  - contaminated papers `0`
  - false-ready papers `1` (`30`)
  - false-not-ready papers `1` (`34`)
  - JSON validation failures `1` (`34`)
- Telemetry:
  - estimated cost `$1.36457`
  - latency `560090` ms
  - input tokens `39430`
  - output tokens `38914`
  - reasoning tokens `31592`
- Interpretation:
  - Medium effort was much slower and more expensive than low effort. It improved paper `10`, but still over-selected paper `30` and produced offset validation failures for paper `34`.

#### `O2_gpt55_high_40k_partial`

- Intended run:
  - `O2_gpt55_high_40k` on the same three papers
- Outcome:
  - completed raw responses for papers `10` and `30`
  - timed out while waiting for paper `34`
  - no final Stage-07 telemetry CSV was written because the runner did not reach its final write step
- Preserved partial benchmark directory:
  - `qa/validation/stage07_xml/evaluation/openai_matrix_3paper_20260428_O2_gpt55_high_40k_partial`
- Partial gate result:
  - `fail`
- Partial metrics for papers `10` and `30` only:
  - micro precision `0.708597`
  - micro recall `0.859041`
  - micro F1 `0.776600`
  - contaminated papers `0`
  - false-ready papers `0`
- Raw completed-call token/cost estimates from response metadata:
  - paper `10`: input `12888`, output `17216`, reasoning `13984`, estimated cost about `$0.580920`
  - paper `30`: input `16965`, output `18007`, reasoning `15970`, estimated cost about `$0.625035`
- Interpretation:
  - High effort improved overlap on the two completed papers but remained far below promotion thresholds and was operationally too slow for paper `34`. The planned larger 64k/high-or-xhigh run was not launched because this staged run already showed that higher effort alone is not the bottleneck.

#### Matrix readout

- None of the live OpenAI block-offset configurations met promotion gates.
- No completed candidate produced contamination flags after the new safety demotions, which suggests the safety gate is doing useful post-processing.
- Main remaining failure modes:
  - over-selection of broad text, especially paper `30`
  - offset validation fragility, especially paper `34`
  - readiness calibration failures, especially low effort false-ready outputs
- Practical conclusion:
  - Tuning effort/token settings alone is unlikely to reach human-review quality.
  - The next architecture experiment should be the planned source-unit `unit_id` selection path, where the model selects deterministic paragraph/sentence/table-row units and Python compiles offsets.
