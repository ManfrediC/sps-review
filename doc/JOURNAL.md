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
