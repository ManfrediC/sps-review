# LangExtract OpenAI Pilot 10 Gold And PDF Audit

Date: 2026-05-29

## Scope

This report audits the second 10-paper LangExtract bootstrap pilot produced with
the OpenAI API from the manually reviewed MC case-report gold rows.

Primary artefacts:

- OpenAI run directory: `qa/validation/langextract_example_bootstrap/openai_pilot_10/`
- Selected papers: `524`, `537`, `551`, `552`, `554`, `566`, `573`, `615`, `621`, `623`
- Manual gold standard: `examples/datasheet_examples_MC_Case_Report_Form.csv`
- Stage 07 source text: `qa/validation/stage07_single_case_codex_gold/.../target_views/{paper_id}/p1.json`
- Original PDFs: `data/pdf_original/...`
- All-gold LangExtract JSON: `examples/langextract_bootstrap/draft_langextract_examples_openai_pilot10_all_gold.json`

The audit question was stricter than "did the model find a plausible answer".
Every non-empty manual gold value had to be represented in a span plan, and every
span used in the LangExtract example JSON had to be exact source text after only
whitespace normalisation.

## Run And Validation Summary

The successful paid run used:

- Provider: `openai`
- Model: `gpt-5.5`
- Reasoning effort: `low`
- Max output tokens per paper: `8000`
- Completed records: `10/10`
- Raw review rows: `263`

The first higher-effort run timed out before a completed paper was flushed, so
`src/pipelines/09_build_langextract_examples.py` now checkpoints partial paid
results after every completed paper. The successful run wrote a complete
manifest, review CSV, and JSONL candidate file.

Raw OpenAI validator status:

| Status | Count |
|---|---:|
| `passed` | 112 |
| `inference_snippet_not_found` | 71 |
| `quote_not_found` | 51 |
| `needs_review` | 29 |

The repaired span plan now covers all 263 manual gold fields:

| Coverage quality | Count | Meaning |
|---|---:|---|
| `direct_exact_span_ready` | 112 | OpenAI supplied exact source text that validated directly. |
| `covered_by_repaired_exact_source_text` | 127 | The value is source-backed, but I repaired the span to exact Stage 07 text. |
| `gold_source_conflict_or_partial_support` | 12 | The gold value conflicts with, or is only partly supported by, the source/PDF. |
| `needs_human_adjudication` | 7 | The source gives related evidence, but the coding interpretation is not safe to promote. |
| `context_or_absence_only_not_direct_extraction` | 5 | The gold value is an absence/context code, not a directly extractable positive span. |

LangExtract compatibility validation:

| Check | Result |
|---|---:|
| Source documents | 10 |
| Generated example payloads | 50 |
| Extraction rows | 387 |
| Alignment issues | 0 |
| Attribute type errors | 0 |
| Literal `\n` in example text/extraction text | 0 |

The generated JSON is technically LangExtract-compatible. It is intentionally an
all-gold audit JSON, not a clean promotion set. Rows with
`langextract_recommendation=do_not_promote_as_standard_langextract_example` or
`review_before_promoting` should be filtered out or adjudicated before use as
standard examples.

## LangExtract Span Practice Applied

For LangExtract, the `extraction_text` should be the shortest exact source text
that supports the field. The normalised spreadsheet value is stored as the
`value` attribute, because many MC fields are coded values, semicolon-delimited
normalisations, inferred classifications, or absence codes.

When a value required more than one non-contiguous source passage, the span plan
uses multiple exact spans instead of a stitched quote. When spans overlapped, the
builder split the paper into multiple example payloads for the same source text,
which is why 10 source documents became 50 compatible example payloads.

## PDF Extraction Tool Note

I compared liteparse against `pypdf` and the Stage 07 text while checking the
source PDFs.

ID `537` is the clearest case where liteparse helps. `pypdf` extracted only 647
characters, while liteparse extracted 43,238 characters and recovered evidence
around the anti-GAD negative result and the literature-review table. The output
was noisy and column/table text was interleaved, but it was useful for locating
terms that `pypdf` missed.

ID `623` is the clearest table case. `pypdf` extracted 20,063 characters and
liteparse extracted 30,372 characters. Both tools flattened the table row around
`Present 40 F SPS ... steroid pulse ... immunoadsorption ... thymectomy ...
radiation`. Liteparse was slightly cleaner around some OCR artefacts, for
example anti-GAD and thymoma wording, but it did not preserve table cells or
headers well enough to rely on it as a structured table extractor.

