# Stage 06 optimisation plan

## What I'm doing

Designing a concrete optimisation plan for `src/pipelines/06_extract_sps_case_counts.py` that keeps deterministic heuristics, adds LLM verification, and aims for near-100% exact extractable SPS case counts while staying reproducible, auditable, and conservative when the evidence is weak.

## Assumptions

- Stage 06 continues to consume `source_category` and `source_subtype` from `data/references/source_categorisation_registry.csv`; it does not reclassify the paper from scratch.
- Preferred text order remains:
  - `data/extraction_json/text_proceedings_ready/{paper_id}.json`
  - `data/extraction_json/text_trimmed/{paper_id}.json`
  - `data/extraction_json/text/{paper_id}.json`
- Paid LLM calls stay opt-in and should follow the same safety pattern already used by stage 04: `--estimate-only`, explicit approval via `--allow-paid-run`, checkpointed runs, resumability, and publish-only finalisation.
- The reviewed gold file `qa/validation/source_categorisation/gold_standard/04_categorisation_gold_standard.csv` is the calibration target. It currently contains 80 reviewed rows with explicit reviewed case counts.
- If the count cannot be supported safely, stage 06 should prefer `count_manual_review_required=true` over a speculative numeric guess. The path to near-100% accuracy is allowed to include deliberate abstention.
- The preferred production pattern is the successful stage-05 workflow: heuristics build a small ordered set of plausible solutions first, then the LLM acts as an adjudicator and manual-check gate over those candidates.
- That stage-05 pattern should be melded with the earlier hybrid ideas already in this plan, not replace them: evidence-bearing heuristics, deterministic validators, strict verification modes, provenance capture, and selective audit checks should all remain.

## Proposed change

### 1. Stabilise the current stage-06 code path before changing behaviour

- Fix the import brittleness in `src/pipelines/_proceedings_ready.py`. The current sibling-import pattern breaks stage-06 tests when the module is loaded directly.
- Stop duplicating registry-building logic between `src/pipelines/06_extract_sps_case_counts.py` and `src/pipelines/_sps_case_count_registry.py`. The script should become a thin runner over shared helpers.
- Cache proceedings-ready registry rows once per run instead of reopening the registry inside paper-level processing.
- Keep the current registry columns working while the hybrid path is introduced, so downstream joins and review tools do not break.

### 2. Upgrade heuristics from a single guess into an evidence-bearing candidate generator

- Extend `_sps_case_counting.py` so it no longer returns only one final integer. The heuristic layer should emit a small ordered `CountCandidatePackage`, modelled on the stage-05 candidate-package flow.
- Each package should expose:
  - one or more plausible final `CountCandidate` options
  - the current preferred heuristic candidate
  - a conservative `manual_review_required` candidate whenever the ambiguity cannot be compressed safely
  - `candidate_id`, `proposed_count`, `candidate_kind`, and heuristic rank
  - the evidence snippet or span behind each candidate
  - the basis, score, and blockers for each candidate
  - explicit conflict signals showing why candidate A beats or loses to candidate B
  - a deterministic fallback order if the LLM response is missing or invalid
- Candidate kinds should be explicit and auditable, for example:
  - `exact_numeric_count`
  - `diagnosis_specific_subset_count`
  - `single_case_default`
  - `forced_zero`
  - `manual_review_required`
- Replace the current single `early_body_text` view with targeted evidence windows:
  - metadata abstract
  - title-localised opening window
  - candidate `Methods`, `Results`, `Patients`, `Case`, and table windows
  - proceedings-ready text when present
- Preserve raw snippets and page indices where possible instead of only returning heavily normalised text. The LLM verifier and human reviewer both need quotable evidence.
- Use a strict-to-permissive candidate-generation order, as in stage 05, so the package naturally captures both the best conservative answer and the nearest plausible alternatives.
- Keep the strongest current rules, but make them explicit and testable:
  - single-case defaults
  - diagnosis-specific subgroup counting
  - conference-abstract safeguards
  - lab-heavy zeroing unless the SPS subgroup is explicit
  - review/basic-science forced zero
  - observational mixed-cohort zeroing when the visible numbers are assays, controls, or non-SPS subsets
