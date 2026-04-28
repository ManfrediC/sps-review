from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import langextract as lx
from tqdm import tqdm

from _proceedings_ready import TEXT_PROCEEDINGS_READY_DIR, preferred_proceedings_text_path
from _source_routing import load_csv_rows_by_id, resolve_source_row, truthy
from _stage07_units import build_input_blocks


# Resolve repository-relative paths once so CLI defaults stay stable.
REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "config" / "prompts"
TEXT_JSON_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
CASE_UNITS_DIR = REPO_ROOT / "data" / "extraction_json" / "text_case_series_units"
RAW_OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "langextract"
SUMMARY_OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "summary"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"
SOURCE_CATEGORISATION_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"

# Ensure output folders exist even on first run.
RAW_OUT_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_OUT_DIR.mkdir(parents=True, exist_ok=True)

# Canonical order for individual-level and group-level summaries.
INDIVIDUAL_SECTION_ORDER = [
    "individual_presentation",
    "individual_diagnostics",
    "individual_treatment",
    "individual_outcome",
    "individual_limitations",
]

GROUP_SECTION_ORDER = [
    "group_design",
    "group_characteristics",
    "group_findings",
    "group_treatment_outcomes",
    "group_limitations",
]

# Individual-level prompt (case/patient-level evidence).
DEFAULT_INDIVIDUAL_PROMPT_DESCRIPTION = """
Extract concise, evidence-grounded snippets about individual-level (case-level) data.

Return extraction classes:
- individual_presentation: symptoms, signs, case phenotype, clinical course
- individual_diagnostics: antibodies, CSF, EMG/electrophysiology, MRI, diagnosis details
- individual_treatment: symptomatic or immunotherapy interventions at case level
- individual_outcome: individual response, disability trajectory, follow-up outcomes
- individual_limitations: case-level uncertainty, ambiguity, missing details

Rules:
- Extract only information explicitly stated in the text.
- Keep snippets short and literal when possible.
- Ignore aggregated cohort statistics in this pass.
""".strip()

# Group-level prompt (cohort/aggregate evidence).
DEFAULT_GROUP_PROMPT_DESCRIPTION = """
Extract concise, evidence-grounded snippets about group-level (cohort/aggregate) data.

Return extraction classes:
- group_design: study design, sampling, setting, inclusion framework
- group_characteristics: sample size and aggregate demographics/diagnostic composition
- group_findings: aggregate clinical and investigation findings (counts, percentages, trends)
- group_treatment_outcomes: treatment exposure and aggregate response/outcome patterns
- group_limitations: study-level or cohort-level limitations and caveats

Rules:
- Extract only information explicitly stated in the text.
- Keep snippets short and literal when possible.
- Focus on aggregated data; avoid single-patient anecdotes unless explicitly summarised as cohort findings.
""".strip()


# Build a minimal few-shot example for individual-level extraction.
def default_individual_examples_payload() -> list[dict[str, Any]]:
    # Few-shot guidance: this strongly improves extraction consistency.
    text = (
        "A 45-year-old woman presented with progressive axial stiffness and painful spasms. "
        "EMG showed continuous motor unit activity and serum anti-GAD antibodies were positive. "
        "She received diazepam and monthly IVIG. After 6 months, spasms were less frequent and "
        "she could walk independently with mild residual stiffness."
    )

    return [
        {
            "text": text,
            "extractions": [
                {
                    "extraction_class": "individual_presentation",
                    "extraction_text": "progressive axial stiffness and painful spasms",
                },
                {
                    "extraction_class": "individual_diagnostics",
                    "extraction_text": "EMG showed continuous motor unit activity and serum anti-GAD antibodies were positive",
                },
                {
                    "extraction_class": "individual_treatment",
                    "extraction_text": "received diazepam and monthly IVIG",
                },
                {
                    "extraction_class": "individual_outcome",
                    "extraction_text": "After 6 months, spasms were less frequent and she could walk independently with mild residual stiffness",
                },
            ],
        }
    ]


