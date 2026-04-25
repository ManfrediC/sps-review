# Stage 07 XML + JSON implementation plan

## Summary

Stage 07 now has a new implementation path under:

```text
src/pipelines/stage07_XML/
```

The existing script remains untouched:

```text
src/pipelines/07_split_case_series.py
```

The new Stage 07 XML path prepares source-backed patient and group views for the next LangExtract stage. Its purpose is routing and attribution, not clinical fact extraction.

The key invariant is:

```text
strip_stage07_tags(annotated_text) == prepared_source_text
```

This protects the downstream provenance chain.

## Annotation design

GPT-5.5 does not produce rewritten source text or literal XML. It returns structured span metadata against deterministic paragraph blocks.

The model receives blocks shaped like:

```json
{
  "block_id": "b0001",
  "source_offsets": {"start": 0, "end": 86},
  "page_index": 0,
  "text": "Case 1 had axial stiffness and painful spasms."
}
```

The model returns metadata shaped like:

```json
{
  "segments": [
    {
      "targets": ["p1"],
      "role": "patient_specific",
      "confidence": "high",
      "evidence": "The block explicitly describes Case 1.",
      "spans": [
        {
          "block_id": "b0001",
          "start_offset": 0,
          "end_offset": 45,
          "selected_text": "Case 1 had axial stiffness and painful spasms."
        }
      ]
    }
  ]
}
```

Python validates every span exactly:

```text
block_text[start_offset:end_offset] == selected_text
```

If the check fails, Stage 07 does not guess, repair, or use fuzzy matching. It writes validation artefacts and marks the affected paper or target views not ready for LangExtract.

Python then generates XML tags deterministically:

```xml
<seg id="s0001" group="l0001" targets="p1" role="patient_specific">Case 1 had axial stiffness and painful spasms.</seg>
```

## Output contract

Canonical Stage 07 XML outputs live under:

```text
data/extraction_json/stage07_xml/
  papers/{paper_id}.json
  annotated_text/{paper_id}.annotated.txt
  segments/{paper_id}.segments.json
  target_views/{paper_id}/{target_id}.json
  validation/{paper_id}.validation.json
  manifests/{manifest_run_id}.jsonl
```

The Stage 07 XML registry lives at:

```text
data/references/stage07_xml_registry.csv
```

Raw prompts and model responses are trace artefacts, not canonical research data. They live under:

```text
results/stage07_xml_runs/{manifest_run_id}/
```

The master artefact registry indexes Stage 07 XML outputs with compact path and status columns, including validation status, round-trip status, target-view counts, readiness counts, and Stage 06 divergence flags.

## Target-view JSON

LangExtract should consume target-view JSON files, one per patient or group target. Each file contains source-backed `input_text` plus offset mappings back to the prepared source text.

Example:

```json
{
  "stage07_target_view_schema_version": "stage07_xml_target_view_v1",
  "document_id": "9003::p1",
  "paper_id": "9003",
  "target_id": "p1",
  "target_kind": "patient",
  "target_label": "Patient 1",
  "ready_for_langextract": true,
  "input_text": "Case 1 had axial stiffness and painful spasms.\n\nBoth patients had anti-GAD antibodies.",
  "source_blocks": [
    {
      "block_id": "tb0001",
      "segment_id": "s0001",
      "logical_segment_id": "l0001",
      "relation_to_target": "direct",
      "role": "patient_specific",
      "shared_with": [],
      "source_offsets": {"start": 0, "end": 45},
      "compiled_offsets": {"start": 0, "end": 45}
    }
  ],
  "manual_review": {
    "manual_review_required": false,
    "reasons": []
  }
}
```

LangExtract outputs can later be mapped from `compiled_offsets` back to original Stage 07 source offsets.

## Behaviour

- Single-patient sources get deterministic `p1` pass-through target views.
- Multi-patient sources use Stage 06 patient count as the target prior and require span metadata before becoming ready.
- There is no hard high-count cutoff. Counts above roughly 20 are recorded as higher risk and require complete expected-target coverage before readiness.
- Group sources get Stage 06-guided group targets. Additional explicit group targets may be accepted only when the model supplies source-backed evidence.
- Uncertain spans are preserved in segment JSON but excluded from ready target-view input text.
- Partial outputs are written for review, but incomplete target coverage is not marked ready.
- Existing per-paper outputs are skipped unless `--force` is supplied.

## CLI

Run with mocked annotation responses:

```bash
python src/pipelines/stage07_XML/run_stage07_xml.py --paper-id 9003 --mock-annotation-dir qa/validation/stage07_xml/mock_annotations --skip-artifact-registry-refresh
```

Run a guarded live GPT-5.5 pass:

```bash
python src/pipelines/stage07_XML/run_stage07_xml.py --paper-id 9003 --annotation-model gpt-5.5 --allow-paid-run
```

The default live model is:

```text
gpt-5.5
```

No paid model call happens unless `--allow-paid-run` is supplied.

## Validation

Focused tests:

```bash
py -3.14 -m pytest tests/test_stage07_xml.py tests/test_12_build_paper_artifact_registry.py tests/test_07_split_case_series.py -q
```

The relevant coverage includes:

```text
paragraph block indexing
block-local offset validation
exact XML round trip
multi-patient shared-segment compilation
single-patient deterministic pass-through
missing split-annotation not-ready handling
artefact-registry Stage 07 XML indexing
legacy Stage 07 regression checks
```
