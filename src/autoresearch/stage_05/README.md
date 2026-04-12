# Stage-05 Autoresearch

## Purpose
This directory contains the frozen autoresearch harness for proceedings trimming.

The harness is intentionally separate from the canonical stage-05 pipeline so extraction experiments can run against a fixed benchmark without changing production outputs.

## Files
- `gold.py`
  - scans direct gold JSONs in `qa/trimming/gold_standard/papers/`
  - rewrites `qa/trimming/gold_standard/manifest.json`
  - records provenance fields such as `source_text_path`, `reviewer`, and `notes` when present
- `benchmark.py`
  - frozen benchmark for the stage-05 autoresearch loop
  - defines the fixed labels `missing_output`, `spillover`, `truncated`, `exact_match`, and `wrong_abstract`
  - owns the strict normalisation and scoring rules
- `program.md`
  - instructions for the autoresearch agent
- `loop.py`
  - outer-loop runner that calls `codex exec` for one bounded edit at a time
  - keeps only changes that improve the frozen keep metrics
  - stops once all gold papers are exact matches and regression failures are zero

## Freeze Rules
Do not let the autoresearch loop modify:
- `benchmark.py`
- the scoring rules
- the strict normalisation

This is deliberate. The loop should optimise extraction behaviour, not the metric.

## Editable Pipeline Surface
The stage-05 loop should edit only:
- `src/pipelines/_proceedings_text_autoresearch.py`
- `src/pipelines/05_trim_proceedings_text_autoresearch.py`

`src/pipelines/05b_validate_proceedings_text_autoresearch.py` stays frozen in v1 and is used only for diagnostics and failure labelling.

## Commands
Sync the gold manifest:

```bash
python src/autoresearch/stage_05/gold.py --sync
```

Run the frozen gold benchmark:

```bash
python src/autoresearch/stage_05/benchmark.py --mode gold --output-dir qa/trimming/gold_standard/autoresearch/manual_run
```

Run the frozen regression benchmark:

```bash
python src/autoresearch/stage_05/benchmark.py --mode regression --output-dir qa/trimming/gold_standard/autoresearch/manual_run/regression_guard
```

Wait for gold completion and launch the frozen baseline automatically:

```bash
python src/autoresearch/stage_05/trigger.py --ready-file qa/trimming/gold_standard/COMPLETE
```

Or launch automatically once the active manifest reaches a target size:

```bash
python src/autoresearch/stage_05/trigger.py --target-paper-count 100
```

The trigger:
- re-syncs `qa/trimming/gold_standard/manifest.json` while waiting
- requires the ready condition to hold for two consecutive polls by default
- writes timestamped outputs under `qa/trimming/gold_standard/autoresearch/trigger_runs/`
- starts the stage-05 loop by default once the gold set is ready

Run the loop directly without waiting:

```bash
python src/autoresearch/stage_05/loop.py
```

The loop uses `codex exec` for bounded edit iterations, then stops as soon as:
- every gold paper is labelled `exact_match`
- regression failed count is `0`

Use `--launch-mode baseline` on the trigger if you want the old baseline-only behaviour.

Do not run the live gold benchmark until the gold-standard JSON corpus is complete.
