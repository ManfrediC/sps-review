# OpenAI Pilot 10 LangExtract Goal Plan

## Goal
Build a second 10-paper LangExtract example pilot from reviewed MC gold rows using the OpenAI API, then audit and repair the generated evidence against the Stage 07 text and original source PDFs before promotion.

## Acceptance Evidence
- Stage 09 defaults to the chosen GPT model for OpenAI bootstrapping, with a dry-run path and paid-run gate.
- The paid OpenAI run writes selected rows, candidate JSONL, review CSV, and manifest under this directory.
- Each selected paper has all non-empty gold fields represented in the reviewed span plan or explicitly documented as a discrepancy.
- Exact LangExtract examples validate with strict alignment and string-only attributes.
- A report in `doc/reports/` records paper-by-paper correctness, repairs, and source-vs-gold discrepancies for human review.

## Constraints And Boundaries
- Do not print or write API secrets.
- Treat model output as untrusted until validated against source text/PDF evidence.
- Keep non-canonical review artefacts under `qa/validation/`.
- Preserve raw source provenance; normalise whitespace only in LangExtract-facing examples.

## Current Plan
1. Completed: ran OpenAI on 10 reviewed papers outside the earlier Gemini pilot.
2. Completed: validated raw model spans and separated unsupported, weak, and supported fields.
3. Completed: repaired source spans from Stage 07 text/PDF evidence and documented discrepancies.
4. Completed: built strict LangExtract-compatible all-gold JSON and ran focused tests.

## Completion Evidence
- `field_review.csv`: 263 reviewed field rows from 10 completed OpenAI records.
- `gold_source_span_plan.csv`: 263/263 non-empty manual gold fields have at least one exact source span.
- `span_plan_examples_manifest.json`: 50 example payloads, 387 extraction rows, 0 alignment issues, 0 attribute errors.
- `doc/reports/langextract_openai_pilot10_gold_pdf_audit.md`: paper-by-paper correctness audit.
- `doc/reports/langextract_openai_pilot10_gold_pdf_discrepancies.md`: discrepancy and weak-evidence note.

## Open Risks / Unknowns
- Some gold values may be inferred rather than directly quoteable; these need source-backed support spans and explicit notes.
- Some PDF OCR text may preserve line breaks or hyphenation that require careful normalisation for LangExtract alignment.
