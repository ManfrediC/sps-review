from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipelines._proceedings_text import (
    LineRef,
    abstract_code,
    collect_title_cluster,
    flatten_lines,
    is_header_preamble_line,
    is_abstract_boundary,
    is_footer_like,
    is_header_noise,
    is_potential_title_line,
    is_uppercase_title_like,
    normalize_text,
    score_authors,
    score_title,
    strip_abstract_code,
    token_set,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
DEFAULT_SEED = 20260406

METADATA_MARKERS = {
    "conference paper": "conference_paper",
    "conference abstract": "conference_abstract",
    "poster": "poster",
    "abstract": "abstract",
    "supplement": "supplement",
    "proceedings": "proceedings",
    "annual meeting": "annual_meeting",
    "meeting": "meeting",
    "congress": "congress",
    "symposium": "symposium",
    "session": "session",
    "eposter": "eposter",
}
STRONG_MARKER_LABELS = {
    "conference_paper",
    "conference_abstract",
    "poster",
    "supplement",
    "proceedings",
    "annual_meeting",
    "congress",
    "symposium",
    "eposter",
}
LOCAL_MARKERS = {
    "abstract details": "abstract_details",
    "poster session": "poster_session",
    "poster presentation": "poster_presentation",
    "program and abstracts": "program_and_abstracts",
    "program abstracts": "program_abstracts",
    "annual meeting": "annual_meeting",
    "supplement": "supplement",
    "control id": "control_id",
}
STRICT_AUTHOR_CREDENTIAL_RE = re.compile(
    r"\b(MD|M\.D\.|DO|D\.O\.|PHD|PH\.D\.|MSC|M\.S\.|MS|BS|B\.S\.|MBA|MBBS|MPH|RN|FRCPC|FAAN|FRCP|DPhil)\b",
    re.IGNORECASE,
)
STRICT_AUTHOR_PAIR_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z]\.)?\s+[A-Z][a-z]+\b")
CONTROL_ID_RE = re.compile(r"\bcontrol id\b", re.IGNORECASE)


@dataclass(frozen=True)
class TitleAnchor:
    start_index: int
    end_index: int
    title_text: str
    title_score: float
    author_score: float


@dataclass(frozen=True)
class HeaderMatch:
    start_index: int
    end_index: int
    title_text: str
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit non-conference papers for missed proceedings, supplement, or short multi-abstract sources."
    )
    parser.add_argument(
        "--source-registry-path",
        type=Path,
        default=SOURCE_REGISTRY_PATH,
        help="Path to source_categorisation_registry.csv.",
    )
    parser.add_argument(
        "--text-dir",
        type=Path,
        default=TEXT_DIR,
        help="Directory containing extracted text JSON files.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Optional paper ID(s) to audit. Repeat the flag to build a focused batch.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Optional JSON report path.",
    )
    parser.add_argument(
        "--review-csv-path",
        type=Path,
        default=None,
        help="Optional CSV review sheet path.",
    )
    parser.add_argument(
        "--snippet-dir",
        type=Path,
        default=None,
        help="Optional directory for candidate text snippets.",
    )
    parser.add_argument(
        "--min-candidate-score",
        type=int,
        default=7,
        help="Minimum composite score to include a candidate in the review queue.",
    )
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def load_text_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_excerpt_text(text: str) -> str:
    return " ".join(text.split())


def strict_author_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped.split()) > 24:
        return False
    if STRICT_AUTHOR_CREDENTIAL_RE.search(stripped) or CONTROL_ID_RE.search(stripped):
        return True
    if ";" in stripped:
        return True
    if len(STRICT_AUTHOR_PAIR_RE.findall(stripped)) >= 2:
        return True
    if stripped.count(",") >= 2:
        capital_tokens = re.findall(r"\b(?:[A-Z][a-z]{2,}|[A-Z]\.)\b", stripped)
        if len(capital_tokens) >= 4:
            return True
    if re.search(r"\b[A-Z]\.\s*[A-Z][a-z]+", stripped) and stripped.count(",") >= 1:
        return True
    return False


def build_metadata_markers(row: dict[str, str]) -> list[str]:
    markers: list[str] = []
    for field in ("title", "journal", "tags", "notes"):
        value = normalize_text(row.get(field) or "")
        if not value:
            continue
        for needle, label in METADATA_MARKERS.items():
            if needle in value:
                markers.append(f"{field}:{label}")
    return sorted(set(markers))


