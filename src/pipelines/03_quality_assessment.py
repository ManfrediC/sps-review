from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import langextract as lx
from tqdm import tqdm


# Resolve repository-relative defaults once.
REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "config" / "prompts"
TEXT_JSON_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
QUALITY_DICT_PATH = REPO_ROOT / "config" / "dictionaries" / "SPS_quality_dictionary.csv"
QUALITY_SCHEMA_PATH = REPO_ROOT / "config" / "schema" / "SPS_quality_assessment.schema.json"
RAW_OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "quality" / "raw"
RECORD_OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "quality" / "records"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "00_build_paper_artifact_registry.py"

# Ensure output folders exist even on first run.
RAW_OUT_DIR.mkdir(parents=True, exist_ok=True)
RECORD_OUT_DIR.mkdir(parents=True, exist_ok=True)

NA_HINTS = (
    "na",
    "not available",
    "not applicable",
    "not reported",
    "unknown",
    "unclear",
)


# Default prompt template for publication-type classification.
DEFAULT_PUBTYPE_PROMPT_TEMPLATE = (
    "Classify the study design type for quality assessment.\n"
    "Return extraction class 'publication_type' with one option exactly as listed below.\n"
    "If uncertain, choose the closest fit.\n\n"
    "Options:\n"
    "{options}"
)

# Default prompt template for dictionary-driven quality extraction.
DEFAULT_QUALITY_PROMPT_TEMPLATE = (
    "Extract quality-assessment values for publication type: {publication_type}.\n"
    "Return extraction classes exactly as field names listed below.\n"
    "For each extraction, start extraction_text with the proposed value, then optional short evidence.\n"
    "Use format: <value> :: <evidence>.\n"
    "Use NA when the item is not available/not applicable/not reported.\n\n"
    "Fields:\n"
    "{field_block}"
)


# Default few-shot publication-type examples used when JSON files are missing.
def default_pubtype_examples_payload() -> list[dict[str, Any]]:
    return [
        {
            "text": (
                "This retrospective cohort study reviewed consecutive patients at a tertiary centre "
                "and analysed exposure-outcome associations."
            ),
            "extractions": [
                {
                    "extraction_class": "publication_type",
                    "extraction_text": "Observ Cohort & Cross sect",
                }
            ],
        },
        {
            "text": (
                "This randomised controlled trial assigned participants to intervention and placebo arms "
                "with blinded outcome assessment."
            ),
            "extractions": [
                {
                    "extraction_class": "publication_type",
                    "extraction_text": "Controlled Intervention Studies",
                }
            ],
        },
    ]


# Convert generic example dictionaries into LangExtract ExampleData objects.
def to_example_data(payload: list[dict[str, Any]]) -> list[Any]:
    examples: list[Any] = []
    for item in payload:
        text = (item.get("text") or "").strip()
        extraction_payload = item.get("extractions") or []
        if not text or not isinstance(extraction_payload, list):
            continue
        extractions = []
        for row in extraction_payload:
            extraction_class = (row.get("extraction_class") or "").strip()
            extraction_text = (row.get("extraction_text") or "").strip()
            if extraction_class and extraction_text:
                extractions.append(
                    lx.data.Extraction(
                        extraction_class=extraction_class,
                        extraction_text=extraction_text,
                    )
                )
        if extractions:
            examples.append(lx.data.ExampleData(text=text, extractions=extractions))
    return examples


# Load prompt text from file with fallback to in-code templates.
def load_prompt_text(path: Path, fallback: str) -> str:
    if not path.exists():
        return fallback
    text = path.read_text(encoding="utf-8").strip()
    return text or fallback


