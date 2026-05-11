# data / pdf_original

Original local source PDFs used as the immutable extraction input layer.

Files are usually named with the Covidence `paper_id` prefix, for example
`1001_<source filename>.pdf`. The PDF-to-reference linkage is recorded in
`data/references/pdf_source_registry.csv`, and missing or failed acquisitions
are tracked in `data/references/pdf_acquisition_queue.csv`.

This directory is ignored by git except for placeholders. Do not treat the file
listing alone as authoritative; use the registries.
