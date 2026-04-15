# Stage-04 Gold Standard

This folder stores the manual-review gold-standard rounds for stage 04 source categorisation and stage 06 extractable SPS case counts.

Canonical cumulative reviewed file:
- `04_categorisation_gold_standard.csv`

Compatibility alias kept for older scripts:
- `stage04_gold_standard_master.csv`

Stage-06 gold JSON corpus:
- `stage06_count_gold/manifest.json`
- `stage06_count_gold/papers/{paper_id}.json`

The stage-06 JSON corpus complements the cumulative CSV by freezing one reviewed per-paper stage-06-style result payload for each active gold row. Each JSON embeds:
- the reviewed gold count row
- review provenance from the cumulative CSV
- the live count/source registry snapshots used during promotion
- any attached historical stage-06 run artefacts that were available at bootstrap time

Per-round files:
- `2026-04-05_round_01/gold_standard_stage04_2026-04-05_round_01.csv`
- `2026-04-05_round_02/gold_standard_stage04_2026-04-05_round_02.csv`
- `2026-04-05_round_03/gold_standard_stage04_2026-04-05_round_03.csv`

Each round directory also contains:
- `selection_manifest.json`
- `selection_queue.csv`
- `responses.csv`

Use the cumulative CSV for benchmarking and review analysis, and use `stage06_count_gold/` when you need a stable per-paper JSON corpus for stage-06 calibration or regression work.
