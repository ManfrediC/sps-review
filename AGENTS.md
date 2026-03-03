# AGENTS.md

## Runtime
- Use the existing Windows-native repository setup. Do not switch to WSL for this project.
- Use the repository Python environment at `.venv` unless a script explicitly documents a different interpreter.
- Do not install host-level dependencies with `winget`, `choco`, `scoop`, `apt`, or similar tools during unattended runs.

## Canonical Outputs
- Canonical research artefacts stay under `data/` and `data/references/`.
- `results/overnight/` is for orchestration logs, calibration reports, and stage execution traces only.
- Do not move or duplicate the canonical registries into `results/overnight/`.

## Pipeline Order
1. `00_download_covidence_pdfs.py` when acquisition is needed.
2. `01_extract_text.py` for text extraction and OCR fallback.
3. `01a_source_categorisation.py` on extracted or trimmed text, not raw PDFs.
4. `01b_split_case_series.py` before LangExtract whenever a source contains multiple cases that should be split.
5. `02_LangExtract.py` on the eligible subset.
6. `03_quality_assessment.py` after LangExtract.
7. `04_model_comparison.py` only after LangExtract outputs exist and both API keys are available.

## Stopping Conditions
- If a step needs a host-level install or admin access, write a clear blocked status to the overnight log and stop.
- If a calibration gate fails, do not continue to the next full-corpus stage.
- If the pipeline detects a source/reference linkage problem, stop and preserve the evidence for manual review.

## Metadata And Registries
- Treat `data/references/sps_references_export.csv` and `data/references/sps_references_export.ris` as upstream source metadata.
- Write derived linkage data only into the generated registries under `data/references/`.
- Preserve both export metadata and live Covidence card metadata when a workflow compares them.

## Secrets
- Keep secrets in environment variables or local files under `env/*.env`.
- The preferred variables are `OPENAI_API_KEY` and `GEMINI_API_KEY`.
- Do not write secrets into tracked files, logs, prompts, or example artefacts.

## Overnight Logging
- Append status updates to `results/overnight/LOG.md`.
- Keep one machine-readable stage report at `results/overnight/stage_status.tsv`.
- When a stage fails, capture the command, exit code, and log file path.