def has_strong_metadata_markers(markers: list[str]) -> bool:
    for marker in markers:
        field, _, label = marker.partition(":")
        if label not in STRONG_MARKER_LABELS:
            continue
        if field == "journal" and label in {"proceedings", "meeting", "abstract"}:
            continue
        return True
    return False


def proceedings_boundary_code(line_text: str, *, require_alpha: bool = False) -> str:
    code = abstract_code(line_text)
    normalised = re.sub(r"[^A-Z0-9]", "", code.upper())
    if not normalised:
        return ""
    has_alpha = any(character.isalpha() for character in normalised)
    if require_alpha and not has_alpha:
        return ""
    if has_alpha:
        return normalised
    digits = "".join(character for character in normalised if character.isdigit())
    if len(digits) >= 2:
        return normalised
    return ""


def anchor_candidate_indices(lines: list[LineRef], title: str) -> list[int]:
    title_tokens = token_set(title, min_len=4)
    candidates: list[int] = []
    for index, line in enumerate(lines):
        text = line.text
        if is_footer_like(text):
            continue
        line_tokens = token_set(text, min_len=4)
        if is_abstract_boundary(text) or title_tokens.intersection(line_tokens):
            candidates.append(index)
    if not candidates:
        return list(range(min(len(lines), 80)))
    return sorted(set(candidates))


def best_title_anchor(
    lines: list[LineRef],
    reference_title: str,
    reference_authors: str,
) -> TitleAnchor | None:
    best: TitleAnchor | None = None
    best_combined = 0.0
    for start_index in anchor_candidate_indices(lines, reference_title):
        cluster_texts: list[tuple[int, str]] = []
        if is_abstract_boundary(lines[start_index].text) or is_potential_title_line(lines[start_index].text):
            for length in range(1, 5):
                cluster = lines[start_index : start_index + length]
                if len(cluster) < length:
                    break
                if any(is_footer_like(item.text) for item in cluster):
                    break
                text = " ".join(strip_abstract_code(item.text) for item in cluster).strip()
                if text:
                    cluster_texts.append((length, text))
        cluster_texts.append((1, strip_abstract_code(lines[start_index].text)))
        author_window = " ".join(
            line.text for line in lines[max(0, start_index - 2) : min(len(lines), start_index + 6)]
        )
        author_score = score_authors(reference_authors, author_window)
        for length, text in cluster_texts:
            title_score = score_title(reference_title, text)
            combined = (0.8 * title_score) + (0.2 * author_score)
            if combined > best_combined:
                best_combined = combined
                best = TitleAnchor(
                    start_index=start_index,
                    end_index=min(len(lines), start_index + length),
                    title_text=text,
                    title_score=title_score,
                    author_score=author_score,
                )
    return best


def strict_header_match(lines: list[LineRef], start_index: int) -> HeaderMatch | None:
    if start_index < 0 or start_index >= len(lines):
        return None
    line_text = lines[start_index].text
    if is_abstract_boundary(line_text):
        title_text = strip_abstract_code(line_text)
        if not title_text:
            cluster = collect_title_cluster(lines, start_index + 1, max_lines=3)
            title_text = " ".join(line.text for line in cluster).strip()
        return HeaderMatch(
            start_index=start_index,
            end_index=min(len(lines), start_index + 1),
            title_text=title_text or abstract_code(line_text) or line_text,
            reason="coded_boundary",
        )
    if not is_potential_title_line(line_text):
        return None
    if is_header_noise(line_text):
        return None
    if line_text.endswith(".") and not is_uppercase_title_like(line_text):
        return None
    cluster = collect_title_cluster(lines, start_index, max_lines=4)
    if not cluster:
        return None
    end_index = start_index + len(cluster)
    lookahead = lines[end_index : min(len(lines), end_index + 4)]
    if not any(strict_author_line(item.text) for item in lookahead):
        return None
    return HeaderMatch(
        start_index=start_index,
        end_index=end_index,
        title_text=" ".join(line.text for line in cluster).strip(),
        reason="title_plus_authors",
    )


