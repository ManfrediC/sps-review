"""Build and optionally run Qwen/Ollama single-case extraction packs.

Without --run-ollama this prepares only the local field contract, instruction
reference, paper manifest, and prompt files for review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKBOOK_PATH = Path(
    r"C:\NOS\Stiff Person Review\data extraction forms"
    r"\Stiff Person risk of Bias and Data Extraction Forms_shermyn_2024_09_18.xlsx"
)
DEFAULT_CONTRACT_PATH = REPO_ROOT / "config" / "extraction" / "qwen_case_report_contract.json"
DEFAULT_INSTRUCTION_DOC_PATH = REPO_ROOT / "doc" / "case_report_extraction_instructions.md"
DEFAULT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
DEFAULT_MANUAL_CSV_PATH = REPO_ROOT / "examples" / "datasheet_examples_MC_Case_Report_Form.csv"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "validation" / "ollama_single_case_extraction"
DEFAULT_ENV_PATH = REPO_ROOT / "env" / "ollama_api_key.env"
DEFAULT_RUN_ID = "pilot_10_dry_run"
DEFAULT_MODEL_ID = "qwen3.5:397b-cloud"
DEFAULT_BASE_URL = "https://ollama.com/v1"
CONTRACT_VERSION = "qwen_single_case_contract_v1"
SHEET_NAME = "Case Reports"
FOLLOWUP_FIELD = "Followup_Duration_Months"
FIXED_WORKSHEET_FIELDS = {"extractor", "Reference"}
MISSING_VALUE = "NA"
VERBATIM_QUOTE_FIELD = "verbatim_quote"
ALLOWED_EVIDENCE_TYPES = {"verbatim_quote", "deterministic_derivation", "not_reported"}
DETERMINISTIC_DERIVATION_FIELDS = {
    "age_onset",
    FOLLOWUP_FIELD,
    "time_to_diagnosis",
    "onset_to_established",
}
STRICT_NUMERIC_FIELDS = {
    "age_description",
    "age_onset",
    FOLLOWUP_FIELD,
    "time_to_diagnosis",
    "onset_to_established",
    "onset_mRS",
    "established_mRS",
}
BINARY_FIELDS = {
    "CMUA",
    "exteroceptive_refl",
    "brainstem_refl",
    "MRI_normal",
    "tu_screening",
}
MANUAL_OPTION_FIELDS = {
    "first_manifestation_multiple",
    "first_manifestation_other",
    "early_symptoms",
    "stiffness_distribution_onset_multiple",
    "stiffness_distribution_onset_other",
    "spasms_distribution_onset_multiple",
    "spasms_distribution_onset_other",
    "excessive_startle_onset_multiple",
    "excessive_startle_onset_other",
    "other_symptoms_onset",
    "other_symptoms_onset_auto",
    "other_symptoms_onset_oculo",
    "other_symptoms_onset_seizures",
    "overview_established",
    "stiffness_distribution_established_multiple",
    "stiffness_distribution_established_other",
    "spasms_distribution_established_multiple",
    "spasms_distribution_established_other",
    "excessive_startle_established_multipleother",
    "other_symptoms_established",
    "other_symptoms_established_auto",
    "other_symptoms_established_oculo",
    "other_symptoms_established_seizures",
    "antibody_status_other",
    "antibody_tests",
    "antibody_testsystem",
    "CSF_antibody",
    "immunotherapy",
    "sympt_treatment",
    "other_treatment",
    "autoimmunity",
    "family_history",
}
REVIEWED_SYMPTOM_OPTION_FIELDS = {
    "first_manifestation_multiple",
    "early_symptoms",
    "other_symptoms_onset",
    "overview_established",
    "other_symptoms_established",
}
USER_APPROVED_SYMPTOM_TOKENS = ["fatigue", "tingling"]
USER_APPROVED_ALLOWED_VALUE_OVERRIDES = {
    field_name: USER_APPROVED_SYMPTOM_TOKENS
    for field_name in REVIEWED_SYMPTOM_OPTION_FIELDS
}

FIELD_RENAMES = {
    "first_manifestation_mother": "first_manifestation_other",
    "immuntherapy_detail": "immunotherapy_detail",
}

SYSTEM_PROMPT = (
    "You are the most accurate clinical data-extraction system available, built for "
    "a published systematic review of Stiff-Person Spectrum Disorders (SPSD). You are "
    "given the full text of ONE case report (one patient, or one specified case of a "
    "series) and must extract the requested fields with maximum fidelity.\n"
    "\n"
    "Absolute rules:\n"
    "1. Extract ONLY what the text states. Never guess, infer, or use outside knowledge.\n"
    f'2. If a field is not reported in this paper, the value is exactly "{MISSING_VALUE}".\n'
    "3. Copy numbers, ratios, titres, doses and units VERBATIM - keep "
    '"1:122,000", "250 U/mL", "1/128" exactly; never convert, round, '
    "reformat or split them unless the user prompt explicitly allows arithmetic conversion.\n"
    "4. For categorical fields, return EXACTLY one of the allowed values; if none apply "
    f'or it is not reported, return "{MISSING_VALUE}".\n'
    f"5. Every non-{MISSING_VALUE} value must be supported by a short verbatim quote from the text.\n"
    "6. Hard quote constraint: quote text and any ellipsis fragments must appear in source order. "
    "If you cannot support a value with in-order quoted evidence, use a narrower supported value or "
    f'{MISSING_VALUE}.\n'
    "7. Output strict JSON only - no commentary, no markdown, no extra fields."
)

FOLLOWUP_INSTRUCTION = (
    "Total reported follow-up duration in months. If the paper reports follow-up in "
    f"years, convert to months. If no follow-up duration is reported, use {MISSING_VALUE}. This is "
    "the only permitted numeric conversion; ratios, titres, doses, units, and all "
    "other reported measurements stay verbatim."
)


@dataclass(frozen=True)
class FieldSpec:
    name: str
    section: str
    instruction: str
    source_columns: list[str]
    source_labels: list[str]
    allowed_values: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "section": self.section,
            "instruction": self.instruction,
            "source_columns": self.source_columns,
            "source_labels": self.source_labels,
            "allowed_values": self.allowed_values,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldSpec":
        return cls(
            name=str(data["name"]),
            section=str(data.get("section") or ""),
            instruction=str(data.get("instruction") or ""),
            source_columns=[str(value) for value in data.get("source_columns", [])],
            source_labels=[str(value) for value in data.get("source_labels", [])],
            allowed_values=[str(value) for value in data.get("allowed_values", [])],
        )


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def bool_text(value: str | None) -> bool:
    return str(value or "").strip().lower() == "true"


def normalise_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def column_number(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref)
    if not match:
        raise ValueError(f"invalid cell reference: {cell_ref}")
    value = 0
    for char in match.group(1):
        value = value * 26 + ord(char) - 64
    return value


def column_letters(number: int) -> str:
    value = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        value = chr(65 + remainder) + value
    return value


def xlsx_sheet_rows(path: Path, sheet_name: str, *, n_rows: int | None = None) -> list[dict[int, str]]:
    """Read cell text from a simple XLSX sheet without adding an Excel dependency."""
    ns = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    with zipfile.ZipFile(path) as workbook_zip:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in workbook_zip.namelist():
            shared_root = ET.fromstring(workbook_zip.read("xl/sharedStrings.xml"))
            for shared_item in shared_root.findall("a:si", ns):
                shared_strings.append(
                    "".join(text.text or "" for text in shared_item.findall(".//a:t", ns))
                )

        workbook_root = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
        rels_root = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))
        rels = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root}
        target = None
        for sheet in workbook_root.findall("a:sheets/a:sheet", ns):
            if sheet.attrib["name"] == sheet_name:
                rel_id = sheet.attrib[
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                ]
                target = rels[rel_id]
                break
        if target is None:
            raise ValueError(f"sheet not found: {sheet_name}")

        sheet_path = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
        sheet_root = ET.fromstring(workbook_zip.read(sheet_path))
        rows: list[dict[int, str]] = []
        for row in sheet_root.findall("a:sheetData/a:row", ns):
            cells: dict[int, str] = {}
            for cell in row.findall("a:c", ns):
                value_node = cell.find("a:v", ns)
                value = "" if value_node is None or value_node.text is None else value_node.text
                if cell.attrib.get("t") == "s":
                    value = shared_strings[int(value)]
                elif cell.attrib.get("t") == "inlineStr":
                    value = "".join(text.text or "" for text in cell.findall(".//a:t", ns))
                cells[column_number(cell.attrib["r"])] = value
            rows.append(cells)
            if n_rows is not None and len(rows) >= n_rows:
                break
    return rows


def nearest_section(section_row: dict[int, str], column: int) -> str:
    sections = [
        (col, normalise_space(label))
        for col, label in sorted(section_row.items())
        if normalise_space(label) and "Use this tab" not in label
    ]
    if not sections:
        return ""
    preceding = [item for item in sections if item[0] <= column]
    return (preceding[-1] if preceding else sections[0])[1]


def parse_allowed_values(instruction: str) -> list[str]:
    values: list[str] = []
    for raw_line in instruction.splitlines():
        line = raw_line.strip()
        bullet = re.match(r"-\s*([A-Za-z0-9_]+)\b", line)
        numeric = re.match(r"([0-6])\s*[-=]", line)
        value = (bullet or numeric).group(1) if bullet or numeric else ""
        if value and value not in values:
            values.append(value)
    return values


def normalised_field_name(raw_name: str) -> str:
    raw_name = raw_name.strip()
    if raw_name == "FU_duration":
        return FOLLOWUP_FIELD
    return FIELD_RENAMES.get(raw_name, raw_name)


def short_option_tokens(raw_value: str) -> list[str]:
    tokens: list[str] = []
    for token in re.split(r"[;,]", raw_value):
        token = token.strip()
        if not token or token.upper() in {MISSING_VALUE, "N/A"}:
            continue
        if len(token) <= 40 and re.fullmatch(r"[A-Za-z0-9_./+><-]+", token):
            tokens.append(token)
    return tokens


def field_with_allowed_values(field: FieldSpec, allowed_values: list[str]) -> FieldSpec:
    return FieldSpec(
        name=field.name,
        section=field.section,
        instruction=field.instruction,
        source_columns=field.source_columns,
        source_labels=field.source_labels,
        allowed_values=allowed_values,
    )


def augment_allowed_values_from_manual(fields: list[FieldSpec], manual_csv_path: Path) -> list[FieldSpec]:
    """Add compact option-like manual values without making prose notes categorical."""
    if not manual_csv_path.exists():
        return fields

    rows = read_csv_rows(manual_csv_path)
    if not rows:
        return fields

    additions: dict[str, list[str]] = {
        field_name: list(values)
        for field_name, values in USER_APPROVED_ALLOWED_VALUE_OVERRIDES.items()
    }
    header = [normalised_field_name(name) for name in rows[0]]
    augmentable = {field.name for field in fields if field.allowed_values} | MANUAL_OPTION_FIELDS
    for row in rows[1:]:
        for index, raw_value in enumerate(row):
            if index >= len(header) or header[index] not in augmentable:
                continue
            for token in short_option_tokens(raw_value):
                if token not in additions.setdefault(header[index], []):
                    additions[header[index]].append(token)

    augmented: list[FieldSpec] = []
    for field in fields:
        values = list(field.allowed_values)
        for token in additions.get(field.name, []):
            if token not in values:
                values.append(token)
        augmented.append(field_with_allowed_values(field, values) if values != field.allowed_values else field)
    return augmented


def build_contract_from_workbook(workbook_path: Path) -> list[FieldSpec]:
    rows = xlsx_sheet_rows(workbook_path, SHEET_NAME, n_rows=3)
    if len(rows) < 3:
        raise ValueError(f"{workbook_path} does not contain the expected three header rows")

    section_row, instruction_row, header_row = rows
    followup_columns = [
        col for col, raw_name in sorted(header_row.items()) if raw_name.strip() == "FU_duration"
    ]
    fields: list[FieldSpec] = []
    followup_added = False

    for column, raw_name in sorted(header_row.items()):
        raw_name = raw_name.strip()
        if not raw_name:
            continue

        source_column = column_letters(column)
        if raw_name == "FU_duration":
            if followup_added:
                continue
            fields.append(
                FieldSpec(
                    name=FOLLOWUP_FIELD,
                    section=nearest_section(section_row, column),
                    instruction=FOLLOWUP_INSTRUCTION,
                    source_columns=[column_letters(col) for col in followup_columns],
                    source_labels=[
                        instruction_row.get(col, "").strip()
                        for col in followup_columns
                        if instruction_row.get(col, "").strip()
                    ],
                    allowed_values=[],
                )
            )
            followup_added = True
            continue

        field_name = normalised_field_name(raw_name)
        instruction = instruction_row.get(column, "").strip()
        fields.append(
            FieldSpec(
                name=field_name,
                section=nearest_section(section_row, column),
                instruction=instruction,
                source_columns=[source_column],
                source_labels=[instruction] if instruction else [],
                allowed_values=parse_allowed_values(instruction),
            )
        )

    return fields


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_contract(path: Path, fields: list[FieldSpec], workbook_path: Path) -> None:
    payload = {
        "schema_version": CONTRACT_VERSION,
        "generated_at_utc": now_utc_iso(),
        "source_workbook": str(workbook_path),
        "source_sheet": SHEET_NAME,
        "model_default": DEFAULT_MODEL_ID,
        "fixed_worksheet_fields": sorted(FIXED_WORKSHEET_FIELDS),
        "notes": [
            f"Legacy FU_duration columns are collapsed into {FOLLOWUP_FIELD}.",
            "first_manifestation_mother is corrected to first_manifestation_other.",
            "immuntherapy_detail is corrected to immunotherapy_detail.",
            f"Missing values use {MISSING_VALUE}; N/A is not accepted in this workflow.",
        "Allowed values include compact option-like tokens observed in the manual CSV "
        "plus reviewed symptom tokens surfaced during Qwen pilot review.",
        ],
        "fields": [field.to_dict() for field in fields],
    }
    write_json(path, payload)


def load_contract(path: Path) -> list[FieldSpec]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [FieldSpec.from_dict(item) for item in data["fields"]]


def write_instruction_doc(path: Path, fields: list[FieldSpec], workbook_path: Path) -> None:
    lines = [
        "# Case report extraction instructions",
        "",
        "Generated reference for the Qwen/Ollama single-case extraction pilot.",
        "",
        "## Source",
        "",
        f"- Workbook: `{workbook_path}`",
        f"- Sheet: `{SHEET_NAME}`",
        "- Source rows: row 1 section labels, row 2 human instructions, row 3 machine names",
        "",
        "## Corrections",
        "",
        f"- Replace both legacy `FU_duration` columns with `{FOLLOWUP_FIELD}`.",
        "- Correct `first_manifestation_mother` to `first_manifestation_other`.",
        "- Correct `immuntherapy_detail` to `immunotherapy_detail`.",
        "- Do not include CSV-only fields `included_diagnosis` or `included_diagnosis_specify`.",
        "",
        "## General rules",
        "",
        "- Extract only what the source text states.",
        f"- Use `{MISSING_VALUE}` when a value is not reported; do not use `N/A`.",
        "- Preserve ratios, titres, doses, units, and reported measurements verbatim.",
        "- Every non-missing value must carry a short verbatim source quote.",
        "- If a quote uses ellipsis, post-processing searches the source for its beginning and end and saves the full recovered source span.",
        "- Hard constraint: ellipsis quote fragments must appear in the same source order and refer to the same clinical phase as the field.",
        "- Use worksheet value formats: numeric age/duration/mRS fields are numbers only; binary fields are `0`, `1`, or `NA`.",
        f"- Deterministic arithmetic derivations are allowed only for: {', '.join(sorted(DETERMINISTIC_DERIVATION_FIELDS))}.",
        f"- `{FOLLOWUP_FIELD}` should be normalised to months when a duration is reported in years.",
        "- `case_ID` should use the exact identifier the article gives, whether that is `Case 1`, `Patient 2`, patient initials, etc.",
        "- Separate multiple values inside one cell with semicolons when the field instruction asks for it.",
        "",
        "## Fields",
        "",
    ]
    for index, field in enumerate(fields, start=1):
        lines.extend(
            [
                f"### {index}. `{field.name}`",
                "",
                f"- Section: {field.section or MISSING_VALUE}",
                f"- Source column(s): {', '.join(field.source_columns) or MISSING_VALUE}",
            ]
        )
        if field.source_labels:
            lines.append("- Source label(s):")
            for label in field.source_labels:
                lines.append(f"  - {label.replace(chr(10), ' / ')}")
        if field.allowed_values:
            lines.append(f"- Allowed values parsed from instruction: {', '.join(field.allowed_values)}")
        lines.extend(["", field.instruction or MISSING_VALUE, ""])

    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines)
    content = "\n".join(line.rstrip() for line in content.splitlines()).rstrip() + "\n"
    path.write_text(content, encoding="utf-8")


def read_csv_rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def manual_reference_order(path: Path) -> list[str]:
    rows = read_csv_rows(path)
    if not rows:
        return []
    header = rows[0]
    reference_index = header.index("Reference")
    seen: set[str] = set()
    refs: list[str] = []
    for row in rows[1:]:
        if reference_index >= len(row):
            continue
        paper_id = row[reference_index].strip()
        if paper_id and paper_id not in seen:
            seen.add(paper_id)
            refs.append(paper_id)
    return refs


def load_registry(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row["paper_id"].strip(): row
            for row in csv.DictReader(handle)
            if row.get("paper_id", "").strip()
        }


def eligible_single_case(row: dict[str, str]) -> bool:
    return (
        bool_text(row.get("count_eligible"))
        and row.get("source_category") == "single_case_report"
        and row.get("likely_sps_case_count") == "1"
        and row.get("count_confidence") == "high"
        and not bool_text(row.get("count_manual_review_required"))
    )


def resolve_repo_path(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else REPO_ROOT / path


def source_text_from_json(path: Path) -> tuple[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    pages = sorted(data.get("pages", []), key=lambda item: int(item.get("page_index", 0)))
    parts: list[str] = []
    for page in pages:
        page_number = int(page.get("page_index", 0)) + 1
        parts.append(f"[Page {page_number}]\n{page.get('text', '')}")
    text = "\n\n".join(parts).strip()
    metadata = {
        "paper_id": str(data.get("paper_id") or ""),
        "source_filename": str(data.get("source_filename") or ""),
        "source_sha256": str(data.get("source_sha256") or ""),
        "extractor": str(data.get("extractor") or ""),
        "n_pages": data.get("n_pages"),
    }
    return text, metadata


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def path_for_record(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def build_manifest_records(
    *,
    manual_csv_path: Path,
    registry_path: Path,
    limit: int,
    paper_ids: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    registry = load_registry(registry_path)
    ordered_refs = paper_ids or manual_reference_order(manual_csv_path)
    records: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for manual_order, paper_id in enumerate(ordered_refs, start=1):
        row = registry.get(paper_id)
        if row is None:
            skipped.append({"paper_id": paper_id, "reason": "not_in_stage06_registry"})
            continue
        if not eligible_single_case(row):
            skipped.append({"paper_id": paper_id, "reason": "not_high_confidence_single_case"})
            continue

        text_path = resolve_repo_path(row.get("preferred_text_json_path", ""))
        if not text_path.exists():
            skipped.append({"paper_id": paper_id, "reason": "preferred_text_json_missing"})
            continue

        source_text, text_metadata = source_text_from_json(text_path)
        records.append(
            {
                "paper_id": paper_id,
                "manual_reference_order": manual_order,
                "title": row.get("title", ""),
                "authors": row.get("authors", ""),
                "source_category": row.get("source_category", ""),
                "source_subtype": row.get("source_subtype", ""),
                "likely_sps_case_count": row.get("likely_sps_case_count", ""),
                "count_confidence": row.get("count_confidence", ""),
                "preferred_text_json_path": path_for_record(text_path),
                "preferred_text_source": row.get("preferred_text_source", ""),
                "text_metadata": text_metadata,
                "source_text_sha256": sha256_text(source_text),
                "source_text_chars": len(source_text),
                "selection_reason": "manual_example_high_confidence_single_case_step06",
            }
        )
        if len(records) >= limit:
            break

    return records, skipped


def field_block(field: FieldSpec) -> list[str]:
    lines = [f"- {field.name}"]
    if field.allowed_values:
        lines[0] += f" [allowed: {', '.join(field.allowed_values)}]"
    if field.instruction:
        lines.append(f"  Instruction: {normalise_space(field.instruction)}")
    return lines


def build_user_prompt(
    fields: list[FieldSpec],
    manifest_record: dict[str, Any],
    source_text: str,
    *,
    model_id: str = DEFAULT_MODEL_ID,
) -> str:
    model_fields = [field for field in fields if field.name not in FIXED_WORKSHEET_FIELDS]
    paper_id = manifest_record["paper_id"]
    lines = [
        (
            f"Extract the {len(model_fields)} source-derived Case Reports fields below "
            f"from paper {paper_id}."
        ),
        "",
        "The final worksheet will fill these metadata fields outside the model:",
        f"- extractor: QWEN_{model_id}",
        f"- Reference: {paper_id}",
        "",
        f"Return one JSON entry per requested field, in this exact order. Use {MISSING_VALUE} "
        f"when a field is not reported; never use N/A. Use worksheet value formats: numeric "
        "age, duration, and mRS fields are numbers only; binary fields are 0, 1, or NA.",
        "",
        "For case_ID, use the exact identifier the article gives, whether that is Case 1, "
        "Patient 2, patient initials, etc. If the paper gives no case identifier, use NA; "
        "do not invent one.",
        "",
        "Deterministic arithmetic derivations are allowed only for these fields: "
        f"{', '.join(sorted(DETERMINISTIC_DERIVATION_FIELDS))}. For example, age_onset may "
        "be age at report minus reported disease duration, and Followup_Duration_Months may "
        "convert years to months. The quote must contain the source numbers and derivation "
        "must state the arithmetic. Do not convert any other measurements.",
        "",
        "Hard quote constraint: every quote must be recoverable from the source text in "
        "source order. If you use ellipsis, each fragment must appear after the previous "
        "fragment and must refer to the same clinical phase as the field, such as onset "
        "versus established disease. Do not stitch onset-history evidence into "
        "established-disease fields. If you cannot support a value with in-order quoted "
        "evidence, use a narrower supported value or NA.",
        "",
        "Fields:",
    ]
    for field in model_fields:
        lines.extend(field_block(field))

    lines.extend(
        [
            "",
            "Return strict JSON only, this exact shape:",
            "{",
            f'  "paper_id": "{paper_id}",',
            '  "extractions": [',
            (
                '    {"field_name": "...", "value": "...", "verbatim_quote": "...", '
                '"evidence_type": "verbatim_quote|deterministic_derivation|not_reported", '
                '"derivation": "NA or arithmetic expression using quoted source values", '
                '"confidence": "high|medium|low"}'
            ),
            "  ]",
            "}",
            "",
            "For value NA, set verbatim_quote to NA, evidence_type to not_reported, and "
            "derivation to NA. For every other value, verbatim_quote must be a contiguous "
            "verbatim quote from the paper text or an ellipsis quote whose fragments appear "
            "in source order.",
            "",
            "Step 06 metadata:",
            json.dumps(
                {
                    "paper_id": paper_id,
                    "title": manifest_record.get("title", ""),
                    "authors": manifest_record.get("authors", ""),
                    "source_category": manifest_record.get("source_category", ""),
                    "source_subtype": manifest_record.get("source_subtype", ""),
                    "likely_sps_case_count": manifest_record.get("likely_sps_case_count", ""),
                    "count_confidence": manifest_record.get("count_confidence", ""),
                },
                ensure_ascii=False,
                indent=2,
            ),
            "",
            "Paper text:",
            source_text,
        ]
    )
    return "\n".join(lines)


def build_prompt(
    fields: list[FieldSpec],
    manifest_record: dict[str, Any],
    source_text: str,
    *,
    model_id: str = DEFAULT_MODEL_ID,
) -> str:
    return "\n".join(
        [
            "# System message",
            "",
            SYSTEM_PROMPT,
            "",
            "# User message",
            "",
            build_user_prompt(fields, manifest_record, source_text, model_id=model_id),
        ]
    )


def write_manifest_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_prompt_packs(
    *,
    run_dir: Path,
    fields: list[FieldSpec],
    manifest_records: list[dict[str, Any]],
    model_id: str = DEFAULT_MODEL_ID,
) -> list[dict[str, Any]]:
    prompt_dir = run_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_records: list[dict[str, Any]] = []
    for record in manifest_records:
        text_path = resolve_repo_path(str(record["preferred_text_json_path"]))
        source_text, _metadata = source_text_from_json(text_path)
        prompt = build_prompt(fields, record, source_text, model_id=model_id)
        prompt_path = prompt_dir / f"{record['paper_id']}.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        prompt_records.append(
            {
                "paper_id": record["paper_id"],
                "prompt_path": path_for_record(prompt_path),
                "prompt_sha256": sha256_text(prompt),
                "prompt_chars": len(prompt),
            }
        )
    return prompt_records


def load_ollama_api_key(env_path: Path) -> str:
    if not env_path.exists():
        raise FileNotFoundError(f"Ollama API key file not found: {env_path}")
    value = ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("OLLAMA_API_KEY="):
            value = line.split("=", 1)[1].strip()
            break
    if not value:
        raise RuntimeError(f"OLLAMA_API_KEY is missing or empty in {env_path}")
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RuntimeError("OLLAMA_API_KEY contains non-ASCII characters") from exc
    if any(char.isspace() for char in value) or len(value) > 200:
        raise RuntimeError("OLLAMA_API_KEY looks malformed")
    return value


def call_ollama_cloud(
    *,
    api_key: str,
    base_url: str,
    model_id: str,
    user_prompt: str,
    timeout_seconds: int,
    max_retries: int,
) -> str:
    try:
        import openai as openai_module
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The openai package is required for Ollama Cloud calls") from exc

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout_seconds)
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except (openai_module.APITimeoutError, openai_module.APIConnectionError) as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(5 * attempt)
        except openai_module.RateLimitError as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(30 * attempt)
    raise last_error if last_error is not None else RuntimeError("Unknown Ollama call failure")


def parse_model_json(raw_text: str) -> tuple[dict[str, Any] | None, str | None]:
    text = raw_text.strip()
    if not text:
        return None, "empty_response"
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None, None if isinstance(data, dict) else "json_not_object"
    except json.JSONDecodeError:
        pass

    # Some OpenAI-compatible services still wrap JSON despite response_format.
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        data = json.loads(fenced)
        return data if isinstance(data, dict) else None, None if isinstance(data, dict) else "json_not_object"
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None, None if isinstance(data, dict) else "json_not_object"
        except json.JSONDecodeError as exc:
            return None, f"json_parse_error: {exc}"
    return None, "json_object_not_found"


def model_field_names(fields: list[FieldSpec]) -> list[str]:
    return [field.name for field in fields if field.name not in FIXED_WORKSHEET_FIELDS]


def is_missing_value(value: str) -> bool:
    return value.strip().upper() == MISSING_VALUE


def is_forbidden_missing_variant(value: str) -> bool:
    return value.strip().upper() == "N/A"


def allowed_value_tokens(value: str) -> list[str]:
    return [token.strip() for token in re.split(r"[;,]", value) if token.strip()]


QUOTE_CHAR_REPLACEMENTS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u00a0": " ",
}
MAX_SALVAGE_SPAN_CHARS = 6000
MAX_GAPPED_FRAGMENT_CHARS = 600


def quote_match_text_with_map(value: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    index_map: list[int] = []
    index = 0
    while index < len(value):
        page_match = re.match(r"\[Page\s+\d+\]", value[index:])
        if page_match:
            if chars and chars[-1] != " ":
                chars.append(" ")
                index_map.append(index)
            index += len(page_match.group(0))
            continue

        raw_char = value[index]
        char = QUOTE_CHAR_REPLACEMENTS.get(raw_char, raw_char)
        if char == "-" and chars and chars[-1].isalpha():
            next_index = index + 1
            while next_index < len(value) and value[next_index].isspace():
                next_index += 1
            if next_index > index + 1 and next_index < len(value):
                next_char = QUOTE_CHAR_REPLACEMENTS.get(value[next_index], value[next_index])
                if next_char.isalpha():
                    index = next_index
                    continue
        if char.isspace():
            if chars and chars[-1] != " ":
                chars.append(" ")
                index_map.append(index)
            index += 1
            continue
        chars.append(char)
        index_map.append(index)
        index += 1

    start = 0
    end = len(chars)
    while start < end and chars[start] == " ":
        start += 1
    while end > start and chars[end - 1] == " ":
        end -= 1
    return "".join(chars[start:end]), index_map[start:end]


def quote_match_text(value: str) -> str:
    return quote_match_text_with_map(value)[0]


def quote_in_source(quote: str, source_text: str) -> bool:
    return quote_match_text(quote) in quote_match_text(source_text)


def identifier_in_source(identifier: str, source_text: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9]){re.escape(identifier)}(?![A-Za-z0-9])"
    return re.search(pattern, quote_match_text(source_text), flags=re.IGNORECASE) is not None


def ellipsis_fragments(quote: str) -> list[str]:
    return [normalise_space(fragment) for fragment in re.split(r"\s*(?:\.{3}|\u2026)\s*", quote) if fragment.strip()]


def has_ellipsis(quote: str) -> bool:
    return bool(re.search(r"\.{3}|\u2026", quote))


def match_record(
    *,
    fragment: str,
    source_text: str,
    source_norm: str,
    source_map: list[int],
    norm_start: int,
    norm_end: int,
    match_type: str,
    score: float,
) -> dict[str, Any]:
    char_start = source_map[norm_start]
    char_end = source_map[norm_end - 1] + 1
    return {
        "text": normalise_space(fragment),
        "matched_in_source": True,
        "match_type": match_type,
        "score": round(score, 3),
        "char_start": char_start,
        "char_end": char_end,
        "source_text": normalise_space(source_text[char_start:char_end]),
        "_norm_start": norm_start,
        "_norm_end": norm_end,
    }


def strip_internal_match_keys(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if not key.startswith("_")}


def exact_match_fragment(
    fragment: str,
    source_text: str,
    source_norm: str,
    source_map: list[int],
    *,
    start_norm: int = 0,
    end_norm: int | None = None,
) -> dict[str, Any] | None:
    fragment_norm = quote_match_text(fragment)
    if not fragment_norm:
        return None
    haystack = source_norm[:end_norm] if end_norm is not None else source_norm
    norm_start = haystack.find(fragment_norm, start_norm)
    match_type = "exact"
    if norm_start < 0:
        norm_start = haystack.casefold().find(fragment_norm.casefold(), start_norm)
        match_type = "exact_case_insensitive"
    if norm_start < 0:
        return None
    norm_end = norm_start + len(fragment_norm)
    return match_record(
        fragment=fragment,
        source_text=source_text,
        source_norm=source_norm,
        source_map=source_map,
        norm_start=norm_start,
        norm_end=norm_end,
        match_type=match_type,
        score=1.0,
    )


def fuzzy_threshold(length: int) -> float:
    if length < 12:
        return 1.1
    if length < 30:
        return 0.9
    if length < 90:
        return 0.86
    return 0.82


def fuzzy_match_fragment(
    fragment: str,
    source_text: str,
    source_norm: str,
    source_map: list[int],
    *,
    start_norm: int = 0,
    end_norm: int | None = None,
) -> dict[str, Any] | None:
    fragment_norm = quote_match_text(fragment)
    if not fragment_norm:
        return None
    threshold = fuzzy_threshold(len(fragment_norm))
    if threshold > 1:
        return None

    source_end = len(source_norm) if end_norm is None else min(end_norm, len(source_norm))
    if start_norm >= source_end:
        return None
    fragment_fold = fragment_norm.casefold()
    source_fold = source_norm.casefold()
    window_sizes = sorted(
        {
            max(4, int(len(fragment_norm) * 0.75)),
            len(fragment_norm),
            len(fragment_norm) + 6,
            int(len(fragment_norm) * 1.25) + 2,
        }
    )
    step = max(1, len(fragment_norm) // 6)
    best: tuple[float, int, int] = (0.0, -1, -1)
    for norm_start in range(start_norm, source_end, step):
        for window_size in window_sizes:
            norm_end = min(source_end, norm_start + window_size)
            if norm_end <= norm_start:
                continue
            score = SequenceMatcher(None, fragment_fold, source_fold[norm_start:norm_end]).ratio()
            if score > best[0]:
                best = (score, norm_start, norm_end)

    if best[0] < threshold:
        return None

    refine_start = max(start_norm, best[1] - step)
    refine_end = min(source_end, best[1] + step + 1)
    for norm_start in range(refine_start, refine_end):
        for window_size in window_sizes:
            norm_end = min(source_end, norm_start + window_size)
            score = SequenceMatcher(None, fragment_fold, source_fold[norm_start:norm_end]).ratio()
            if score > best[0]:
                best = (score, norm_start, norm_end)

    return match_record(
        fragment=fragment,
        source_text=source_text,
        source_norm=source_norm,
        source_map=source_map,
        norm_start=best[1],
        norm_end=best[2],
        match_type="fuzzy",
        score=best[0],
    )


def gapped_fragment_edges(fragment: str) -> tuple[str, str] | None:
    words = normalise_space(fragment).split()
    if len(words) < 4:
        return None
    begin = " ".join(words[:2])
    end = " ".join(words[-2:])
    if len(begin) < 6 or len(end) < 8 or begin == end:
        return None
    return begin, end


def gapped_match_fragment(
    fragment: str,
    source_text: str,
    source_norm: str,
    source_map: list[int],
    *,
    start_norm: int = 0,
    end_norm: int | None = None,
) -> dict[str, Any] | None:
    edges = gapped_fragment_edges(fragment)
    if not edges:
        return None
    source_end = len(source_norm) if end_norm is None else min(end_norm, len(source_norm))
    begin = exact_match_fragment(
        edges[0],
        source_text,
        source_norm,
        source_map,
        start_norm=start_norm,
        end_norm=source_end,
    )
    if not begin:
        return None
    end_search_end = min(source_end, begin["_norm_end"] + MAX_GAPPED_FRAGMENT_CHARS)
    end = exact_match_fragment(
        edges[1],
        source_text,
        source_norm,
        source_map,
        start_norm=begin["_norm_end"],
        end_norm=end_search_end,
    )
    if not end:
        return None
    return match_record(
        fragment=fragment,
        source_text=source_text,
        source_norm=source_norm,
        source_map=source_map,
        norm_start=begin["_norm_start"],
        norm_end=end["_norm_end"],
        match_type="gapped",
        score=round((begin["score"] + end["score"]) / 2, 3),
    )


def find_fragment_match(
    fragment: str,
    source_text: str,
    source_norm: str,
    source_map: list[int],
    *,
    start_norm: int = 0,
    end_norm: int | None = None,
) -> dict[str, Any] | None:
    return exact_match_fragment(
        fragment,
        source_text,
        source_norm,
        source_map,
        start_norm=start_norm,
        end_norm=end_norm,
    ) or gapped_match_fragment(
        fragment,
        source_text,
        source_norm,
        source_map,
        start_norm=start_norm,
        end_norm=end_norm,
    ) or fuzzy_match_fragment(
        fragment,
        source_text,
        source_norm,
        source_map,
        start_norm=start_norm,
        end_norm=end_norm,
    )


def quote_edge_fragments(quote: str) -> tuple[str, str] | None:
    words = normalise_space(quote).split()
    if len(words) < 6:
        return None
    begin = " ".join(words[: min(6, len(words) - 2)])
    end = " ".join(words[-2:])
    if len(begin) < 12 or len(end) < 8 or begin == end:
        return None
    return begin, end


def source_span_from_begin_end(
    *,
    begin_fragment: str,
    end_fragment: str,
    source_text: str,
    source_norm: str,
    source_map: list[int],
    method_prefix: str,
) -> dict[str, Any] | None:
    begin = find_fragment_match(begin_fragment, source_text, source_norm, source_map)
    if not begin:
        return None
    end_search_start = begin["_norm_end"]
    end_search_end = min(len(source_norm), end_search_start + MAX_SALVAGE_SPAN_CHARS)
    end = find_fragment_match(
        end_fragment,
        source_text,
        source_norm,
        source_map,
        start_norm=end_search_start,
        end_norm=end_search_end,
    )
    if not end:
        return None

    method = f"{method_prefix}_exact_span"
    if begin["match_type"] == "fuzzy" or end["match_type"] == "fuzzy":
        method = f"{method_prefix}_fuzzy_span"
    span_start = begin["char_start"]
    span_end = end["char_end"]
    return {
        "status": "salvaged",
        "method": method,
        "source_text": normalise_space(source_text[span_start:span_end]),
        "char_start": span_start,
        "char_end": span_end,
        "begin_fragment": strip_internal_match_keys(begin),
        "end_fragment": strip_internal_match_keys(end),
    }


def quote_fragment_records(quote: str, source_text: str) -> list[dict[str, Any]]:
    if not quote.strip() or is_missing_value(quote):
        return []
    source_norm, source_map = quote_match_text_with_map(source_text)
    full_match = exact_match_fragment(quote, source_text, source_norm, source_map)
    if full_match:
        full_match["match_type"] = "full_quote"
        full_match["in_source_order"] = True
        return [strip_internal_match_keys(full_match)]

    if not has_ellipsis(quote):
        fuzzy = fuzzy_match_fragment(quote, source_text, source_norm, source_map)
        if fuzzy:
            fuzzy["match_type"] = "full_quote_fuzzy"
            fuzzy["in_source_order"] = True
            return [strip_internal_match_keys(fuzzy)]

        edge_fragments = quote_edge_fragments(quote)
        if edge_fragments:
            span = source_span_from_begin_end(
                begin_fragment=edge_fragments[0],
                end_fragment=edge_fragments[1],
                source_text=source_text,
                source_norm=source_norm,
                source_map=source_map,
                method_prefix="begin_end",
            )
            if span:
                begin = dict(span["begin_fragment"], match_type="full_quote_begin_fragment", in_source_order=True)
                end = dict(span["end_fragment"], match_type="full_quote_end_fragment", in_source_order=True)
                return [begin, end]

        return [
            {
                "text": quote,
                "matched_in_source": False,
                "match_type": "full_quote_not_found",
                "score": 0.0,
                "in_source_order": False,
            }
        ]

    fragments: list[dict[str, Any]] = []
    search_start = 0
    for fragment in ellipsis_fragments(quote):
        match = find_fragment_match(fragment, source_text, source_norm, source_map, start_norm=search_start)
        if match:
            match["match_type"] = f"ellipsis_fragment_{match['match_type']}"
            match["in_source_order"] = True
            search_start = match["_norm_end"]
            fragments.append(strip_internal_match_keys(match))
        else:
            unordered_match = find_fragment_match(fragment, source_text, source_norm, source_map)
            if unordered_match:
                unordered_match["match_type"] = f"ellipsis_fragment_{unordered_match['match_type']}_unordered"
                unordered_match["in_source_order"] = False
                fragments.append(strip_internal_match_keys(unordered_match))
            else:
                fragments.append(
                    {
                        "text": fragment,
                        "matched_in_source": False,
                        "match_type": "ellipsis_fragment_not_found",
                        "score": 0.0,
                        "in_source_order": False,
                    }
                )
    return fragments


def quote_source_span_record(quote: str, source_text: str) -> dict[str, Any]:
    empty = {
        "status": "not_applicable",
        "method": "none",
        "source_text": MISSING_VALUE,
        "char_start": None,
        "char_end": None,
    }
    if not quote.strip() or is_missing_value(quote):
        return empty

    source_norm, source_map = quote_match_text_with_map(source_text)
    exact = exact_match_fragment(quote, source_text, source_norm, source_map)
    if exact:
        return {
            "status": "exact",
            "method": exact["match_type"],
            "source_text": exact["source_text"],
            "char_start": exact["char_start"],
            "char_end": exact["char_end"],
            "score": exact["score"],
        }

    if not has_ellipsis(quote):
        fuzzy = fuzzy_match_fragment(quote, source_text, source_norm, source_map)
        if fuzzy:
            return {
                "status": "salvaged",
                "method": "fuzzy_full_quote",
                "source_text": fuzzy["source_text"],
                "char_start": fuzzy["char_start"],
                "char_end": fuzzy["char_end"],
                "score": fuzzy["score"],
            }
        edge_fragments = quote_edge_fragments(quote)
        if edge_fragments:
            span = source_span_from_begin_end(
                begin_fragment=edge_fragments[0],
                end_fragment=edge_fragments[1],
                source_text=source_text,
                source_norm=source_norm,
                source_map=source_map,
                method_prefix="begin_end",
            )
            if span:
                return span
        return {**empty, "status": "failed", "method": "full_quote_not_found"}

    fragments = ellipsis_fragments(quote)
    if len(fragments) < 2:
        return {**empty, "status": "failed", "method": "ellipsis_needs_begin_and_end"}

    span = source_span_from_begin_end(
        begin_fragment=fragments[0],
        end_fragment=fragments[-1],
        source_text=source_text,
        source_norm=source_norm,
        source_map=source_map,
        method_prefix="ellipsis",
    )
    if not span:
        return {**empty, "status": "failed", "method": "ellipsis_end_not_found"}
    return span


def attach_quote_fragments(data: dict[str, Any] | None, source_text: str) -> None:
    if not data or not isinstance(data.get("extractions"), list):
        return
    for item in data["extractions"]:
        if not isinstance(item, dict):
            continue
        quote = str(item.get(VERBATIM_QUOTE_FIELD, "")).strip()
        item["verbatim_quote_exact"] = bool(quote and not is_missing_value(quote) and quote_in_source(quote, source_text))
        item["verbatim_quote_fragments"] = quote_fragment_records(quote, source_text)
        item["verbatim_quote_source_span"] = quote_source_span_record(quote, source_text)


def validate_model_output(
    data: dict[str, Any] | None,
    *,
    paper_id: str,
    expected_fields: list[str],
    parse_error: str | None,
    field_specs: list[FieldSpec] | None = None,
    source_text: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    specs_by_name = {field.name: field for field in field_specs or []}
    if parse_error:
        errors.append(parse_error)
    if data is None:
        return {
            "status": "failed",
            "errors": errors or ["missing_parsed_json"],
            "warnings": warnings,
            "missing_fields": expected_fields,
            "extra_fields": [],
            "duplicate_fields": [],
            "quote_missing_fields": [],
            "quote_not_in_source_fields": [],
            "quote_fragmented_fields": [],
            "quote_unordered_fragment_fields": [],
            "quote_salvaged_fields": [],
            "invalid_value_fields": [],
        }

    if str(data.get("paper_id", "")).strip() != paper_id:
        errors.append("paper_id_mismatch")
    extractions = data.get("extractions")
    if not isinstance(extractions, list):
        errors.append("extractions_not_list")
        extractions = []

    seen: dict[str, int] = {}
    quote_missing: list[str] = []
    quote_not_in_source: list[str] = []
    quote_fragmented: list[str] = []
    quote_unordered_fragments: list[str] = []
    quote_salvaged: list[str] = []
    invalid_values: list[str] = []
    malformed_items: list[str] = []
    for item in extractions:
        if not isinstance(item, dict):
            warnings.append("non_object_extraction_item")
            continue
        field_name = str(item.get("field_name", "")).strip()
        seen[field_name] = seen.get(field_name, 0) + 1
        value = str(item.get("value", "")).strip()
        quote = str(item.get(VERBATIM_QUOTE_FIELD, "")).strip()
        evidence_type = str(item.get("evidence_type", "")).strip()
        derivation = str(item.get("derivation", "")).strip()

        if is_forbidden_missing_variant(value) or is_forbidden_missing_variant(quote):
            invalid_values.append(field_name or "<missing_field_name>")
        if VERBATIM_QUOTE_FIELD not in item or "evidence_type" not in item or "derivation" not in item:
            malformed_items.append(field_name or "<missing_field_name>")
        if evidence_type not in ALLOWED_EVIDENCE_TYPES:
            invalid_values.append(field_name or "<missing_field_name>")
        if is_missing_value(value):
            if not is_missing_value(quote) or evidence_type != "not_reported":
                invalid_values.append(field_name or "<missing_field_name>")
            continue

        if quote == "" or is_missing_value(quote):
            quote_missing.append(field_name)
        elif source_text is not None and not quote_in_source(quote, source_text):
            fragments = quote_fragment_records(quote, source_text)
            fragments_all_matched = bool(fragments) and all(fragment["matched_in_source"] for fragment in fragments)
            fragments_unordered = any(
                fragment["matched_in_source"] and not fragment.get("in_source_order", True)
                for fragment in fragments
            )
            if fragments_unordered:
                if fragments_all_matched:
                    quote_fragmented.append(field_name)
                quote_unordered_fragments.append(field_name)
                quote_not_in_source.append(field_name)
            else:
                span = quote_source_span_record(quote, source_text)
                if span["status"] == "salvaged":
                    quote_salvaged.append(field_name)
                    if has_ellipsis(quote):
                        quote_fragmented.append(field_name)
                else:
                    if fragments_all_matched:
                        quote_fragmented.append(field_name)
                    quote_not_in_source.append(field_name)

        if evidence_type == "deterministic_derivation":
            if field_name not in DETERMINISTIC_DERIVATION_FIELDS or is_missing_value(derivation):
                invalid_values.append(field_name or "<missing_field_name>")
        elif not is_missing_value(derivation):
            invalid_values.append(field_name or "<missing_field_name>")

        if field_name == "case_ID" and source_text is not None and not identifier_in_source(value, source_text):
            invalid_values.append(field_name)
        if field_name in STRICT_NUMERIC_FIELDS and not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
            invalid_values.append(field_name)
        if field_name in BINARY_FIELDS and value not in {"0", "1"}:
            invalid_values.append(field_name)

        field_spec = specs_by_name.get(field_name)
        if field_spec and field_spec.allowed_values:
            allowed = set(field_spec.allowed_values)
            if any(token not in allowed for token in allowed_value_tokens(value)):
                invalid_values.append(field_name)

    expected_set = set(expected_fields)
    seen_set = {name for name in seen if name}
    missing = [name for name in expected_fields if name not in seen_set]
    extra = sorted(name for name in seen_set if name not in expected_set)
    duplicate = sorted(name for name, count in seen.items() if name and count > 1)
    if missing:
        errors.append("missing_fields")
    if extra:
        errors.append("extra_fields")
    if duplicate:
        errors.append("duplicate_fields")
    if quote_missing:
        errors.append("quote_missing_for_non_na_values")
    if quote_not_in_source:
        errors.append("quote_not_in_source")
    if quote_unordered_fragments:
        errors.append("quote_fragments_out_of_order")
    if quote_fragmented:
        warnings.append("quote_fragmented_but_fragments_found")
    if quote_salvaged:
        warnings.append("quote_salvaged_from_source_span")
    if malformed_items:
        errors.append("malformed_extraction_items")
    if invalid_values:
        errors.append("invalid_values")

    return {
        "status": "failed" if errors else "passed",
        "errors": errors,
        "warnings": warnings,
        "missing_fields": missing,
        "extra_fields": extra,
        "duplicate_fields": duplicate,
        "quote_missing_fields": quote_missing,
        "quote_not_in_source_fields": sorted(set(quote_not_in_source)),
        "quote_fragmented_fields": sorted(set(quote_fragmented)),
        "quote_unordered_fragment_fields": sorted(set(quote_unordered_fragments)),
        "quote_salvaged_fields": sorted(set(quote_salvaged)),
        "invalid_value_fields": sorted(set(invalid_values)),
        "malformed_item_fields": sorted(set(malformed_items)),
    }


def extraction_values(data: dict[str, Any] | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if not data or not isinstance(data.get("extractions"), list):
        return values
    for item in data["extractions"]:
        if isinstance(item, dict):
            field_name = str(item.get("field_name", "")).strip()
            if field_name and field_name not in values:
                values[field_name] = str(item.get("value", "")).strip()
    return values


def write_extractions_csv(
    *,
    run_dir: Path,
    fields: list[FieldSpec],
    actual_records: list[dict[str, Any]],
    model_id: str,
) -> None:
    csv_path = run_dir / "qwen_extractions.csv"
    field_names = [field.name for field in fields]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_names)
        writer.writeheader()
        for record in actual_records:
            if record.get("status") != "passed":
                continue
            values = extraction_values(record.get("parsed_response"))
            row = {name: values.get(name, MISSING_VALUE) for name in field_names}
            row["extractor"] = f"QWEN_{model_id}"
            row["Reference"] = record["paper_id"]
            writer.writerow(row)


def run_ollama_batch(
    *,
    run_dir: Path,
    fields: list[FieldSpec],
    manifest_records: list[dict[str, Any]],
    env_path: Path,
    base_url: str,
    model_id: str,
    timeout_seconds: int,
    max_retries: int,
) -> list[dict[str, Any]]:
    api_key = load_ollama_api_key(env_path)
    raw_dir = run_dir / "raw"
    parsed_dir = run_dir / "parsed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)
    expected_fields = model_field_names(fields)
    actual_records: list[dict[str, Any]] = []

    for manifest_record in manifest_records:
        paper_id = manifest_record["paper_id"]
        text_path = resolve_repo_path(str(manifest_record["preferred_text_json_path"]))
        source_text, _metadata = source_text_from_json(text_path)
        user_prompt = build_user_prompt(fields, manifest_record, source_text, model_id=model_id)
        raw_payload: dict[str, Any] = {
            "paper_id": paper_id,
            "model_id": model_id,
            "base_url": base_url,
            "requested_at_utc": now_utc_iso(),
            "user_prompt_sha256": sha256_text(user_prompt),
        }
        try:
            raw_response = call_ollama_cloud(
                api_key=api_key,
                base_url=base_url,
                model_id=model_id,
                user_prompt=user_prompt,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
            raw_payload["raw_response"] = raw_response
            raw_payload["received_at_utc"] = now_utc_iso()
            parsed, parse_error = parse_model_json(raw_response)
            attach_quote_fragments(parsed, source_text)
            validation = validate_model_output(
                parsed,
                paper_id=paper_id,
                expected_fields=expected_fields,
                parse_error=parse_error,
                field_specs=fields,
                source_text=source_text,
            )
            status = validation["status"]
        except Exception as exc:  # The raw file is the audit trail for failed calls.
            raw_payload["error"] = f"{type(exc).__name__}: {exc}"
            raw_payload["received_at_utc"] = now_utc_iso()
            parsed = None
            validation = validate_model_output(
                None,
                paper_id=paper_id,
                expected_fields=expected_fields,
                parse_error=raw_payload["error"],
            )
            status = "failed"

        write_json(raw_dir / f"{paper_id}.json", raw_payload)
        parsed_payload = {
            "paper_id": paper_id,
            "model_id": model_id,
            "status": status,
            "validation": validation,
            "parsed_response": parsed,
        }
        write_json(parsed_dir / f"{paper_id}.json", parsed_payload)
        actual_records.append(parsed_payload)

    write_extractions_csv(run_dir=run_dir, fields=fields, actual_records=actual_records, model_id=model_id)
    return actual_records


def write_summary(
    *,
    run_dir: Path,
    run_id: str,
    fields: list[FieldSpec],
    manifest_records: list[dict[str, Any]],
    skipped: list[dict[str, str]],
    prompt_records: list[dict[str, Any]],
    contract_path: Path,
    instruction_doc_path: Path,
    model_id: str = DEFAULT_MODEL_ID,
    actual_records: list[dict[str, Any]] | None = None,
) -> None:
    actual_records = actual_records or []
    actual_status_counts: dict[str, int] = {}
    for record in actual_records:
        status = str(record.get("status") or "unknown")
        actual_status_counts[status] = actual_status_counts.get(status, 0) + 1

    summary = {
        "run_id": run_id,
        "generated_at_utc": now_utc_iso(),
        "dry_run": not actual_records,
        "model_default": model_id,
        "field_count_total_worksheet": len(fields),
        "field_count_model_requested": len([f for f in fields if f.name not in FIXED_WORKSHEET_FIELDS]),
        "manifest_count": len(manifest_records),
        "skipped_before_limit_count": len(skipped),
        "contract_path": path_for_record(contract_path),
        "instruction_doc_path": path_for_record(instruction_doc_path),
        "prompt_records": prompt_records,
        "actual_status_counts": actual_status_counts,
        "actual_records": [
            {
                "paper_id": record.get("paper_id"),
                "status": record.get("status"),
                "errors": record.get("validation", {}).get("errors", []),
                "warnings": record.get("validation", {}).get("warnings", []),
                "missing_fields": record.get("validation", {}).get("missing_fields", []),
                "extra_fields": record.get("validation", {}).get("extra_fields", []),
            }
            for record in actual_records
        ],
        "skipped": skipped,
    }
    write_json(run_dir / "validation_summary.json", summary)

    run_label = "actual-run" if actual_records else "dry-run"
    lines = [
        f"# Qwen/Ollama single-case {run_label} summary",
        "",
        f"- Run ID: `{run_id}`",
        f"- Dry run: `{str(not actual_records).lower()}`",
        f"- Model default: `{model_id}`",
        f"- Worksheet fields: {summary['field_count_total_worksheet']}",
        f"- Model-requested fields: {summary['field_count_model_requested']}",
        f"- Manifest records: {summary['manifest_count']}",
        f"- Prompt files: {len(prompt_records)}",
        f"- Contract: `{summary['contract_path']}`",
        f"- Instruction document: `{summary['instruction_doc_path']}`",
    ]
    if actual_records:
        lines.append(f"- Actual status counts: `{actual_status_counts}`")
    lines.extend(["", "## Paper IDs", ""])
    lines.extend(f"- `{record['paper_id']}`" for record in manifest_records)
    if actual_records:
        lines.extend(["", "## Actual Results", ""])
        for record in actual_records:
            validation = record.get("validation", {})
            lines.append(
                f"- `{record.get('paper_id')}`: {record.get('status')} "
                f"(errors={len(validation.get('errors', []))}, "
                f"warnings={len(validation.get('warnings', []))})"
            )
    if skipped:
        lines.extend(["", "## Skipped Before Limit", ""])
        lines.extend(f"- `{item['paper_id']}`: {item['reason']}" for item in skipped[:20])
    (run_dir / "validation_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_dry_run(args: argparse.Namespace) -> Path:
    if args.use_existing_contract:
        fields = load_contract(args.contract_path)
    else:
        fields = build_contract_from_workbook(args.workbook_path)
        fields = augment_allowed_values_from_manual(fields, args.manual_csv_path)
        write_contract(args.contract_path, fields, args.workbook_path)
        write_instruction_doc(args.instruction_doc_path, fields, args.workbook_path)

    run_dir = args.output_root / args.run_id
    manifest_records, skipped = build_manifest_records(
        manual_csv_path=args.manual_csv_path,
        registry_path=args.registry_path,
        limit=args.limit,
        paper_ids=args.paper_id or None,
    )
    write_manifest_jsonl(run_dir / "manifest.jsonl", manifest_records)
    prompt_records = write_prompt_packs(
        run_dir=run_dir,
        fields=fields,
        manifest_records=manifest_records,
        model_id=args.model,
    )
    actual_records: list[dict[str, Any]] = []
    if args.run_ollama:
        actual_records = run_ollama_batch(
            run_dir=run_dir,
            fields=fields,
            manifest_records=manifest_records,
            env_path=args.env_path,
            base_url=args.base_url,
            model_id=args.model,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
        )
    write_summary(
        run_dir=run_dir,
        run_id=args.run_id,
        fields=fields,
        manifest_records=manifest_records,
        skipped=skipped,
        prompt_records=prompt_records,
        contract_path=args.contract_path,
        instruction_doc_path=args.instruction_doc_path,
        model_id=args.model,
        actual_records=actual_records,
    )
    return run_dir


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook-path", type=Path, default=DEFAULT_WORKBOOK_PATH)
    parser.add_argument("--contract-path", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--instruction-doc-path", type=Path, default=DEFAULT_INSTRUCTION_DOC_PATH)
    parser.add_argument("--registry-path", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--manual-csv-path", type=Path, default=DEFAULT_MANUAL_CSV_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--paper-id", action="append", default=[])
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--env-path", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument(
        "--run-ollama",
        action="store_true",
        help="Call Ollama Cloud and write raw/parsed outputs. Default is prompt-pack only.",
    )
    parser.add_argument(
        "--use-existing-contract",
        action="store_true",
        help="Read the local JSON contract instead of refreshing it from the XLSX.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = build_dry_run(args)
    mode = "Actual-run" if args.run_ollama else "Dry-run"
    print(f"{mode} artefacts written to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