# Build a minimal few-shot example for group-level extraction.
def default_group_examples_payload() -> list[dict[str, Any]]:
    text = (
        "In this retrospective cohort of 48 patients, 68% had classic SPSD and 28% had partial SPSD. "
        "Mean age was 47 years and 42% were male. Anti-GAD antibodies were detected in 85% of cases. "
        "IVIG was used in 73%, and 38% of treated patients had moderate or marked improvement. "
        "The study was single-centre and retrospective, limiting generalisability."
    )

    return [
        {
            "text": text,
            "extractions": [
                {
                    "extraction_class": "group_design",
                    "extraction_text": "retrospective cohort",
                },
                {
                    "extraction_class": "group_characteristics",
                    "extraction_text": "48 patients, mean age 47 years, 42% male",
                },
                {
                    "extraction_class": "group_findings",
                    "extraction_text": "Anti-GAD antibodies were detected in 85% of cases",
                },
                {
                    "extraction_class": "group_treatment_outcomes",
                    "extraction_text": "IVIG was used in 73%, and 38% of treated patients had moderate or marked improvement",
                },
                {
                    "extraction_class": "group_limitations",
                    "extraction_text": "single-centre and retrospective, limiting generalisability",
                },
            ],
        }
    ]


# Convert example payload dictionaries into LangExtract ExampleData objects.
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


# Load prompt text from file, with fallback to in-code defaults.
def load_prompt_text(path: Path, fallback: str) -> str:
    if not path.exists():
        return fallback
    text = path.read_text(encoding="utf-8").strip()
    return text or fallback


# Load example payload from JSON file, with fallback defaults.
def load_examples_payload(path: Path, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not path.exists():
        return fallback
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Examples JSON must be a list: {path}")


# Resolve all prompt/example assets once per run.
def load_prompt_assets(prompt_dir: Path) -> dict[str, Any]:
    individual_prompt = load_prompt_text(
        prompt_dir / "02_individual_prompt.md",
        DEFAULT_INDIVIDUAL_PROMPT_DESCRIPTION,
    )
    group_prompt = load_prompt_text(
        prompt_dir / "02_group_prompt.md",
        DEFAULT_GROUP_PROMPT_DESCRIPTION,
    )
    individual_examples = to_example_data(
        load_examples_payload(
            prompt_dir / "examples" / "02_individual_examples.json",
            default_individual_examples_payload(),
        )
    )
    group_examples = to_example_data(
        load_examples_payload(
            prompt_dir / "examples" / "02_group_examples.json",
            default_group_examples_payload(),
        )
    )
    return {
        "individual_prompt": individual_prompt,
        "group_prompt": group_prompt,
        "individual_examples": individual_examples,
        "group_examples": group_examples,
    }


# Parse all runtime controls so the script can run single-file or batch modes.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarise extracted paper text JSONs with LangExtract + OpenAI."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=TEXT_JSON_DIR,
        help="Directory containing text extraction JSON files.",
    )
    parser.add_argument(
        "--raw-out-dir",
        type=Path,
        default=RAW_OUT_DIR,
        help="Directory for raw LangExtract outputs.",
    )
    parser.add_argument(
        "--summary-out-dir",
        type=Path,
        default=SUMMARY_OUT_DIR,
        help="Directory for summarised outputs.",
    )
    parser.add_argument(
        "--prompt-dir",
        type=Path,
        default=PROMPTS_DIR,
        help="Directory containing prompt markdown and example JSON files.",
    )
    parser.add_argument(
        "--case-units-dir",
        type=Path,
        default=CASE_UNITS_DIR,
        help="Directory containing stage-07 per-paper unit JSON files.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Paper ID to process (repeat flag for multiple IDs).",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max files to process.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs.")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs only; no API calls.")
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
    parser.add_argument(
        "--ignore-routing",
        action="store_true",
        help="Ignore reviewed routing and process files according to explicit CLI include flags only.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-char-buffer", type=int, default=1200)
    parser.add_argument("--batch-length", type=int, default=8)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--extraction-passes", type=int, default=2)
    parser.add_argument(
        "--include-individual",
        action="store_true",
        help="Run individual-level extraction pass (default: on unless --include-group only).",
    )
    parser.add_argument(
        "--include-group",
        action="store_true",
        help="Run group-level extraction pass (default: on unless --include-individual only).",
    )
    return parser.parse_args()


# Load one upstream text-extraction JSON file.
def load_text_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# Build preferred text record path.
def preferred_text_record_path(path: Path) -> Path:
    return preferred_proceedings_text_path(
        path,
        ready_dir=TEXT_PROCEEDINGS_READY_DIR,
        fallback_trimmed_dir=TEXT_TRIMMED_DIR,
    )


