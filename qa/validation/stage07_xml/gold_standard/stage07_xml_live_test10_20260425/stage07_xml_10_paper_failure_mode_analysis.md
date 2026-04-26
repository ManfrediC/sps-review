# Stage 07 XML 10-Paper Failure-Mode Analysis

## Current Corrected Set

Reviewed annotations now exist for the full 10-paper live batch:

- `10`, `11`, `17`, `19`, `22`, `23`, `25`, `29`, `30`, `34`
- regenerated run: `stage07_xml_reviewed_gold10_20260426`
- review pack: `qa\validation\stage07_xml\gold_standard\stage07_xml_reviewed_gold10_20260426\index.html`
- canonical Stage 07 XML registry rows: 10
- ready target views: 16 of 16
- review rows in the regenerated pack: 69

The reviewed set should now be treated as the first gold regression set for Stage 07 XML routing, assignment, and source-preserving span handling.

## Main Failure Modes

### 1. Correct Target Structure, Fragile Coordinates

The original live run often chose plausible text and target IDs but failed exact offset validation. This was most visible in `10`, `19`, `22`, `25`, and `30`.

The correct general heuristic is narrow:

- keep model-selected text and offsets only if exact;
- if offsets fail but `selected_text` occurs exactly once in the same block, relocate to that exact occurrence;
- record every relocation in validation JSON;
- reject non-unique or cross-block fuzzy matches.

This keeps source text authoritative and avoids silent paraphrase or fuzzy repair.

### 2. Group Route Can Hide Individual SPSD Cases

Papers `22` and `34` show that upstream `group` routing is sometimes too coarse for mixed-cohort or lab-heavy studies.

- `22` is a mixed movement-disorder trial with one explicit SPSD case, so the correct Stage 07 route is `individual` with target `p1`.
- `34` is lab-heavy, but the source contains two explicit SMS patients, Be and Rm, so the correct Stage 07 route is `individual_case_split`.
- `25` is the contrasting case: lab-heavy and clinically sparse, so it remains `group` with only limited `g1` evidence.

The route-recovery heuristic should therefore require explicit source-backed case/patient units. It should not promote every lab-heavy group paper into patient splits.

### 3. Single-Patient Pass-Through Is Safe but Noisy

Papers `17` and `29` show that broad single-patient pass-through preserves attribution but carries too much front matter, generic disease background, references, acknowledgements, and publisher boilerplate.

The hybrid policy is appropriate:

- deterministic clinical-window trimming first;
- GPT fallback only when boundaries are uncertain and paid runs are allowed;
- otherwise emit a manual-review reason instead of silently using noisy full text.

For `29`, the useful patient evidence is concentrated in the abstract clinical summary, the case report, and a short patient-specific treatment interpretation in the discussion.

### 4. Shared Patient Context Is Not a Separate Group

Papers `10`, `19`, and `30` need shared statements to be copied into each relevant patient view, not stored as a disconnected `g1` group.

Useful rule:

- for case-series papers with declared patient targets, all-patient statements should normally use all patient target IDs with role `shared`;
- reserve `g1` for true aggregate-only group evidence where patient views should not receive the text.

This is especially important before LangExtract, because otherwise patient-level extraction can miss criteria, common treatments, or shared laboratory context.

### 5. Tables Require Prose-Guided Row Relevance

Papers `11` and `22` show that table relevance is usually discoverable from prose.

- If prose identifies SPSD cases, such as cases `8`, `9`, and `10`, only matching table rows should be included.
- If a row has a direct diagnosis-cell match, such as `Stiff-person syndrome`, it can be included when row boundaries are clear.
- If relevant IDs exist but row boundaries cannot be isolated, warn with `ambiguous_table_row_mapping` and require review.

This avoids sending non-SPSD rows to LangExtract while preserving source-verifiability.

### 6. OCR Layout Interruptions Need Split Spans

Papers `30` and `34` contain page headers, journal footers, figure legends, and interrupted words inside otherwise clinical text.

The safest correction pattern is to split spans around interruptions rather than pretending the source is continuous:

- `30` Patient 3 is split around `continu-` / `ous motor-unit activity`;
- `34` Patient Be is split around `discon-` / `tinued`;
- figure legends can be patient-specific when they contain patient-specific clinical measurements.

The XML output should preserve the source order and make these interruptions visible for human review.

### 7. Lab-Heavy Papers Need a Sparse-Evidence Mode

Paper `25` is clinically relevant but not rich clinical source material. The useful output is a small `g1` group summary, not a broad lab-methods extraction.

Conservative rule:

- include patient/sample population and clinically relevant group findings;
- exclude methods-only laboratory procedures, reagent descriptions, reference lists, and broad mechanistic discussion unless explicitly tied to the SPSD group.

## Recommended Next Actions

1. Use the 10-paper corrected review pack to visually confirm the new gold set, especially `25`, `29`, `30`, and `34`.
2. Keep the reviewed JSON specs as regression fixtures rather than editing generated XML/JSON by hand.
3. Add future reviewed batches incrementally, prioritising:
   - mixed cohort plus table papers;
   - lab-heavy papers with a small number of explicit patients;
   - OCR-disrupted case reports.
4. Before scaling paid runs, improve model-input compaction and deterministic boilerplate trimming to reduce cost and reduce irrelevant source exposure.
5. For LangExtract, treat ready target views from reviewed-gold runs as preferred inputs over broader deterministic outputs.
