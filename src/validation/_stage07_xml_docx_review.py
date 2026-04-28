from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lxml import etree

from src.validation import _stage07_xml_review as review


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCX_REVIEW_ROOT = REPO_ROOT / "qa" / "validation" / "stage07_xml" / "docx_review"
DEFAULT_EVALUATION_ROOT = REPO_ROOT / "qa" / "validation" / "stage07_xml" / "evaluation"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NSMAP = {"w": W_NS, "r": R_NS}

HEADING_RE = re.compile(
    r"^REVIEW TARGET \| target_id=(?P<target_id>[^|]+) \| label=(?P<label>[^|]+) "
    r"\| kind=(?P<kind>[^|]+) \| colour=(?P<colour>[^|]+) \| fill=(?P<fill>[0-9A-Fa-f]{6})$"
)

DOCX_INDEX_FIELDNAMES = [
    "round_id",
    "paper_id",
    "paper_title",
    "docx_path",
    "legend_path",
    "metadata_path",
    "n_targets",
    "n_segments",
    "manual_review_required",
    "manual_review_reasons",
]


@dataclass(frozen=True)
class ColourEntry:
    target_id: str
    target_label: str
    target_kind: str
    colour_name: str
    colour_hex: str
    notes: str = ""


@dataclass(frozen=True)
class RunSpec:
    text: str
    fill: str = ""
    bold: bool = False


@dataclass(frozen=True)
class ParsedRun:
    text: str
    fill: str = ""


@dataclass(frozen=True)
class ParsedParagraph:
    text: str
    runs: list[ParsedRun]


@dataclass(frozen=True)
class ParsedSection:
    target_id: str
    label: str
    kind: str
    colour_name: str
    fill: str
    paragraphs: list[ParsedParagraph]


@dataclass(frozen=True)
class DocxSafeText:
    text: str
    replacements: list[dict[str, Any]]


DOCX_TARGET_PALETTE = [
    ("yellow", "FFF2CC"),
    ("orange", "F4B183"),
    ("green", "A9D18E"),
    ("cyan", "9DC3E6"),
    ("pink", "F4B6D2"),
    ("purple", "C9B6E4"),
    ("blue", "A7C7E7"),
    ("gold", "FFD966"),
    ("teal", "9ADBCF"),
    ("red", "F4A7A3"),
    ("lime", "D9EAD3"),
    ("lavender", "D9D2E9"),
    ("lightBlue", "CFE2F3"),
    ("peach", "FCE5CD"),
    ("mint", "D9EAD3"),
    ("rose", "EAD1DC"),
    ("steel", "D0E0E3"),
    ("tan", "EADFC8"),
    ("violet", "D5A6BD"),
    ("olive", "D9D2A9"),
    ("sky", "B6D7F0"),
    ("apricot", "F9CB9C"),
    ("seafoam", "B7E1CD"),
    ("plum", "D9B8C4"),
    ("slate", "C9DAF8"),
    ("sand", "EFE4B0"),
    ("sage", "CFE2C0"),
    ("coral", "F6B26B"),
    ("aqua", "B7DEE8"),
    ("mauve", "C27BA0"),
    ("leaf", "B6D7A8"),
    ("amber", "F1C232"),
]