# Load examples payload from JSON with fallback defaults.
def load_examples_payload(path: Path, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not path.exists():
        return fallback
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Examples JSON must be a list: {path}")


# Resolve all prompt/example assets once per run.
def load_prompt_assets(prompt_dir: Path) -> dict[str, Any]:
    pubtype_prompt_template = load_prompt_text(
        prompt_dir / "03_publication_type_prompt.md",
        DEFAULT_PUBTYPE_PROMPT_TEMPLATE,
    )
    quality_prompt_template = load_prompt_text(
        prompt_dir / "03_quality_prompt.md",
        DEFAULT_QUALITY_PROMPT_TEMPLATE,
    )
    pubtype_examples = to_example_data(
        load_examples_payload(
            prompt_dir / "examples" / "03_publication_type_examples.json",
            default_pubtype_examples_payload(),
        )
    )
    return {
        "pubtype_prompt_template": pubtype_prompt_template,
        "quality_prompt_template": quality_prompt_template,
        "pubtype_examples": pubtype_examples,
    }


# Parse CLI arguments for batch processing, model settings, and validation controls.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract quality-assessment fields from paper text JSONs with LangExtract."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=TEXT_JSON_DIR,
        help="Directory containing text extraction JSON files.",
    )
    parser.add_argument(
        "--quality-dict",
        type=Path,
        default=QUALITY_DICT_PATH,
        help="Path to SPS quality dictionary CSV.",
    )
    parser.add_argument(
        "--raw-out-dir",
        type=Path,
        default=RAW_OUT_DIR,
        help="Directory for raw LangExtract outputs.",
    )
    parser.add_argument(
        "--record-out-dir",
        type=Path,
        default=RECORD_OUT_DIR,
        help="Directory for structured quality records.",
    )
    parser.add_argument(
        "--prompt-dir",
        type=Path,
        default=PROMPTS_DIR,
        help="Directory containing prompt markdown and example JSON files.",
    )
    parser.add_argument(
        "--schema-path",
        type=Path,
        default=QUALITY_SCHEMA_PATH,
        help="Path to quality JSON schema used for record validation.",
    )
    parser.add_argument(
        "--skip-schema-validation",
        action="store_true",
        help="Skip schema validation for structured records.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Paper ID to process (repeat flag for multiple IDs).",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max files to process.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs.")
    parser.add_argument("--dry-run", action="store_true", help="Validate only; no API calls.")
    parser.add_argument(
        "--publication-type",
        default="",
        help="Override publication type (skip auto-detection).",
    )
    parser.add_argument(
        "--model-id",
        default="gpt-4.1-mini",
        help="OpenAI model ID used by LangExtract (e.g. gpt-4.1-mini, gpt-5-mini).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI API key; defaults to OPENAI_API_KEY env var.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-char-buffer", type=int, default=1200)
    parser.add_argument("--batch-length", type=int, default=8)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--extraction-passes", type=int, default=2)
    return parser.parse_args()


# Split semicolon-delimited dictionary cells into clean token lists.
def split_semicolon_values(text: str) -> list[str]:
    return [tok.strip() for tok in (text or "").split(";") if tok.strip()]


# Load the quality dictionary CSV and group field specifications by publication type.
def load_quality_dictionary(path: Path) -> dict[str, list[dict[str, Any]]]:
    # Read all rows first so we can validate headers before grouping data.
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    required = {
        "publication_type",
        "field",
        "section",
        "criterion_text",
        "entry_guidance",
        "inferred_type",
        "accepted",
    }
    missing = required.difference(rows[0].keys() if rows else set())
    if missing:
        raise ValueError(f"Missing required columns in quality dictionary: {sorted(missing)}")

    # Build a publication-type -> field-spec list map used downstream for prompts/normalisation.
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        pub_type = (row.get("publication_type") or "").strip()
        field = (row.get("field") or "").strip()
        if not pub_type or not field:
            continue
        grouped.setdefault(pub_type, [])
        grouped[pub_type].append(
            {
                "field": field,
                "section": (row.get("section") or "").strip(),
                "criterion_text": (row.get("criterion_text") or "").strip(),
                "entry_guidance": (row.get("entry_guidance") or "").strip(),
                "inferred_type": (row.get("inferred_type") or "").strip(),
                "accepted_values": split_semicolon_values(row.get("accepted") or ""),
            }
        )

    if not grouped:
        raise ValueError(f"No usable rows found in quality dictionary: {path}")
    return grouped


# Collect candidate input JSON files with optional ID and count filtering.
def collect_input_files(input_dir: Path, paper_ids: list[str], limit: int) -> list[Path]:
    files = sorted(input_dir.glob("*.json"))
    if paper_ids:
        wanted = set(paper_ids)
        files = [p for p in files if p.stem in wanted]
    if limit and limit > 0:
        files = files[:limit]
    return files


# Load one upstream text-extraction record.
def load_text_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# Load and parse the JSON schema used for structured-record validation.
def load_schema(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# Merge page-wise text into one LangExtract input string with page markers.
def normalise_text(record: dict[str, Any]) -> str:
    pages = record.get("pages", [])
    chunks: list[str] = []
    for page in pages:
        page_index = page.get("page_index", 0)
        text = (page.get("text") or "").strip()
        if text:
            chunks.append(f"[Page {int(page_index) + 1}]\n{text}")
    return "\n\n".join(chunks).strip()


# Convert LangExtract dataclass objects to JSON-serialisable dictionaries.
def serialise_extraction(extraction: Any) -> dict[str, Any]:
    data = asdict(extraction)
    status = data.get("alignment_status")
    if status is not None:
        data["alignment_status"] = str(status)
    return data


# Build the prompt used to classify publication type before quality extraction.
def build_pubtype_prompt(publication_types: list[str], template: str) -> str:
    options = "\n".join(f"- {name}" for name in publication_types)
    return template.format(options=options)


# Resolve free-form publication-type text to one canonical dictionary key.
def resolve_publication_type(candidate: str, publication_types: list[str]) -> str | None:
    cand = (candidate or "").strip().lower()
    if not cand:
        return None

    # Fast path: exact case-insensitive match.
    exact = {p.lower(): p for p in publication_types}
    if cand in exact:
        return exact[cand]

    # Fallback: substring overlap between prediction and known options.
    for p in publication_types:
        pl = p.lower()
        if pl in cand or cand in pl:
            return p

    # Alias mapping handles common study-design wording variants.
    aliases = [
        ("case-control", "Case Control"),
        ("case control", "Case Control"),
        ("case series", "Case Series & Reports"),
        ("case report", "Case Series & Reports"),
        ("pre-post", "Before-After (Pre-Post) N contr"),
        ("before-after", "Before-After (Pre-Post) N contr"),
        ("randomized", "Controlled Intervention Studies"),
        ("randomised", "Controlled Intervention Studies"),
        ("rct", "Controlled Intervention Studies"),
        ("cross-sectional", "Observ Cohort & Cross sect"),
        ("cross sectional", "Observ Cohort & Cross sect"),
        ("cohort", "Observ Cohort & Cross sect"),
        ("observational", "Observ Cohort & Cross sect"),
    ]
    for key, target in aliases:
        if key in cand and target in publication_types:
            return target
    return None


# Run one LangExtract call with shared OpenAI/runtime parameters.
def run_langextract(
    text: str,
    args: argparse.Namespace,
    prompt_description: str,
    examples: list[Any],
) -> Any:
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    return lx.extract(
        text_or_documents=text,
        prompt_description=prompt_description,
        examples=examples,
        model_id=args.model_id,
        api_key=api_key,
        temperature=args.temperature,
        max_char_buffer=args.max_char_buffer,
        batch_length=args.batch_length,
        max_workers=args.max_workers,
        extraction_passes=args.extraction_passes,
        use_schema_constraints=False,
        fence_output=False,
        show_progress=False,
    )


# Detect publication type from text and return both label and detection trace.
def detect_publication_type(
    text: str,
    args: argparse.Namespace,
    publication_types: list[str],
    pubtype_prompt_template: str,
    pubtype_examples: list[Any],
) -> tuple[str, list[dict[str, Any]]]:
    # First pass: model-based classification using constrained options.
    annotated = run_langextract(
        text=text,
        args=args,
        prompt_description=build_pubtype_prompt(publication_types, pubtype_prompt_template),
        examples=pubtype_examples,
    )
    extracted = [serialise_extraction(x) for x in (annotated.extractions or [])]

    for item in extracted:
        if item.get("extraction_class") == "publication_type":
            resolved = resolve_publication_type(item.get("extraction_text") or "", publication_types)
            if resolved:
                return resolved, extracted

    # Last fallback: try resolving directly from source text when extraction failed.
    fallback = resolve_publication_type(text, publication_types)
    if fallback:
        return fallback, extracted

    raise ValueError(
        "Could not determine publication type automatically. "
        "Use --publication-type to set it explicitly."
    )


# Build the quality-extraction prompt from dictionary specs for one publication type.
def build_quality_prompt(
    publication_type: str,
    field_specs: list[dict[str, Any]],
    template: str,
) -> str:
    lines = []
    for spec in field_specs:
        accepted = ", ".join(spec["accepted_values"]) if spec["accepted_values"] else "as reported"
        criterion = spec["criterion_text"] or spec["entry_guidance"]
        lines.append(
            f"- {spec['field']} | type: {spec['inferred_type']} | accepted: {accepted} | criterion: {criterion}"
        )

    field_block = "\n".join(lines)
    return template.format(
        publication_type=publication_type,
        field_block=field_block,
    )


# Return the first field matching a requested inferred type.
def first_field(
    field_specs: list[dict[str, Any]], inferred_type: str, fallback: str | None = None
) -> str | None:
    for spec in field_specs:
        if spec["inferred_type"] == inferred_type:
            return spec["field"]
    return fallback


# Build few-shot examples tailored to fields available in the loaded dictionary.
def build_quality_examples(field_specs: list[dict[str, Any]]) -> list[Any]:
    binary_field = first_field(field_specs, "binary_ordinal")
    quality_field = first_field(field_specs, "categorical", "quality_assessment")
    notes_field = first_field(field_specs, "string", "notes")

    examples: list[Any] = []
    if binary_field and quality_field:
        examples.append(
            lx.data.ExampleData(
                text=(
                    "The objective was clearly stated, but the participation rate was below 50%. "
                    "Overall quality was judged as fair."
                ),
                extractions=[
                    lx.data.Extraction(
                        extraction_class=binary_field,
                        extraction_text="1 :: objective clearly stated",
                    ),
                    lx.data.Extraction(
                        extraction_class=quality_field,
                        extraction_text="fair :: overall quality was judged as fair",
                    ),
                ],
            )
        )
    if binary_field and notes_field:
        examples.append(
            lx.data.ExampleData(
                text="Randomisation details were unclear and no relevant details were reported.",
                extractions=[
                    lx.data.Extraction(
                        extraction_class=binary_field,
                        extraction_text="NA :: details not reported",
                    ),
                    lx.data.Extraction(
                        extraction_class=notes_field,
                        extraction_text="Details not reported",
                    ),
                ],
            )
        )
    return examples


# Parse "<value> :: <evidence>" style output and keep only the value part.
def parse_value_from_extraction_text(text: str) -> str:
    raw = (text or "").strip()
    for sep in ("::", "||", " - ", " -- "):
        if sep in raw:
            return raw.split(sep, 1)[0].strip()
    return raw


# Check whether "NA" is an allowed value for the current field specification.
def accepted_has_na(spec: dict[str, Any]) -> bool:
    return any(v.strip().upper() == "NA" for v in spec.get("accepted_values", []))


# Normalise raw model text into the schema-compatible type/value for one field.
def normalise_value(raw_value: str, spec: dict[str, Any]) -> Any:
    raw = (raw_value or "").strip()
    raw_l = raw.lower()
    inferred = spec.get("inferred_type", "")
    accepted = spec.get("accepted_values", [])

    # Binary/ordinal fields should resolve to "1", "0", or "NA".
    if inferred == "binary_ordinal":
        if re.search(r"\b1\b", raw):
            return "1"
        if re.search(r"\b0\b", raw):
            return "0"
        if any(h in raw_l for h in NA_HINTS):
            return "NA"
        return raw or "NA"

    # Categorical fields should prefer exact or contained accepted tokens.
    if inferred == "categorical":
        for token in accepted:
            if token.lower() == raw_l:
                return token
        for token in accepted:
            if token.lower() in raw_l and token:
                return token
        if any(h in raw_l for h in NA_HINTS):
            for token in accepted:
                if token.upper() == "NA":
                    return token
            return "NA"
        return raw

    # Integer fields extract the first integer-looking token.
    if inferred == "integer":
        if any(h in raw_l for h in NA_HINTS):
            return "NA"
        m = re.search(r"-?\d+", raw)
        if m:
            return int(m.group(0))
        return raw

    # Hybrid ID fields remain strings unless they are purely numeric.
    if inferred == "integer_or_string_id":
        if re.fullmatch(r"-?\d+", raw):
            return int(raw)
        return raw

    # String fields are preserved verbatim, with optional NA fallback.
    if inferred == "string":
        if not raw and accepted_has_na(spec):
            return "NA"
        return raw

    return raw


# Provide deterministic default values when no extraction is found for a field.
def default_value_for_missing(spec: dict[str, Any]) -> Any:
    inferred = spec.get("inferred_type", "")
    if inferred in {"binary_ordinal", "integer"}:
        return "NA"
    if accepted_has_na(spec):
        return "NA"
    return ""


# Minimal JSON Schema type checker used by the built-in validator.
def _is_type(value: Any, schema_type: str) -> bool:
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float)
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "null":
        return value is None
    return True


# Create shortened value previews for compact validation error messages.
def _short_repr(value: Any, max_len: int = 80) -> str:
    rep = repr(value)
    if len(rep) <= max_len:
        return rep
    return rep[: max_len - 3] + "..."


# Recursively validate a value node against a subset of JSON Schema rules.
def _validate_node(value: Any, schema: dict[str, Any], path: str, errors: list[str]) -> None:
    # Handle anyOf first.
    if "anyOf" in schema:
        branch_errors: list[list[str]] = []
        for option in schema["anyOf"]:
            local: list[str] = []
            _validate_node(value, option, path, local)
            if not local:
                return
            branch_errors.append(local)
        errors.append(f"{path}: value {_short_repr(value)} does not match anyOf options")
        return

    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _is_type(value, expected_type):
        errors.append(f"{path}: expected type '{expected_type}', got {_short_repr(value)}")
        return

    # Validate enum constraints for scalar/string-like nodes.
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {_short_repr(value)} not in enum {schema['enum']}")
        return

    # Validate numeric bounds when schema declares minimum/maximum.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: value {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: value {value} > maximum {schema['maximum']}")

    # Validate regex pattern constraints on string fields.
    if isinstance(value, str) and "pattern" in schema:
        pattern = schema["pattern"]
        if re.search(pattern, value) is None:
            errors.append(f"{path}: value {_short_repr(value)} does not match pattern {pattern}")

    # Validate object structure: required keys, additional keys, and child nodes.
    if isinstance(value, dict):
        props: dict[str, Any] = schema.get("properties", {})
        required: list[str] = schema.get("required", [])
        additional_properties = schema.get("additionalProperties", True)

        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required key '{key}'")

        if additional_properties is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}: additional property '{key}' is not allowed")

        for key, val in value.items():
            if key in props:
                _validate_node(val, props[key], f"{path}.{key}", errors)

    # Validate array items and uniqueness when requested.
    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                _validate_node(item, item_schema, f"{path}[{idx}]", errors)
        if schema.get("uniqueItems"):
            seen = set()
            for item in value:
                marker = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
                if marker in seen:
                    errors.append(f"{path}: duplicate item {_short_repr(item)} not allowed (uniqueItems)")
                    break
                seen.add(marker)


