# tests

Automated tests and small fixtures for pipeline and validation behaviour.

Run tests from the repository root with the project virtual environment:

```bash
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Focused Suites

Registry maintenance:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_12_build_paper_artifact_registry.py tests/test_13_build_paper_revisit_registry.py -q
```

Text extraction and cleanup:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_02_build_pdf_source_registry.py tests/test_03_extract_text.py tests/test_03b_clean_text.py tests/test_text_cleanup.py -q
```

Stage 04 and stage 05:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_04_source_categorisation_LLM.py tests/test_05_proceedings_text_llm.py tests/test_05c_publish_proceedings_ready.py -q
```

Stage 06:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_06_extract_sps_case_counts_hybrid.py tests/test_06c_publish_sps_case_count_registry.py tests/test_stage06_review_workflow.py -q
```

Stage 07:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_07_split_case_series.py tests/test_run_stage07_smoke.py tests/test_stage07_review_workflow.py -q
```

Downstream preliminary stages:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_10_langextract.py tests/test_11_quality_assessment.py -q
```
