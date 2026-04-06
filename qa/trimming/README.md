# qa / trimming

## Purpose
Non-canonical review material for the proceedings-trimming improvement loop.

This folder is the working area for small-batch trimming calibration. It is separate from canonical outputs under `data/` and from the older ad hoc validation packs under `qa/validation/`.

## Structure
- `batches/`
  - one JSON manifest per active or completed trimming batch
- `feedback/`
  - structured human-reviewed source-of-truth files
- `regression/`
  - frozen accepted cases used as a regression corpus
- `reports/`
  - per-batch stage-05 subset outputs and evaluation reports

## Workflow
1. Prepare one batch of 10 unreviewed proceedings candidates.
2. Run stage 05 and 05b on that batch only.
3. Store the batch manifest and report under this folder.
4. Wait for structured human feedback.
5. Freeze accepted feedback into `regression/`.
6. Re-run the current batch plus all regression cases after each patch.
7. Do not open a new batch until the current batch is resolved.

## Current helper
- `src/validation/manage_trimming_batches.py`
  - prepares the next unresolved batch
  - refuses to open a new batch if an earlier batch is still awaiting feedback
  - excludes papers already present in `feedback/` or `regression/`
  - writes subset stage-05 outputs under `reports/<batch_id>/`