def find_previous_strict_header(lines: list[LineRef], anchor_index: int, max_backtrack: int = 12) -> HeaderMatch | None:
    lower_bound = max(0, anchor_index - max_backtrack)
    for index in range(anchor_index, lower_bound - 1, -1):
        match = strict_header_match(lines, index)
        if match is not None:
            return match
    return None


def find_next_strict_header(
    lines: list[LineRef],
    start_index: int,
    reference_title: str,
    min_gap: int = 4,
    max_scan: int = 180,
) -> HeaderMatch | None:
    lower_bound = max(0, start_index + min_gap)
    upper_bound = min(len(lines), start_index + max_scan)
    for index in range(lower_bound, upper_bound):
        match = strict_header_match(lines, index)
        if match is None:
            continue
        if match.reason == "coded_boundary" and normalize_text(match.title_text) == normalize_text(reference_title):
            continue
        if match.reason == "title_plus_authors" and score_title(reference_title, match.title_text) >= 0.70:
            continue
        rewound_start = index
        while rewound_start > lower_bound and is_header_preamble_line(lines[rewound_start - 1].text):
            rewound_start -= 1
        if rewound_start != match.start_index:
            return HeaderMatch(
                start_index=rewound_start,
                end_index=match.end_index,
                title_text=match.title_text,
                reason=match.reason,
            )
        return match
    return None


def nearby_strict_headers(lines: list[LineRef], centre_index: int, radius: int = 180) -> list[HeaderMatch]:
    headers: list[HeaderMatch] = []
    lower_bound = max(0, centre_index - radius)
    upper_bound = min(len(lines), centre_index + radius)
    index = lower_bound
    while index < upper_bound:
        match = strict_header_match(lines, index)
        if match is None:
            index += 1
            continue
        headers.append(match)
        index = max(index + 1, match.end_index)
    deduped: list[HeaderMatch] = []
    seen_starts: set[int] = set()
    for header in headers:
        if header.start_index in seen_starts:
            continue
        deduped.append(header)
        seen_starts.add(header.start_index)
    return deduped


def build_local_markers(lines: list[LineRef], start_index: int, end_index: int) -> list[str]:
    window = " ".join(
        line.text for line in lines[max(0, start_index - 3) : min(len(lines), end_index + 6)] if not is_footer_like(line.text)
    )
    normalized = normalize_text(window)
    markers = [label for needle, label in LOCAL_MARKERS.items() if needle in normalized]
    return sorted(set(markers))


def build_snippet(lines: list[LineRef], start_index: int, end_index: int) -> str:
    selected = lines[max(0, start_index) : min(len(lines), end_index)]
    return "\n".join(clean_excerpt_text(line.text) for line in selected if clean_excerpt_text(line.text)).strip()


def is_standalone_short_abstract_page(
    record: dict[str, Any],
    *,
    anchor: TitleAnchor,
    next_header: HeaderMatch | None,
    nearby_headers: list[HeaderMatch],
) -> bool:
    n_pages = int(record.get("n_pages") or len(record.get("pages") or []))
    if n_pages > 2:
        return False
    effective_nearby_headers = [
        header
        for header in nearby_headers
        if header.start_index < anchor.start_index or header.start_index >= anchor.end_index
    ]
    if next_header is not None or effective_nearby_headers:
        return False
    return anchor.start_index <= 12


def candidate_level(score: int, *, title_score: float, evidence_count: int) -> str:
    if score >= 9 and title_score >= 0.65 and evidence_count >= 2:
        return "strong_missed_proceedings"
    if score >= 7 and title_score >= 0.55 and evidence_count >= 1:
        return "moderate_missed_proceedings"
    return ""


