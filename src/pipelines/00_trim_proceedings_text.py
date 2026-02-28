from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "00_build_paper_artifact_registry.py"

ABSTRACT_START_RE = re.compile(
    r"^(?P<code>(?:[A-Z]{1,3}-)?(?:[A-Z]{1,2})?\d{2,3}|\d{2,3})\.\s+(?P<title>.+)$"
)
PROGRAM_MARKERS = (
    "annual meeting",
    "program and abstracts",
    "program abstracts",
    "poster sessions",
    "poster presentations",
)
AUTHOR_CREDENTIAL_RE = re.compile(
    r"\b(MD|M\.D\.|DO|D\.O\.|PHD|PH\.D\.|MSC|M\.S\.|MS|BS|B\.S\.|BA|B\.A\.|MBA|MBBS|MPH|RN|FRCPC|FAAN|FRCP|DPhil)\b",
    re.IGNORECASE,
)
INSTITUTION_MARKERS = (
    "university",
    "hospital",
    "medical center",
    "school of medicine",
    "clinic",
    "department",
    "institute",
    "center",
    "centre",
    "usa",
    "canada",
    "united kingdom",
    "australia",
    "japan",
    "italy",
    "france",
    "germany",
    "korea",
)
FOOTER_MARKERS = (
    "annals of neurology",
    "downloaded from https://",
    "terms and conditions",
    "program and abstracts",
)


@dataclass
class LineRef:
    page_index: int
    line_index: int
    text: str


@dataclass
class AbstractBlock:
    code: str
    start_index: int
    end_index: int
    start_page_index: int
    end_page_index: int
    title_text: str
    header_text: str
    preview_text: str
    line_refs: list[LineRef]
    title_score: float = 0.0
    author_score: float = 0.0
    match_score: float = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trim multi-abstract proceedings PDFs down to the target abstract only."
    )
    parser.add_argument(
        "--references-csv",
        type=Path,
        default=REFERENCES_CSV,
        help="Reference export CSV containing Covidence IDs, titles, and authors.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=TEXT_DIR,
        help="Directory containing full text extraction JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUT_DIR,
        help="Directory for trimmed text JSON files.",
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=REGISTRY_PATH,
        help="CSV registry describing trimming decisions.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Specific paper ID to process. Repeat for multiple IDs.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of text JSON files to process.")
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after trimming.",
    )
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def relative_to_repo(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return " ".join(ascii_text.split())


def token_set(text: str, min_len: int = 3) -> set[str]:
    return {token for token in normalize_text(text).split() if len(token) >= min_len}


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            (row.get("Covidence") or "").strip(): row
            for row in reader
            if (row.get("Covidence") or "").strip()
        }


def collect_input_paths(input_dir: Path, paper_ids: list[str], limit: int) -> list[Path]:
    paths = sorted(input_dir.glob("*.json"))
    if paper_ids:
        wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
        paths = [path for path in paths if path.stem in wanted]
    if limit and limit > 0:
        paths = paths[:limit]
    return paths


def load_text_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_lines(record: dict[str, Any]) -> list[LineRef]:
    lines: list[LineRef] = []
    for page in record.get("pages") or []:
        page_index = int(page.get("page_index") or 0)
        page_text = str(page.get("text") or "")
        for line_index, raw_line in enumerate(page_text.splitlines()):
            line = " ".join(raw_line.split())
            if line:
                lines.append(LineRef(page_index=page_index, line_index=line_index, text=line))
    return lines


def is_abstract_start(line: str) -> re.Match[str] | None:
    return ABSTRACT_START_RE.match(line.strip())


def is_author_like(line: str) -> bool:
    if AUTHOR_CREDENTIAL_RE.search(line):
        return True
    comma_count = line.count(",")
    if comma_count >= 3:
        return True
    if ";" in line and comma_count >= 1:
        return True
    return False


def is_institution_like(line: str) -> bool:
    normalized = normalize_text(line)
    return any(marker in normalized for marker in INSTITUTION_MARKERS)


def is_footer_like(line: str) -> bool:
    normalized = normalize_text(line)
    return any(marker in normalized for marker in FOOTER_MARKERS)


