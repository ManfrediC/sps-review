# AGENTS.md

## Scope
This repo uses AI for:
- Python coding/refactoring
- debugging
- literature extraction/summarisation
- systematic review tooling
- reproducibility/documentation work

Optimise for:
1. correctness
2. reproducibility
3. non-hallucination
4. publication-quality output

## Working style
- Be concise and structured.
- Explain what you are doing.
- Make reasonable low-risk assumptions and proceed.
- Ask immediately if ambiguity materially affects correctness.
- Give options with pros/cons when there is no single clear path.
- Prefer small, reviewable patches over rewrites.
- Never make irreversible changes without approval.

## Modes
### Tutor
- Explain approach before code.
- Teach concepts explicitly.
- Avoid doing too much at once.

### Builder
- Read relevant files first.
- Preserve existing architecture unless change is justified.
- Propose a plan before multi-file edits.
- Prefer patch-style edits.

### Debugger
- State likely root cause first.
- Propose the 2-3 most informative checks.
- Isolate with the smallest possible test.
- Do not rewrite broadly before localising the bug.

### Reviewer
- Separate must-fix issues from optional improvements.
- Focus on correctness, reproducibility, and clarity.

### Repo steward
- Inspect README, config, tests, and entry points first.
- Keep docs and workflow descriptions in sync with behaviour.

## Editing rules
- Read relevant files before suggesting changes.
- Do not touch unrelated files without reason.
- Do not do giant rewrites without warning.
- If a rewrite is needed, explain why a patch is insufficient.
- Do not silently change interfaces, file locations, or side effects.

## Coding conventions
- Prioritise readability.
- Prefer small functions and clear names.
- Use clear comments only where they add value.
- Use relative paths, not machine-specific absolute paths.
- Avoid unnecessary dependencies.
- Keep I/O separate from core logic where practical.
- Use type hints when practical.

## Debugging protocol
1. Define the failure clearly.
2. Give likely hypotheses.
3. Propose the most informative checks.
4. Isolate with a tiny reproducible test.
5. Patch only after localising the issue.
6. Explain why the patch should work.
7. Show how to verify the fix.

## Testing and validation
- Run tests where possible, otherwise propose exact tests.
- Prefer test-driven development for new behaviour where practical.
- Verify behaviour directly after changes.
- Compare representative inputs and outputs for data workflows.
- Never claim code was run if it was not.
- Never invent values in tables, manuscripts, or summaries.

## Literature and scientific guardrails
- Do not fabricate references or study details.
- Separate evidence from interpretation.
- Quote or point to supporting evidence when extracting fields.
- Flag uncertain extractions explicitly.
- Be cautious with statistical claims.
- Never infer clinical facts not present in the source.
- Preserve patient confidentiality.

## Git and reproducibility
- Prefer small atomic commits.
- Suggest useful commit messages.
- Never commit secrets or large raw data.
- Keep raw and derived files separate.
- Preserve provenance of derived outputs.
- Update docs when workflows change.

## Runtime
- Use the existing Windows-native setup. Do not switch to WSL.
- Use `.venv` unless documented otherwise.
- Do not install host-level dependencies during unattended runs.

## Canonical outputs
- Canonical research artefacts stay under `data/` and `data/references/`.
- `results/overnight/` is for logs, calibration reports, and stage traces only.
- Do not move or duplicate canonical registries into `results/overnight/`.

## Pipeline order
1. `01_download_covidence_pdfs.py` when Covidence acquisition is needed; this also refreshes `02_build_pdf_source_registry.py` and `12_build_paper_artifact_registry.py` unless skipped
2. `02_build_pdf_source_registry.py` after new or manually changed PDFs when the PDF-to-reference registry needs rebuilding
3. `03_extract_text.py`
4. `90_screen_text_extraction.py` as an optional screening pass after extraction when triaging text-quality issues or likely proceedings PDFs
5. `04_source_categorisation.py` on extracted text; rerun after proceedings trimming if you want routing to consume preferred trimmed text
6. `05_trim_proceedings_text.py` for proceedings / `conference_abstract` candidates
7. `06_validate_proceedings_text.py` after trimming; required before auto-splitting conference-abstract case series
8. `07_split_case_series.py` for reviewed case-series candidates before LangExtract
9. `09_build_langextract_examples.py` when curated examples change
10. `10_langextract.py`
11. `11_quality_assessment.py`
12. `12_build_paper_artifact_registry.py` as the cross-pipeline provenance refresh; most pipeline stages call it automatically, but run it directly after manual artifact changes
13. `99_overnight_run.py` is the orchestration wrapper for staged batch runs, not a separate canonical data-processing stage

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

## Response template
For substantial tasks, use:
- What I’m doing
- Assumptions
- Proposed change
- How to validate
- Next checks

## Hard prohibitions
- No hallucinated citations or references.
- No invented values.
- No pretending commands/tests ran when they did not.
- No giant rewrites without warning.
- No irreversible actions without approval.
- No secrets in commits or tracked files.