WORD_HIGHLIGHT_TO_HEX = {
    "yellow": "FFFF00",
    "green": "00FF00",
    "cyan": "00FFFF",
    "magenta": "FF00FF",
    "blue": "0000FF",
    "red": "FF0000",
    "darkBlue": "000080",
    "darkCyan": "008080",
    "darkGreen": "008000",
    "darkMagenta": "800080",
    "darkRed": "800000",
    "darkYellow": "808000",
    "darkGray": "808080",
    "lightGray": "D9D9D9",
    "black": "000000",
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def w_tag(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def rel_tag(local: str) -> str:
    return f"{{{REL_NS}}}{local}"


def content_tag(local: str) -> str:
    return f"{{{CONTENT_TYPES_NS}}}{local}"


def normalise_hex(value: str) -> str:
    text = str(value or "").strip().lstrip("#").upper()
    if not re.fullmatch(r"[0-9A-F]{6}", text):
        return ""
    return text


def display_path(path: Path) -> str:
    return review.display_path(path)


def source_paragraph_slices(source_text: str) -> list[tuple[str, int, int]]:
    paragraphs: list[tuple[str, int, int]] = []
    cursor = 0
    for part in source_text.split("\n\n"):
        start = cursor
        end = start + len(part)
        paragraphs.append((part, start, end))
        cursor = end + 2
    return paragraphs


def is_xml_compatible_char(character: str) -> bool:
    codepoint = ord(character)
    return (
        codepoint in {0x09, 0x0A, 0x0D}
        or 0x20 <= codepoint <= 0xD7FF
        or 0xE000 <= codepoint <= 0xFFFD
        or 0x10000 <= codepoint <= 0x10FFFF
    )


def docx_safe_text(source_text: str) -> DocxSafeText:
    chars: list[str] = []
    replacements: list[dict[str, Any]] = []
    for offset, character in enumerate(source_text):
        if is_xml_compatible_char(character):
            chars.append(character)
            continue
        chars.append(" ")
        replacements.append(
            {
                "offset": offset,
                "source_codepoint": ord(character),
                "docx_character": " ",
            }
        )
    return DocxSafeText(text="".join(chars), replacements=replacements)


def restore_source_text(docx_text: str, replacements: list[dict[str, Any]]) -> str:
    chars = list(docx_text)
    for replacement in replacements:
        offset = int(replacement.get("offset") or -1)
        codepoint = int(replacement.get("source_codepoint") or 0)
        if 0 <= offset < len(chars) and codepoint:
            chars[offset] = chr(codepoint)
    return "".join(chars)


def merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def target_colour_entries(entities: list[dict[str, Any]]) -> list[ColourEntry]:
    entries: list[ColourEntry] = []
    used: set[str] = set()
    for index, entity in enumerate(entities):
        target_id = str(entity.get("id") or entity.get("target_id") or "").strip()
        if not target_id:
            continue
        target_label = str(entity.get("label") or entity.get("target_label") or target_id).strip()
        target_kind = str(entity.get("kind") or entity.get("target_kind") or "patient").strip()
        colour_name, colour_hex = colour_for_index(index)
        while colour_hex in used:
            colour_name, colour_hex = colour_for_index(index + len(used) + 1)
        entries.append(
            ColourEntry(
                target_id=target_id,
                target_label=target_label,
                target_kind=target_kind,
                colour_name=colour_name,
                colour_hex=colour_hex,
            )
        )
        used.add(colour_hex)
    return entries


def colour_for_index(index: int) -> tuple[str, str]:
    if index < len(DOCX_TARGET_PALETTE):
        return DOCX_TARGET_PALETTE[index]
    # Deterministic pastel fallback for unusually high target counts.
    hue = (index * 47) % 360
    saturation = 42
    lightness = 82
    return f"target{index + 1}", hsl_to_hex(hue, saturation, lightness)


def hsl_to_hex(hue: int, saturation: int, lightness: int) -> str:
    import colorsys

    red, green, blue = colorsys.hls_to_rgb(hue / 360, lightness / 100, saturation / 100)
    return f"{round(red * 255):02X}{round(green * 255):02X}{round(blue * 255):02X}"


def segment_ranges_for_target(segments: list[dict[str, Any]], target_id: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for segment in segments:
        targets = [str(target) for target in segment.get("targets") or []]
        if target_id not in targets:
            continue
        offsets = segment.get("source_offsets") or {}
        start = int(offsets.get("start") or 0)
        end = int(offsets.get("end") or start)
        if start < end:
            ranges.append((start, end))
    return merge_ranges(ranges)


def prediction_ranges(segments: list[dict[str, Any]], entries: list[ColourEntry]) -> list[tuple[int, int, str]]:
    colours = {entry.target_id: entry.colour_hex for entry in entries}
    ranges: list[tuple[int, int, str]] = []
    for segment in sorted(segments, key=lambda item: int((item.get("source_offsets") or {}).get("start") or 0)):
        offsets = segment.get("source_offsets") or {}
        start = int(offsets.get("start") or 0)
        end = int(offsets.get("end") or start)
        targets = [str(target) for target in segment.get("targets") or []]
        fill = next((colours[target] for target in targets if target in colours), "D9D9D9")
        if start < end:
            ranges.append((start, end, fill))
    return ranges


def runs_for_source_paragraph(
    source_text: str,
    paragraph_start: int,
    paragraph_end: int,
    ranges: list[tuple[int, int, str]],
) -> list[RunSpec]:
    runs: list[RunSpec] = []
    cursor = paragraph_start
    for start, end, fill in sorted(ranges):
        overlap_start = max(start, paragraph_start)
        overlap_end = min(end, paragraph_end)
        if overlap_start >= overlap_end or overlap_start < cursor:
            continue
        if cursor < overlap_start:
            runs.append(RunSpec(source_text[cursor:overlap_start]))
        runs.append(RunSpec(source_text[overlap_start:overlap_end], fill=fill))
        cursor = overlap_end
    if cursor < paragraph_end:
        runs.append(RunSpec(source_text[cursor:paragraph_end]))
    if not runs:
        runs.append(RunSpec(""))
    return runs


def make_run(spec: RunSpec) -> etree._Element:
    run = etree.Element(w_tag("r"))
    if spec.fill or spec.bold:
        run_properties = etree.SubElement(run, w_tag("rPr"))
        if spec.bold:
            etree.SubElement(run_properties, w_tag("b"))
        if spec.fill:
            etree.SubElement(
                run_properties,
                w_tag("shd"),
                {
                    w_tag("val"): "clear",
                    w_tag("color"): "auto",
                    w_tag("fill"): normalise_hex(spec.fill),
                },
            )
    parts = spec.text.split("\n")
    for index, part in enumerate(parts):
        if part:
            text = etree.SubElement(run, w_tag("t"))
            if part[:1].isspace() or part[-1:].isspace():
                text.set(f"{{{XML_NS}}}space", "preserve")
            text.text = part
        elif len(parts) == 1:
            etree.SubElement(run, w_tag("t")).text = ""
        if index < len(parts) - 1:
            etree.SubElement(run, w_tag("br"))
    return run


def make_paragraph(runs: list[RunSpec], style: str = "") -> etree._Element:
    paragraph = etree.Element(w_tag("p"))
    if style:
        paragraph_properties = etree.SubElement(paragraph, w_tag("pPr"))
        etree.SubElement(paragraph_properties, w_tag("pStyle"), {w_tag("val"): style})
    for run in runs:
        paragraph.append(make_run(run))
    return paragraph


def text_paragraph(text: str, *, style: str = "", bold: bool = False, fill: str = "") -> etree._Element:
    return make_paragraph([RunSpec(text=text, bold=bold, fill=fill)], style=style)


def source_paragraphs(
    source_text: str,
    ranges: list[tuple[int, int, str]],
) -> list[etree._Element]:
    paragraphs: list[etree._Element] = []
    for paragraph_text, start, end in source_paragraph_slices(source_text):
        paragraphs.append(make_paragraph(runs_for_source_paragraph(source_text, start, end, ranges)))
    return paragraphs


def document_xml(paragraphs: list[etree._Element]) -> bytes:
    document = etree.Element(w_tag("document"), nsmap=NSMAP)
    body = etree.SubElement(document, w_tag("body"))
    for paragraph in paragraphs:
        body.append(paragraph)
    etree.SubElement(body, w_tag("sectPr"))
    return etree.tostring(document, xml_declaration=True, encoding="UTF-8", standalone=True)


def styles_xml() -> bytes:
    styles = etree.Element(w_tag("styles"), nsmap=NSMAP)
    for style_id, name, size in [
        ("Normal", "Normal", "22"),
        ("Title", "Title", "32"),
        ("Heading1", "heading 1", "28"),
        ("Heading2", "heading 2", "24"),
    ]:
        style = etree.SubElement(styles, w_tag("style"), {w_tag("type"): "paragraph", w_tag("styleId"): style_id})
        etree.SubElement(style, w_tag("name"), {w_tag("val"): name})
        run_properties = etree.SubElement(style, w_tag("rPr"))
        if style_id != "Normal":
            etree.SubElement(run_properties, w_tag("b"))
        etree.SubElement(run_properties, w_tag("sz"), {w_tag("val"): size})
    return etree.tostring(styles, xml_declaration=True, encoding="UTF-8", standalone=True)


def content_types_xml() -> bytes:
    types = etree.Element(content_tag("Types"), nsmap={None: CONTENT_TYPES_NS})
    etree.SubElement(types, content_tag("Default"), Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    etree.SubElement(types, content_tag("Default"), Extension="xml", ContentType="application/xml")
    etree.SubElement(
        types,
        content_tag("Override"),
        PartName="/word/document.xml",
        ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
    )
    etree.SubElement(
        types,
        content_tag("Override"),
        PartName="/word/styles.xml",
        ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml",
    )
    return etree.tostring(types, xml_declaration=True, encoding="UTF-8", standalone=True)


def package_rels_xml() -> bytes:
    relationships = etree.Element(rel_tag("Relationships"), nsmap={None: REL_NS})
    etree.SubElement(
        relationships,
        rel_tag("Relationship"),
        Id="rId1",
        Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
        Target="word/document.xml",
    )
    return etree.tostring(relationships, xml_declaration=True, encoding="UTF-8", standalone=True)


def document_rels_xml() -> bytes:
    relationships = etree.Element(rel_tag("Relationships"), nsmap={None: REL_NS})
    etree.SubElement(
        relationships,
        rel_tag("Relationship"),
        Id="rIdStyles",
        Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
        Target="styles.xml",
    )
    return etree.tostring(relationships, xml_declaration=True, encoding="UTF-8", standalone=True)


def write_docx(path: Path, paragraphs: list[etree._Element]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml())
        archive.writestr("_rels/.rels", package_rels_xml())
        archive.writestr("word/document.xml", document_xml(paragraphs))
        archive.writestr("word/styles.xml", styles_xml())
        archive.writestr("word/_rels/document.xml.rels", document_rels_xml())


def docx_paragraphs_for_item(
    *,
    item: review.ReviewItem,
    round_id: str,
    entries: list[ColourEntry],
    source_text: str,
) -> list[etree._Element]:
    segments = [dict(segment) for segment in item.segments_payload.get("segments") or []]
    paragraphs: list[etree._Element] = [
        text_paragraph(f"Stage 07 DOCX Review: Paper {item.paper_id}", style="Title"),
        text_paragraph(f"round_id={round_id} | paper_id={item.paper_id}", bold=True),
        text_paragraph("Do not edit source text. Correct assignments by changing highlights only."),
        text_paragraph("Prediction Overview", style="Heading1"),
    ]
    paragraphs.extend(source_paragraphs(source_text, prediction_ranges(segments, entries)))
    paragraphs.extend(
        [
            text_paragraph("Target Colour Legend", style="Heading1"),
            text_paragraph("Edit the Markdown legend if target labels, kinds, or colours need to change."),
        ]
    )
    for entry in entries:
        paragraphs.append(
            text_paragraph(
                f"{entry.target_id} | {entry.target_label} | {entry.target_kind} | {entry.colour_name} | {entry.colour_hex}",
                fill=entry.colour_hex,
            )
        )
    paragraphs.append(text_paragraph("Authoritative Review Sections", style="Heading1"))
    for entry in entries:
        paragraphs.append(
            text_paragraph(
                review_heading(entry),
                style="Heading2",
                fill=entry.colour_hex,
                bold=True,
            )
        )
        target_ranges = [
            (start, end, entry.colour_hex)
            for start, end in segment_ranges_for_target(segments, entry.target_id)
        ]
        paragraphs.extend(source_paragraphs(source_text, target_ranges))
    template = ColourEntry("new_target_1", "New target 1", "template", "lightGray", "D9D9D9")
    paragraphs.append(text_paragraph(review_heading(template), style="Heading2", fill=template.colour_hex, bold=True))
    paragraphs.extend(source_paragraphs(source_text, []))
    return paragraphs


def review_heading(entry: ColourEntry) -> str:
    return (
        f"REVIEW TARGET | target_id={entry.target_id} | label={entry.target_label} "
        f"| kind={entry.target_kind} | colour={entry.colour_name} | fill={entry.colour_hex}"
    )


def markdown_for_item(item: review.ReviewItem, entries: list[ColourEntry]) -> str:
    rows = [
        "| target_id | target_label | target_kind | colour_name | colour_hex | review_notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in entries:
        rows.append(
            f"| {entry.target_id} | {entry.target_label} | {entry.target_kind} | "
            f"{entry.colour_name} | {entry.colour_hex} |  |"
        )
    rows.append(
        "| new_target_1 | New target 1 | template | lightGray | D9D9D9 | "
        "Change target_kind to patient or group and create a matching DOCX section before use. |"
    )
    reasons = review.manual_review_reasons(item)
    reason_text = "\n".join(f"- {reason}" for reason in reasons) if reasons else "- None"
    return "\n".join(
        [
            f"# Stage 07 DOCX Review: Paper {item.paper_id}",
            "",
            "## Instructions",
            "- Do not edit the source text in the DOCX.",
            "- Correct assignments by adding, removing, or changing highlights.",
            "- Target colours define patient/group identity.",
            "- Highlight the same source span in more than one target colour to mark shared context.",
            "",
            "## Colour Legend",
            *rows,
            "",
            "## Existing Validation Warnings",
            reason_text,
            "",
            "## Reviewer Notes",
            "- ",
            "",
        ]
    )


def metadata_for_item(
    *,
    item: review.ReviewItem,
    round_id: str,
    source_text: str,
    safe_text: DocxSafeText,
    entries: list[ColourEntry],
    docx_path: Path,
    legend_path: Path,
) -> dict[str, Any]:
    source = item.segments_payload.get("source") or item.paper_payload.get("source") or {}
    return {
        "stage07_docx_review_schema_version": "stage07_docx_review_v1",
        "round_id": round_id,
        "paper_id": item.paper_id,
        "paper_title": review.paper_title(item),
        "route_mode": str(item.registry_row.get("route_mode") or item.paper_payload.get("source_route", {}).get("resolved_langextract_mode") or ""),
        "source_text_sha256": review.sha256_text(source_text),
        "docx_source_text_sha256": review.sha256_text(safe_text.text),
        "docx_text_replacements": safe_text.replacements,
        "prepared_source_sha256": str(source.get("prepared_source_sha256") or ""),
        "source_text_character_count": len(source_text),
        "docx_path": display_path(docx_path),
        "legend_path": display_path(legend_path),
        "generated_at_utc": now_utc_iso(),
        "targets": [
            {
                "id": entry.target_id,
                "label": entry.target_label,
                "kind": entry.target_kind,
                "colour_name": entry.colour_name,
                "colour_hex": entry.colour_hex,
            }
            for entry in entries
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_docx_review_pack(
    *,
    round_id: str,
    stage07_root: Path = review.STAGE07_XML_ROOT,
    registry_path: Path = review.STAGE07_XML_REGISTRY_PATH,
    review_root: Path = DOCX_REVIEW_ROOT,
    paper_ids: set[str] | None = None,
    force: bool = False,
) -> dict[str, str]:
    round_dir = review_root / round_id
    papers_dir = round_dir / "papers"
    if round_dir.exists() and not force:
        raise FileExistsError(f"DOCX review round already exists: {display_path(round_dir)}")
    papers_dir.mkdir(parents=True, exist_ok=True)

    items = review.load_review_items(stage07_root=stage07_root, registry_path=registry_path, paper_ids=paper_ids)
    if not items:
        raise ValueError("No Stage 07 XML outputs were found for the requested DOCX review pack.")

    index_rows: list[dict[str, str]] = []
    for item in items:
        source_text = review.source_text_for_item(item)
        safe_text = docx_safe_text(source_text)
        entries = target_colour_entries(review.entities_for_item(item))
        docx_path = papers_dir / f"{item.paper_id}.docx"
        legend_path = papers_dir / f"{item.paper_id}.colour_legend_and_notes.md"
        metadata_path = papers_dir / f"{item.paper_id}.docx_metadata.json"
        write_docx(
            docx_path,
            docx_paragraphs_for_item(
                item=item,
                round_id=round_id,
                entries=entries,
                source_text=safe_text.text,
            ),
        )
        legend_path.write_text(markdown_for_item(item, entries), encoding="utf-8")
        write_json(
            metadata_path,
            metadata_for_item(
                item=item,
                round_id=round_id,
                source_text=source_text,
                safe_text=safe_text,
                entries=entries,
                docx_path=docx_path,
                legend_path=legend_path,
            ),
        )
        index_rows.append(
            {
                "round_id": round_id,
                "paper_id": item.paper_id,
                "paper_title": review.paper_title(item),
                "docx_path": display_path(docx_path),
                "legend_path": display_path(legend_path),
                "metadata_path": display_path(metadata_path),
                "n_targets": str(len(entries)),
                "n_segments": str(len(item.segments_payload.get("segments") or [])),
                "manual_review_required": str(item.registry_row.get("manual_review_required") or ""),
                "manual_review_reasons": "|".join(review.manual_review_reasons(item)),
            }
        )
    index_path = round_dir / "docx_review_index.csv"
    write_csv(index_path, index_rows, DOCX_INDEX_FIELDNAMES)
    return {
        "round_id": round_id,
        "round_dir": display_path(round_dir),
        "index_path": display_path(index_path),
        "paper_count": str(len(items)),
    }


def parse_colour_legend(path: Path) -> tuple[list[ColourEntry], str]:
    rows: list[ColourEntry] = []
    notes: list[str] = []
    in_notes = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## reviewer notes"):
            in_notes = True
            continue
        if in_notes:
            notes.append(line)
            continue
        if not stripped.startswith("|") or "---" in stripped or "target_id" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 5:
            continue
        target_id, target_label, target_kind, colour_name, colour_hex = cells[:5]
        notes_cell = cells[5] if len(cells) > 5 else ""
        hex_value = normalise_hex(colour_hex)
        if not target_id or not hex_value:
            continue
        rows.append(
            ColourEntry(
                target_id=target_id,
                target_label=target_label or target_id,
                target_kind=target_kind or "patient",
                colour_name=colour_name or target_id,
                colour_hex=hex_value,
                notes=notes_cell,
            )
        )
    return rows, "\n".join(notes).strip()


def parse_docx_paragraphs(path: Path) -> list[ParsedParagraph]:
    with zipfile.ZipFile(path) as archive:
        document = etree.fromstring(archive.read("word/document.xml"))
    paragraphs: list[ParsedParagraph] = []
    for paragraph in document.findall(".//w:body/w:p", namespaces=NSMAP):
        runs: list[ParsedRun] = []
        pieces: list[str] = []
        for run in paragraph.findall("w:r", namespaces=NSMAP):
            text = text_for_run(run)
            fill = fill_for_run(run)
            runs.append(ParsedRun(text=text, fill=fill))
            pieces.append(text)
        paragraphs.append(ParsedParagraph(text="".join(pieces), runs=runs))
    return paragraphs


def text_for_run(run: etree._Element) -> str:
    pieces: list[str] = []
    for child in run:
        if child.tag == w_tag("t"):
            pieces.append(child.text or "")
        elif child.tag == w_tag("br"):
            pieces.append("\n")
        elif child.tag == w_tag("tab"):
            pieces.append("\t")
    return "".join(pieces)


def fill_for_run(run: etree._Element) -> str:
    run_properties = run.find("w:rPr", namespaces=NSMAP)
    if run_properties is None:
        return ""
    shading = run_properties.find("w:shd", namespaces=NSMAP)
    if shading is not None:
        fill = normalise_hex(shading.get(w_tag("fill")) or "")
        if fill:
            return fill
    highlight = run_properties.find("w:highlight", namespaces=NSMAP)
    if highlight is not None:
        return WORD_HIGHLIGHT_TO_HEX.get(str(highlight.get(w_tag("val")) or ""), "")
    return ""


def parse_review_sections(paragraphs: list[ParsedParagraph]) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    current: dict[str, Any] | None = None
    current_paragraphs: list[ParsedParagraph] = []
    for paragraph in paragraphs:
        match = HEADING_RE.match(paragraph.text.strip())
        if match:
            if current is not None:
                sections.append(section_from_parts(current, current_paragraphs))
            current = match.groupdict()
            current_paragraphs = []
            continue
        if current is not None:
            current_paragraphs.append(paragraph)
    if current is not None:
        sections.append(section_from_parts(current, current_paragraphs))
    return sections


def section_from_parts(values: dict[str, str], paragraphs: list[ParsedParagraph]) -> ParsedSection:
    return ParsedSection(
        target_id=values["target_id"].strip(),
        label=values["label"].strip(),
        kind=values["kind"].strip(),
        colour_name=values["colour"].strip(),
        fill=normalise_hex(values["fill"]),
        paragraphs=paragraphs,
    )


def source_text_for_section(section: ParsedSection) -> str:
    return "\n\n".join(paragraph.text for paragraph in section.paragraphs)


def active_legend_entries(entries: list[ColourEntry]) -> list[ColourEntry]:
    active_kinds = {"patient", "group"}
    return [entry for entry in entries if entry.target_kind.strip().casefold() in active_kinds]


def highlight_ranges_for_section(
    section: ParsedSection,
    fill_to_target: dict[str, str],
    warnings: list[str],
) -> dict[str, list[tuple[int, int]]]:
    ranges: dict[str, list[tuple[int, int]]] = {}
    cursor = 0
    for paragraph_index, paragraph in enumerate(section.paragraphs):
        if paragraph_index:
            cursor += 2
        for run in paragraph.runs:
            start = cursor
            end = start + len(run.text)
            if run.fill and run.text:
                target_id = fill_to_target.get(run.fill)
                if target_id:
                    ranges.setdefault(target_id, []).append((start, end))
                else:
                    warnings.append(f"unknown_highlight_colour:{section.target_id}:{run.fill}:{start}:{end}")
            cursor = end
    return ranges


def interval_segments(ranges_by_target: dict[str, list[tuple[int, int]]]) -> list[tuple[int, int, list[str]]]:
    merged = {target: merge_ranges(ranges) for target, ranges in ranges_by_target.items()}
    boundaries = sorted({point for ranges in merged.values() for span in ranges for point in span})
    intervals: list[tuple[int, int, list[str]]] = []
    for start, end in zip(boundaries, boundaries[1:]):
        if start >= end:
            continue
        targets = sorted(
            target
            for target, ranges in merged.items()
            if any(span_start <= start and end <= span_end for span_start, span_end in ranges)
        )
        if not targets:
            continue
        if intervals and intervals[-1][2] == targets and intervals[-1][1] == start:
            intervals[-1] = (intervals[-1][0], end, targets)
        else:
            intervals.append((start, end, targets))
    return intervals


def role_for_targets(targets: list[str], entries_by_id: dict[str, ColourEntry]) -> str:
    if len(targets) > 1:
        return "shared"
    target = targets[0]
    kind = entries_by_id[target].target_kind.strip().casefold()
    if kind == "group":
        return "group_summary"
    return "patient_specific"


def route_mode_for_entries(entries: list[ColourEntry], fallback: str) -> str:
    patient_count = sum(1 for entry in entries if entry.target_kind.strip().casefold() == "patient")
    group_count = sum(1 for entry in entries if entry.target_kind.strip().casefold() == "group")
    if patient_count > 1:
        return "individual_case_split"
    if patient_count == 1 and group_count == 0:
        return "individual"
    if patient_count == 0 and group_count > 0:
        return "group"
    return fallback


def import_paper_review(
    *,
    docx_path: Path,
    legend_path: Path,
    metadata_path: Path,
    reviewed_annotations_dir: Path,
    import_reports_dir: Path,
    force: bool = False,
) -> dict[str, Any]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    paper_id = str(metadata.get("paper_id") or metadata_path.name.split(".")[0])
    entries, reviewer_notes = parse_colour_legend(legend_path)
    active_entries = active_legend_entries(entries)
    entries_by_id = {entry.target_id: entry for entry in active_entries}
    fill_to_target = {entry.colour_hex: entry.target_id for entry in active_entries}
    sections = parse_review_sections(parse_docx_paragraphs(docx_path))
    sections_by_id = {section.target_id: section for section in sections}
    warnings: list[str] = []
    errors: list[str] = []

    source_text = ""
    ranges_by_target: dict[str, list[tuple[int, int]]] = {}
    for entry in active_entries:
        if entry.target_id not in sections_by_id:
            errors.append(f"missing_review_section:{entry.target_id}")
    for section in sections:
        if section.target_id not in entries_by_id:
            continue
        section_text = source_text_for_section(section)
        if not source_text:
            source_text = section_text
        if section_text != source_text:
            errors.append(f"source_text_differs_between_sections:{section.target_id}")
            continue
        section_hash = review.sha256_text(section_text)
        expected_hash = str(metadata.get("docx_source_text_sha256") or metadata.get("source_text_sha256") or "")
        if section_hash != expected_hash:
            errors.append(f"source_text_hash_mismatch:{section.target_id}")
            continue
        section_ranges = highlight_ranges_for_section(section, fill_to_target, warnings)
        for target_id, ranges in section_ranges.items():
            ranges_by_target.setdefault(target_id, []).extend(ranges)

    segments: list[dict[str, Any]] = []
    original_source_text = restore_source_text(
        source_text,
        list(metadata.get("docx_text_replacements") or []),
    )
    if original_source_text and review.sha256_text(original_source_text) != str(metadata.get("source_text_sha256") or ""):
        errors.append("restored_source_text_hash_mismatch")
    for index, (start, end, targets) in enumerate(interval_segments(ranges_by_target), start=1):
        role = role_for_targets(targets, entries_by_id)
        segments.append(
            {
                "targets": targets,
                "role": role,
                "confidence": "reviewed",
                "evidence": f"DOCX gold review import for {paper_id}.",
                "selections": [
                    {
                        "source_start": start,
                        "source_end": end,
                        "text": original_source_text[start:end],
                    }
                ],
                "review_segment_id": f"docx_l{index:04d}",
            }
        )

    reviewed_payload = {
        "paper_id": paper_id,
        "route_mode": route_mode_for_entries(active_entries, str(metadata.get("route_mode") or "")),
        "targets": [
            {
                "id": entry.target_id,
                "kind": entry.target_kind,
                "label": entry.target_label,
                "evidence": "docx_gold_review",
            }
            for entry in active_entries
        ],
        "segments": segments,
        "validation_warnings": warnings,
        "manual_review_reasons": [],
        "reviewer_notes": reviewer_notes,
    }

    report = {
        "paper_id": paper_id,
        "docx_path": display_path(docx_path),
        "legend_path": display_path(legend_path),
        "metadata_path": display_path(metadata_path),
        "reviewed_annotation_path": "",
        "status": "failed" if errors else "passed",
        "errors": errors,
        "warnings": warnings,
        "n_targets": len(active_entries),
        "n_segments": len(segments),
        "reviewer_notes": reviewer_notes,
        "imported_at_utc": now_utc_iso(),
    }

    import_reports_dir.mkdir(parents=True, exist_ok=True)
    reviewed_annotations_dir.mkdir(parents=True, exist_ok=True)
    report_path = import_reports_dir / f"{paper_id}.import_report.json"
    annotation_path = reviewed_annotations_dir / f"{paper_id}.json"
    if not errors:
        if annotation_path.exists() and not force:
            raise FileExistsError(f"Reviewed annotation already exists: {display_path(annotation_path)}")
        write_json(annotation_path, reviewed_payload)
        report["reviewed_annotation_path"] = display_path(annotation_path)
    write_json(report_path, report)
    return report


def import_docx_review_round(
    *,
    round_dir: Path,
    paper_ids: set[str] | None = None,
    force: bool = False,
    regenerate_gold: bool = True,
    rescore_candidate_stage07_root: Path | None = None,
    rescore_candidate_registry_path: Path | None = None,
    rescore_evaluation_root: Path | None = None,
    rescore_run_id: str = "",
    rescore_matrix_config_name: str = "",
    rescore_api_telemetry_path: Path | None = None,
) -> dict[str, str]:
    papers_dir = round_dir / "papers"
    reviewed_annotations_dir = round_dir / "reviewed_annotations"
    import_reports_dir = round_dir / "import_reports"
    reports: list[dict[str, Any]] = []
    for metadata_path in sorted(papers_dir.glob("*.docx_metadata.json"), key=lambda path: review.sort_key_for_paper_id(path.name.split(".")[0])):
        paper_id = metadata_path.name.split(".")[0]
        if paper_ids is not None and paper_id not in paper_ids:
            continue
        reports.append(
            import_paper_review(
                docx_path=papers_dir / f"{paper_id}.docx",
                legend_path=papers_dir / f"{paper_id}.colour_legend_and_notes.md",
                metadata_path=metadata_path,
                reviewed_annotations_dir=reviewed_annotations_dir,
                import_reports_dir=import_reports_dir,
                force=force,
            )
        )
    passed_ids = [str(report["paper_id"]) for report in reports if report.get("status") == "passed"]
    if regenerate_gold and passed_ids:
        regenerate_gold_outputs(round_dir=round_dir, paper_ids=passed_ids, reviewed_annotations_dir=reviewed_annotations_dir)
    benchmark_summary: dict[str, str] = {}
    if rescore_candidate_stage07_root is not None and passed_ids:
        benchmark_summary = rescore_imported_docx_round(
            round_dir=round_dir,
            paper_ids=passed_ids,
            candidate_stage07_root=rescore_candidate_stage07_root,
            candidate_registry_path=rescore_candidate_registry_path,
            evaluation_root=rescore_evaluation_root or DEFAULT_EVALUATION_ROOT,
            run_id=rescore_run_id or f"{round_dir.name}_rescore",
            matrix_config_name=rescore_matrix_config_name,
            api_telemetry_path=rescore_api_telemetry_path,
        )
    summary_path = round_dir / "import_summary.json"
    summary = {
        "round_dir": display_path(round_dir),
        "paper_count": str(len(reports)),
        "passed_count": str(sum(1 for report in reports if report.get("status") == "passed")),
        "failed_count": str(sum(1 for report in reports if report.get("status") == "failed")),
        "reviewed_annotations_dir": display_path(reviewed_annotations_dir),
        "import_reports_dir": display_path(import_reports_dir),
        "gold_stage07_root": display_path(round_dir / "gold_stage07_xml"),
        "benchmark_run_dir": benchmark_summary.get("benchmark_run_dir", ""),
        "benchmark_summary_path": benchmark_summary.get("benchmark_summary_path", ""),
        "summary_path": display_path(summary_path),
    }
    write_json(summary_path, summary)
    return {key: str(value) for key, value in summary.items()}


def rescore_imported_docx_round(
    *,
    round_dir: Path,
    paper_ids: list[str],
    candidate_stage07_root: Path,
    candidate_registry_path: Path | None,
    evaluation_root: Path,
    run_id: str,
    matrix_config_name: str,
    api_telemetry_path: Path | None,
) -> dict[str, str]:
    command = [
        sys.executable,
        str(REPO_ROOT / "src" / "pipelines" / "stage07_benchmarking" / "run_stage07_benchmark.py"),
        "--docx-round-dir",
        str(round_dir),
        "--candidate-stage07-root",
        str(candidate_stage07_root),
        "--evaluation-root",
        str(evaluation_root),
        "--run-id",
        run_id,
    ]
    if candidate_registry_path is not None:
        command.extend(["--candidate-registry-path", str(candidate_registry_path)])
    if matrix_config_name:
        command.extend(["--matrix-config-name", matrix_config_name])
    if api_telemetry_path is not None:
        command.extend(["--api-telemetry-path", str(api_telemetry_path)])
    for paper_id in paper_ids:
        command.extend(["--paper-id", paper_id])
    subprocess.run(command, cwd=str(REPO_ROOT), check=True)
    benchmark_run_dir = evaluation_root / run_id
    return {
        "benchmark_run_dir": display_path(benchmark_run_dir),
        "benchmark_summary_path": display_path(benchmark_run_dir / "summary.json"),
    }


def regenerate_gold_outputs(*, round_dir: Path, paper_ids: list[str], reviewed_annotations_dir: Path) -> None:
    output_root = round_dir / "gold_stage07_xml"
    registry_path = round_dir / "gold_stage07_xml_registry.csv"
    if output_root.exists():
        resolved_output = output_root.resolve()
        resolved_round = round_dir.resolve()
        if resolved_round not in resolved_output.parents and resolved_output != resolved_round:
            raise ValueError(f"Refusing to remove output outside round directory: {display_path(output_root)}")
        shutil.rmtree(output_root)
    command = [
        sys.executable,
        str(REPO_ROOT / "src" / "pipelines" / "stage07_XML" / "run_stage07_xml.py"),
        "--output-root",
        str(output_root),
        "--registry-path",
        str(registry_path),
        "--reviewed-annotation-dir",
        str(reviewed_annotations_dir),
        "--manifest-run-id",
        f"{round_dir.name}_docx_gold",
        "--skip-artifact-registry-refresh",
        "--force",
    ]
    for paper_id in paper_ids:
        command.extend(["--paper-id", paper_id])
    subprocess.run(command, cwd=str(REPO_ROOT), check=True)
