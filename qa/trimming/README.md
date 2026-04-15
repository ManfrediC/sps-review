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
  - accepted per-paper gold JSONs, the synced manifest, and tranche bootstrap reports for the live manual workflow
- `regression/`
  - frozen accepted cases used as a regression corpus
- `reports/`
  - per-batch stage-05 subset outputs, review files, and evaluation reports

## Workflow
1. Prepare one batch of 50 unreviewed proceedings candidates in ascending `paper_id` order.
2. Run `05_trim_proceedings_text_LLM.py`, `05b_validate_proceedings_text_LLM.py`, and `05c_publish_proceedings_ready.py` incrementally on that batch only, persisting outputs after each paper so the run can resume after interruption.
3. Store the batch manifest, batch-local candidate/final/ready artefacts, and the machine-readable report under this folder.
4. Review the batch in `src/validation/review_stage05_llm_app.py`, pointing it at the batch-local registries when needed.
5. Prefer general stage-05 code patches where a shared failure mode is visible.
6. Use `manual_overrides.csv` only for residual fallback cases that still fail after the general patch.
7. Re-run the current batch plus all regression cases after each accepted patch or override.
8. Do not open a new batch until the current batch is resolved.

## Current helper
- `src/validation/manage_trimming_batches.py`
  - prepares the next unresolved 50-paper batch or resumes an interrupted preparation run
  - excludes papers already present in `feedback/` or `regression/`
  - writes subset stage-05 LLM outputs plus a batch report under `reports/<batch_id>/`
- `src/validation/review_stage05_llm_app.py`
  - reviews stage-05 LLM outputs against the source PDF
  - can inspect either the canonical registries or batch-local registries from `reports/<batch_id>/`
- `src/validation/update_trimming_review_outputs.py`
  - refreshes the review queue, feedback export, override file, and acceptance reports after a general code patch rerun
- `src/validation/apply_trimming_manual_overrides.py`
  - applies fallback per-paper overrides from `manual_overrides.csv` and republishes the affected batch-local proceedings-ready outputs

## Retired Archive

The former stage-05 autoresearch harness, the isolated `_autoresearch` scripts, the watcher marker, and the saved benchmark runs have been retired to `legacy/stage_05_autoresearch/`.

The live proceedings-trimming workflow in `qa/trimming/` no longer depends on that archived bundle.
