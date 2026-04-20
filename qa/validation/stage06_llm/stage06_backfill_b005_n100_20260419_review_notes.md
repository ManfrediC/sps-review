# Stage 06 b005 Review Notes

- Combined QA CSV: `qa\validation\stage06_llm\stage06_backfill_b005_n100_20260419_combined.csv`
- Inspection pack: `qa\validation\stage06_llm\stage06_backfill_b005_n100_20260419_inspection.md`
- Per-paper comments: `qa\validation\stage06_llm\stage06_backfill_b005_n100_20260419_review_comments.csv`

## Outcome

- Reviewed papers: 100
- `heuristic_only`: 1
- `llm_bounded_alternative`: 9
- `llm_candidate_exact`: 84
- `llm_manual_review_required`: 4
- `llm_semantic_conflict_manual_review_required`: 2

## Model-Based Triage

- Likely clean on first pass: 3134, 3135, 3136, 3279, 3386, 3438, 3699, 4430, 4877, 5029, 5048, 5079, 5087, 5094, 5142, 5153, 5158, 5191, 5212, 5230, 5240, 5243, 5254, 5265, 5268, 5270, 5280, 5286, 5315, 5321, 5371, 5373, 5381, 5398, 5472, 5499, 5502, 5529, 5535, 5537, 5542, 5545, 5552, 5554, 5573, 5600, 5631, 5647, 5726, 5727, 5748, 5753, 5803, 5808, 5831, 5839, 5861, 5884, 5963, 5970, 5985, 5992, 6010, 6012, 6021, 6072, 6073, 6089, 6101, 6106, 6128, 6141, 6152, 6185, 6198, 6204, 6219, 6257, 6268, 6271, 6278, 6310, 6321, 6336
- Must review: 3139, 5519, 5755, 5850
- Should review: 5180, 5233, 6054

## Resolved Manual Overrides

- None applied for this batch.

## Must Review Candidates

- `3139`: Pipeline output: 18. Extracted counts seen: 18 (diagnosis_specific_fraction_suffix_count), 108 (abstract_count_signal), 22 (early_body_count_signal). Review trigger: verification_status=llm_manual_review_required. GPT decision: manual_review_required; low. The likelier count is still unclear because the candidate package surfaced competing counts: 18, 108, 22. Model rationale: The paper clearly reports an SPSD manifestation count of 71 within 212 patients with GAD65 neurological autoimmunity, but 71 is not offered as a candidate. The listed 18-count candidate refers only to the myelopathy-with-SPSD subgroup and would undercount SPS-spectrum cases, while the other candidates are non-SPSD totals or irrelevant. Because the explicit overall SPSD count is present but absent from the candidate list, this requires manual review rather than selecting an incorrect candidate.
- `5519`: Pipeline output: 4. Extracted counts seen: 4 (diagnosis_specific_mixed_diagnosis_subgroup_count), 0 (no_reliable_count_signal). Review trigger: verification_status=llm_manual_review_required. GPT decision: manual_review_required; low. Model rationale: The evidence pack contains an explicit SPS subgroup count of 4 in one experimental comparison, but other snippets indicate a larger SPS cohort (e.g., 'Eleven SPS patients' and multiple analyses in 5, 7, and 8 SPS patients). Because it is unclear whether 4 is the total unique SPS cohort or only a subset used for one procedure, the extractable paper-level SPS count cannot be resolved safely without human review.
- `5755`: Pipeline output: 38. Extracted counts seen: 38 (title_count_signal). Review trigger: verification_status=llm_manual_review_required. GPT decision: manual_review_required; low. Model rationale: The paper reports a cohort of 38 patients with autoimmune encephalitis, not an explicitly SPS-spectrum cohort. Although the abstract mentions 3 glycine-antibody patients and 6 GAD-antibody patients, the provided text does not state how many of these had SPS/PERM/stiff-limb syndrome rather than encephalitis or other neurologic phenotypes, so no extractable SPS-spectrum count can be resolved safely.
- `5850`: Pipeline output: 0. Extracted counts seen: 0 (no_reliable_count_signal). Review trigger: verification_status=llm_manual_review_required. GPT decision: manual_review_required; low. Model rationale: The paper reports 621 patients with clinically suspected SPS in reviewed records and identifies 11 amphiphysin-antibody patients, but the evidence pack also flags these as suspected/cohort-screening counts rather than a clearly confirmed extractable SPS-spectrum cohort. Because provenance is uncertain and one patient was previously reported elsewhere, the safest decision is manual review rather than counting 11 or accepting a forced zero.

## Should Review Candidates

- `5180`: Pipeline output: 13. Extracted counts seen: 13 (abstract_count_signal), 39 (early_body_count_signal). Review trigger: verification_status=llm_semantic_conflict_manual_review_required. GPT decision: manual_review_required; low. The likelier count is still unclear because the candidate package surfaced competing counts: 13, 39. Model rationale: The paper clearly reports 13 studied SMS patients, but the methods excerpt also shows a broader pool of 39 patients identified with a diagnosis of SMS and includes language about testing anti-GAD antibodies in patients with suspected SMS. Because the challenge flag indicates unresolved concern that the cohort may include suspected/referred rather than clearly diagnosis-supported SPS cases, the safest adjudication is manual review rather than accepting 13 with high confidence.
- `5233`: Pipeline output: 2. Extracted counts seen: 1 (source_single_case_default), 0 (no_reliable_count_signal). Review trigger: llm_bounded_alternative_competing_counts=1, 0. GPT decision: bounded_alternative; high. Model rationale: The abstract explicitly reports two original SPS-spectrum patients: a father and his daughter, both described as having stiff-man syndrome. This is clearer than the single-case default candidate, so the best-supported extractable count is 2.
- `6054`: Pipeline output: 1. Extracted counts seen: 1 (source_single_case_default), 0 (no_reliable_count_signal). Review trigger: verification_status=llm_semantic_conflict_manual_review_required. GPT decision: candidate_exact; high. Model rationale: The paper explicitly describes a single original patient with a diagnosis of PERM, which is within the SPS-spectrum definition for this review. References to multiple serum samples reflect repeated specimens from that same patient rather than additional SPS-spectrum cases.

## Assistant QA Notes

- No reviewed override rows were available for this batch when these notes were generated.
- Populate the paired review-comments CSV during manual batch QA for the remaining review candidates.