def is_title_like(line: str) -> bool:
    if is_abstract_start(line) or is_author_like(line) or is_institution_like(line) or is_footer_like(line):
        return False
    words = line.split()
    if len(words) < 4 or len(words) > 24:
        return False
    alpha_words = sum(1 for word in words if re.search(r"[A-Za-z]", word))
    return alpha_words >= max(3, len(words) - 2)


def strip_abstract_code(line: str) -> str:
    match = is_abstract_start(line)
    if match:
        return match.group("title").strip()
    return line.strip()


def parse_reference_surnames(authors: str) -> list[str]:
    surnames: list[str] = []
    for chunk in re.split(r";", authors or ""):
        part = chunk.strip()
        if not part:
            continue
        surname = part.split(",", 1)[0].strip()
        normalized = normalize_text(surname)
        if normalized and normalized not in surnames:
            surnames.append(normalized)
    return surnames[:6]


def score_title(reference_title: str, block_title: str) -> float:
    ref_norm = normalize_text(reference_title)
    block_norm = normalize_text(block_title)
    if not ref_norm or not block_norm:
        return 0.0
    if ref_norm == block_norm:
        return 1.0
    sequence = SequenceMatcher(None, ref_norm, block_norm).ratio()
    ref_tokens = token_set(ref_norm, min_len=4)
    block_tokens = token_set(block_norm, min_len=4)
    overlap = len(ref_tokens & block_tokens) / max(1, len(ref_tokens))
    if ref_norm in block_norm or block_norm in ref_norm:
        overlap = max(overlap, 0.95)
    return max(sequence, (0.65 * sequence) + (0.35 * overlap))


def score_authors(reference_authors: str, block_text: str) -> float:
    surnames = parse_reference_surnames(reference_authors)
    if not surnames:
        return 0.0
    normalized_block = normalize_text(block_text)
    block_tokens = token_set(block_text, min_len=3)
    matches = 0
    for surname in surnames:
        if surname in normalized_block:
            matches += 1
            continue
        surname_tokens = {token for token in surname.split() if len(token) >= 3}
        if surname_tokens and surname_tokens.issubset(block_tokens):
            matches += 1
    return matches / len(surnames)


def proceedings_signals(record: dict[str, Any], lines: list[LineRef]) -> dict[str, Any]:
    first_window = [line for line in lines if line.page_index < 40]
    first_pages_text = " ".join(line.text for line in lines if line.page_index < 5)
    normalized_first_pages = normalize_text(first_pages_text)
    abstract_starts = [line for line in first_window if is_abstract_start(line.text)]
    title_like_count = sum(1 for line in first_window if is_title_like(line.text))
    author_like_count = sum(1 for line in first_window if is_author_like(line.text))
    marker_text = " ".join(
        [
            str(record.get("source_filename") or ""),
            normalized_first_pages,
        ]
    )
    program_marker_count = sum(1 for marker in PROGRAM_MARKERS if marker in normalize_text(marker_text))
    n_pages = int(record.get("n_pages") or 0)
    proceedings_detected = n_pages >= 40 and (
        len(abstract_starts) >= 8
        or (title_like_count >= 20 and author_like_count >= 10)
        or program_marker_count > 0
    )
    return {
        "n_pages": n_pages,
        "abstract_block_count": len(abstract_starts),
        "title_like_line_count": title_like_count,
        "author_like_line_count": author_like_count,
        "program_marker_count": program_marker_count,
        "proceedings_detected": proceedings_detected,
    }


def extract_blocks(lines: list[LineRef]) -> list[AbstractBlock]:
    start_indices = [index for index, line in enumerate(lines) if is_abstract_start(line.text)]
    blocks: list[AbstractBlock] = []
    for offset, start_index in enumerate(start_indices):
        end_index = start_indices[offset + 1] if offset + 1 < len(start_indices) else len(lines)
        block_lines = lines[start_index:end_index]
        if not block_lines:
            continue
        title_parts = [strip_abstract_code(block_lines[0].text)]
        consumed = 1
        for line_ref in block_lines[1:5]:
            if is_abstract_start(line_ref.text) or is_author_like(line_ref.text) or is_institution_like(line_ref.text):
                break
            if is_footer_like(line_ref.text):
                break
            title_parts.append(line_ref.text)
            consumed += 1
        title_text = " ".join(part.strip() for part in title_parts if part.strip())
        header_lines = [line.text for line in block_lines[: min(len(block_lines), consumed + 4)]]
        preview_lines = [line.text for line in block_lines[: min(len(block_lines), 12)] if not is_footer_like(line.text)]
        match = is_abstract_start(block_lines[0].text)
        blocks.append(
            AbstractBlock(
                code=match.group("code") if match else "",
                start_index=start_index,
                end_index=end_index,
                start_page_index=block_lines[0].page_index,
                end_page_index=block_lines[-1].page_index,
                title_text=title_text,
                header_text=" ".join(header_lines),
                preview_text=" ".join(preview_lines),
                line_refs=block_lines,
            )
        )
    return blocks