Practical conclusion: liteparse is a useful fallback for scanned or difficult
PDFs and for term hunting, especially where `pypdf` returns little text. It does
not extract tables well enough to replace exact Stage 07 spans or manual PDF
review for LangExtract examples.

## Paper-By-Paper Audit

### ID 524

Title: "Stiff person syndrome associated with lower motor neuron disease and
infiltration of cytotoxic T cells in the spinal cord."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 4 |
| Repaired exact span | 32 |
| Context/absence only | 1 |

Verdict: mostly correct after span repair. The clinical values are covered by
exact source text, including the normal neuroaxis imaging evidence for
`MRI_normal=0` and the malignancy workup/autopsy evidence for `tu_screening=0`.
The one non-promotable row is `ethnicity=white`: the case text says
`A previously healthy 67-year-old male presented`, but I found no patient
ethnicity evidence in the Stage 07 text or PDF-derived text. The row is covered
only as a discrepancy/context row and should not be promoted.

### ID 537

Title: "The occurrence of stiff person syndrome in a patient with thymoma: case
report and literature review."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 21 |
| Gold/source conflict or partial support | 2 |

Verdict: strong for most fields, but two gold rows conflict with the source. The
PDF/OCR text says the paraneoplastic panel included anti-GAD antibodies and that
the result was negative, so `antibody_status=GAD` is contradicted. The treatment
row is also only partly supported: the patient received chemotherapy with
complete radiographic resolution, while initial surgical treatment was deferred.
The gold value includes `resection`, which should not be promoted unless the
manual gold row is corrected or a later source passage is adjudicated.

Liteparse was materially better than `pypdf` for this PDF, but its table output
remained flattened and interleaved with body text.

### ID 551

Title: "A perplexing consult for pseudoseizures: stiff-man syndrome."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 3 |
| Repaired exact span | 19 |
| Needs human adjudication | 3 |
| Context/absence only | 1 |

Verdict: usable as a reviewed evidence pack, not clean as a promoted example.
Most demographics, diagnosis, antibody, symptom, and treatment values can be
covered by exact text after span repair. The distribution rows
`spasms_distribution_onset_multiple` and
`spasms_distribution_established_multiple` need adjudication because the source
mentions lower-left-extremity seizure activity, leg pain, falls, and kicking,
but does not cleanly encode the distal/proximal lower-extremity categories. The
`diagnosis_onset=functional` row is related to psychogenic seizure concern and
conversion disorder wording, but it is a coding judgement rather than a direct
extract. `immunotherapy=none` is absence-coded and should not be promoted as a
positive LangExtract example.

### ID 552

Title: "Stiff-person syndrome: a case report and review of the literature."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 6 |
| Repaired exact span | 18 |
| Context/absence only | 2 |

Verdict: mostly correct after span repair. The paper supports the core SPS
case, demographic, antibody, EMG, symptomatic treatment, and clinical-course
fields. `ethnicity=NA` is absence-coded because no ethnicity is stated.
`MRI_normal=NA` is also absence/context only: the source says CT findings of the
head, chest, and abdomen were normal, but does not give an MRI result.

### ID 554

Title: "Stiff-person syndrome treated with rituximab."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 2 |
| Repaired exact span | 5 |
| Gold/source conflict or partial support | 6 |

Verdict: not correct as a clean example until the gold values are adjudicated.
The source describes `A 41-year-old female patient`, while the gold row has
`age_description=32`. It says symptoms began 7 years before admission, which
implies onset around 34, not the gold `age_onset=30`. Follow-up/treatment effect
is stated as about 1 year, not 24 months. The patient treatment passage supports
rituximab at `375 mg/m2`; the text discusses plasma exchange and hyperimmune
globulin as literature options, not as treatments received by this patient. The
symptomatic-treatment evidence supports benzodiazepines/diazepam and botulinum
toxin, but not gabapentin or tizanidine.

The remaining rows are covered by exact spans, but this paper should not be used
as a standard example until the conflicting gold values are corrected or
explicitly accepted.

### ID 566

Title: "A case of glycine-receptor antibody-associated encephalomyelitis with
rigidity and myoclonus (PERM): clinical course, treatment and CSF findings."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 20 |
| Repaired exact span | 4 |