- Add more explicit blockers for common false positives:
  - ages and years
  - scale ranges and titre values
  - percentages and fractions
  - control-group counts
  - literature totals
  - serum/sample/specimen counts
  - administrative datasets
  - overlapping subgroup totals
- Write candidate packages to run artefacts rather than directly into the canonical registry so the heuristic search space can be inspected independently of the final published count.

### 3. Add a stage-05-style LLM adjudicator as the primary LLM path

- Create a dedicated `src/pipelines/stage06_counting/` package for the verification path:
  - `models.py`
  - `prepare.py`
  - `classify.py`
  - `validate.py`
  - `controller.py`
  - `run_state.py`
- The production LLM path should read a candidate package, not start from a blank page.
- The prompt should treat `source_category` and `source_subtype` as fixed inputs and answer a narrower adjudication question:
  - "Which candidate count is best supported by the evidence, or should this row go to manual review?"
- The LLM input should include:
  - the fixed source routing fields
  - the preferred text source/path
  - the ordered candidate list
  - the evidence quotes and local windows for each candidate
  - the heuristic conflict summary and blockers
  - a bounded overshoot context around the strongest competing numeric mentions
- Use a structured output closer to the stage-05 decision model than the stage-04 free-form classifier, for example:
  - `decision_type`
  - `selected_candidate_id`
  - `alternative_count`
  - `count_confidence`
  - `count_manual_review_required`
  - `count_reasoning_summary`
  - `evidence[]`
  - `validator_flags[]`
- Recommended decision types:
  - `candidate_exact`
  - `bounded_alternative`
  - `manual_review_required`
  - `unable_to_determine`
- `bounded_alternative` should be allowed only when the paper contains explicit count evidence that the heuristic candidate package failed to encode. This keeps the stage-05-style candidate selection workflow primary while preserving a safe escape hatch.
- This does not remove the earlier verification ideas from the plan. It reframes them:
  - the candidate adjudicator is the main production LLM step
  - deterministic validators still police the adjudicator output
  - a blind independent verifier can remain as a secondary audit/calibration layer for selected rows, not the default first-pass path

### 4. Retain selective independent verification as an audit layer

- Keep an optional second-pass blind audit for rows where we want extra assurance beyond candidate adjudication.
- This audit layer should reuse the earlier ideas already in the plan:
  - independent evidence review
  - disagreement detection
  - strict release gating
  - manual-review escalation when the signals diverge
- The audit path should be triggered only for high-risk or release-gate subsets, for example:
  - rows where the adjudicator chose `bounded_alternative`
  - rows where validators downgraded confidence
  - rows with high-impact candidate conflicts
  - rows selected by `strict` mode
- If the audit result agrees with the adjudicator, publish normally.
- If the audit result disagrees materially, do not silently choose one side; send the row to `count_manual_review_required=true`.

### 5. Reconcile heuristic, adjudicator, and audit outputs deterministically

- Decision order:
  1. Apply category-level hard gates first.
  2. Build the heuristic candidate package.
  3. Decide whether the package can be auto-accepted or should be routed to the LLM adjudicator under the selected policy.
  4. If routed, let the LLM choose a candidate, propose a bounded alternative, or force manual review.
  5. Validate the LLM response deterministically.
  6. If the LLM answer is missing or invalid, fall back to the heuristic candidate order.
  7. If the fallback path is still unsafe, set `count_manual_review_required=true`.
  8. For selected high-risk or strict-mode rows, run the optional blind audit layer.
  9. If adjudicator and audit disagree materially, set `count_manual_review_required=true`.
  10. Publish the final count row plus the supporting candidate/decision artefacts.
