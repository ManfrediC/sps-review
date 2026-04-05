# tests

## Purpose
Automated tests and test fixtures for pipeline and utility validation.

## Running tests
Use the standard-library test runner unless the environment explicitly includes `pytest`.

Example:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Focused cleanup-stage suite:

```bash
python -m unittest tests.test_text_cleanup tests.test_03b_clean_text tests.test_12_build_paper_artifact_registry -v
```

Routing and downstream exclusion checks:

```bash
python -m unittest tests.test_source_routing tests.test_10_langextract tests.test_11_quality_assessment -v
```

## Directory Contents Snapshot
- Last updated: `2026-04-05`
- Immediate subdirectories (0): _None_
- Immediate files (13, excluding `README.md`): `covidence_example_html.txt`, `test_02_build_pdf_source_registry.py`, `test_03_extract_text.py`, `test_03b_clean_text.py`, `test_05_trim_proceedings_text.py`, `test_10_langextract.py`, `test_11_quality_assessment.py`, `test_12_build_paper_artifact_registry.py`, `test_export_text_json_to_txt.py`, `test_source_routing.py`, `test_text_cleanup.py`, `test_validate_pdf_source_registry.py`, ... (+1 more)