Verdict: correct and one of the strongest OpenAI pilot examples after span
repair. The source text supports the PERM/SPSD diagnosis, glycine receptor
antibody status, MRI normal coding, treatment details, CSF findings, and notes.
The four repaired rows now use exact spans rather than inferred or paraphrased
snippets. No gold/PDF conflict stood out in this audit.

### ID 573

Title: "Stiff person syndrome and pregnancy."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 5 |
| Repaired exact span | 7 |

Verdict: correct after span repair. This is a compact example with relatively
few gold fields, and all are covered by exact source text. I did not identify a
gold/PDF contradiction in the audited fields.

### ID 615

Title: "Anti-GAD antibodies and breast cancer in a patient with stiff-person
syndrome: a puzzling association."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 37 |
| Repaired exact span | 2 |
| Needs human adjudication | 4 |

Verdict: very strong for direct fields, but four inferred course/startle fields
need adjudication. The source supports the diagnosis, anti-GAD findings,
malignancy context, treatment, EMG, and MRI coding. `MRI_normal=0` is supported
because MRI of the whole neuraxis was unremarkable and the column dictionary
uses `0 = normal`. The rows `excessive_startle_onset=unspecified`,
`excessive_startle_established=unspecified`, `timecourse_onset=insidious`, and
`timecourse_subsequent=monophasic` depend on coding interpretation from related
phrases rather than direct extractable facts. They should be adjudicated before
promotion.

### ID 621

Title: "Stiff-person syndrome associated with cerebellar ataxia and high
glutamic acid decarboxylase antibody titer."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 9 |
| Repaired exact span | 23 |
| Gold/source conflict or partial support | 2 |

Verdict: source-rich but OCR-noisy. The case text supports SPS with cerebellar
ataxia, high anti-GAD antibodies, diabetes/autoimmunity, CMUA, diazepam
response, and MRI abnormality coding (`MRI_normal=1`, because asymmetric/mild
cerebellar atrophy is abnormal under the column dictionary). I repaired several
spans because the OCR text fuses words such as `womanexperienced` and
`showedcontinuous`; the final LangExtract JSON uses narrower token-aligned
spans.

Two gold rows conflict or over-specify the source. `age_description=58` is
contradicted by `A 46-year-old Japanese woman`. `diagnosis_onset_other` is coded
as `spinocerebellar_ataxia`, but the source says cerebellar ataxia was
diagnosed and gene analysis for familial ataxia/SCA found no abnormality. The
spinocerebellar-specific code should be adjudicated.

### ID 623

Title: "Stiff-person syndrome associated with invasive thymoma: a case report."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 5 |
| Repaired exact span | 17 |
| Gold/source conflict or partial support | 2 |
| Context/absence only | 1 |

Verdict: mostly source-backed, with three do-not-promote rows. The source/PDF
supports the SPS diagnosis, invasive thymoma, high anti-GAD antibody findings,
CSF antibody evidence, steroid pulse/immunoadsorption therapy, thymectomy, and
radiotherapy. It contradicts `age_description=42`, because the paper reports a
40-year-old female. It contradicts `antibody_status=seronegative`, because high
anti-GAD antibodies were detected in serum and CSF. `ethnicity=E_asia` is not
directly stated for the patient; Japanese context may be inferential, but the
case text only says `A 40-year-old female clerical worker`.

The original PDF table was useful for confirming the treatment summary, but both
`pypdf` and liteparse flatten it. Liteparse gives a slightly cleaner table row,
but neither gives reliable table structure.

## Promotion Recommendation

The OpenAI pilot is successful as an all-gold audit and span-repair workflow.
The generated JSON is compatible with LangExtract and covers every non-empty
manual gold field with exact source text. It should not be promoted wholesale as
a clean examples set.

For the next 10 or full 85-paper build, use this policy:

1. Promote rows with `candidate_for_promotion_after_spot_check` after quick
   human spot check.
2. Promote rows with `candidate_after_span_review` only after the repaired span
   is reviewed in `gold_source_span_plan_long.csv`.
3. Exclude rows with `do_not_promote_as_standard_langextract_example` unless the
   gold standard is corrected.
4. Hold rows with `review_before_promoting` until the field-specific coding rule
   is adjudicated.

This keeps the examples scientifically faithful while preserving an auditable
record of every gold value, including values where the source/PDF does not agree
with the current manual extraction.
