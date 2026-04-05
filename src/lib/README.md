# src / lib

## Purpose
Reusable Python library helpers shared across pipeline scripts.

## Current modules

- `text_cleanup.py`
  - Deterministic, phase-1 text-cleanup helpers used by `src/pipelines/03b_clean_text.py`.
  - Keeps cleanup intentionally conservative: mojibake repair, ligature repair, whitespace normalization, light header/footer cleanup, and related artifact counting.
  - Does not use LLM rewriting and should not invent or paraphrase source content.
- `text_cleanup_stage2.py`
  - Shared stage-2 rescue helpers used by `src/pipelines/03b_clean_text.py --stage2`.
  - Handles reviewed source replacement, page-localized `pdftotext` or OCR rescue, and explicit per-paper substitution rules.
  - Exists so the canonical `03b` stage can keep the residual-cleanup logic separate from the deterministic phase-1 helpers.

## Directory Contents Snapshot
- Last updated: `2026-04-05`
- Immediate subdirectories (0): _None_
- Immediate files (2, excluding `README.md`): `text_cleanup.py`, `text_cleanup_stage2.py`