- Category-level hard gates should remain deterministic:
  - `review_article` and `non_clinical_basic_science` normally stay at `0`
  - explicit single-case categories default to `1` unless contradicted by stronger evidence
  - count-ineligible or text-mismatch cases should not be "rescued" by a weak LLM answer
- Add count-specific validators modelled on stage 04 and stage 05:
  - selected candidate must exist unless `bounded_alternative` is used
  - `bounded_alternative` must be backed by explicit evidence and not violate hard gates
  - low-confidence or conflicting candidate packages should escalate to review rather than silently forcing a count
  - no positive count without original data support
  - single-case categories should resolve to `1`
  - review/non-clinical categories should not carry positive counts
  - high confidence requires enough evidence
  - conference cases with pending trim/QC should be downgraded to review

### 6. Use a strict verification policy for publication-quality runs

- The default development mode can stay cheaper, but the release gate should be strict.
- Proposed verification modes:
  - `heuristic_only`
  - `targeted`
  - `strict`
- `strict` should verify at least:
  - all rows where the candidate package contains more than one materially different numeric solution
  - all rows where the top-ranked candidate is `manual_review_required`
  - all rows where the adjudicator chose `bounded_alternative`
  - every positive count above `1`
  - every `0` count inside count-eligible categories
  - all `conference_abstract` rows
  - all `lab_heavy_clinical_or_translational` rows
  - all `observational_group_study` rows
  - all counts driven by `patient_label_count`, body-only evidence, or diagnosis-specific subgroup extraction
  - all rows where candidate counts disagree or negative signals are present
- In `strict` mode, the selective blind audit layer should be enabled automatically for the highest-risk subset rather than only the adjudicator path.
- If the benchmark shows that even explicit single-case papers still contribute residual misses, promote `strict` further to "verify every count-eligible row".

### 7. Preserve the CSV contract but append provenance

- Keep the existing stage-06 fields consumed by downstream code:
  - `likely_sps_case_count`
  - `count_confidence`
  - `count_basis`
  - `count_manual_review_required`
  - `count_reason`
  - `count_version`
- Append flat provenance fields so the registry stays comparable and auditable:
  - `heuristic_likely_sps_case_count`
  - `heuristic_count_confidence`
  - `heuristic_count_basis`
  - `count_candidate_json_path`
  - `heuristic_candidate_count`
  - `llm_likely_sps_case_count`
  - `llm_count_confidence`
  - `llm_selected_candidate_id`
  - `heuristic_fallback_used`
  - `count_audit_status`
  - `count_verification_status`
  - `count_validator_flags`
  - `count_evidence_json_path`
- Store verbose raw evidence and structured per-paper decisions in `results/stage06_count_runs/<run_id>/` rather than overloading the canonical CSV.
- Suggested versioning:
  - `heuristic_v2` for the improved deterministic layer
  - `hybrid_v1_gpt5.4` for the verified final output

### 8. Make stage 06 reproducible in the same style as stage 04

- Add checkpointed run state under `results/stage06_count_runs/`.
- Preserve a stage-05-like internal separation between:
  - candidate generation
  - LLM adjudication
  - optional audit verification
  - publish/finalise
- This can still remain one public script, but the run state should keep these phases separate so we can resume at the candidate-package boundary instead of recomputing everything.
- Support:
  - `--estimate-only`
  - `--allow-paid-run`
  - `--run-id`
  - `--resume`
  - `--publish`
  - `--publish-only`
  - `--verification-mode {heuristic_only,targeted,strict}`
- Estimate-only mode should report:
  - papers selected
  - candidate packages built
  - papers that would require LLM verification
  - papers that would require secondary audit verification
  - projected API calls
  - projected verification-mode mix
- Publishing should only happen after a complete run, never from a partial checkpoint.

### 9. Implement in phases so each patch stays reviewable

1. Phase 1: harden imports and deduplicate the runner
   Files:
   - `src/pipelines/_proceedings_ready.py`
   - `src/pipelines/_sps_case_count_registry.py`
   - `src/pipelines/06_extract_sps_case_counts.py`
   - `tests/test_sps_case_counting.py`
   - `tests/test_06_extract_sps_case_counts.py`
   Deliverable:
   - stage 06 imports cleanly
   - the current heuristic benchmark can run again
   - the script becomes a thin wrapper over shared logic

