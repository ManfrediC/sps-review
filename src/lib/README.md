# src / lib

## Purpose
Reusable Python library helpers shared across pipeline scripts.

## Current modules

- `text_cleanup.py`
  - Deterministic, phase-1 text-cleanup helpers used by `src/pipelines/03b_clean_text.py`.
  - Keeps cleanup intentionally conservative: mojibake repair, ligature repair, whitespace normalization, light header/footer cleanup, and related artifact counting.
  - Does not use LLM rewriting and should not invent or paraphrase source content.

## Directory Contents Snapshot
- Last updated: `2026-03-31`
- Immediate subdirectories (0): _None_
- Immediate files (1, excluding `README.md`): `text_cleanup.py`
