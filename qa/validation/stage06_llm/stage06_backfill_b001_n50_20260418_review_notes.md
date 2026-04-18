# Stage 06 b001 Review Notes

- Combined QA CSV: `qa\validation\stage06_llm\stage06_backfill_b001_n50_20260418_combined.csv`
- Inspection pack: `qa\validation\stage06_llm\stage06_backfill_b001_n50_20260418_inspection.md`
- Per-paper comments: `qa\validation\stage06_llm\stage06_backfill_b001_n50_20260418_review_comments.csv`

## Outcome

- Reviewed papers: 50
- `llm_candidate_exact`: 41
- `manual_review_override`: 9

## Model-Based Triage

- Likely clean on first pass: 232, 241, 259, 274, 287, 289, 290, 291, 296, 398, 401, 413, 420, 421, 422, 429, 437, 439, 445, 452, 454
- Likely user review candidates: 233, 243, 247, 248, 261, 263, 266, 272, 286, 294, 387, 389, 391, 395, 415, 419, 423, 434, 436, 446

## Resolved Manual Overrides

- `238 -> 14`: Competing counts were extracted for this paper: 14 and 8. The likelier extractable cohort is 14, because the 8 appears to be a narrower analysed subgroup rather than the full original SPS cohort described by the paper.
- `239 -> 2`: The competing numbers here were 2 and 5. The likelier count is 2, because the paper is a father-and-daughter SPS report, while 5 comes from unrelated antibody-positive/thyroid-antibody text rather than the original SPS cohort.
- `252 -> 18`: The paper surfaces at least two SPS-related counts: 18 in Table 1 ('Stiff-Person syndrome 18' under 'Groups of patients / No. of cases') and 2 in Table 2 ('Stiff-Person syndrome 2 anti-GAD 6'). The likelier extractable cohort is 18, because Table 1 is the full cohort breakdown, whereas Table 2 only reports the anti-neuronal-antibody-positive subset.
- `264 -> 10`: The extracted cohort numbers are 5 familial hyperekplexia, 2 acquired hyperekplexia, 10 SMS patients, and 15 healthy controls. The likelier SPS-spectrum count is 10; the previous manual-review state came from over-cautious mixed-cohort/control handling rather than a real numeric ambiguity.
- `288 -> 8`: The competing counts are 8 SPS patients and 16 control subjects. The likelier SPS-spectrum count is 8, because 16 is the control denominator in this case-control study rather than an SPS cohort size.
- `386 -> 32`: The competing counts are 33 from the abstract ('20 of 33 patients...') and 32 from Methods ('serum samples from 32 patients ... who had been given a diagnosis of stiff-man syndrome'). The likelier extractable count is 32, because one previously described index patient is folded into the broader 33 total and the newly collected diagnosed cohort is 32.
- `404 -> 16`: The competing counts are 19 from `SPS (19,20)` and 16 from the abstract/body trial cohort statements. The likelier extractable count is 16, because `SPS (19,20)` reads like an inline citation pair, while `16 patients with anti-GAD antibody-positive SPS` is the explicit trial cohort.
- `411 -> 1`: This is a single-patient perioperative case report following one woman with established SPS across two surgeries. The likelier count is 1; the old manual-review state came from treating 'suspected an exacerbation of SPS' as cohort uncertainty when it was only describing the same confirmed patient.
- `432 -> 16`: The competing counts are 16 from Table 1 (`Stiff-man phenomena 16 (26)`) and 2 from the narrower subentry `stiff-man syndrome (2)`. The likelier extractable count is 16, because this review is counting the broader SPS-spectrum manifestation row and `26` is the percentage, not a separate patient count.

## Priority Review Candidates

- `233`: Pipeline output: 48. Extracted counts seen: 28 (abstract_count_signal), 48 (diagnosis_specific_group_breakdown_count). GPT decision: candidate_exact; medium. The likelier count is still unclear because the candidate package surfaced competing counts: 28, 48.
- `243`: Pipeline output: 2. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default; source_single_case_override), 2 (diagnosis_specific_patient_case_count). GPT decision: candidate_exact; medium. The likelier count is still unclear because the candidate package surfaced competing counts: 1, 2.
- `247`: Pipeline output: 21. Extracted counts seen: 21 (diagnosis_specific_group_breakdown_count; abstract_count_signal), 15 (early_body_count_signal). GPT decision: candidate_exact; medium. The likelier count is still unclear because the candidate package surfaced competing counts: 21, 15.
- `248`: Pipeline output: 1. Extracted counts seen: 1 (single_case_text_signal; source_single_case_default; source_single_case_override). GPT decision: candidate_exact; medium.
- `261`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default). GPT decision: candidate_exact; medium.
- `263`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default; early_body_count_signal). GPT decision: candidate_exact; medium.
- `266`: Pipeline output: 1. Extracted counts seen: 1 (source_single_case_default). GPT decision: candidate_exact; medium.
- `272`: Pipeline output: 1. Extracted counts seen: 1 (early_body_count_signal; source_single_case_default; diagnosis_specific_patient_case_count). GPT decision: candidate_exact; medium.
- `286`: Pipeline output: 1. Extracted counts seen: 1 (source_single_case_default). GPT decision: candidate_exact; medium.
- `294`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default). GPT decision: candidate_exact; medium.
- `387`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default). GPT decision: candidate_exact; medium.
- `389`: Pipeline output: 1. Extracted counts seen: 1 (single_case_text_signal; source_single_case_default; diagnosis_specific_patient_case_count). GPT decision: candidate_exact; medium.
- `391`: Pipeline output: 2. Extracted counts seen: 2 (abstract_count_signal), 9 (early_body_count_signal). GPT decision: candidate_exact; high. The likelier count is still unclear because the candidate package surfaced competing counts: 2, 9.
- `395`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default). GPT decision: candidate_exact; medium.
- `415`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default; diagnosis_specific_patient_case_count). GPT decision: candidate_exact; high.
- `419`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default). GPT decision: candidate_exact; medium.
- `423`: Pipeline output: 1. Extracted counts seen: 1 (source_single_case_default). GPT decision: candidate_exact; medium.
- `434`: Pipeline output: 25. Extracted counts seen: 25 (diagnosis_specific_suffix_count), 27 (early_body_count_signal). GPT decision: candidate_exact; medium. The likelier count is still unclear because the candidate package surfaced competing counts: 25, 27.
- `436`: Pipeline output: 38. Extracted counts seen: 38 (abstract_count_signal; diagnosis_specific_direct_cohort_count; early_body_count_signal). GPT decision: candidate_exact; medium.
- `446`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default; early_body_count_signal). GPT decision: candidate_exact; medium.

## Assistant QA Notes

- Reviewed overrides have already been folded into the combined QA CSV and these notes.
- Populate the paired review-comments CSV during manual batch QA for the remaining review candidates.