def best_matching_block(
    blocks: list[AbstractBlock],
    reference_title: str,
    reference_authors: str,
) -> AbstractBlock | None:
    best: AbstractBlock | None = None
    for block in blocks:
        block.title_score = score_title(reference_title, block.title_text)
        block.author_score = score_authors(reference_authors, block.preview_text)
        block.match_score = (0.75 * block.title_score) + (0.25 * block.author_score)
        if best is None or block.match_score > best.match_score:
            best = block
    return best


def trim_pages_from_block(block: AbstractBlock) -> list[dict[str, Any]]:
    grouped: dict[int, list[str]] = {}
    for line_ref in block.line_refs:
        if is_footer_like(line_ref.text):
            continue
        grouped.setdefault(line_ref.page_index, []).append(line_ref.text)
    return [
        {"page_index": page_index, "text": "\n".join(lines).strip()}
        for page_index, lines in sorted(grouped.items())
        if "\n".join(lines).strip()
    ]


def build_trimmed_record(
    source_record: dict[str, Any],
    source_path: Path,
    block: AbstractBlock,
    reference_row: dict[str, str],
) -> dict[str, Any]:
    pages = trim_pages_from_block(block)
    return {
        "paper_id": str(source_record.get("paper_id") or source_path.stem),
        "source_filename": str(source_record.get("source_filename") or ""),
        "source_sha256": str(source_record.get("source_sha256") or ""),
        "source_text_json_path": relative_to_repo(source_path),
        "trim_status": "trimmed_auto",
        "trim_method": "fuzzy_title_author_block_match",
        "proceedings_detected": True,
        "title": (reference_row.get("Title") or "").strip(),
        "authors": (reference_row.get("Authors") or "").strip(),
        "matched_block_code": block.code,
        "matched_block_title": block.title_text,
        "match_score": round(block.match_score, 4),
        "title_score": round(block.title_score, 4),
        "author_score": round(block.author_score, 4),
        "start_page_index": block.start_page_index,
        "end_page_index": block.end_page_index,
        "original_n_pages": int(source_record.get("n_pages") or 0),
        "n_pages": len(pages),
        "page_char_counts": [len(page["text"]) for page in pages],
        "trimmed_at_utc": now_utc_iso(),
        "pages": pages,
    }


def decision_row(
    paper_id: str,
    reference_row: dict[str, str],
    source_record: dict[str, Any],
    source_path: Path,
    trimmed_path: Path | None,
    signals: dict[str, Any],
    trim_status: str,
    trim_reason: str,
    block: AbstractBlock | None,
) -> dict[str, str]:
    return {
        "paper_id": paper_id,
        "covidence_id": (reference_row.get("Covidence") or paper_id).strip(),
        "title": (reference_row.get("Title") or "").strip(),
        "authors": (reference_row.get("Authors") or "").strip(),
        "source_filename": str(source_record.get("source_filename") or ""),
        "source_text_json_path": relative_to_repo(source_path),
        "trimmed_text_json_path": relative_to_repo(trimmed_path) if trimmed_path else "",
        "n_pages": str(signals["n_pages"]),
        "abstract_block_count": str(signals["abstract_block_count"]),
        "title_like_line_count": str(signals["title_like_line_count"]),
        "author_like_line_count": str(signals["author_like_line_count"]),
        "program_marker_count": str(signals["program_marker_count"]),
        "proceedings_detected": bool_text(bool(signals["proceedings_detected"])),
        "trim_status": trim_status,
        "trim_reason": trim_reason,
        "trim_method": "fuzzy_title_author_block_match" if trim_status == "trimmed_auto" else "",
        "matched_block_code": block.code if block else "",
        "matched_block_title": block.title_text if block else "",
        "title_score": f"{block.title_score:.4f}" if block else "",
        "author_score": f"{block.author_score:.4f}" if block else "",
        "match_score": f"{block.match_score:.4f}" if block else "",
        "start_page_index": str(block.start_page_index) if block else "",
        "end_page_index": str(block.end_page_index) if block else "",
        "trimmed_at_utc": now_utc_iso() if trim_status == "trimmed_auto" else "",
    }