# Load case split record.
def load_case_split_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# Build the exact LangExtract input text for one stage-07 unit.
def build_stage07_unit_input_text(
    unit: dict[str, Any],
    shared_context_by_id: dict[str, dict[str, Any]],
) -> str:
    shared_context_blocks = [
        shared_context_by_id[context_id]
        for context_id in unit.get("linked_shared_context_ids") or []
        if context_id in shared_context_by_id
    ]
    input_blocks = build_input_blocks(unit, shared_context_blocks)
    return "\n\n".join(
        (block.get("text") or "").strip()
        for block in input_blocks
        if (block.get("text") or "").strip()
    ).strip()


# Resolve route.
def resolve_route(
    paper_id: str,
    heuristic_rows: dict[str, dict[str, str]],
    manual_rows: dict[str, dict[str, str]],
) -> dict[str, str]:
    return resolve_source_row(
        paper_id=paper_id,
        heuristic_row=heuristic_rows.get(paper_id, {}),
        manual_row=manual_rows.get(paper_id, {}),
    )


# Build requested modes.
def requested_modes(args: argparse.Namespace, route: dict[str, str]) -> tuple[bool, bool, bool]:
    if args.ignore_routing:
        individual_enabled = should_run_individual(args)
        group_enabled = should_run_group(args)
        return individual_enabled, group_enabled, False

    route_mode = route.get("resolved_langextract_mode") or "manual_review"
    route_eligible = truthy(route.get("resolved_langextract_eligible"))
    if not route_eligible or route_mode in {"skip", "manual_review"}:
        return False, False, False

    if route_mode == "individual_case_split":
        if args.include_group:
            return False, True, False
        return False, False, True

    if args.include_individual or args.include_group:
        return should_run_individual(args), should_run_group(args), False

    if route_mode == "individual":
        return True, False, False
    if route_mode == "group":
        return False, True, False
    return True, True, False


# Convert page-wise text into one model input while preserving page markers.
def normalise_text(record: dict[str, Any]) -> str:
    # Join pages into one document while preserving page boundaries.
    pages = record.get("pages", [])
    chunks: list[str] = []
    for page in pages:
        page_index = page.get("page_index", 0)
        text = (page.get("text") or "").strip()
        if text:
            chunks.append(f"[Page {int(page_index) + 1}]\n{text}")
    return "\n\n".join(chunks).strip()


# Convert LangExtract dataclass objects into plain JSON-serialisable dicts.
def serialise_extraction(extraction: Any) -> dict[str, Any]:
    # LangExtract objects are dataclasses; normalise enum-like fields for JSON.
    data = asdict(extraction)
    status = data.get("alignment_status")
    if status is not None:
        data["alignment_status"] = str(status)
    return data


# Group extracted snippets by target summary section.
def section_texts(
    extractions: list[dict[str, Any]], section_order: list[str]
) -> dict[str, list[str]]:
    # Group snippets by extraction class and drop duplicates.
    grouped: dict[str, list[str]] = {key: [] for key in section_order}
    for item in extractions:
        cls = item.get("extraction_class")
        txt = (item.get("extraction_text") or "").strip()
        if cls in grouped and txt and txt not in grouped[cls]:
            grouped[cls].append(txt)
    return grouped


# Render section summaries using deterministic snippet concatenation.
def render_summary(
    sections: dict[str, list[str]], section_order: list[str]
) -> dict[str, str]:
    # Keep section summaries short and deterministic.
    rendered: dict[str, str] = {}
    for key in section_order:
        snippets = sections.get(key, [])
        rendered[key] = " ".join(snippets[:3]) if snippets else "Not stated."
    return rendered


# Combine section summaries into one compact overall narrative.
def build_overall_summary(
    rendered_sections: dict[str, str], section_order: list[str], labels: dict[str, str]
) -> str:
    parts = []
    for key in section_order:
        label = labels.get(key, key)
        parts.append(f"{label}: {rendered_sections.get(key, 'Not stated.')}")
    return " ".join(parts).strip()


# Summarise extractions.
def summarise_extractions(
    extractions: list[dict[str, Any]],
    section_order: list[str],
    labels: dict[str, str],
) -> tuple[dict[str, str], str]:
    grouped = section_texts(extractions, section_order)
    rendered = render_summary(grouped, section_order)
    overall = build_overall_summary(
        rendered_sections=rendered,
        section_order=section_order,
        labels=labels,
    )
    return rendered, overall


