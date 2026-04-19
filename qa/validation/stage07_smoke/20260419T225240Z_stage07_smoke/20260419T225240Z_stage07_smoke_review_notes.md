# 20260419T225240Z_stage07_smoke Stage-07 Review Notes

- Selection JSON: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\selection.json`
- Stage-07 registry: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\case_series_split_registry.csv`
- Combined QA CSV: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\20260419T225240Z_stage07_smoke_combined.csv`
- Inspection pack: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\20260419T225240Z_stage07_smoke_inspection.md`
- Per-paper comments: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\20260419T225240Z_stage07_smoke_review_comments.csv`

## Review prompts

- Check whether each published unit is attribution-safe.
- Check whether shared-context blocks are linked to the correct units only.
- Check whether any unresolved remainder contains information that should block automatic publication.
- Record must-fix issues in `review_comments.csv` before any canonical rerun.

## Initial review summary

- Smoke subset: `10` reviewed stage-06 papers with finalised counts and `likely_sps_case_count >= 2`.
- GPT-assisted outcome after validator tightening: `4/10` papers yielded published units, for `9` total published units.
- Cleanest auto-publish candidate remains `559`, where the three patient units still match the reviewed stage-06 count and no unresolved remainder remains.
- Plausible but still partial: `140`, `239`, and `748`, where the patient splits look usable but shared-context linkage and residual text are still too broad for canonical auto-publication.
- The most important safeguard win is `668`: the first GPT-assisted attempt tried to turn tiny patient mentions into published units, and the stronger patient-anchor validator now blocks that unsafe split.

## Main findings

- GPT adjudication is useful as a recovery and audit layer, but it is not reliable enough to publish on raw span-count agreement alone.
- Strong deterministic validation is essential. Without it, papers like `668` can satisfy the stage-06 count numerically while still producing attribution-unsafe micro-units.
- Most current publishable wins in this subset still come from the deterministic splitter rather than from novel GPT-only recoveries.
- Shared-context selection remains too broad on several otherwise good splits, especially `140`, `239`, and `748`.
- `715` still appears to suffer from an upstream article-window or preferred-text problem: the available stage-07 input is wrapper-heavy and the model correctly abstains.
- `456`, `679`, `766`, and `776` remain appropriate manual-review holds under the current contract.

## Next troubleshooting priorities

- Tighten shared-context selection so discussion-wide or assay-wide statements are not attached automatically to every patient unit.
- Improve continuation capture so late follow-up material stays attached to the correct patient instead of leaking into unresolved remainder.
- Investigate the upstream text/windowing issue affecting `715`.
- Keep the patient-anchor validator in place for GPT outputs; it prevented a clear false-positive publication on `668`.
