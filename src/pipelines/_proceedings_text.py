from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


ALPHANUMERIC_ABSTRACT_CODE_RE = r"(?:[A-Z]{1,3}-)?(?:[A-Z]{1,2})?\d{1,5}(?:[.-]?[A-Z]{2,6})?"
NUMERIC_ABSTRACT_CODE_RE = r"\d{2,5}"
SPACED_ALPHA_ABSTRACT_CODE_RE = r"[A-Z]{1,4}\s+\d{1,5}(?:[A-Z])?"
ABSTRACT_START_RE = re.compile(
    rf"^(?P<code>{ALPHANUMERIC_ABSTRACT_CODE_RE}|{NUMERIC_ABSTRACT_CODE_RE})\.\s+(?P<title>.+)$"
)
ABSTRACT_START_DELIM_RE = re.compile(
    rf"^(?P<code>{ALPHANUMERIC_ABSTRACT_CODE_RE}|{NUMERIC_ABSTRACT_CODE_RE})\s*[\.\|\:\-\)]\s+(?P<title>[A-Za-z].+)$"
)
SPACED_ALPHA_ABSTRACT_START_RE = re.compile(
    rf"^(?P<code>{SPACED_ALPHA_ABSTRACT_CODE_RE})\s*(?:[\.\|\:\-\)]\s*)?(?P<title>[A-Za-z].+)$"
)
ID_ABSTRACT_START_RE = re.compile(
    r"^(?P<code>ID\s+\d{1,5})\s*[\.\|\:\-\)\u2013\u2014]\s+(?P<title>.+)$",
    re.IGNORECASE,
)
ABSTRACT_START_SPACE_CODE_RE = re.compile(
    rf"^(?P<code>{ALPHANUMERIC_ABSTRACT_CODE_RE})\s+(?P<title>[A-Za-z].+)$"
)
ABSTRACT_CODE_ONLY_RE = re.compile(rf"^(?P<code>{ALPHANUMERIC_ABSTRACT_CODE_RE})$")
SPACED_ALPHA_ABSTRACT_CODE_ONLY_RE = re.compile(rf"^(?P<code>{SPACED_ALPHA_ABSTRACT_CODE_RE})$")
ID_ABSTRACT_CODE_ONLY_RE = re.compile(r"^(?P<code>ID\s+\d{1,5})$", re.IGNORECASE)
NUMERIC_DATE_CODE_ONLY_RE = re.compile(
    r"^(?P<code>\d{1,5})\s+\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}$",
    re.IGNORECASE,
)
POSTER_CODE_ONLY_RE = re.compile(r"^(?P<code>Poster\s+\d{1,5}[A-Z]?)$", re.IGNORECASE)
SESSION_CODE_ONLY_RE = re.compile(
    r"^(?P<code>[A-Z]{1,4}\d{1,2}(?:\.\d+)+(?:\s*[-–]\s*\d{1,5})?)$"
)
ABSTRACT_BOUNDARY_RE = re.compile(
    rf"^(?P<code>{ALPHANUMERIC_ABSTRACT_CODE_RE}|{NUMERIC_ABSTRACT_CODE_RE})\s*(?:[\.\|\:\-\)]\s+|$)"
)
AUTHOR_CREDENTIAL_RE = re.compile(
    r"\b(MD|M\.D\.|DO|D\.O\.|PHD|PH\.D\.|MSC|M\.S\.|MS|BS|B\.S\.|BA|B\.A\.|MBA|MBBS|MPH|RN|FRCPC|FAAN|FRCP|DPhil)\b",
    re.IGNORECASE,
)
CONTROL_ID_RE = re.compile(r"\bcontrol id\b", re.IGNORECASE)
DOI_LINE_RE = re.compile(r"^\s*doi\s*:", re.IGNORECASE)
DATE_LINE_RE = re.compile(
    r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:,\s+[a-z]+(?:\s+\d{1,2})?(?:,\s+\d{4})?)?$",
    re.IGNORECASE,
)
ORDINAL_DATE_LINE_RE = re.compile(r"^\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}$", re.IGNORECASE)
TIME_RANGE_RE = re.compile(r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\s*[–-]\s*\d{1,2}:\d{2}\s*(?:am|pm)?\b", re.IGNORECASE)
REFERENCE_ENTRY_RE = re.compile(r"^[A-Z][a-z]+,\s*[A-Z]")
PROCEEDINGS_PAGE_HEADER_RE = re.compile(r"^[A-Z]?\d+\s*ABSTRACTS$", re.IGNORECASE)
JOURNAL_VOLUME_METADATA_RE = re.compile(
    r"\bvol\.\s*\d+\b.*\b(?:suppl\.?|supplement)\b.*\b(?:19|20)\d{2}\b",
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
    "material and methods",
    "materials and methods",
    "methods",
    "method",
    "design methods",
    "study design methods",
    "results",
    "observation",
    "observations",
    "discussion",
    "conclusion",
    "conclusions",
)
HEADER_NOISE_MARKERS = (
    "abstracts",
    "abstract details",
    "poster session",
    "poster sessions",
    "program and abstracts",
    "table of contents",
    "contents",
    "index",
    "corresponding author",
    "keywords",
    "disclosure",
)
ARTICLE_MARKERS = (
    "article open access",
    "article history",
    "a r t i c l e i n f o",
    "available online",
    "correspondence",
    "full disclosures",
    "disclosure of interest",
    "go to neurology org",
    "article processing charge",
    "creative commons attribution",
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


def alpha_word_count(text: str) -> int:
    return sum(1 for word in text.split() if re.search(r"[A-Za-z]", word))


def starts_like_title_opening(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    for character in stripped:
        if character.isalpha():
            return character.isupper()
    return bool(re.match(r"^[\d\(\[]", stripped))


def is_article_numbered_section(line: str) -> bool:
    match = re.match(r"^\d+\.\s+(?P<title>.+)$", line.strip())
    if not match:
        return False
    title = str(match.group("title") or "").strip()
    if not title:
        return False
    normalized = normalize_text(title)
    if normalized == "references" or normalized == "disclosure of interest":
        return True
    return alpha_word_count(title) <= 4 and is_section_heading(title)


def is_article_metadata_line(line: str) -> bool:
    normalized = normalize_text(line)
    if not normalized:
        return False
    if any(normalized.startswith(marker) for marker in ARTICLE_MARKERS):
        return True
    if normalized.startswith("received ") or normalized.startswith("accepted "):
        return True
    if normalized.startswith("keywords") or normalized == "keywords":
        return True
    return False


def looks_like_reference_entry(text: str) -> bool:
    stripped = text.strip()
    normalized = normalize_text(stripped)
    if not stripped or not normalized:
        return False
    if not REFERENCE_ENTRY_RE.match(stripped):
        return False
    has_year = bool(re.search(r"\b(?:19|20)\d{2}\b", stripped))
    return has_year or " et al " in f" {normalized} "


def parse_reference_surnames(authors: str) -> list[str]:
    surnames: list[str] = []
    for chunk in re.split(r";| and | & ", authors or "", flags=re.IGNORECASE):
        part = chunk.strip()
        if not part:
            continue
        part = re.sub(r"\b(MD|PhD|DO|MSc|MBBS|RN|FRCP|FAAN)\b\.?", "", part, flags=re.IGNORECASE).strip()
        if "," in part:
            surname = part.split(",", 1)[0].strip()
        else:
            tokens = [token for token in re.split(r"\s+", part) if token]
            if not tokens:
                continue
            surname = tokens[-1]
            if len(tokens) >= 2 and len(tokens[-1]) <= 2:
                surname = tokens[-2]
        normalized = normalize_text(surname)
        if len(normalized) <= 1:
            continue
        if normalized and normalized not in surnames:
            surnames.append(normalized)
    return surnames[:8]


def is_inline_reference_citation(line: str) -> bool:
    stripped = line.strip()
    normalized = normalize_text(stripped)
    if not stripped or not normalized:
        return False
    if looks_like_reference_entry(stripped):
        return True
    has_year = bool(re.search(r"\b(?:19|20)\d{2}\b", stripped))
    has_compact_citation = bool(re.search(r"\b\d{1,4}\s*[:;]\s*\d{1,4}(?:\s*-\s*\d{1,4})?\b", stripped))
    if has_year and stripped.startswith("("):
        return True
    if has_year and " et al " in f" {normalized} ":
        return True
    if has_year and has_compact_citation:
        return True
    return False


def score_title(reference_title: str, candidate_text: str) -> float:
    ref_norm = normalize_text(reference_title)
    candidate_norm = normalize_text(candidate_text)
    if not ref_norm or not candidate_norm:
        return 0.0
    if ref_norm == candidate_norm:
        return 1.0
    sequence = SequenceMatcher(None, ref_norm, candidate_norm).ratio()
    ref_tokens = token_set(reference_title, min_len=4)
    candidate_tokens = token_set(candidate_text, min_len=4)
    overlap = len(ref_tokens & candidate_tokens) / max(1, len(ref_tokens))
    if ref_norm in candidate_norm or candidate_norm in ref_norm:
        overlap = max(overlap, 0.95)
    blended = (0.35 * sequence) + (0.65 * overlap)
    return max(min(sequence, overlap), blended)


def score_authors(reference_authors: str, candidate_text: str) -> float:
    surnames = parse_reference_surnames(reference_authors)
    if not surnames:
        return 0.0
    normalized_candidate = normalize_text(candidate_text)
    candidate_tokens = token_set(candidate_text, min_len=3)
    matches = 0
    for surname in surnames:
        if surname in normalized_candidate:
            matches += 1
            continue
        surname_tokens = {token for token in surname.split() if len(token) >= 3}
        if surname_tokens and surname_tokens.issubset(candidate_tokens):
            matches += 1
    return matches / len(surnames)


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
    id_match = ID_ABSTRACT_START_RE.match(stripped)
    if id_match:
        title = str(id_match.groupdict().get("title") or "")
        if title and (is_header_noise(title) or looks_like_reference_entry(title)):
            return None
        return id_match
    spaced_match = SPACED_ALPHA_ABSTRACT_START_RE.match(stripped)
    if spaced_match:
        title = str(spaced_match.groupdict().get("title") or "")
        if title and (is_header_noise(title) or looks_like_reference_entry(title)):
            return None
        if not starts_like_title_opening(title):
            return None
        return spaced_match
    strict_match = ABSTRACT_START_RE.match(stripped)
    if strict_match:
        code = str(strict_match.groupdict().get("code") or "")
        title = str(strict_match.groupdict().get("title") or "")
        if title and (is_header_noise(title) or looks_like_reference_entry(title)):
            return None
        if not re.search(r"[A-Z]", code) and (alpha_word_count(title) < 4 or is_section_heading(title)):
            return None
        return strict_match
    delim_match = ABSTRACT_START_DELIM_RE.match(stripped)
    if delim_match:
        code = str(delim_match.groupdict().get("code") or "")
        title = str(delim_match.groupdict().get("title") or "")
        if title and (is_header_noise(title) or looks_like_reference_entry(title)):
            return None
        if not re.search(r"[A-Z]", code) and (alpha_word_count(title) < 4 or is_section_heading(title)):
            return None
        return delim_match
    space_match = ABSTRACT_START_SPACE_CODE_RE.match(stripped)
    if space_match:
        code = str(space_match.group("code") or "")
        title = str(space_match.group("title") or "")
        if title and (is_header_noise(title) or looks_like_reference_entry(title)):
            return None
        if not starts_like_title_opening(title):
            return None
        if not re.search(r"[A-Z]", code) and (alpha_word_count(title) < 4 or is_section_heading(title)):
            return None
        if re.search(r"[A-Z]", code) and len(title.split()) >= 3:
            return space_match
    return None


def is_abstract_code_only(line: str) -> re.Match[str] | None:
    stripped = line.strip()
    poster_match = POSTER_CODE_ONLY_RE.match(stripped)
    if poster_match:
        return poster_match
    spaced_code_match = SPACED_ALPHA_ABSTRACT_CODE_ONLY_RE.match(stripped)
    if spaced_code_match:
        return spaced_code_match
    id_code_match = ID_ABSTRACT_CODE_ONLY_RE.match(stripped)
    if id_code_match:
        return id_code_match
    numeric_date_code_match = NUMERIC_DATE_CODE_ONLY_RE.match(stripped)
    if numeric_date_code_match:
        return numeric_date_code_match
    session_match = SESSION_CODE_ONLY_RE.match(stripped)
    if session_match:
        return session_match
    code_only_match = ABSTRACT_CODE_ONLY_RE.match(stripped)
    if code_only_match:
        return code_only_match
    boundary_match = ABSTRACT_BOUNDARY_RE.match(stripped)
    if not boundary_match:
        return None
    boundary_code = str(boundary_match.group("code") or "")
    digits = "".join(character for character in boundary_code if character.isdigit())
    if not re.search(r"[A-Z]", boundary_code) and len(digits) < 2:
        return None
    trailing = stripped[boundary_match.end("code") :].strip(" .|:-)")
    if trailing and is_header_noise(trailing):
        return None
    return boundary_match


def is_abstract_boundary(line: str) -> bool:
    return is_abstract_start(line) is not None or is_abstract_code_only(line) is not None


def author_fragment_count(text: str) -> int:
    count = 0
    for fragment in re.split(r";|,", text):
        part = fragment.strip(" .-*")
        if not part:
            continue
        if re.search(r"\b(?:[A-Z]{1,3}\.\s*)+[A-Z][A-Za-z'’\-]+\d*\b", part):
            count += 1
            continue
        if re.search(r"\b[A-Z]{1,3}\s+[A-Z][A-Z'’\-]{2,}\b", part):
            count += 1
            continue
        if re.search(r"\b[A-Z][A-Za-z'’\-]+\d*\s+[A-Z][A-Za-z'’\-]+\d*\b", part):
            count += 1
    return count


def has_initialled_author_pattern(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if re.search(r"\b(?:[A-Z]\.){1,3}\s*[A-Z][A-Za-z'’\-]+\d*\b", stripped):
        return True
    return bool(re.search(r"\b[A-Z][A-Za-z'’\-]+\d*,\s*(?:[A-Z]\.){1,3}\s*[A-Z][A-Za-z'’\-]+\d*\b", stripped))


def looks_like_numbered_affiliation_line(line: str) -> bool:
    stripped = line.strip()
    normalized = normalize_text(stripped)
    if not stripped or not normalized:
        return False
    if not re.match(r"^\d+[A-Za-z]", stripped):
        return False
    if "," not in stripped:
        return False
    if any(marker in normalized for marker in INSTITUTION_MARKERS):
        return True
    return bool(
        re.search(
            r"\b(?:neurology|medicine|immunology|neuroimmunology|oncology|pathology|engineering|computer|paediatrics|pediatrics|surgery|radiology)\b",
            normalized,
        )
    )


def is_author_like(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if is_footer_like(stripped) or is_header_noise(stripped):
        return False
    if is_inline_reference_citation(stripped):
        return False
    if AUTHOR_CREDENTIAL_RE.search(stripped):
        return True
    if CONTROL_ID_RE.search(stripped):
        return True
    normalized = normalize_text(stripped)
    tokens = normalized.split()
    fragment_count = author_fragment_count(stripped)
    initialled_author = has_initialled_author_pattern(stripped)
    name_pair_count = len(re.findall(r"\b[A-Z][A-Za-z'’\-]+\d*\s+[A-Z][A-Za-z'’\-]+\d*\b", stripped))
    stopword_tokens = {"of", "and", "or", "with", "for", "from", "into", "during", "after", "before", "about", "between"}
    if ";" not in stripped and "," not in stripped and not initialled_author and not re.search(r"\b[A-Z]\.", stripped):
        if any(
            stopword in tokens
            for stopword in stopword_tokens
        ):
            return False
    comma_count = stripped.count(",")
    if (
        ";" not in stripped
        and not initialled_author
        and fragment_count < 2
        and name_pair_count < 2
        and any(stopword in tokens for stopword in stopword_tokens)
    ):
        return False
    if comma_count >= 2 and fragment_count >= 2:
        return True
    if ";" in stripped and comma_count >= 1:
        return True
    if ";" in stripped and len(stripped.split()) <= 20:
        return True
    if comma_count >= 1 and initialled_author:
        return True
    if name_pair_count >= 2 and len(stripped.split()) <= 22:
        return True
    if comma_count >= 1 and name_pair_count >= 1 and len(stripped.split()) <= 22:
        return True
    if fragment_count >= 2 and len(stripped.split()) <= 22:
        return True
    return False


def is_institution_like(line: str) -> bool:
    normalized = normalize_text(line)
    return looks_like_numbered_affiliation_line(line) or any(marker in normalized for marker in INSTITUTION_MARKERS)


def is_footer_like(line: str) -> bool:
    stripped = line.strip()
    if PROCEEDINGS_PAGE_HEADER_RE.match(stripped):
        return True
    if JOURNAL_VOLUME_METADATA_RE.search(stripped):
        return True
    normalized = normalize_text(line)
    return any(marker in normalized for marker in FOOTER_MARKERS)


def is_section_heading(line: str) -> bool:
    normalized = normalize_text(line)
    return any(normalized.startswith(marker) for marker in SECTION_HEADING_MARKERS)


def is_header_noise(line: str) -> bool:
    normalized = normalize_text(line)
    if not normalized:
        return True
    if DOI_LINE_RE.match(line.strip()):
        return True
    if normalized == "abstract":
        return True
    if normalized.startswith("abstract wcn"):
        return True
    if normalized.startswith("abstract number"):
        return True
    if normalized.startswith("meeting"):
        return True
    if normalized.startswith("topic "):
        return True
    if normalized.startswith("first published "):
        return True
    if re.match(r"^no \d", normalized):
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
    if not starts_like_title_opening(stripped):
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
        if (
            previous.page_index == current.page_index
            and not is_footer_like(previous.text)
            and not is_header_noise(previous.text)
            and not is_abstract_boundary(previous.text)
            and len(normalize_text(previous.text).split()) >= 5
            and not previous.text.endswith((".", ":", ";"))
        ):
            return 0, start_index, ""

    title_cluster = collect_title_cluster(lines, start_index)
    if not title_cluster:
        return 0, start_index, ""

    end_index = start_index + len(title_cluster)
    lookahead = [
        line
        for line in lines[end_index : min(len(lines), end_index + 6)]
        if not is_header_noise(line.text) and not is_footer_like(line.text)
    ]
    author_hit = any(is_author_like(line.text) for line in lookahead[:3])
    institution_hit = any(is_institution_like(line.text) for line in lookahead[:3])
    section_hit = any(is_section_heading(line.text) for line in lookahead[:4])
    control_id_hit = any(CONTROL_ID_RE.search(line.text) for line in lookahead[:4])
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
    if not author_hit and not control_id_hit:
        return 0, end_index, ""
    return score, end_index, "+".join(reasons)


def coded_header_boundary(lines: list[LineRef], start_index: int) -> tuple[bool, int]:
    if start_index >= len(lines):
        return False, start_index
    line_text = lines[start_index].text
    if is_abstract_start(line_text) is not None:
        return True, start_index + 1
    code_match = is_abstract_code_only(line_text)
    if code_match is None:
        return False, start_index
    saw_preamble = False
    for line in lines[start_index + 1 : min(len(lines), start_index + 5)]:
        if is_footer_like(line.text):
            continue
        if is_potential_title_line(line.text) or is_uppercase_title_like(line.text):
            return True, start_index + 1
        if is_header_noise(line.text) or is_header_preamble_line(line.text) or is_abstract_code_only(line.text):
            saw_preamble = True
            continue
        if saw_preamble and is_author_like(line.text):
            continue
        break
    return False, start_index


def infer_proceedings_pattern(lines: list[LineRef]) -> ProceedingsPattern:
    coded_header_count = sum(1 for index in range(len(lines)) if coded_header_boundary(lines, index)[0])
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
    if coded_header_count == 0 and uncoded_header_count >= 1:
        dominant_start_style = "uncoded_uppercase" if uppercase_header_count >= 1 else "uncoded_title_author"
    elif uncoded_header_count >= max(2, coded_header_count):
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
    coded_match, coded_end_index = coded_header_boundary(lines, start_index)
    if coded_match:
        return True, coded_end_index, "coded_boundary", 100
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


def rewind_header_preamble_start(lines: list[LineRef], start_index: int, lower_bound: int = 0) -> int:
    index = start_index
    while index > lower_bound:
        previous = lines[index - 1]
        if previous.page_index != lines[start_index].page_index:
            break
        if not is_header_preamble_line(previous.text):
            break
        index -= 1
    return index


def is_header_preamble_line(line: str) -> bool:
    stripped = line.strip()
    normalized = normalize_text(stripped)
    if not normalized:
        return False
    if DOI_LINE_RE.match(stripped):
        return False
    if normalized.startswith(("disclosure", "keywords", "corresponding author")):
        return False
    if is_footer_like(stripped):
        return True
    if is_header_noise(stripped):
        return True
    if ORDINAL_DATE_LINE_RE.match(stripped):
        return True
    if DATE_LINE_RE.match(normalized) or normalized.startswith(
        ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    ):
        return True
    if TIME_RANGE_RE.search(stripped):
        return True
    if normalized.startswith("posters available for viewing"):
        return True
    words = normalized.split()
    if 1 <= len(words) <= 5 and not stripped.endswith("."):
        if is_author_like(stripped) or is_section_heading(stripped):
            return False
        title_case_ratio = sum(1 for word in stripped.split() if word[:1].isupper()) / max(1, len(stripped.split()))
        if is_uppercase_title_like(stripped) or is_title_like(stripped) or title_case_ratio >= 0.75:
            return True
    return False


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
                return rewind_header_preamble_start(lines, index, lower_bound=max(0, start_index + min_gap)), "next_index_code_boundary"
            if boundary_code_norm:
                return rewind_header_preamble_start(lines, index, lower_bound=max(0, start_index + min_gap)), "next_abstract_boundary"
        matched, _, reason, _ = header_boundary(lines, index, pattern, allow_soft=True)
        if matched and reason != "coded_boundary":
            return rewind_header_preamble_start(lines, index, lower_bound=max(0, start_index + min_gap)), "next_soft_header"
    return None, "no_header_found"
