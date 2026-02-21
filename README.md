# sps-review

AI-assisted, human-verified data extraction pipeline for stiff-person-spectrum case reports.

## Repository layout
- data/pdf_original/      Source PDFs (not committed)
- data/extraction_json/   Structured extraction + evidence (not committed)
- data/pdf_annotated/     Highlighted PDFs for reviewer verification (not committed)
- data/excel/             Reviewer workbook (not committed)
- src/pipelines/          Pipeline scripts (extract → annotate → export)
- config/                 Schema + data dictionary + colour map
- doc/                    Methods/protocol documentation
- results/                Analysis-ready exports (not committed by default)

## Core idea
Excel remains the reviewer interface; quotes live outside the main sheet and are used to generate annotated PDFs with colour-coded highlights, enabling fast verification.