def write_registry(rows: list[dict[str, str]], path: Path) -> None:
    fieldnames = [
        "paper_id",
        "covidence_id",
        "title",
        "authors",
        "source_filename",
        "source_text_json_path",
        "trimmed_text_json_path",
        "n_pages",
        "abstract_block_count",
        "title_like_line_count",
        "author_like_line_count",
        "program_marker_count",
        "proceedings_detected",
        "trim_status",
        "trim_reason",
        "trim_method",
        "matched_block_code",
        "matched_block_title",
        "title_score",
        "author_score",
        "match_score",
        "start_page_index",
        "end_page_index",
        "trimmed_at_utc",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def refresh_artifact_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )


def process_record(
    path: Path,
    reference_rows: dict[str, dict[str, str]],
    output_dir: Path,
) -> dict[str, str]:
    record = load_text_record(path)
    paper_id = str(record.get("paper_id") or path.stem)
    reference_row = reference_rows.get(paper_id, {})
    lines = flatten_lines(record)
    signals = proceedings_signals(record, lines)
    trimmed_path = output_dir / f"{paper_id}.json"

    if not signals["proceedings_detected"]:
        if trimmed_path.exists():
            trimmed_path.unlink()
        return decision_row(
            paper_id=paper_id,
            reference_row=reference_row,
            source_record=record,
            source_path=path,
            trimmed_path=None,
            signals=signals,
            trim_status="not_needed",
            trim_reason="Document does not look like a large proceedings/program PDF.",
            block=None,
        )

    blocks = extract_blocks(lines)
    block = best_matching_block(
        blocks=blocks,
        reference_title=(reference_row.get("Title") or "").strip(),
        reference_authors=(reference_row.get("Authors") or "").strip(),
    )
    if block is None:
        if trimmed_path.exists():
            trimmed_path.unlink()
        return decision_row(
            paper_id=paper_id,
            reference_row=reference_row,
            source_record=record,
            source_path=path,
            trimmed_path=None,
            signals=signals,
            trim_status="manual_review_required",
            trim_reason="No abstract block could be segmented from the proceedings text.",
            block=None,
        )

    high_confidence = block.title_score >= 0.70 or (
        block.title_score >= 0.55 and block.author_score >= 0.25 and block.match_score >= 0.60
    )
    if not high_confidence:
        if trimmed_path.exists():
            trimmed_path.unlink()
        return decision_row(
            paper_id=paper_id,
            reference_row=reference_row,
            source_record=record,
            source_path=path,
            trimmed_path=None,
            signals=signals,
            trim_status="manual_review_required",
            trim_reason=(
                "Proceedings detected, but the best abstract block match is below the auto-trim confidence threshold."
            ),
            block=block,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    trimmed_record = build_trimmed_record(record, path, block, reference_row)
    trimmed_path.write_text(
        json.dumps(trimmed_record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return decision_row(
        paper_id=paper_id,
        reference_row=reference_row,
        source_record=record,
        source_path=path,
        trimmed_path=trimmed_path,
        signals=signals,
        trim_status="trimmed_auto",
        trim_reason="Proceedings detected and the target abstract block matched with sufficient confidence.",
        block=block,
    )


def main() -> None:
    args = parse_args()
    reference_rows = load_reference_rows(args.references_csv)
    rows = [
        process_record(path, reference_rows, args.output_dir)
        for path in collect_input_paths(args.input_dir, args.paper_id, args.limit)
    ]
    write_registry(rows, args.registry_path)
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Wrote {len(rows)} rows to {args.registry_path}")


if __name__ == "__main__":
    main()
