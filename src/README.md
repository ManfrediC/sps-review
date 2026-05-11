# src

Pipeline entry points, validation utilities, and shared Python helpers.

Run scripts from the repository root so relative paths resolve correctly. Use
the project virtual environment unless a specific README says otherwise:

```bash
.\.venv\Scripts\python.exe <script>
```

Validation scripts should write non-canonical review and audit outputs under
`qa/validation/`, not `data/` or `results/`.

## Main Folders

- `pipelines/`: numbered canonical and preliminary workflow stages.
- `validation/`: review apps, benchmark tools, smoke runners, and audit
  utilities.
- `lib/`: shared helper modules used by pipeline scripts.
- `notebooks/`: exploratory notebooks, if any.
- `autoresearch/`: inactive placeholder for older automation ideas.

The retired stage-05 autoresearch and deterministic proceedings bundles are
preserved under `legacy/`, outside the live `src/` tree.

## Pipeline Order

The developed workflow currently runs through stage 07:

1. `pipelines/01_download_covidence_pdfs.py`
2. `pipelines/02_build_pdf_source_registry.py`
3. `pipelines/03_extract_text.py`
4. `pipelines/03b_clean_text.py`
5. `pipelines/90_screen_text_extraction.py` as optional QA triage.
6. `pipelines/04_source_categorisation_LLM.py`
7. `pipelines/05_trim_proceedings_text_LLM.py`
8. `pipelines/05b_validate_proceedings_text_LLM.py`
9. `pipelines/05c_publish_proceedings_ready.py`
10. `pipelines/06_extract_sps_case_counts_hybrid.py`
11. `pipelines/06c_publish_sps_case_count_registry.py`
12. `pipelines/07_split_case_series.py`
13. `pipelines/09_build_langextract_examples.py`
14. `pipelines/10_langextract.py` as preliminary downstream extraction.
15. `pipelines/11_quality_assessment.py` as preliminary downstream QA.
16. `pipelines/12_build_paper_artifact_registry.py`
17. `pipelines/13_build_paper_revisit_registry.py`
18. `pipelines/99_overnight_run.py` as an orchestration wrapper.

Everything after stage 07 is preliminary except the registry maintenance stages
12 and 13.

## Core Registries

- `data/references/paper_artifact_registry.csv`: cross-stage artefact and path
  index.
- `data/references/paper_revisit_registry.csv`: unresolved paper/stage issue
  queue.
- `data/references/source_categorisation_registry.csv`: stage-04 routing.
- `data/references/source_sps_case_count_registry.csv`: canonical stage-06
  counts.
- `data/references/case_series_split_registry.csv`: stage-07 split state.

For a collaborator-facing stage-by-stage overview, start with
`doc/notes/repo_overview_to_stage07.md`.
