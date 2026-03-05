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
- `01a_source_categorisation.py` -> `04_source_categorisation.py`
- `00_trim_proceedings_text.py` -> `05_trim_proceedings_text.py`
- `00_validate_proceedings_text.py` -> `06_validate_proceedings_text.py`
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
- extraction -> source categorisation -> proceedings trim -> proceedings QC -> case-series split -> LangExtract stages.

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
- `src/pipelines/06_validate_proceedings_text.py`
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
- `src/pipelines/04_source_categorisation.py`
- `src/pipelines/05_trim_proceedings_text.py`
- `src/pipelines/06_validate_proceedings_text.py`
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
