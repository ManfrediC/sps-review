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

Key progress on this date:
- Implemented `src/pipelines/00_download_covidence_pdfs.py` using Playwright against the Covidence extraction view.
- Validated the live workflow end-to-end on Covidence:
  - successful single-reference test for `#13799`
  - successful batch download of 5 additional references (`5020`, `816`, `800`, `5029`, `12807`)
- Standardized saved filenames as `<Covidence_ID>_<original_filename>.pdf` in `data/pdf_original/`.
- Added Covidence operator documentation in:
  - `doc/COVIDENCE_DOWNLOAD_AGENT.md`
  - `src/pipelines/README.md`
  - top-level `README.md`
- Built `src/pipelines/00_build_pdf_source_registry.py` and generated `data/references/pdf_source_registry.csv` to link Covidence references to local PDF files and download status.
- Built `src/pipelines/00_build_paper_artifact_registry.py` and generated `data/references/paper_artifact_registry.csv` as the larger source-of-truth table linking:
  - reference metadata
  - local PDF files
  - text extraction JSON
  - LangExtract raw/summary outputs
  - quality raw/record outputs
- Wired automatic registry refresh so the following scripts now rebuild the artifact registry after successful runs:
  - `src/pipelines/00_download_covidence_pdfs.py`
  - `src/pipelines/01_extract_text.py`
  - `src/pipelines/02_LangExtract.py`
  - `src/pipelines/03_quality_assessment.py`

Observed issues / notes:
- Covidence study cards do not hydrate immediately after page load; explicit wait logic was needed before scanning for `View full text`.
- At this point, the artifact registry is populated mainly for reference, PDF, and text stages; LangExtract and quality columns will fill as those pipelines are run on the newly downloaded PDFs.
