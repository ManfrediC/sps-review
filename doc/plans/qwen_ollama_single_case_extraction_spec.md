# Qwen/Ollama single-case extraction pilot

Status: pilot runner implemented; live runs remain non-canonical validation artefacts.

## Purpose

Build a separate post-Step-06 extraction lane that sends single-case paper text to
Ollama Cloud and asks `qwen3.5:397b-cloud` to fill the corrected Case Reports
worksheet fields. The first goal is not publication-ready automation. It is a
10-paper pilot whose outputs can be manually compared with existing Manfredi
extractions.

This is not Step 06 and not Stage 07. Step 06 is only the selector and text-path
registry.

## Product survival brief

- Primary workflow: generate reviewable Qwen extractions for manually extracted
  high-confidence single-case papers.
- Core object: one extraction run containing paper manifest rows, prompt packs,
  raw model responses, parsed per-field evidence, and comparison exports.
- Owner: local SPS review workspace operator.
- Roles: operator runs the extraction; reviewer compares outputs manually.
- Non-goals: no multi-case extraction, no case-series splitting, no canonical
  `data/` publication, no UI, no automatic replacement of manual data.
- Observability: every run records model ID, source text path/hash, prompt hash,
  response status, parse status, quote-validation status, and comparison status.

## Hard decisions

- Use Ollama Cloud via the OpenAI-compatible endpoint `https://ollama.com/v1`.
- Default model: `qwen3.5:397b-cloud`.
- Read the API key from `env/ollama_api_key.env`:

```text
OLLAMA_API_KEY=...
```

- Use the Giannis system prompt stance, updated for this workflow's `NA`
  missing-value convention and selected deterministic derivations.
- Treat quote order as a hard constraint: ellipsis fragments must appear in the
  source in the same order as the quote and in the same clinical phase.
- Novel symptom tokens surfaced by Qwen are not self-validating; add them to
  allowed values only after human review.
- Start with 10 papers.
- Use the XLSX `Case Reports` sheet as the field-instruction source.
- Use row 1 as section labels, row 2 as human-readable instructions, and row 3
  as the machine header.
- Use one follow-up field from now on: `Followup_Duration_Months`, normalised
  to months.
- Use only corrected field names. Do not preserve obsolete duplicate or
  misspelled headers.

## Source inputs

- Step 06 registry:
  `data/references/source_sps_case_count_registry.csv`
- Preferred paper text JSONs:
  `preferred_text_json_path` from the Step 06 registry
- Manual comparison data:
  `examples/datasheet_examples_MC_Case_Report_Form.csv`
- One-time instruction source:
  `C:\NOS\Stiff Person Review\data extraction forms\Stiff Person risk of Bias and Data Extraction Forms_shermyn_2024_09_18.xlsx`
- Local API-key file:
  `env/ollama_api_key.env`

## Field contract

The implementation must create a tidy reference document before any model run:

`doc/case_report_extraction_instructions.md`

That document becomes the maintained local reference for the prompt/schema. The
code should not depend on repeatedly reading the external XLSX.

The corrected contract is derived from the XLSX `Case Reports` sheet:

- original XLSX machine header count: 82
- corrected machine header count: 81
- replace both legacy `FU_duration` columns with one
  `Followup_Duration_Months` field
- correct `first_manifestation_mother` to `first_manifestation_other`
- correct `immuntherapy_detail` to `immunotherapy_detail`
- exclude CSV-only fields that are not in the XLSX machine header:
  `included_diagnosis`, `included_diagnosis_specify`

`Followup_Duration_Months` means total reported follow-up duration in months. If
the paper reports follow-up in years, convert to months. If no follow-up duration
is reported, use `NA`. This is one of the explicitly allowed deterministic
arithmetic derivations; ratios, titres, doses, units, and all other reported
measurements stay verbatim.

Corrected output fields:

