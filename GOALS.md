# Current goal: correct single-case-report PDF assignments

## Measurable outcome

- Identify every reference in `giannis/single_case_reports_clean` whose assigned PDF does not match its reference metadata.
- Acquire the correct full-text PDF for each confirmed mismatch.
- Store each corrected PDF in the dataset location required by the existing folder structure without changing unrelated records.
- Replace the multi-article source bundles for IDs 193, 228, 272, 526, 568, 647, and 6012 with verified publisher-faithful article sources.

## Verification surface

- Compare the original and inspected dataset inventories and any audit artefacts.
- Match each suspect record using title, authors, journal, year, volume/pages, and DOI where available.
- Verify each downloaded file by inspecting its PDF metadata and first-page/article text.
- Record the source URL, resolved citation, local filename, and validation result in an audit artefact under `qa/validation/`.

## Constraints and boundaries

- Treat exported reference metadata as upstream evidence; do not rewrite it.
- Do not infer missing clinical or bibliographic facts.
- Do not overwrite an existing PDF until its mismatch and replacement are both verified.
- Do not start paid API or LLM runs.
- Preserve unrelated user changes and dataset files.

## Iteration policy

- Use local comparison and metadata/text inspection first.
- Use publisher or authoritative bibliographic pages for unresolved records.
- Retry alternate legitimate full-text routes when a publisher download is unavailable.

## Tracking files

- `GOALS.md`
- `qa/validation/single_case_report_pdf_corrections.csv`

## Stop/blocker conditions

- Stop and report any record whose source/reference linkage cannot be verified.
- Stop before any irreversible or destructive replacement if the exact target is ambiguous.
- Stop if access requires credentials or permissions not already available to the user.

## Completion evidence

- All five corrected or explicitly accepted PDFs are published as `pdf/{paper_id}.pdf`.
- Each PDF hash matches the corresponding raw JSON, clean JSON, and 476-row canonical registry entry.
- The final registry contains 476 unique verified records and no unresolved-source rows.
- The identity-bearing page of every final PDF was rendered and inspected.
- Record 1297 is retained as a documented English-abstract exception because the full article is in Japanese.
- IDs 193, 228, 526, 568, and 6012 use lossless publisher-page extracts that render pixel-for-pixel identically to the original issue pages.
- IDs 272 and 647 use official archived publisher PDFs.
- The seven recovered source hashes agree across `data/pdf_original`, main extraction JSON, clean-collection PDF/raw JSON/clean JSON, and both canonical registries.
