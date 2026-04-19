# 20260419T122648Z_stage07_smoke Stage-07 Review Notes

- Selection JSON: `qa\validation\stage07_smoke\20260419T122648Z_stage07_smoke\selection.json`
- Stage-07 registry: `qa\validation\stage07_smoke\20260419T122648Z_stage07_smoke\case_series_split_registry.csv`
- Combined QA CSV: `qa\validation\stage07_smoke\20260419T122648Z_stage07_smoke\20260419T122648Z_stage07_smoke_combined.csv`
- Inspection pack: `qa\validation\stage07_smoke\20260419T122648Z_stage07_smoke\20260419T122648Z_stage07_smoke_inspection.md`
- Per-paper comments: `qa\validation\stage07_smoke\20260419T122648Z_stage07_smoke\20260419T122648Z_stage07_smoke_review_comments.csv`

## Review prompts

- Check whether each published unit is attribution-safe.
- Check whether shared-context blocks are linked to the correct units only.
- Check whether any unresolved remainder contains information that should block automatic publication.
- Record must-fix issues in `review_comments.csv` before any canonical rerun.

## Initial review summary

- Smoke subset: `10` reviewed stage-06 papers with finalised counts and `likely_sps_case_count >= 2`.
- Current heuristics-only outcome: `4/10` papers yielded published units, for `9` total published units.
- Cleanest auto-publish win: `559`, where the three patient units matched the reviewed stage-06 count and looked acceptable on spot check.
- Plausible but still partial: `140`, `239`, and `748`, where the core patient split looks right but broad shared-context linkage or unresolved residue still makes the manual-review flag appropriate.
- Remaining manual-review holds break down into two main buckets:
  - no stable deterministic headings in the current pass: `456`, `668`, `679`, `715`, `766`
  - mixed or structurally unclear case layout: `776`

## Main findings

- The new article-window trimming and inline case-marker handling materially improved recall on this subset.
- Shared-context linking is still too broad in some successful splits, especially when later discussion sentences mention all patients.
- Some papers still need better continuation handling across page interruptions or inline prose so that follow-up material stays attached to the right case.
- A heuristics-only stage `07` is now useful as a high-precision first pass, but the remaining six papers in this batch reinforce the earlier conclusion that GPT adjudication will still be necessary for the harder narrative layouts.