# Validate final structured values against the quality schema.
def validate_record_against_schema(
    values_record: dict[str, Any], publication_type: str, schema: dict[str, Any]
) -> None:
    # Schema expects publication_type alongside values.
    candidate = dict(values_record)
    candidate["publication_type"] = publication_type
    errors: list[str] = []
    _validate_node(candidate, schema, "$", errors)
    if errors:
        preview = "; ".join(errors[:12])
        suffix = f" (and {len(errors) - 12} more)" if len(errors) > 12 else ""
        raise ValueError(f"Schema validation failed: {preview}{suffix}")


# Build structured values/evidence tables from raw LangExtract snippets.
def build_structured_record(
    extractions: list[dict[str, Any]], field_specs: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, list[str]], list[str], list[dict[str, Any]]]:
    field_order = [spec["field"] for spec in field_specs]
    fields_set = set(field_order)

    # Group extraction texts by known field and drop duplicates.
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in extractions:
        cls = item.get("extraction_class")
        txt = (item.get("extraction_text") or "").strip()
        if cls in fields_set and txt and txt not in grouped[cls]:
            grouped[cls].append(txt)

    values: dict[str, Any] = {}
    evidence: dict[str, list[str]] = {}
    missing_fields: list[str] = []

    # Resolve one canonical value per field (first snippet) and keep top evidence snippets.
    spec_by_field = {spec["field"]: spec for spec in field_specs}
    for field in field_order:
        spec = spec_by_field[field]
        snippets = grouped.get(field, [])
        evidence[field] = snippets[:3]
        if snippets:
            raw_value = parse_value_from_extraction_text(snippets[0])
            values[field] = normalise_value(raw_value, spec)
        else:
            values[field] = default_value_for_missing(spec)
            missing_fields.append(field)

    # Preserve model outputs that do not map to dictionary fields for diagnostics.
    unmatched = [
        item
        for item in extractions
        if (item.get("extraction_class") or "") not in fields_set
    ]
    return values, evidence, missing_fields, unmatched


