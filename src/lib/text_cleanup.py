from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass


DEFAULT_PROFILE = "combined_basic"

# Phase-1 cleanup stays deliberately deterministic and conservative. The goal is
# to repair common corpus-specific text-layer damage without inventing content.
PROFILE_RULES = {
    "basic_mojibake": (
        "unicode_normalize",
        "normalize_spaces",
        "replace_common_mojibake",
        "repair_ligatures",
        "collapse_whitespace",
    ),
    "basic_spacing": (
        "unicode_normalize",
        "normalize_spaces",
        "repair_linebreak_hyphenation",
        "insert_punctuation_spaces",
        "split_camel_case",
        "collapse_whitespace",
    ),
    "header_footer_light": (
        "unicode_normalize",
        "normalize_spaces",
        "remove_known_boilerplate_lines",
        "drop_repeated_boundary_lines",
        "collapse_whitespace",
    ),
    "combined_basic": (
        "unicode_normalize",
        "normalize_spaces",
        "replace_common_mojibake",
        "repair_ligatures",
        "repair_linebreak_hyphenation",
        "insert_punctuation_spaces",
        "split_camel_case",
        "remove_known_boilerplate_lines",
        "drop_repeated_boundary_lines",
        "collapse_whitespace",
    ),
}

SPACE_TRANSLATION = str.maketrans(
    {
        "\u00a0": " ",
        "\u2000": " ",
        "\u2001": " ",
        "\u2002": " ",
        "\u2003": " ",
        "\u2004": " ",
        "\u2005": " ",
        "\u2006": " ",
        "\u2007": " ",
        "\u2008": " ",
        "\u2009": " ",
        "\u200a": " ",
        "\u202f": " ",
        "\u205f": " ",
        "\u3000": " ",
        "\u200b": None,
        "\u200c": None,
        "\u200d": None,
        "\u2060": None,
        "\ufeff": None,
    }
)
SPACE_CHARACTERS = (
    "\u00a0",
    "\u2000",
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2009",
    "\u200a",
    "\u202f",
    "\u205f",
    "\u3000",
)

COMMON_MOJIBAKE_REPLACEMENTS = {
    "/H9253-Aminobutyric": "Gamma-Aminobutyric",
    "/H9253-aminobutyric": "gamma-aminobutyric",
    "\u2425-Aminobutyric": "Gamma-Aminobutyric",
    "\u2425-aminobutyric": "gamma-aminobutyric",
    "\u00e2\u20ac\u201c": "-",
    "\u00e2\u20ac\u201d": "-",
    "\u00e2\u20ac\u02dc": "'",
    "\u00e2\u20ac\u2122": "'",
    "\u00e2\u20ac\u0153": '"',
    "\u00e2\u20ac\u009d": '"',
    "\u00e2\u20ac\u00a6": "...",
    "\u00c2\u00ae": "\u00ae",
    "\u00c2\u00b0": "\u00b0",
    "\u00c2\u00b1": "\u00b1",
}

LIGATURE_REPLACEMENTS = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\u00ef\u00ac\u0080": "ff",
    "\u00ef\u00ac\u0081": "fi",
    "\u00ef\u00ac\u0082": "fl",
    "\u00ef\u00ac\u0083": "ffi",
    "\u00ef\u00ac\u0084": "ffl",
}

BOILERPLATE_PATTERNS = (
    re.compile(r"protected by copyright", re.IGNORECASE),
    re.compile(r"downloaded from", re.IGNORECASE),
    re.compile(r"first published as", re.IGNORECASE),
)


@dataclass(frozen=True)
class CleanupResult:
    cleaned_text: str
    rules_applied: tuple[str, ...]
    artifact_counts_before: dict[str, int]
    artifact_counts_after: dict[str, int]
    changed: bool


@dataclass(frozen=True)
class DocumentCleanupResult:
    pages: list[dict]
    rules_applied: tuple[str, ...]
    artifact_counts_before: dict[str, int]
    artifact_counts_after: dict[str, int]
    changed_page_count: int