# Run LangExtract with OpenAI settings and return one annotated document.
def run_langextract(
    text: str,
    args: argparse.Namespace,
    prompt_description: str,
    examples: list[Any],
) -> Any:
    # OpenAI path for LangExtract: raw JSON mode is more reliable here.
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


# Decide whether to run the individual-level pass from CLI flags.
def should_run_individual(args: argparse.Namespace) -> bool:
    # If neither flag is set, run both passes by default.
    if not args.include_individual and not args.include_group:
        return True
    return args.include_individual


# Decide whether to run the group-level pass from CLI flags.
def should_run_group(args: argparse.Namespace) -> bool:
    # If neither flag is set, run both passes by default.
    if not args.include_individual and not args.include_group:
        return True
    return args.include_group


# Process one stage-07 per-paper unit file.
def process_case_split_file(
    paper_id: str,
    split_path: Path,
    out_raw: Path,
    out_summary: Path,
    args: argparse.Namespace,
    prompt_assets: dict[str, Any],
    route: dict[str, str],
) -> str:
    split_record = load_case_split_record(split_path)
    publication_decision = split_record.get("publication_decision") or {}
    units = split_record.get("units") or []
    if publication_decision.get("status") == "manual_review_required" or not units:
        return "skipped_stage07_manual_review"

    if args.dry_run:
        return "validated"

    shared_context_by_id = {
        block.get("context_id"): block
        for block in (split_record.get("shared_context_blocks") or [])
        if block.get("context_id")
    }
    unit_runs_raw: list[dict[str, Any]] = []
    unit_runs_summary: list[dict[str, Any]] = []
    mode_counts: dict[str, dict[str, int]] = {}

    for unit in units:
        unit_text = build_stage07_unit_input_text(unit, shared_context_by_id)
        if not unit_text:
            continue
        unit_type = (unit.get("unit_type") or "individual").strip().lower()
        if unit_type == "group":
            prompt_description = prompt_assets["group_prompt"]
            examples = prompt_assets["group_examples"]
            section_order = GROUP_SECTION_ORDER
            labels = {
                "group_design": "Group design",
                "group_characteristics": "Group characteristics",
                "group_findings": "Group findings",
                "group_treatment_outcomes": "Group treatment/outcomes",
                "group_limitations": "Group limitations",
            }
            prompt_mode = "group"
        else:
            prompt_description = prompt_assets["individual_prompt"]
            examples = prompt_assets["individual_examples"]
            section_order = INDIVIDUAL_SECTION_ORDER
            labels = {
                "individual_presentation": "Individual presentation",
                "individual_diagnostics": "Individual diagnostics",
                "individual_treatment": "Individual treatment",
                "individual_outcome": "Individual outcome",
                "individual_limitations": "Individual limitations",
            }
            prompt_mode = "individual"

        annotated = run_langextract(
            text=unit_text,
            args=args,
            prompt_description=prompt_description,
            examples=examples,
        )
        unit_extractions = [serialise_extraction(x) for x in (annotated.extractions or [])]
        rendered, overall = summarise_extractions(
            unit_extractions,
            section_order,
            labels,
        )
        mode_counts.setdefault(prompt_mode, {"unit_count": 0, "extraction_count": 0})
        mode_counts[prompt_mode]["unit_count"] += 1
        mode_counts[prompt_mode]["extraction_count"] += len(unit_extractions)
        unit_runs_raw.append(
            {
                "unit_id": unit.get("unit_id"),
                "unit_order": unit.get("unit_order"),
                "unit_type": unit.get("unit_type"),
                "unit_label": unit.get("unit_label"),
                "prompt_mode": prompt_mode,
                "linked_shared_context_ids": unit.get("linked_shared_context_ids") or [],
                "text_char_count": len(unit_text),
                "extraction_count": len(unit_extractions),
                "extractions": unit_extractions,
            }
        )
        unit_runs_summary.append(
            {
                "unit_id": unit.get("unit_id"),
                "unit_order": unit.get("unit_order"),
                "unit_type": unit.get("unit_type"),
                "unit_label": unit.get("unit_label"),
                "prompt_mode": prompt_mode,
                "section_summaries": rendered,
                "overall_summary": overall,
                "extraction_count": len(unit_extractions),
            }
        )

    raw_payload = {
        "paper_id": paper_id,
        "source_filename": split_record.get("source_filename"),
        "source_sha256": split_record.get("source_sha256"),
        "source_text_json_path": split_record.get("source_text_json_path"),
        "source_case_series_units_path": str(split_path),
        "publication_decision": publication_decision,
        "route": route,
        "model_id": args.model_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "extraction_modes": mode_counts,
        "unit_runs": unit_runs_raw,
        "total_extraction_count": sum(unit_run["extraction_count"] for unit_run in unit_runs_raw),
    }
    out_raw.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_payload = {
        "paper_id": paper_id,
        "source_filename": split_record.get("source_filename"),
        "source_sha256": split_record.get("source_sha256"),
        "source_text_json_path": split_record.get("source_text_json_path"),
        "source_case_series_units_path": str(split_path),
        "publication_decision": publication_decision,
        "route": route,
        "model_id": args.model_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "extraction_modes": mode_counts,
        "unit_runs": unit_runs_summary,
        "total_extraction_count": sum(unit_run["extraction_count"] for unit_run in unit_runs_summary),
    }
    out_summary.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return "processed"


