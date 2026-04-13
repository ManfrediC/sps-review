# Repo Stale Files And Legacy Retirement Plan

## Goal

Remove ambiguity in the repo by separating live pipeline code from archived experiments, obsolete copies, and stale benchmark artefacts.

## High-Confidence Stale Or Superseded Areas

### 1. Stage-05 `_autoresearch` Bundle

These files have already been superseded by the live LLM stage-05 flow and appear to be in the middle of retirement:

- `src/autoresearch/stage_05/`
- `src/pipelines/05_trim_proceedings_text_autoresearch.py`
- `src/pipelines/05b_validate_proceedings_text_autoresearch.py`
- `src/pipelines/_proceedings_text_autoresearch.py`
- `tests/test_stage05_*.py`
- `qa/trimming/gold_standard/autoresearch/`

Recommended action:

- move the live-code copies fully into `legacy/stage_05_autoresearch/`
- keep only the still-used gold manifest and manually reviewed gold JSONs in active locations
- remove active-doc references once the archive move is committed

### 2. Deterministic Stage-05 Outputs

These are now superseded as a downstream interface:

- `data/extraction_json/text_trimmed/`
- `data/references/text_trim_registry.csv`
- `data/references/proceedings_text_qc_registry.csv`

Recommended action:

- keep them during transition as provenance
- mark them as legacy in docs
- retire them from live fallback logic once all papers are gold or LLM-finalised

### 3. Parallel Stage-05 Script Variants

The repo currently exposes multiple stage-05 routes:

- deterministic `05`
- LLM `05_LLM`
- publication `05c`
- archived `_autoresearch`

Recommended action:

- leave one official route in `src/pipelines/`
- move all retired alternatives under `legacy/`
- make the naming reflect live status clearly

### 4. Non-Canonical Temporary QA Outputs

Potentially stale local review artefacts include:

- `qa/validation/tmp_stage05_compare/`

Recommended action:

- confirm whether any files there are still needed for audit
- otherwise delete or archive them under a dated `qa/validation/archive/` folder

## Proposed Removal / Retirement Phases

### Phase 1: Commit The Existing Stage-05 Autoresearch Retirement Work

- review the current uncommitted deletions and doc edits
- commit the archive move as a standalone batch
- ensure active docs point to `legacy/` rather than deleted paths

### Phase 2: Reduce Live Stage-05 Surface Area

- officialise the LLM stage-05 route
- retire deterministic and `_autoresearch` duplicates from `src/pipelines/`

### Phase 3: Archive Obsolete QA Artefacts

- move benchmark snapshots, trigger runs, and stale temporary compare folders out of active QA locations if they must be preserved
- otherwise remove them

### Phase 4: Sweep Docs And Tests

- remove references to retired scripts from:
  - `src/README.md`
  - `src/pipelines/README.md`
  - `src/validation/README.md`
  - any stale tests that still assume live `_autoresearch` paths

## Review Checklist Before Deletion

- Is the file still referenced by active docs?
- Is it still imported by live code?
- Is it still part of the published pipeline order?
- Is it needed for provenance or reproducibility?
- If yes, archive it under `legacy/` rather than deleting it outright.

## Immediate Candidate Batches

### Batch A: Safe To Archive Soon

- stage-05 `_autoresearch` code and tests
- `qa/trimming/gold_standard/autoresearch/` run artefacts
- `qa/validation/tmp_stage05_compare/` if no longer needed

### Batch B: Retire After Stage-05 Officialisation

- deterministic stage-05 scripts
- deterministic stage-05 registries as live interfaces
- legacy fallback branches in proceedings publication logic