def normalize_compare_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", lowered).split())


def count_text_artifacts(text: str) -> dict[str, int]:
    counts = {
        "nbsp_like_spaces": sum(text.count(char) for char in SPACE_CHARACTERS),
        "soft_hyphen": text.count("\u00ad"),
        "linebreak_hyphenation": len(re.findall(r"(?<=\w)-\s*\n\s*(?=\w)", text)),
        "punctuation_space_repairs": len(re.findall(r"(?<=[\.\,\;\:\!\?])(?=[A-Z0-9])", text)),
        "camel_case_boundaries": len(re.findall(r"(?<=[a-z])(?=[A-Z][a-z])", text)),
        "boilerplate_lines": sum(
            1
            for line in text.splitlines()
            if _is_known_boilerplate_line(line)
        ),
        "mojibake_tokens": sum(text.count(token) for token in COMMON_MOJIBAKE_REPLACEMENTS),
        "ligature_tokens": sum(text.count(token) for token in LIGATURE_REPLACEMENTS),
    }
    return counts


def resolve_profile_rules(profile: str) -> tuple[str, ...]:
    resolved = PROFILE_RULES.get((profile or "").strip())
    if resolved is None:
        raise ValueError(f"Unsupported cleanup profile: {profile}")
    return resolved


def clean_page_text(
    text: str,
    *,
    profile: str = DEFAULT_PROFILE,
    repeated_boundary_lines: set[str] | None = None,
    page_index: int = 0,
) -> CleanupResult:
    repeated_boundary_lines = repeated_boundary_lines or set()
    rules = resolve_profile_rules(profile)
    before_counts = count_text_artifacts(text)
    cleaned_text = text
    applied_rules: list[str] = []

    for rule_name in rules:
        next_text = apply_rule(
            rule_name,
            cleaned_text,
            repeated_boundary_lines=repeated_boundary_lines,
            page_index=page_index,
        )
        if next_text != cleaned_text:
            applied_rules.append(rule_name)
            cleaned_text = next_text

    after_counts = count_text_artifacts(cleaned_text)
    return CleanupResult(
        cleaned_text=cleaned_text,
        rules_applied=tuple(applied_rules),
        artifact_counts_before=before_counts,
        artifact_counts_after=after_counts,
        changed=cleaned_text != text,
    )


def clean_document_pages(pages: list[dict], *, profile: str = DEFAULT_PROFILE) -> DocumentCleanupResult:
    rules = resolve_profile_rules(profile)
    repeated_boundary_lines: set[str] = set()
    if "drop_repeated_boundary_lines" in rules:
        # Boundary stripping is only safe when the same line recurs across several
        # pages; otherwise a short title or section header could be removed by mistake.
        repeated_boundary_lines = detect_repeated_boundary_lines(pages)

    cleaned_pages: list[dict] = []
    document_rules: set[str] = set()
    before_totals: Counter[str] = Counter()
    after_totals: Counter[str] = Counter()
    changed_page_count = 0

    for page in pages:
        page_index = int(page.get("page_index", 0) or 0)
        text = str(page.get("text") or "")
        page_result = clean_page_text(
            text,
            profile=profile,
            repeated_boundary_lines=repeated_boundary_lines,
            page_index=page_index,
        )
        before_totals.update(page_result.artifact_counts_before)
        after_totals.update(page_result.artifact_counts_after)
        document_rules.update(page_result.rules_applied)
        if page_result.changed:
            changed_page_count += 1
        cleaned_page = dict(page)
        cleaned_page["text"] = page_result.cleaned_text
        cleaned_pages.append(cleaned_page)

    return DocumentCleanupResult(
        pages=cleaned_pages,
        rules_applied=tuple(sorted(document_rules)),
        artifact_counts_before=dict(before_totals),
        artifact_counts_after=dict(after_totals),
        changed_page_count=changed_page_count,
    )