# Process a single paper JSON: extract snippets, then save raw + summary outputs.
def process_file(
    path: Path,
    args: argparse.Namespace,
    prompt_assets: dict[str, Any],
    heuristic_rows: dict[str, dict[str, str]],
    manual_rows: dict[str, dict[str, str]],
) -> str:
    paper_id = path.stem
    route = resolve_route(paper_id, heuristic_rows, manual_rows)
    route_mode = route.get("resolved_langextract_mode") or "manual_review"
    out_raw = args.raw_out_dir / f"{paper_id}.json"
    out_summary = args.summary_out_dir / f"{paper_id}.json"

    # Keep reviewed incorrect references out of downstream extraction explicitly.
    if route_mode == "incorrect_reference" and not args.ignore_routing:
        return "skipped_incorrect_reference"

    # Skip work when outputs already exist unless user forces overwrite.
    if not args.force and out_raw.exists() and out_summary.exists():
        return "skipped"

    individual_enabled, group_enabled, split_enabled = requested_modes(args, route)
    if not individual_enabled and not group_enabled and not split_enabled:
        return "skipped_by_routing"

    if split_enabled:
        split_path = args.case_units_dir / f"{paper_id}.json"
        if not split_path.exists():
            return "skipped_missing_case_split"
        return process_case_split_file(
            paper_id=paper_id,
            split_path=split_path,
            out_raw=out_raw,
            out_summary=out_summary,
            args=args,
            prompt_assets=prompt_assets,
            route=route,
        )

    # Read source record and derive output locations from paper_id.
    source_path = preferred_text_record_path(path)
    record = load_text_record(source_path)

    # Build model input text and guard against empty inputs.
    text = normalise_text(record)
    if not text:
        raise ValueError(f"No extractable text found in {path}")

    # Dry-run validates inputs without spending tokens.
    if args.dry_run:
        return "validated"

    extraction_runs: dict[str, Any] = {}
    summary_runs: dict[str, Any] = {}

    # 1) Individual-level extraction pass.
    if individual_enabled:
        individual_annotated = run_langextract(
            text=text,
            args=args,
            prompt_description=prompt_assets["individual_prompt"],
            examples=prompt_assets["individual_examples"],
        )
        individual_extractions = [
            serialise_extraction(x) for x in (individual_annotated.extractions or [])
        ]
        individual_rendered, individual_overall = summarise_extractions(
            individual_extractions,
            INDIVIDUAL_SECTION_ORDER,
            {
                "individual_presentation": "Individual presentation",
                "individual_diagnostics": "Individual diagnostics",
                "individual_treatment": "Individual treatment",
                "individual_outcome": "Individual outcome",
                "individual_limitations": "Individual limitations",
            },
        )
        extraction_runs["individual"] = {
            "extraction_count": len(individual_extractions),
            "extractions": individual_extractions,
        }
        summary_runs["individual"] = {
            "section_summaries": individual_rendered,
            "overall_summary": individual_overall,
            "extraction_count": len(individual_extractions),
        }

    # 2) Group-level extraction pass.
    if group_enabled:
        group_annotated = run_langextract(
            text=text,
            args=args,
            prompt_description=prompt_assets["group_prompt"],
            examples=prompt_assets["group_examples"],
        )
        group_extractions = [
            serialise_extraction(x) for x in (group_annotated.extractions or [])
        ]
        group_rendered, group_overall = summarise_extractions(
            group_extractions,
            GROUP_SECTION_ORDER,
            {
                "group_design": "Group design",
                "group_characteristics": "Group characteristics",
                "group_findings": "Group findings",
                "group_treatment_outcomes": "Group treatment/outcomes",
                "group_limitations": "Group limitations",
            },
        )
        extraction_runs["group"] = {
            "extraction_count": len(group_extractions),
            "extractions": group_extractions,
        }
        summary_runs["group"] = {
            "section_summaries": group_rendered,
            "overall_summary": group_overall,
            "extraction_count": len(group_extractions),
        }

    # Save full extraction payload for auditability and downstream debugging.
    raw_payload = {
        "paper_id": paper_id,
        "source_filename": record.get("source_filename"),
        "source_sha256": record.get("source_sha256"),
        "source_text_json_path": str(source_path),
        "used_trimmed_text": source_path != path,
        "route": route,
        "model_id": args.model_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "extraction_modes": extraction_runs,
        "total_extraction_count": sum(
            mode_data.get("extraction_count", 0) for mode_data in extraction_runs.values()
        ),
    }
    out_raw.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Save compact summaries for reviewer-facing consumption.
    summary_payload = {
        "paper_id": paper_id,
        "source_filename": record.get("source_filename"),
        "source_sha256": record.get("source_sha256"),
        "source_text_json_path": str(source_path),
        "used_trimmed_text": source_path != path,
        "route": route,
        "model_id": args.model_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "extraction_modes": summary_runs,
        "total_extraction_count": sum(
            mode_data.get("extraction_count", 0) for mode_data in summary_runs.values()
        ),
    }
    out_summary.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return "processed"