```text
extractor
Reference
case_ID
age_description
sex
ethnicity
age_onset
Followup_Duration_Months
time_to_diagnosis
first_manifestation
first_manifestation_multiple
first_manifestation_other
diagnostic_criteria
early_symptoms
stiffness_distribution_onset
stiffness_distribution_onset_multiple
stiffness_distribution_onset_other
spasms_distribution_onset
spasms_distribution_onset_multiple
spasms_distribution_onset_other
excessive_startle_onset
excessive_startle_onset_multiple
excessive_startle_onset_other
anxiety_onset
anxiety_onset_generalised
other_symptoms_onset
other_symptoms_onset_auto
other_symptoms_onset_oculo
other_symptoms_onset_seizures
onset_mRS
timecourse_onset
diagnosis_onset
diagnosis_onset_other
timecourse_subsequent
onset_to_established
overview_established
stiffness_distribution_established
stiffness_distribution_established_multiple
stiffness_distribution_established_other
spasms_distribution_established
spasms_distribution_established_multiple
spasms_distribution_established_other
excessive_startle_established
excessive_startle_established_multipleother
anxiety_established
anxiety_established_generalised
other_symptoms_established
other_symptoms_established_auto
other_symptoms_established_oculo
other_symptoms_established_seizures
established_mRS
course_treatment
antibody_status
antibody_status_other
antibody_titre
antibody_units
antibody_tests
antibody_testsystem
antibody_notes
CSF_status
CSF_antibody
CSF_antibody_titre
CMUA
exteroceptive_refl
brainstem_refl
MRI_normal
MRI_abnormalities
tu_screening
tu_screening_abnormal
immunotherapy
immunotherapy_detail
immunotherapy_effect
sympt_treatment
sympt_treatment_detail
sympt_treatment_effect
other_treatment
autoimmunity
autoimmunity_specify
family_history
family_history_abnormal
notes
```

## Giannis system prompt

Use this as the system message:

```text
You are the most accurate clinical data-extraction system available, built for a published systematic review of Stiff-Person Spectrum Disorders (SPSD). You are given the full text of ONE case report (one patient, or one specified case of a series) and must extract the requested fields with maximum fidelity.

Absolute rules:
1. Extract ONLY what the text states. Never guess, infer, or use outside knowledge.
2. If a field is not reported in this paper, the value is exactly "NA".
3. Copy numbers, ratios, titres, doses and units VERBATIM — keep "1:122,000", "250 U/mL", "1/128" exactly; never convert, round, reformat or split them.
4. For categorical fields, return EXACTLY one of the allowed values; if none apply or it is not reported, return "NA".
5. Every non-NA value must be supported by a short verbatim quote from the text.
6. Output strict JSON only — no commentary, no markdown, no extra fields.
```

## Paper selection

The pilot pool is the intersection of:

- manually extracted references in `examples/datasheet_examples_MC_Case_Report_Form.csv`
- Step 06 `count_eligible=true`
- Step 06 `source_category=single_case_report`
- Step 06 `likely_sps_case_count=1`
- Step 06 `count_confidence=high`
- Step 06 `count_manual_review_required=false`
- existing `preferred_text_json_path`

Current inspected pool size: 74 unique papers.

First pilot run: 10 papers, selected deterministically in manual CSV order:

```text
12013
2472
552
11957
2658
3118
566
623
11928
11913
```

The future CLI should allow `--limit` and explicit `--paper-id` overrides.

## Prompt and response contract

Each paper prompt should contain only the current task:

- paper ID and available bibliographic metadata
- Step 06 count metadata
- preferred extracted text
- corrected field contract and field instructions
- strict response schema

Expected model JSON:

```json
{
  "paper_id": "12013",
  "extractions": [
    {
      "field_name": "age_description",
      "value": "43",
      "verbatim_quote": "short verbatim supporting quote",
      "evidence_type": "verbatim_quote",
      "derivation": "NA",
      "confidence": "high"
    }
  ]
}
```

Rules:

