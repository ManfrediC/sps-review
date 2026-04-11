# qa / trimming

## Purpose
Non-canonical review material for the proceedings-trimming improvement loop.

This folder is the working area for resumable stage-05 trimming review rounds. It is separate from canonical outputs under `data/` and from the older ad hoc validation packs under `qa/validation/`.

## Structure
- `batches/`
  - one JSON manifest per active or completed trimming batch
- `feedback/`
  - structured human-reviewed source-of-truth files
- `gold_standard/`
  - accepted per-paper gold JSONs, the synced manifest, and autoresearch benchmark runs
- `regression/`
  - frozen accepted cases used as a regression corpus
- `reports/`
  - per-batch stage-05 subset outputs, review files, and evaluation reports

## Workflow
1. Prepare one batch of 50 unreviewed proceedings candidates in ascending `paper_id` order.
2. Run stage 05 and 05b incrementally on that batch only, persisting outputs after each paper so the run can resume after interruption.
3. Store the batch manifest, review queue, responses, feedback, override file, and reports under this folder.
4. Review the batch in the Streamlit app and save responses immediately.
5. Prefer general `05/05b` code patches where a shared failure mode is visible; refresh the batch feedback and acceptance reports after each rerun.
6. Use `manual_overrides.csv` only for residual fallback cases that still fail after the general patch.
7. Re-run the current batch plus all regression cases after each accepted patch or override.
8. Do not open a new batch until the current batch is resolved.

## Current helper
- `src/validation/manage_trimming_batches.py`
  - prepares the next unresolved 50-paper batch or resumes an interrupted preparation run
  - excludes papers already present in `feedback/` or `regression/`
  - writes subset stage-05 outputs plus review artefacts under `reports/<batch_id>/`
- `src/validation/review_stage05_app.py`
  - reviews stage-05 outputs against the source PDF
  - saves responses immediately and refreshes `feedback.json`, `acceptance_report.json`, and `patch_review_summary.json`
- `src/validation/update_trimming_review_outputs.py`
  - refreshes the review queue, feedback export, override file, and acceptance reports after a general code patch rerun
- `src/validation/apply_trimming_manual_overrides.py`
  - applies fallback per-paper overrides from `manual_overrides.csv` and re-runs stage 05b on the affected papers
- `src/autoresearch/stage_05/gold.py`
  - scans direct stage-05 gold JSONs in `gold_standard/papers/`
  - writes `gold_standard/manifest.json`
- `src/autoresearch/stage_05/benchmark.py`
  - runs the frozen gold and regression benchmarks against the isolated `_autoresearch` stage-05 scripts
  - keeps labels, scoring rules, and strict normalisation outside the editable loop

## Frozen benchmark rules
- The autoresearch loop must not modify `src/autoresearch/stage_05/benchmark.py`.
- The autoresearch loop must not modify the benchmark scoring rules or strict normalisation.
- Per-paper labels are fixed:
  - `missing_output`
  - `spillover`
  - `truncated`
  - `exact_match`
  - `wrong_abstract`
