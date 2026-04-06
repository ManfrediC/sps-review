from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any


ABSTRACT_START_RE = re.compile(
    r"^(?P<code>(?:[A-Z]{1,3}-)?(?:[A-Z]{1,2})?\d{2,3}|\d{2,3})\.\s+(?P<title>.+)$"
)
ABSTRACT_START_DELIM_RE = re.compile(
    r"^(?P<code>(?:[A-Z]{1,3}-)?(?:[A-Z]{1,2})?\d{1,5}|\d{2,5})\s*[\.\|\:\-\)]\s+(?P<title>[A-Za-z].+)$"
)
ABSTRACT_START_SPACE_CODE_RE = re.compile(
    r"^(?P<code>(?:[A-Z]{1,3}-)?(?:[A-Z]{1,2})?\d{1,5})\s+(?P<title>[A-Za-z].+)$"
)
ABSTRACT_CODE_ONLY_RE = re.compile(
    r"^(?P<code>(?:[A-Z]{1,3}-)?(?:[A-Z]{1,2})?\d{1,3})$"
)
ABSTRACT_BOUNDARY_RE = re.compile(
    r"^(?P<code>(?:[A-Z]{1,3}-)?(?:[A-Z]{1,2})?\d{1,5})\s*(?:[\.\|\:\-\)]\s+|$)"
)
AUTHOR_CREDENTIAL_RE = re.compile(
    r"\b(MD|M\.D\.|DO|D\.O\.|PHD|PH\.D\.|MSC|M\.S\.|MS|BS|B\.S\.|BA|B\.A\.|MBA|MBBS|MPH|RN|FRCPC|FAAN|FRCP|DPhil)\b",
    re.IGNORECASE,
)
CONTROL_ID_RE = re.compile(r"\bcontrol id\b", re.IGNORECASE)

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
    "copyright",
    "all rights reserved",
    "supplement",
    "poster sessions",
)
SECTION_HEADING_MARKERS = (
    "background",
    "purpose",
    "objective",
    "objectives",
    "introduction",
    "case",
    "methods",
    "results",
    "discussion",
    "conclusion",
)
HEADER_NOISE_MARKERS = (
    "abstracts",
    "poster sessions",
    "program and abstracts",
    "table of contents",
    "contents",
    "index",
    "corresponding author",
    "keywords",
    "disclosure",
)


@dataclass(frozen=True)
class LineRef:
    global_index: int
    page_index: int
    line_index: int
    text: str


@dataclass(frozen=True)
class ProceedingsPattern:
    coded_header_count: int
    uncoded_header_count: int
    uppercase_header_count: int
    control_id_header_count: int
    dominant_start_style: str


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return " ".join(ascii_text.split())


def token_set(text: str, min_len: int = 3) -> set[str]:
    return {token for token in normalize_text(text).split() if len(token) >= min_len}


def normalize_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def flatten_lines(record: dict[str, Any]) -> list[LineRef]:
    lines: list[LineRef] = []
    global_index = 0
    for page in record.get("pages") or []:
        page_index = int(page.get("page_index") or 0)
        page_text = str(page.get("text") or "")
        for line_index, raw_line in enumerate(page_text.splitlines()):
            line = " ".join(raw_line.split())
            if line:
                lines.append(
                    LineRef(
                        global_index=global_index,
                        page_index=page_index,
                        line_index=line_index,
                        text=line,
                    )
                )
                global_index += 1
    return lines


def is_abstract_start(line: str) -> re.Match[str] | None:
    stripped = line.strip()
    strict_match = ABSTRACT_START_RE.match(stripped)
    if strict_match:
        return strict_match
    delim_match = ABSTRACT_START_DELIM_RE.match(stripped)
    if delim_match:
        return delim_match
    space_match = ABSTRACT_START_SPACE_CODE_RE.match(stripped)
    if space_match:
        code = str(space_match.group("code") or "")
        title = str(space_match.group("title") or "")
        if re.search(r"[A-Z]", code) and len(title.split()) >= 3:
            return space_match
    return None


