# stage_05 autoresearch

This is a frozen stage-05 autoresearch harness modelled on `karpathy/autoresearch`.

## Scope

You are optimising proceedings trimming for stage 05 only.

The production stage-05 scripts are intentionally untouched. Work only on the isolated `_autoresearch` copies:

- `src/pipelines/_proceedings_text_autoresearch.py`
- `src/pipelines/05_trim_proceedings_text_autoresearch.py`

The validator copy is frozen for this loop and is diagnostic only:

- `src/pipelines/05b_validate_proceedings_text_autoresearch.py`

## Frozen files

Do not modify anything under:

- `src/autoresearch/stage_05/`

In particular, do not modify:

- `src/autoresearch/stage_05/benchmark.py`
- scoring rules
- per-paper failure labels
- normalisation
- gold manifest logic

Reason: otherwise you would optimise the metric instead of the extraction.

## Setup

1. Sync the gold manifest:
   - `python src/autoresearch/stage_05/gold.py --sync`
2. Use a dedicated run tag and branch when practical:
   - recommended branch: `autoresearch/<run_tag>`
3. Establish a baseline with no code edits:
   - `python src/autoresearch/stage_05/benchmark.py --mode gold --output-dir <run_dir>/gold_baseline`
   - `python src/autoresearch/stage_05/benchmark.py --mode regression --output-dir <run_dir>/regression_baseline`
4. Record results in `<run_dir>/results.tsv`.

The outer loop also writes:
- `<iteration_dir>/decision.json`
- `<iteration_dir>/candidate.patch`
- `<iteration_dir>/agent_stdout.log`
- `<iteration_dir>/agent_stderr.log`
- benchmark command stdout/stderr logs under the gold and regression output directories

## Goal

Maximise `exact_match_rate` on the gold benchmark without increasing regression failures.

Stop the loop once:
- the gold benchmark marks every gold paper as `exact_match`
- regression failed count is `0`

The benchmark requires:

- correct abstract text
- no truncation
- no spill-over into neighbouring abstracts

## Keep / discard rule

Keep a change only if:

1. `exact_match_rate` improves, or
2. `exact_match_rate` ties and `regression_failed_count` decreases

If still tied, prefer the simpler change.
A pure simplification win is acceptable when the keep metrics tie and the editable diff removes more lines than it adds.

## Per-paper labels

The benchmark emits fixed labels:

- `missing_output`
- `spillover`
- `truncated`
- `exact_match`
- `wrong_abstract`

Use them to choose the next extraction change. Do not change the labels themselves.

## Experiment loop

Loop:

1. Inspect the last benchmark outputs.
2. Make one bounded extraction change in the allowed files only.
3. Keep the diff small enough to explain in one sentence.
4. Run:
   - `python src/autoresearch/stage_05/benchmark.py --mode gold --output-dir <run_dir>/gold_current`
   - `python src/autoresearch/stage_05/benchmark.py --mode regression --output-dir <run_dir>/regression_current`
5. Append results to `<run_dir>/results.tsv`.
6. Keep or discard the change using the rule above.

The outer loop owns commits, keep/discard, timeout handling, and standard log paths.

## Constraints

- Do not touch production stage-05 files.
- Do not touch gold JSONs.
- Do not touch regression fixtures.
- Do not add dependencies.
- Do not refresh canonical registries.
