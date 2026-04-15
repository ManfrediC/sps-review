# tests

## Purpose
Automated tests and test fixtures for pipeline and utility validation.

## Running tests
Use `pytest` from the project virtual environment.

Example:

```bash
.\.venv\Scripts\python.exe -m pytest tests -q
```

Focused cleanup-stage suite:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_text_cleanup.py tests/test_03b_clean_text.py tests/test_12_build_paper_artifact_registry.py -q
```

Routing and downstream exclusion checks:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_source_routing.py tests/test_10_langextract.py tests/test_11_quality_assessment.py -q
```

## Directory Contents Snapshot
- Last updated: `2026-04-05`
- Immediate subdirectories (0): _None_
- Immediate files (13, excluding `README.md`): `covidence_example_html.txt`, `test_02_build_pdf_source_registry.py`, `test_03_extract_text.py`, `test_03b_clean_text.py`, `test_05_proceedings_text_llm.py`, `test_10_langextract.py`, `test_11_quality_assessment.py`, `test_12_build_paper_artifact_registry.py`, `test_apply_trimming_manual_overrides.py`, `test_export_text_json_to_txt.py`, `test_manage_trimming_batches.py`, `test_source_routing.py`, ... (+1 more)