def is_abstract_code_only(line: str) -> re.Match[str] | None:
    stripped = line.strip()
    return ABSTRACT_CODE_ONLY_RE.match(stripped) or ABSTRACT_BOUNDARY_RE.match(stripped)


def is_abstract_boundary(line: str) -> bool:
    return is_abstract_start(line) is not None or is_abstract_code_only(line) is not None


def is_author_like(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if AUTHOR_CREDENTIAL_RE.search(stripped):
        return True
    if CONTROL_ID_RE.search(stripped):
        return True
    normalized = normalize_text(stripped)
    if normalized.count(" and ") >= 1 and len(normalized.split()) <= 18:
        return True
    comma_count = stripped.count(",")
    if comma_count >= 3:
        return True
    if ";" in stripped and comma_count >= 1:
        return True
    if ";" in stripped and len(stripped.split()) <= 20:
        return True
    if re.search(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", stripped) and len(stripped.split()) <= 22:
        return True
    return False


def is_institution_like(line: str) -> bool:
    normalized = normalize_text(line)
    return any(marker in normalized for marker in INSTITUTION_MARKERS)


def is_footer_like(line: str) -> bool:
    normalized = normalize_text(line)
    return any(marker in normalized for marker in FOOTER_MARKERS)


def is_section_heading(line: str) -> bool:
    normalized = normalize_text(line)
    return any(normalized.startswith(marker) for marker in SECTION_HEADING_MARKERS)


def is_header_noise(line: str) -> bool:
    normalized = normalize_text(line)
    if not normalized:
        return True
    if normalized in HEADER_NOISE_MARKERS:
        return True
    return any(normalized.startswith(marker) for marker in HEADER_NOISE_MARKERS)


def is_title_like(line: str) -> bool:
    if is_abstract_boundary(line) or is_author_like(line) or is_institution_like(line) or is_footer_like(line):
        return False
    words = line.split()
    if len(words) < 4 or len(words) > 24:
        return False
    alpha_words = sum(1 for word in words if re.search(r"[A-Za-z]", word))
    return alpha_words >= max(3, len(words) - 2)


def is_uppercase_title_like(line: str) -> bool:
    stripped = line.strip()
    if (
        not stripped
        or is_abstract_boundary(stripped)
        or is_author_like(stripped)
        or is_institution_like(stripped)
        or is_footer_like(stripped)
        or is_section_heading(stripped)
        or is_header_noise(stripped)
    ):
        return False
    words = [word for word in stripped.split() if re.search(r"[A-Za-z]", word)]
    if len(words) < 2 or len(words) > 24:
        return False
    letters = [char for char in stripped if char.isalpha()]
    if len(letters) < 6:
        return False
    upper_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
    return upper_ratio >= 0.68


def is_potential_title_line(line: str) -> bool:
    stripped = line.strip()
    if (
        not stripped
        or is_abstract_boundary(stripped)
        or is_author_like(stripped)
        or is_institution_like(stripped)
        or is_footer_like(stripped)
        or is_section_heading(stripped)
        or is_header_noise(stripped)
    ):
        return False
    if is_title_like(stripped) or is_uppercase_title_like(stripped):
        return True
    words = [word for word in stripped.split() if re.search(r"[A-Za-z]", word)]
    if len(words) < 3 or len(words) > 18:
        return False
    if stripped.endswith("."):
        return False
    alpha_words = sum(1 for word in words if re.search(r"[A-Za-z]", word))
    return alpha_words >= max(2, len(words) - 1)


def is_title_continuation_like(line: str) -> bool:
    stripped = line.strip()
    if (
        not stripped
        or is_abstract_boundary(stripped)
        or is_author_like(stripped)
        or is_institution_like(stripped)
        or is_footer_like(stripped)
        or is_section_heading(stripped)
        or is_header_noise(stripped)
    ):
        return False
    if is_potential_title_line(stripped):
        return True
    words = [word for word in stripped.split() if re.search(r"[A-Za-z]", word)]
    if len(words) > 8:
        return False
    return bool(words)


def strip_abstract_code(line: str) -> str:
    stripped = line.strip()
    match = is_abstract_start(stripped)
    if match and match.groupdict().get("title"):
        return str(match.group("title")).strip()
    boundary_match = ABSTRACT_BOUNDARY_RE.match(stripped)
    if boundary_match:
        without_code = stripped[boundary_match.end("code") :].strip(" .|:-)")
        if without_code:
            return without_code
    return line.strip()


def abstract_code(line: str) -> str:
    stripped = line.strip()
    start_match = is_abstract_start(stripped)
    if start_match and start_match.groupdict().get("code"):
        return str(start_match.group("code"))
    code_only_match = is_abstract_code_only(line)
    if code_only_match and code_only_match.groupdict().get("code"):
        return str(code_only_match.group("code"))
    return ""


def body_signal_count(lines: list[LineRef]) -> int:
    return sum(1 for line in lines if is_section_heading(line.text))


def body_char_count(lines: list[LineRef]) -> int:
    if not lines:
        return 0
    header_span = min(len(lines), 6)
    body_lines = [line.text for line in lines[header_span:] if not is_footer_like(line.text)]
    return len(" ".join(body_lines))


def has_enough_body(lines: list[LineRef]) -> tuple[bool, int, bool]:
    section_hits = body_signal_count(lines)
    chars = body_char_count(lines)
    header_only = section_hits == 0 and chars < 280
    enough = chars >= 420 or (section_hits >= 3 and chars >= 160) or (section_hits >= 1 and chars >= 220)
    return enough, section_hits, header_only


def collect_title_cluster(lines: list[LineRef], start_index: int, max_lines: int = 4) -> list[LineRef]:
    cluster: list[LineRef] = []
    end_index = min(len(lines), start_index + max_lines)
    for index in range(start_index, end_index):
        line_ref = lines[index]
        if index == start_index:
            if not is_potential_title_line(line_ref.text):
                break
        elif not is_title_continuation_like(line_ref.text):
            break
        cluster.append(line_ref)
    return cluster


def soft_header_score(lines: list[LineRef], start_index: int) -> tuple[int, int, str]:
    if start_index >= len(lines):
        return 0, start_index, ""
    current = lines[start_index]
    if not is_potential_title_line(current.text):
        return 0, start_index, ""
    if current.text.endswith(".") and not is_uppercase_title_like(current.text):
        return 0, start_index, ""
    if start_index > 0:
        previous = lines[start_index - 1]
        if previous.page_index == current.page_index and (
            is_uppercase_title_like(previous.text)
            or is_title_continuation_like(previous.text)
            or is_abstract_boundary(previous.text)
            or is_author_like(previous.text)
            or is_institution_like(previous.text)
        ) and not previous.text.endswith("."):
            return 0, start_index, ""

    title_cluster = collect_title_cluster(lines, start_index)
    if not title_cluster:
        return 0, start_index, ""

    end_index = start_index + len(title_cluster)
    lookahead = lines[end_index : min(len(lines), end_index + 6)]
    author_hit = any(is_author_like(line.text) for line in lookahead)
    institution_hit = any(is_institution_like(line.text) for line in lookahead)
    section_hit = any(is_section_heading(line.text) for line in lookahead)
    control_id_hit = any(CONTROL_ID_RE.search(line.text) for line in lookahead)
    score = 0
    reasons: list[str] = []
    if author_hit:
        score += 2
        reasons.append("author")
    if institution_hit:
        score += 1
        reasons.append("institution")
    if section_hit:
        score += 1
        reasons.append("section")
    if len(title_cluster) >= 2:
        score += 1
        reasons.append("wrapped_title")
    if is_uppercase_title_like(current.text):
        score += 1
        reasons.append("uppercase_title")
    if control_id_hit:
        score += 1
        reasons.append("control_id")
    if not author_hit and not institution_hit and not section_hit:
        return 0, end_index, ""
    return score, end_index, "+".join(reasons)


def infer_proceedings_pattern(lines: list[LineRef]) -> ProceedingsPattern:
    coded_header_count = sum(1 for line in lines if is_abstract_boundary(line.text))
    uncoded_header_count = 0
    uppercase_header_count = 0
    control_id_header_count = 0
    index = 0
    while index < len(lines):
        score, end_index, _ = soft_header_score(lines, index)
        if score >= 3:
            uncoded_header_count += 1
            if is_uppercase_title_like(lines[index].text):
                uppercase_header_count += 1
            if any(CONTROL_ID_RE.search(line.text) for line in lines[index : min(len(lines), end_index + 4)]):
                control_id_header_count += 1
            index = max(index + 1, end_index)
            continue
        index += 1

    dominant_start_style = "coded"
    if uncoded_header_count >= max(2, coded_header_count):
        dominant_start_style = "uncoded_uppercase" if uppercase_header_count >= max(2, uncoded_header_count // 3) else "uncoded_title_author"
    elif coded_header_count >= 3 and uncoded_header_count >= 3:
        dominant_start_style = "mixed"

    return ProceedingsPattern(
        coded_header_count=coded_header_count,
        uncoded_header_count=uncoded_header_count,
        uppercase_header_count=uppercase_header_count,
        control_id_header_count=control_id_header_count,
        dominant_start_style=dominant_start_style,
    )


def header_boundary(
    lines: list[LineRef],
    start_index: int,
    pattern: ProceedingsPattern,
    allow_soft: bool = True,
) -> tuple[bool, int, str, int]:
    if start_index >= len(lines):
        return False, start_index, "", 0
    if is_abstract_boundary(lines[start_index].text):
        return True, start_index + 1, "coded_boundary", 100
    if not allow_soft:
        return False, start_index, "", 0
    score, end_index, reason = soft_header_score(lines, start_index)
    threshold = 4 if pattern.dominant_start_style == "coded" else 3
    if score >= threshold:
        return True, end_index, f"soft_header::{reason or 'title_context'}", score
    return False, end_index, "", score


def header_start_indices(lines: list[LineRef], pattern: ProceedingsPattern) -> list[int]:
    starts: list[int] = []
    index = 0
    while index < len(lines):
        matched, end_index, _, _ = header_boundary(lines, index, pattern, allow_soft=True)
        if matched:
            starts.append(index)
            index = max(index + 1, end_index)
            continue
        index += 1
    return starts


def find_previous_header_index(
    lines: list[LineRef],
    anchor_index: int,
    pattern: ProceedingsPattern,
    target_code: str = "",
    max_backtrack: int = 12,
) -> tuple[int | None, str]:
    target_code_norm = normalize_code(target_code)
    lower_bound = max(0, anchor_index - max_backtrack)
    for index in range(anchor_index, lower_bound - 1, -1):
        line_code_norm = normalize_code(abstract_code(lines[index].text))
        if target_code_norm and line_code_norm and line_code_norm == target_code_norm:
            return index, "target_code_boundary"
        matched, _, reason, _ = header_boundary(lines, index, pattern, allow_soft=True)
        if matched:
            if reason == "coded_boundary":
                return index, "backtrack_abstract_boundary"
            return index, "backtrack_soft_header"
    return None, ""


def find_next_header_index(
    lines: list[LineRef],
    start_index: int,
    pattern: ProceedingsPattern,
    expected_code: str = "",
    next_code: str = "",
    min_gap: int = 4,
) -> tuple[int | None, str]:
    expected_code_norm = normalize_code(expected_code)
    next_code_norm = normalize_code(next_code)
    for index in range(max(0, start_index + min_gap), len(lines)):
        line = lines[index]
        if is_abstract_boundary(line.text):
            boundary_code_norm = normalize_code(abstract_code(line.text))
            if boundary_code_norm and expected_code_norm and boundary_code_norm == expected_code_norm:
                continue
            if next_code_norm and boundary_code_norm == next_code_norm:
                return index, "next_index_code_boundary"
            if boundary_code_norm:
                return index, "next_abstract_boundary"
        matched, _, reason, _ = header_boundary(lines, index, pattern, allow_soft=True)
        if matched and reason != "coded_boundary":
            return index, "next_soft_header"
    return None, "no_header_found"