# Process one paper end-to-end: detect type, extract fields, validate, and write outputs.
def process_file(
    path: Path,
    args: argparse.Namespace,
    quality_dict: dict[str, list[dict[str, Any]]],
    publication_types: list[str],
    schema: dict[str, Any] | None,
    prompt_assets: dict[str, Any],
) -> str:
    # Resolve IO paths for this paper and skip if outputs already exist.
    record = load_text_record(path)
    paper_id = str(record.get("paper_id") or path.stem)
    out_raw = args.raw_out_dir / f"{paper_id}.json"
    out_record = args.record_out_dir / f"{paper_id}.json"

    if not args.force and out_raw.exists() and out_record.exists():
        return "skipped"

    # Build model input and stop early on empty text.
    text = normalise_text(record)
    if not text:
        raise ValueError(f"No extractable text found in {path}")

    # Dry-run mode validates file discovery and parsing without API calls.
    if args.dry_run:
        return "validated"

    # Resolve publication type either from explicit CLI override or auto-detection.
    if args.publication_type:
        if args.publication_type not in quality_dict:
            raise ValueError(
                f"Unknown --publication-type '{args.publication_type}'. "
                f"Expected one of: {publication_types}"
            )
        publication_type = args.publication_type
        pubtype_extractions: list[dict[str, Any]] = []
        publication_type_method = "user_override"
    else:
        publication_type, pubtype_extractions = detect_publication_type(
            text=text,
            args=args,
            publication_types=publication_types,
            pubtype_prompt_template=prompt_assets["pubtype_prompt_template"],
            pubtype_examples=prompt_assets["pubtype_examples"],
        )
        publication_type_method = "auto_detected"

    # Run quality extraction using publication-type-specific field definitions.
    field_specs = quality_dict[publication_type]
    annotated = run_langextract(
        text=text,
        args=args,
        prompt_description=build_quality_prompt(
            publication_type,
            field_specs,
            prompt_assets["quality_prompt_template"],
        ),
        examples=build_quality_examples(field_specs),
    )
    extractions = [serialise_extraction(x) for x in (annotated.extractions or [])]

    values, evidence, missing_fields, unmatched = build_structured_record(
        extractions=extractions,
        field_specs=field_specs,
    )

    # Validate typed values against schema before writing outputs.
    if schema is not None and not args.skip_schema_validation:
        validate_record_against_schema(
            values_record=values,
            publication_type=publication_type,
            schema=schema,
        )

    # Write raw extraction payload for traceability and debugging.
    raw_payload = {
        "paper_id": paper_id,
        "source_filename": record.get("source_filename"),
        "source_sha256": record.get("source_sha256"),
        "model_id": args.model_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "publication_type": publication_type,
        "publication_type_method": publication_type_method,
        "publication_type_detections": pubtype_extractions,
        "extraction_count": len(extractions),
        "extractions": extractions,
        "unmatched_extractions": unmatched,
    }
    out_raw.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Write structured quality record for downstream analysis/aggregation.
    record_payload = {
        "paper_id": paper_id,
        "source_filename": record.get("source_filename"),
        "source_sha256": record.get("source_sha256"),
        "model_id": args.model_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "publication_type": publication_type,
        "field_order": [spec["field"] for spec in field_specs],
        "values": values,
        "evidence": evidence,
        "missing_fields": missing_fields,
    }
    out_record.write_text(
        json.dumps(record_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return "processed"


# Entry point: load configs, run batch processing, and report summary stats.
def main() -> None:
    # Parse runtime options and ensure output directories exist.
    args = parse_args()
    args.raw_out_dir.mkdir(parents=True, exist_ok=True)
    args.record_out_dir.mkdir(parents=True, exist_ok=True)
    prompt_assets = load_prompt_assets(args.prompt_dir)

    # Load dictionary and schema context used for every input file.
    quality_dict = load_quality_dictionary(args.quality_dict)
    publication_types = list(quality_dict.keys())
    schema = None if args.skip_schema_validation else load_schema(args.schema_path)

    # Resolve input files and fail fast if none were found.
    files = collect_input_files(args.input_dir, args.paper_id, args.limit)
    if not files:
        raise SystemExit(f"No input JSON files found in: {args.input_dir}")

    # Track outcome counts so batch status is explicit at the end.
    stats = {"processed": 0, "validated": 0, "skipped": 0, "failed": 0}

    # Continue processing even if single files fail.
    for path in tqdm(files, desc="Quality assessment"):
        try:
            outcome = process_file(
                path,
                args,
                quality_dict,
                publication_types,
                schema,
                prompt_assets,
            )
            stats[outcome] = stats.get(outcome, 0) + 1
        except Exception as exc:
            stats["failed"] += 1
            print(f"[ERROR] {path.name}: {exc}")

    # Print run totals for quick CLI monitoring/automation logs.
    print(
        "Run summary:",
        f"processed={stats['processed']}",
        f"validated={stats['validated']}",
        f"skipped={stats['skipped']}",
        f"failed={stats['failed']}",
    )
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )

    if stats["failed"] > 0:
        raise SystemExit(1)


# Standard Python script entry point.
if __name__ == "__main__":
    main()
