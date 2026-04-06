# missed proceedings audit 2026-04-06

## Purpose
Non-canonical audit pack for sources that stage 04 did not currently label `conference_abstract`, but which may still be short proceedings fragments, supplement abstracts, or conference-style single-abstract pages.

## Contents

- `report.json`
  - exploratory whole-corpus audit output from the first broad pass
- `review_queue.csv`
  - exploratory whole-corpus review queue from the same pass
- `snippets/`
  - exploratory whole-corpus snippet exports
- `focused_batch_mixed/`
  - the current calibration pack for a smaller mixed batch after tightening the heuristic

## Current trusted subset

Use `focused_batch_mixed/` as the current review pack while the audit logic is still being calibrated.

It contains:
- `report.json`
- `review_queue.csv`
- `snippets/`

Focused mixed batch summary:
- input papers tested: `15`
- candidates retained: `8`
- retained examples:
  - `5753`
  - `6271`
  - `1017`
  - `1597`
  - `1784`
  - `1935`
  - `8198`
  - `8317`
- examples dropped from the same mixed batch after heuristic tightening:
  - `101`
  - `432`
  - `647`
  - `828`
  - `952`

## Notes

- The focused batch overwrites its snippet directory on rerun so stale TXT files do not survive from earlier calibration passes.
- The whole-corpus outputs in this folder are exploratory only and should not yet be treated as a final review queue.
