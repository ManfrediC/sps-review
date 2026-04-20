# Stage-07 Review Sheet Instructions

- Folder: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke`
- Read in this order:
  1. `high_risk_review_rollup.md`
  2. `high_risk_review_rollup_verbatim_snippets.md`
  3. edit `review_paper_decisions.csv`
  4. edit `review_unit_decisions.csv` only for papers with published units
- The CSVs are pre-populated with my current judgement. If you agree, leave the row as-is. If you disagree, overwrite the decision fields and add a short note.
- Keep feedback short and structured. The goal is to make disagreements sortable by failure mode.

## Paper-Level Decision Codes

- `publish_ok`: clean enough for downstream use as published
- `publish_after_cleanup`: core split looks right, but a cleanup pass is needed before downstream use
- `partial_keep`: useful partial output, but not clean enough for full publication
- `manual_hold_ok`: correct to withhold for now
- `stage06_recheck`: stage-06 prior may need manual recheck before stage-07 can be judged cleanly
- `upstream_text_fix`: stage-07 is blocked by bad or incomplete source text selection

## Unit-Level Decision Codes

- `keep`: unit is good enough as-is
- `cleanup`: unit is probably right but needs trimming or cleanup
- `hold_partial`: unit is useful evidence, but should stay in a partial-only paper output
- `withhold`: unit should not have been published

## Failure-Mode Labels

- `TEXT_DIRTY`: author, journal, website, figure, or page furniture leaked into the unit
- `SHARED_BROAD`: shared-context linkage is too broad, too fragmentary, or too discussion-like
- `UNRESOLVED_BLOCKING`: unresolved remainder still contains material that blocks clean downstream use
- `CONTINUATION_MISSING`: later case-specific follow-up was left out of the unit
- `ANCHOR_WEAK`: patient or group anchor is too weak for attribution-safe publication
- `OVERLAP_BOUNDARY`: neighbouring cases overlap or boundaries are unstable
- `MIXED_STRUCTURE`: paper mixes individual and group-style reporting in a way the current splitter does not handle safely
- `UPSTREAM_WINDOW`: the wrong text window reached stage `07`
- `STAGE06_MISMATCH`: stage-06 prior and visible source text do not align cleanly
- `GPT_OVERREACH`: GPT proposed units that looked plausible numerically but were not attribution-safe

## Suggested Workflow

- First fill `review_paper_decisions.csv` for all papers.
- Then review `review_unit_decisions.csv` only for the nine published units.
- If a paper-level decision is `manual_hold_ok`, `stage06_recheck`, or `upstream_text_fix`, you usually do not need to touch the unit sheet for that paper.
