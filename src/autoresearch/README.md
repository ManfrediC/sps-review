# `src` / `autoresearch`

## Purpose
Frozen optimisation harnesses for bounded code-improvement loops.

These harnesses are separate from the canonical production pipeline in `src/pipelines/`:
- production scripts continue to own canonical outputs under `data/` and `results/`
- autoresearch harnesses define fixed gold sets, frozen benchmarks, and agent instructions
- benchmark-local outputs should be written to non-canonical QA folders only

## Available harnesses

### `stage_05/`

Autoresearch harness for proceedings trimming.

It contains:
- `gold.py`
  - scans `qa/trimming/gold_standard/papers/*.json`
  - rewrites `qa/trimming/gold_standard/manifest.json`
- `benchmark.py`
  - frozen benchmark for stage-05 extraction changes
  - owns the scoring rules, labels, and strict text normalisation
- `program.md`
  - the agent instructions for the stage-05 optimisation loop
- `README.md`
  - stage-05-specific usage notes

The stage-05 harness benchmarks only the isolated `_autoresearch` pipeline copies in `src/pipelines/`.