2. Phase 2: heuristic candidate engine
   Files:
   - `src/pipelines/_sps_case_counting.py`
   - `src/pipelines/stage06_counting/models.py`
   - `tests/test_sps_case_counting.py`
   - `tests/test_stage06_count_candidates.py`
   Deliverable:
   - heuristic output now includes ordered candidate packages, candidate evidence, blockers, and verification routing

3. Phase 3: stage-05-style LLM adjudication package
   Files:
   - `src/pipelines/stage06_counting/prepare.py`
   - `src/pipelines/stage06_counting/classify.py`
   - `src/pipelines/stage06_counting/validate.py`
   - `src/pipelines/stage06_counting/controller.py`
   - `tests/test_stage06_llm_counting.py`
   Deliverable:
   - mocked structured-output candidate adjudication flow with deterministic validators and heuristic fallback

4. Phase 4: selective audit layer
   Files:
   - `src/pipelines/stage06_counting/audit.py`
   - `src/pipelines/stage06_counting/controller.py`
   - `tests/test_stage06_count_audit.py`
   Deliverable:
   - optional blind audit path for strict/high-risk rows
   - disagreement-to-manual-review behaviour

5. Phase 5: run-state and CLI integration
   Files:
   - `src/pipelines/stage06_counting/run_state.py`
   - `src/pipelines/06_extract_sps_case_counts.py`
   - `src/pipelines/README.md`
   - `tests/test_06_extract_sps_case_counts.py`
   Deliverable:
   - estimate/resume/publish workflow
   - candidate-generation, adjudication, and audit checkpoints
   - `heuristic_only`, `targeted`, and `strict` modes

6. Phase 6: benchmark and calibration
   Files:
   - `src/validation/benchmark_stage06_gold.py` or an expanded `src/validation/benchmark_stage04_gold.py`
   - `qa/validation/source_categorisation/gold_standard/04_categorisation_gold_standard.csv` as the benchmark input
   - `doc/plans/stage_06_optimisation_plan.md`
   Deliverable:
   - exact-count benchmark report
   - residual mismatch list
   - final decision on the strict release gate

## How to validate

### Before hybrid work

- Fix the current import break and rerun:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_sps_case_counting.py tests/test_06_extract_sps_case_counts.py -q
```

### After heuristic phase

- Rerun the same unit tests plus any new candidate-engine tests:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_sps_case_counting.py tests/test_stage06_count_candidates.py tests/test_06_extract_sps_case_counts.py -q
```

### After LLM-adjudicator phase

- Run mocked verifier tests:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_stage06_llm_counting.py -q
```

### After audit-layer phase

- Run the audit-path tests:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_stage06_count_audit.py -q
```

- Run estimate-only mode without paid calls:

```bash
.\.venv\Scripts\python.exe src/pipelines/06_extract_sps_case_counts.py --estimate-only --verification-mode strict --skip-registry-refresh
```

### Calibration gate

- Benchmark against the reviewed gold file:

```bash
.\.venv\Scripts\python.exe src/validation/benchmark_stage06_gold.py
```

- Release only when one of these is true:
  - exact count accuracy reaches 100% on the reviewed gold set after excluding `likely_wrong_pdf_attached` and `incorrect_reference`
  - or every remaining mismatch is routed to `count_manual_review_required=true` and no silent wrong auto-accepts remain

## Next checks

- Decide whether stage 06 should remain a hybrid comparator stage or become a candidate replacement for the current canonical count output.
- Decide whether `strict` should verify all count-eligible papers by default, or only the current high-risk subset.
- Decide whether the final registry should include only flat provenance fields or also a compact JSON-encoded evidence column.
- Phase 1 is the right first coding batch because the current import failure blocks the benchmark and hides the real accuracy baseline.
