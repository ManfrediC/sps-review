# LangExtract Pilot 10 Gold/PDF Discrepancy Note

Generated: 2026-05-29

This note covers the seven pilot-10 gold fields where the original gold value
was contradicted or only partially supported by the Stage 07 text extracted from
the original PDF. The answers below have been implemented in the manually
reviewed case-report CSV, span plans, and regenerated LangExtract examples.

Important coding correction: `MRI_normal=0` is not a discrepancy. The column
dictionary defines `0 = normal` and `1 = abnormal`, so the normal-MRI source
passages for IDs 187, 197, 439, and 512 support the gold value.

## ID 75 - `excessive_startle_established_multipleother`

Original gold value: `noise;tactile;speaking`

Source: `qa/validation/stage07_single_case_codex_gold/batch000/json/target_views/75/p1.json`, chars 4563-4718

```text
These episodes of opisthotonos seemed trig- 
gered by external stimuli (e.g., by opening the door, 
speaking, and tactile stimuli, but not by loud noises).
```

Audit note: speaking and tactile stimulation are supported, but noise is
directly contradicted by "but not by loud noises". Do not promote this field
until the gold value is adjudicated.

Implemented value: `tactile;speaking`

## ID 92, Case 3 - `age_description`

Original gold value: `68`

Source: `qa/validation/stage07_single_case_codex_gold/batch000/json/target_views/92/p1.json`, chars 10838-10976

```text
In September 1993, a 67-year-old man developed confusion, 
symmetrical stiffness and myoclonus of both legs, and numb- 
ness of both feet.
```

Audit note: the source describes Patient 3 as 67 years old. The gold row also
has `age_onset=67`, which is supported. I did not find an exact 68-year-old
case-description span in the Stage 07 text, so `age_description=68` needs
adjudication or a documented derivation rule.

Implemented value: `67`

## ID 155 - `antibody_status`

Original gold value: `GAD;IA-2`

Source: `qa/validation/stage07_single_case_codex_gold/batch002/json/target_views/155/p1.json`, chars 1169-1288, 4512-4563, and 4618-4715

```text
The patient had GAD antibodies and islet
cell antibodies, but no other organ specific or
non-organ specific antibodies.
```

```text
IA-2As were undetectable in all
samples (figure A).
```

```text
Before immunosuppressive therapy T cells
responded to GAD65 (SI=4) and IA-2
(SI=6. 2) (figure B).
```

Audit note: GAD antibody positivity is supported. IA-2 antibody positivity is
contradicted by "IA-2As were undetectable"; the source supports only a cellular
T-cell response to IA-2. Do not promote IA-2 as an antibody-status example
without gold/schema adjudication.

Implemented value: `GAD;islet_cell`

## ID 155 - `immunotherapy`

Original gold value: `steroids;IVIG`

Source: `qa/validation/stage07_single_case_codex_gold/batch002/json/target_views/155/p1.json`, chars 1798-1980. I also checked the original PDF directly:
`data/pdf_original/155_Hummel-1998-Humoral and cellular immune parame.pdf`.

```text
Immunosuppressive therapy was therefore initiated, starting with 500 mg intravenous prednisolone
from day 1 to 10, followed by oral administration and decreasing doses of 80 to 5 mg.
```

Implemented value: `steroids`

Additional PDF evidence, page 3:

```text
The first dose of prednisolone (2×250 mg daily) injected intravenously led to a
complete disappearance of previously described symptoms within 3–4 hours.
```

Audit note: steroid therapy is supported. I searched the original PDF
page-by-page for `IVIG`, `IV Ig`, `intravenous immunoglobulin`,
`immunoglobulin`, `immune globulin`, `gamma globulin`, and `gammaglobulin`; no
IVIG/immunoglobulin treatment reference was found. The only `IgG` hits were
methodological or unrelated text: `ICA-IgG` in the antibody assay methods on
page 2, and a separate shingles "Neurological Picture" item on page 5. The IVIG
part of the gold value is therefore unsupported by the available PDF text.

## ID 162 - `onset_to_established`

Original gold value: `28`

Implemented value: `NA`. If the sheet later allows inferred approximate durations, about 44 months would be defensible, with an uncertainty range of roughly 42-45 months depending on whether onset is anchored to summer 1994 abdominal pain or fall 1994 lower-extremity pain/weakness.

Source: `qa/validation/stage07_single_case_codex_gold/batch002/json/target_views/162/p1.json`, chars 5673-5792, 6037-6117, 9186-9275, 9761-9841, 9842-10124, and 10337-10486

```text
Also during the summer of 1994 she developed
several episodes of intermittent abdominal pain
which required evaluation.
```

```text
By the fall of 1994, she
had also developed lower extremity pain and weak-
ness.
```

```text
On November 16 she was admitted to
the University of Washington Clinical Research
Center.
```

```text
She
continued with meticulous glycemic control for
the next 28 months (Table 1).
```

```text
Although her blood glucose control improved,
her abdominal pain and lower extremity weakness
continued. In addition, she developed intense pain
in her upper and lower extremities. She also com-
plained of rigidity and spasms of her proximal
limb muscles making ambulation difﬁcult.
```

```text
a dramatic response with im-
provement of her pain and stiffness with 10 mg of
oral diazepam conﬁrmed the diagnosis of stiff
man syndrome (SMS) [2].
```

Audit note: the 28-month span is not onset-to-established disease. It is the
duration of glycaemic control after insulin lispro, starting from the 16 November
1995 admission. SPSD-relevant symptoms began in summer/fall 1994, while the
fully established SPSD/diagnosis evidence appears after the 28-month insulin
lispro follow-up, approximately March 1998. That gives an inferred onset-to-
established interval of about 42-45 months. Because the PDF does not state an
exact month-count for SPSD establishment, `NA` is the safest strict extraction.

## ID 197 - `time_to_diagnosis`

Original gold value: `0.25`

Source: `qa/validation/stage07_single_case_codex_gold/batch003/json/target_views/197/p1.json`, chars 0-195

```text
A 58-year-old male (patient 861 of our caseload) was
admitted in June of 1998 with a 2 month history of progressive gait disturbance, dysarthria, and dysphagia
due to muscle stiffness and spasms.
```

Audit note: the source states a 2-month history. That is about 0.17 years, not
0.25 years, unless a separate rounding or diagnosis-date rule is being applied.

Implemented value: `0.17`

## ID 395 - `age_description`

Original gold value: `59`

Source: `qa/validation/stage07_single_case_codex_gold/batch005/json/target_views/395/p1.json`, chars 0-136, 1298-1363, and 0-53

```text
We treated a 57-year-old woman with a type
B1 thymoma, based on the World Health Organization
classiﬁcation, who had stiff man syndrome.
```

```text
A 57-year-old woman was admitted to our hospital in
February 2001
```

```text
We treated a 57-year-old woman with a type
B1 thymoma
```

Audit note: the PDF text repeatedly describes the patient as 57 years old. I
found no exact support for `age_description=59` in the Stage 07 text, so this
gold value should be adjudicated before promotion.

Implemented value: `57`
