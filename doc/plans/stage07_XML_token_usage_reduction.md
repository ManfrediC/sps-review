# Stage 07 XML Token Usage Reduction Notes

## Current Signal

The live 10-paper test run `stage07_xml_live_test10_20260425` used approximately:

- input: `~71k` tokens across paid Stage 07 XML annotation calls
- output: `~18k` tokens
- largest input requests:
  - paper `30`: `~17.5k` tokens
  - paper `25`: `~15.4k` tokens
  - paper `10`: `~10.6k` tokens
- largest outputs:
  - paper `34`
  - paper `10`
  - paper `25`

The largest avoidable costs are source-block payload verbosity, too many tiny blocks, full-span text repeated in model output, and non-clinical source material sent to the model.

## Recommended Changes

### 1. Compact the Source-Block Payload

Current requests send verbose objects with keys such as `block_id`, `source_offsets`, `page_index`, and `text`.

For the model, use a compact shape:

```json
{"id":"b0001","p":0,"t":"source text"}
```

or, if readability is less important:

```json
["b0001",0,"source text"]
```

Keep absolute source offsets in Python only. The model only needs a stable block id, optional page index, and block text.

Expected effect: moderate input-token reduction, especially for papers with many blocks.

### 2. Remove Duplicate Output Examples From the User Payload

The call now uses a structured JSON schema via the OpenAI Responses API. The inline `required_output_shape` repeats information already provided by the schema.

Replace it with a short instruction such as:

```text
Return JSON matching the supplied schema. Use exact character offsets within the provided block text.
```

Expected effect: small input-token reduction and less schema/example confusion.

### 3. Merge Tiny Adjacent Blocks Before Annotation

Paper `30` had `183` source blocks, which creates large metadata overhead and can encourage fragmented segment assignments.

Add a model-input block merge step:

- merge adjacent short blocks until approximately `800-2500` characters
- preserve natural boundaries at headings such as `Patient`, `Case`, `Subject`, `Methods`, `Results`, and tables
- maintain a Python-only map from model-block offsets back to prepared-source offsets

Expected effect: large input-token reduction for OCR-fragmented papers and more coherent model spans.

### 4. Exclude Obvious Non-Clinical Boilerplate Before GPT

Single-patient pass-through examples showed large amounts of interlibrary loan headers, journal front matter, references, and OCR noise.

Before paid annotation, deterministically classify and exclude low-value blocks such as:

- document-delivery or library cover sheets
- reference lists
- acknowledgements and correspondence details
- repeated journal page headers/footers
- copyright and download notices

Record excluded spans and hashes in the validation payload for provenance.

Expected effect: moderate to large input reduction and cleaner downstream LangExtract inputs.

### 5. Use Candidate Source Windowing for Long Papers

For long papers, send only likely relevant blocks plus context:

- title and abstract
- blocks containing `Patient`, `Case`, `Subject`, `Table`, `Clinical`, `Results`, `SPS`, `SMS`, `PERM`, `stiff-person`, or related terms
- neighbouring blocks around selected hits

If a large fraction of source text is excluded, add a warning such as `stage07_windowed_source:true`.

Expected effect: large token reduction for long lab-heavy or review-like sources, while keeping auditability.

### 6. Replace Full `selected_text` Output With Anchors

Current output repeats the full selected source span, which is expensive. A cheaper schema can ask for:

```json
{
  "block_id": "b0003",
  "start_anchor": "first exact 80 characters",
  "end_anchor": "last exact 80 characters"
}
```

Python then resolves the unique span. If anchors are ambiguous, the paper is marked for review or retried with full-span output.

Expected effect: largest output-token reduction.

### 7. Keep Reasoning Effort Low and Benchmark `minimal`

The Stage 07 task is coordinate selection with deterministic validation, not free-form clinical reasoning.

Current recommendation:

- keep `reasoning.effort = low`
- benchmark `minimal` on the same 10-paper set after span relocation is implemented
- adopt `minimal` only if validation and review quality remain stable

Expected effect: lower hidden reasoning cost without changing the visible contract.

### 8. Use Prompt Caching for Stable Prompt Components

The system prompt and JSON schema are stable across papers. Use an API prompt-cache key or retention option where available.

Expected effect: reduced repeated prompt cost; no change to output behaviour.

## Implementation Priority

1. Add exact unique span relocation.
2. Compact the block payload and remove duplicate inline output examples.
3. Merge tiny adjacent blocks for model input.
4. Add deterministic boilerplate exclusion.
5. Add source windowing for long papers.
6. Trial anchor-based output.
7. Benchmark `minimal` reasoning effort.
8. Add prompt caching.

## Guardrails

- Do not drop source text silently.
- Every excluded or merged span must remain traceable to original source offsets.
- Token-saving changes must preserve the invariant that generated XML strips back to the prepared source text used for annotation.
- Any windowing or boilerplate exclusion should add validation metadata so human reviewers know the model did not see the full paper.
- Full-span output should remain available as a fallback for ambiguous anchor resolution.