def assess_row(
    row: dict[str, str],
    record: dict[str, Any],
    *,
    min_candidate_score: int,
) -> dict[str, str] | None:
    lines = flatten_lines(record)
    if not lines:
        return None
    metadata_markers = build_metadata_markers(row)
    anchor = best_title_anchor(lines, row.get("title") or "", row.get("authors") or "")
    if anchor is None:
        return None

    start_header = find_previous_strict_header(lines, anchor.start_index)
    start_index = start_header.start_index if start_header is not None else anchor.start_index
    next_header = find_next_strict_header(lines, start_index, row.get("title") or "")
    end_index = next_header.start_index if next_header is not None else min(len(lines), anchor.end_index + 24)
    local_markers = build_local_markers(lines, start_index, end_index)
    nearby_headers = nearby_strict_headers(lines, anchor.start_index)
    span_lines = max(0, end_index - start_index)
    start_coded = bool(start_header is not None and proceedings_boundary_code(lines[start_header.start_index].text))
    next_coded = bool(next_header is not None and proceedings_boundary_code(lines[next_header.start_index].text))
    start_alpha_coded = bool(
        start_header is not None and proceedings_boundary_code(lines[start_header.start_index].text, require_alpha=True)
    )
    next_alpha_coded = bool(
        next_header is not None and proceedings_boundary_code(lines[next_header.start_index].text, require_alpha=True)
    )
    metadata_route = has_strong_metadata_markers(metadata_markers) or len(metadata_markers) >= 2
    structural_route = bool(local_markers) or next_alpha_coded or (
        start_alpha_coded and len(nearby_headers) >= 2 and span_lines <= 160
    )

    if anchor.title_score < 0.55:
        return None
    if (
        (row.get("source_category") or "").strip() == "single_case_report"
        and int(record.get("n_pages") or len(record.get("pages") or [])) <= 2
        and anchor.start_index <= 12
        and not start_alpha_coded
        and not next_alpha_coded
        and not local_markers
    ):
        return None
    if is_standalone_short_abstract_page(
        record,
        anchor=anchor,
        next_header=next_header,
        nearby_headers=nearby_headers,
    ):
        return None
    if not (metadata_route or structural_route):
        return None
    if not metadata_route and not local_markers and anchor.author_score < 0.25:
        return None

    score = 0
    if anchor.title_score >= 0.85:
        score += 4
    elif anchor.title_score >= 0.70:
        score += 3
    elif anchor.title_score >= 0.60:
        score += 2
    elif anchor.title_score >= 0.50:
        score += 1

    if anchor.author_score >= 0.75:
        score += 2
    elif anchor.author_score >= 0.30:
        score += 1

    score += min(3, len(metadata_markers))
    score += min(3, len(local_markers))

    if start_header is not None:
        score += 1
    if next_header is not None:
        score += 2
    if len(nearby_headers) >= 3:
        score += 2
    elif len(nearby_headers) == 2:
        score += 1

    if end_index > start_index and span_lines <= 120:
        score += 1

    evidence_count = sum(
        1
        for value in (
            metadata_route,
            bool(local_markers),
            next_coded,
            start_coded and len(nearby_headers) >= 2,
        )
        if value
    )
    level = candidate_level(score, title_score=anchor.title_score, evidence_count=evidence_count)
    if not level or score < min_candidate_score:
        return None

    anchor_page_index = lines[anchor.start_index].page_index
    start_label = start_header.reason if start_header is not None else "title_anchor_only"
    next_label = next_header.reason if next_header is not None else ""

    return {
        "paper_id": (row.get("paper_id") or "").strip(),
        "source_category": (row.get("source_category") or "").strip(),
        "classification_confidence": (row.get("classification_confidence") or "").strip(),
        "title": (row.get("title") or "").strip(),
        "authors": (row.get("authors") or "").strip(),
        "journal": (row.get("journal") or "").strip(),
        "notes": (row.get("notes") or "").strip(),
        "candidate_level": level,
        "candidate_score": str(score),
        "title_score": f"{anchor.title_score:.4f}",
        "author_score": f"{anchor.author_score:.4f}",
        "metadata_markers": "; ".join(metadata_markers),
        "local_markers": "; ".join(local_markers),
        "anchor_page_index": str(anchor_page_index),
        "anchor_title_text": anchor.title_text,
        "start_boundary": start_label,
        "next_boundary": next_label,
        "nearby_header_count": str(len(nearby_headers)),
        "span_lines": str(span_lines),
        "recommended_action": "review_for_stage05_proceedings_trim",
        "snippet_text": build_snippet(lines, start_index, end_index),
    }