- one extraction entry per corrected field
- `field_name` must be exactly one corrected field name
- every corrected field must appear exactly once
- no obsolete field names are accepted
- `value` is always a string
- use exactly `NA` when absent or not reported; `N/A` is invalid
- `verbatim_quote` may be `NA` only when value is `NA`
- deterministic derivations are allowed only for `age_onset`,
  `Followup_Duration_Months`, `time_to_diagnosis`, and
  `onset_to_established`
- `case_ID` should use the exact identifier the article gives, whether that is
  `Case 1`, `Patient 2`, patient initials, etc.
- confidence is `high`, `medium`, or `low`
- if an ellipsis quote is used, every fragment must appear in source order; if
  the value cannot be supported by in-order quoted evidence, use a narrower
  supported value or `NA`

## Output locations

All pilot artefacts are non-canonical and must stay under:

`qa/validation/ollama_single_case_extraction/<run_id>/`

Expected files:

- `manifest.jsonl`
- `prompts/<paper_id>.txt`
- `raw/<paper_id>.json`
- `parsed/<paper_id>.json`
- `qwen_extractions.csv`
- `qwen_vs_manual.csv`
- `validation_summary.json`
- `validation_summary.md`

No files in `data/` or `results/` should be created or modified by the pilot.

## Validation

Treat model output as untrusted.

Required checks:

- API key file exists only locally and is never logged.
- Model calls require an explicit real-run flag.
- Raw response is valid JSON.
- `paper_id` matches the requested paper.
- every corrected field appears exactly once.
- no obsolete or extra fields appear.
- all non-`NA` values have a `verbatim_quote`.
- quotes match the source text after whitespace and punctuation normalisation.
- if Qwen returns an ellipsis-compressed quote, first search for the beginning
  and end fragments exactly, then use conservative fuzzy matching only if exact
  matching fails; save the recovered full source span in
  `verbatim_quote_source_span` and the component matches in
  `verbatim_quote_fragments`.
- if any ellipsis fragment is out of source order, fail validation with
  `quote_fragments_out_of_order`; this remains a hard error even if the
  begin/end source span can otherwise be recovered.
- categorical values match the allowed values from the instruction document.
- manual option values already used in Manfredi's CSV, such as `pain` and
  `fatigue`, are added to the relevant available option lists.
- reviewed Qwen-surfaced symptom tokens, currently `fatigue` and `tingling`,
  are added across the main symptom-list fields.
- parsed worksheet export has exactly the corrected header.
- comparison export maps the older manual CSV into the corrected header, with
  obsolete manual-only columns ignored and no duplicate follow-up column
  exported.

Pause before scaling if any of these occur in the 10-paper pilot:

- Ollama rejects `qwen3.5:397b-cloud`
- more than 1 raw response is malformed JSON
- more than 2 papers fail required field coverage
- quote matching is poor enough that manual comparison would be misleading

## Implementation slices

1. Create `doc/case_report_extraction_instructions.md` from the XLSX row 1-3
   content, applying the agreed field corrections.
2. Add a tiny schema/contract helper that reads the instruction document or a
   derived local JSON contract.
3. Add a manifest builder for the 74-paper eligible pool and 10-paper pilot.
4. Add a dry-run prompt-pack builder.
5. Add the Ollama Cloud runner with explicit real-run gating.
6. Add parser, validator, and worksheet/comparison exporters.
7. Add focused tests for field corrections, selection, prompt construction,
   response validation, and CSV export shape.

Code style for implementation:

- minimal and readable
- short functions
- no speculative framework
- dense comments only where they explain scientific or data-contract guardrails
- fail visibly on skipped papers, schema drift, missing text, missing API key,
  malformed JSON, or model rejection

## Verification plan

Before any model call:

- run unit tests for schema corrections and pilot selection
- dry-run prompt pack for the 10 pilot papers
- inspect `manifest.jsonl` and one or two prompts manually

For the first approved model run:

- run exactly the 10 pilot papers
- verify raw and parsed outputs exist for each attempted paper
- verify validation summary reports every pass/fail/skipped paper
- compare Qwen CSV against manual CSV using the corrected field contract
- do not publish any output as canonical