# Collect candidate input files, with optional ID filter and row-limit.
def collect_input_files(input_dir: Path, paper_ids: list[str], limit: int) -> list[Path]:
    # Optional filtering lets us run focused tests before full-batch runs.
    files = sorted(input_dir.glob("*.json"))
    if paper_ids:
        wanted = set(paper_ids)
        files = [p for p in files if p.stem in wanted]
    if limit and limit > 0:
        files = files[:limit]
    return files


# Entry point: batch orchestration, error accounting, and run summary reporting.
def main() -> None:
    # Parse args and guarantee output folders exist.
    args = parse_args()
    args.raw_out_dir.mkdir(parents=True, exist_ok=True)
    args.summary_out_dir.mkdir(parents=True, exist_ok=True)
    prompt_assets = load_prompt_assets(args.prompt_dir)
    heuristic_rows = load_csv_rows_by_id(SOURCE_CATEGORISATION_PATH, "paper_id")
    manual_rows = load_csv_rows_by_id(SOURCE_MANUAL_REVIEW_PATH, "paper_id")

    # Resolve input set before running.
    files = collect_input_files(args.input_dir, args.paper_id, args.limit)
    if not files:
        raise SystemExit(f"No input JSON files found in: {args.input_dir}")

    # Track outcomes to give a clear end-of-run status.
    stats = {
        "processed": 0,
        "validated": 0,
        "skipped": 0,
        "skipped_by_routing": 0,
        "skipped_incorrect_reference": 0,
        "skipped_missing_case_split": 0,
        "skipped_stage07_manual_review": 0,
        "failed": 0,
    }

    # Continue past single-paper failures so batch runs are resilient.
    for path in tqdm(files, desc="LangExtract summaries"):
        try:
            outcome = process_file(path, args, prompt_assets, heuristic_rows, manual_rows)
            stats[outcome] = stats.get(outcome, 0) + 1
        except Exception as exc:  # keep batch running even if one paper fails
            # Surface per-paper errors and continue the batch.
            stats["failed"] += 1
            print(f"[ERROR] {path.name}: {exc}")

    # Print machine-readable run totals for quick review.
    print(
        "Run summary:",
        f"processed={stats['processed']}",
        f"validated={stats['validated']}",
        f"skipped={stats['skipped']}",
        f"skipped_by_routing={stats['skipped_by_routing']}",
        f"skipped_incorrect_reference={stats['skipped_incorrect_reference']}",
        f"skipped_missing_case_split={stats['skipped_missing_case_split']}",
        f"skipped_stage07_manual_review={stats['skipped_stage07_manual_review']}",
        f"failed={stats['failed']}",
    )

    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )

    # Non-zero exit code if any file failed, for CI/script chaining.
    if stats["failed"] > 0:
        raise SystemExit(1)


# Standard Python script entry point.
if __name__ == "__main__":
    main()
