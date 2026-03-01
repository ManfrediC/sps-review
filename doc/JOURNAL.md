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
