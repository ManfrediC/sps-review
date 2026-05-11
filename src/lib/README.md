# src / lib

Reusable Python helper modules shared across pipeline scripts.

Current modules:

- `text_cleanup.py`: deterministic phase-1 text-cleanup helpers used by
  `src/pipelines/03b_clean_text.py`.
- `text_cleanup_stage2.py`: reviewed residual-cleanup helpers used by
  `src/pipelines/03b_clean_text.py --stage2`.

These helpers must preserve source evidence. They should repair extraction
artefacts, not paraphrase, infer, or rewrite clinical content.