def detect_repeated_boundary_lines(pages: list[dict]) -> set[str]:
    boundary_counter: Counter[str] = Counter()
    for page in pages:
        text = str(page.get("text") or "")
        non_empty_lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in non_empty_lines[:3]:
            normalized = normalize_compare_text(line)
            if len(normalized) >= 10:
                boundary_counter[normalized] += 1
        for line in non_empty_lines[-3:]:
            normalized = normalize_compare_text(line)
            if len(normalized) >= 10:
                boundary_counter[normalized] += 1
    return {line for line, count in boundary_counter.items() if count >= 3}


def apply_rule(
    rule_name: str,
    text: str,
    *,
    repeated_boundary_lines: set[str],
    page_index: int,
) -> str:
    if rule_name == "unicode_normalize":
        return unicodedata.normalize("NFKC", text)
    if rule_name == "normalize_spaces":
        return normalize_spaces(text)
    if rule_name == "replace_common_mojibake":
        return replace_common_mojibake(text)
    if rule_name == "repair_ligatures":
        return repair_ligatures(text)
    if rule_name == "repair_linebreak_hyphenation":
        return re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    if rule_name == "insert_punctuation_spaces":
        return re.sub(r"(?<=[\.\,\;\:\!\?])(?=[A-Z0-9])", " ", text)
    if rule_name == "split_camel_case":
        return re.sub(r"(?<=[a-z])(?=[A-Z][a-z])", " ", text)
    if rule_name == "remove_known_boilerplate_lines":
        return remove_known_boilerplate_lines(text)
    if rule_name == "drop_repeated_boundary_lines":
        return drop_repeated_boundary_lines(text, repeated_boundary_lines, page_index=page_index)
    if rule_name == "collapse_whitespace":
        return collapse_whitespace(text)
    raise ValueError(f"Unsupported cleanup rule: {rule_name}")


def normalize_spaces(text: str) -> str:
    normalized = text.translate(SPACE_TRANSLATION)
    return normalized.replace("\u00ad", "")


def replace_common_mojibake(text: str) -> str:
    cleaned = text
    for bad, good in COMMON_MOJIBAKE_REPLACEMENTS.items():
        cleaned = cleaned.replace(bad, good)
    # Standalone `Â` often survives failed UTF-8/Windows-1252 decoding around symbols.
    cleaned = re.sub(r"\u00c2(?=[^\w\s]|$)", "", cleaned)
    return cleaned


def repair_ligatures(text: str) -> str:
    cleaned = text
    for bad, good in LIGATURE_REPLACEMENTS.items():
        cleaned = cleaned.replace(bad, good)
    return cleaned


def remove_known_boilerplate_lines(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if _is_known_boilerplate_line(line):
            continue
        lines.append(line)
    return "\n".join(lines)


def _is_known_boilerplate_line(line: str) -> bool:
    raw_line = line.strip()
    if not raw_line:
        return False
    normalized = normalize_compare_text(raw_line)
    if "on may" in normalized and "at" in normalized and "protected by copyright" in normalized:
        return True
    return any(pattern.search(raw_line) for pattern in BOILERPLATE_PATTERNS)


def drop_repeated_boundary_lines(text: str, repeated_boundary_lines: set[str], *, page_index: int) -> str:
    if page_index == 0 or not repeated_boundary_lines:
        return text
    raw_lines = text.splitlines()
    if not raw_lines:
        return text
    kept_lines: list[str] = []
    non_empty_indices = [index for index, line in enumerate(raw_lines) if line.strip()]
    top_candidates = set(non_empty_indices[:3])
    bottom_candidates = set(non_empty_indices[-3:])
    boundary_indices = top_candidates | bottom_candidates
    for index, line in enumerate(raw_lines):
        normalized = normalize_compare_text(line.strip())
        if index in boundary_indices and normalized in repeated_boundary_lines:
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def collapse_whitespace(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    collapsed_lines: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = line == ""
        if is_blank and previous_blank:
            continue
        collapsed_lines.append(line)
        previous_blank = is_blank
    return "\n".join(collapsed_lines).strip()