def write_review_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    review_rows = []
    for row in rows:
        review_rows.append(
            {
                "paper_id": row["paper_id"],
                "candidate_level": row["candidate_level"],
                "candidate_score": row["candidate_score"],
                "source_category": row["source_category"],
                "classification_confidence": row["classification_confidence"],
                "title": row["title"],
                "journal": row["journal"],
                "metadata_markers": row["metadata_markers"],
                "local_markers": row["local_markers"],
                "title_score": row["title_score"],
                "author_score": row["author_score"],
                "anchor_page_index": row["anchor_page_index"],
                "nearby_header_count": row["nearby_header_count"],
                "span_lines": row["span_lines"],
                "recommended_action": row["recommended_action"],
                "review_status": "",
                "review_notes": "",
            }
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(review_rows[0].keys()))
        writer.writeheader()
        writer.writerows(review_rows)


def write_snippets(path: Path, rows: list[dict[str, str]]) -> dict[str, str]:
    path.mkdir(parents=True, exist_ok=True)
    for existing_path in path.glob("*.txt"):
        existing_path.unlink()
    snippet_paths: dict[str, str] = {}
    for row in rows:
        paper_id = row["paper_id"]
        snippet_path = path / f"{paper_id}.txt"
        rendered = "\n".join(
            [
                f"Paper ID: {paper_id}",
                f"Title: {row['title']}",
                f"Journal: {row['journal']}",
                f"Source category: {row['source_category']}",
                f"Candidate level: {row['candidate_level']}",
                f"Candidate score: {row['candidate_score']}",
                f"Metadata markers: {row['metadata_markers'] or 'None'}",
                f"Local markers: {row['local_markers'] or 'None'}",
                f"Anchor page index: {row['anchor_page_index']}",
                f"Start boundary: {row['start_boundary']}",
                f"Next boundary: {row['next_boundary'] or 'None'}",
                "",
                row["snippet_text"],
                "",
            ]
        )
        snippet_path.write_text(rendered, encoding="utf-8")
        snippet_paths[paper_id] = display_path(snippet_path)
    return snippet_paths


def build_report(rows: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "generated_at_utc": now_utc_iso(),
        "candidate_count": len(rows),
        "candidate_level_counts": dict(Counter(row["candidate_level"] for row in rows)),
        "source_category_counts": dict(Counter(row["source_category"] for row in rows)),
        "selected_rows": [
            {
                "paper_id": row["paper_id"],
                "candidate_level": row["candidate_level"],
                "candidate_score": row["candidate_score"],
                "source_category": row["source_category"],
                "title_score": row["title_score"],
                "author_score": row["author_score"],
                "metadata_markers": row["metadata_markers"],
                "local_markers": row["local_markers"],
            }
            for row in rows
        ],
    }


def main() -> None:
    args = parse_args()
    source_rows = load_csv_rows(args.source_registry_path)
    selected_ids = {str(paper_id).strip() for paper_id in args.paper_id if str(paper_id).strip()}
    candidates: list[dict[str, str]] = []
    for row in source_rows:
        if (row.get("source_category") or "").strip() == "conference_abstract":
            continue
        paper_id = (row.get("paper_id") or "").strip()
        if selected_ids and paper_id not in selected_ids:
            continue
        text_path = args.text_dir / f"{paper_id}.json"
        if not text_path.exists():
            continue
        assessment = assess_row(
            row,
            load_text_record(text_path),
            min_candidate_score=args.min_candidate_score,
        )
        if assessment is None:
            continue
        candidates.append(assessment)

    candidates.sort(
        key=lambda row: (
            row["candidate_level"] != "strong_missed_proceedings",
            -int(row["candidate_score"]),
            -int(row["nearby_header_count"]),
            row["paper_id"],
        )
    )

    snippet_paths: dict[str, str] = {}
    if args.snippet_dir is not None:
        snippet_paths = write_snippets(args.snippet_dir, candidates)

    if args.review_csv_path is not None:
        write_review_csv(args.review_csv_path, candidates)

    if args.output_path is not None:
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        report = build_report(candidates)
        for row in report["selected_rows"]:
            paper_id = row["paper_id"]
            if paper_id in snippet_paths:
                row["snippet_path"] = snippet_paths[paper_id]
        args.output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Selected {len(candidates)} missed-proceedings candidates.")
    if candidates:
        print(f"Candidate level counts: {dict(Counter(row['candidate_level'] for row in candidates))}")
        print(f"Source category counts: {dict(Counter(row['source_category'] for row in candidates))}")


if __name__ == "__main__":
    main()
