from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pipelines._sps_case_counting import estimate_sps_case_count


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
TEXT_TRIM_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
OUTPUT_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"
CURRENT_YEAR = datetime.now(timezone.utc).year

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
TENS_WORDS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

CONFERENCE_MARKERS = (
    "annual meeting",
    "meeting abstract",
    "meeting abstracts",
    "conference abstract",
    "conference abstracts",
    "paper abstracts",
    "poster abstract",
    "poster session",
    "supplement",
    "symposium",
    "poster presentation",
    "oral presentation",
    "poster number",
    "abstract number",
)
CONFERENCE_METADATA_MARKERS = (
    "conference paper",
    "conference",
    "proceedings",
    "proceeding",
    "abstract",
    "annual meeting",
    "symposium",
    "book chapter",
    "supplement",
)
REVIEW_MARKERS = (
    "review article",
    "systematic review",
    "literature review",
    "review of the literature",
    "narrative review",
    "meta analysis",
    "meta-analysis",
)
CASE_REPORT_MARKERS = (
    "case report",
    "report of a case",
    "a case of",
    "in a patient",
    "a patient with",
    "presenting with",
    "new case",
    "case note",
    "case vignette",
    "clinical vignette",
    "rare case",
    "unusual case",
    "unique case",
    "first case",
    "novel case",
)
# Weaker markers that suggest case-level reporting but can also appear in
# non-case-report contexts (reviews, group studies, conference summaries).
WEAK_CASE_MARKERS = (
    "we report",
    "we describe",
    "we present",
    "is reported",
    "is described",
    "is presented",
)
MULTI_CASE_MARKERS = (
    "case series",
    "series of",
    "patients with",
    "review of patients",
    "review of 21 patients",
    "review of 57 patients",
    "consecutive patients",
    "our patients",
)
OBSERVATIONAL_MARKERS = (
    "retrospective",
    "cohort",
    "cross sectional",
    "cross-sectional",
    "observational",
    "prospective",
    "registry",
    "clinical characteristics of patients",
)
INTERVENTIONAL_MARKERS = (
    "controlled study",
    "controlled trial",
    "randomized",
    "randomised",
    "double blind",
    "double-blind",
    "placebo",
    "open label",
    "cross over",
    "crossover",
    "trial",
)
NON_CLINICAL_MARKERS = (
    "dominant epitope",
    "epitope",
    "autoantigen",
    "synaptic protein",
    "immunohistochemistry",
    "molecular",
    "binding",
    "antibody levels",
    "recognized by autoantibodies",
    "recognised by autoantibodies",
    "serologic",
)
LAB_METHOD_MARKERS = (
    "northern blot",
    "cloned",
    "cdna",
    "hek293",
    "plasmid",
    "plasmids",
    "immunofluorescence",
    "indirect immunofluorescence",
    "expression vector",
    "recombinant proteins",
    "recombinant",
    "gene coding",
    "tissue distribution",
    "substrates",
    "passive antibody transfer model",
    "insertion of full length",
    "sera from",
    "healthy controls",
)
TRANSLATIONAL_CLINICAL_MARKERS = (
    "elisa",
    "western blot",
    "western blots",
    "serological markers",
    "serological evaluation",
    "positive serum",
    "monoclonal",
    "epitope specificities",
    "intrathecal synthesis",
    "antibody titers",
    "antibody titres",
    "glyralpha1",
)
ABSTRACT_STRUCTURE_MARKERS = (
    "background",
    "methods",
    "method s",
    "results",
    "result s",
    "conclusions",
    "conclusion s",
)
SINGULAR_PATIENT_MARKERS = (
    "a patient",
    "woman with",
    "man with",
    "child with",
    "boy with",
    "girl with",
    "a woman",
    "a man",
    "a boy",
    "a girl",
    "one patient",
    "single patient",
)
SPS_CONTEXT_MARKERS = (
    "stiff person syndrome",
    "stiff-person syndrome",
    "stiff man syndrome",
    "stiff-man syndrome",
    " stiff person ",
    " stiff-person ",
    " stiff man ",
    " stiff-man ",
    " sps ",
    " sms ",
    " spsd ",
)
COUNT_POSITIVE_CONTEXT_MARKERS = (
    "we identified",
    "we reviewed",
    "we examined",
    "we studied",
    "we describe",
    "we described",
    "we report",
    "we reported",
    "our patients",
    "consecutive patients",
    "confirmed stiff",
    "had sps",
    "with sps",
    "had sms",
    "with sms",
)
COUNT_NEGATIVE_CONTEXT_MARKERS = (
    "controls",
    "control patients",
    "healthy controls",
    "healthy individuals",
    "other diseases",
    "disease controls",
    "literature review",
    "review of the literature",
    "published references",
    "published reports",
    "identified in the literature",
    "reported from",
    "prevalence",
    "confidence interval",
    "inhab",
)
FULL_ARTICLE_HEADER_MARKERS = (
    "case report",
    "research open access",
    "research article",
    "original article",
    "original research",
)
SUPPLEMENT_REFERENCE_MARKERS = (
    "supplement",
    "suppl",
    "meetingabstracts",
    "meeting abstracts",
)
COUNT_FILLER_PATTERN = r"(?:[a-z][a-z0-9\-/]*\s+)"
SPS_DIAGNOSIS_PATTERN = (
    r"(?:stiff person syndrome|stiff-person syndrome|stiff man syndrome|"
    r"stiff-man syndrome|sps|sms|spsd)"
)

COUNT_TOKEN_PATTERN = (
    r"(?P<count>\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"thirty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"forty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"fifty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"sixty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"seventy(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"eighty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"ninety(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?)"
)
COUNT_NOUN_PATTERN = r"(?:patients|patient|cases|case subjects|subjects|women|men|children|people|individuals)"
PATIENT_COUNT_RE = re.compile(
    rf"\b{COUNT_TOKEN_PATTERN}(?!\s*%)\s+{COUNT_FILLER_PATTERN}{{0,4}}?{COUNT_NOUN_PATTERN}\b",
    re.IGNORECASE,
)
CONTEXTUAL_PATIENT_COUNT_RE = re.compile(
    rf"\b(?:of|in|among|with|included|including|includes|review of|series of|cohort of|study of|"
    rf"observations in|observed in|our|these|those|following)\s+{COUNT_TOKEN_PATTERN}(?!\s*%)\s+"
    rf"{COUNT_FILLER_PATTERN}{{0,4}}?{COUNT_NOUN_PATTERN}\b",
    re.IGNORECASE,
)
SPS_DIRECT_COUNT_RE = re.compile(
    rf"\b{COUNT_TOKEN_PATTERN}(?!\s*%)\s+{COUNT_FILLER_PATTERN}{{0,2}}?"
    rf"(?:had|with|were|diagnosed with|presented with)\s+{COUNT_FILLER_PATTERN}{{0,3}}?"
    rf"{SPS_DIAGNOSIS_PATTERN}\b",
    re.IGNORECASE,
)
COUNT_RANGE_RE = re.compile(r"\b\d+\s+to\s+\d+\s+(?:percent|cases|patients)\b", re.IGNORECASE)
TITLE_CASE_COUNT_RE = re.compile(
    rf"\b{COUNT_TOKEN_PATTERN}(?!\s*%)\s+{COUNT_FILLER_PATTERN}{{0,2}}?(?:cases|patients)\b",
    re.IGNORECASE,
)
PATIENT_LABEL_RE = re.compile(r"\b(?:patient|case)\s*(?:#\s*)?(?:\d+|i|ii|iii|iv|v|vi|vii|viii|ix|x)\b")


# Build now utc iso.
def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Build bool text.
def bool_text(value: bool) -> str:
    return "true" if value else "false"


# Convert a path to a repository-relative string.
def relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


# Normalize text.
def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return " ".join(ascii_text.split())


def normalize_count_text(text: str) -> str:
    count_text = unicodedata.normalize("NFKD", text or "")
    count_text = count_text.encode("ascii", "ignore").decode("ascii")
    count_text = re.sub(r"\b\d+\.\d+\b", " decimal_number ", count_text)
    count_text = re.sub(r"\b\d+/\d+\b", " fraction_number ", count_text)
    count_text = count_text.replace("%", " percent ")
    count_text = count_text.lower()
    count_text = re.sub(r"[^a-z0-9]+", " ", count_text)
    return " ".join(count_text.split())


# Load reference rows.
def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            (row.get("Covidence") or "").strip(): row
            for row in reader
            if (row.get("Covidence") or "").strip()
        }


# Load CSV rows by ID.
def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        latest: dict[str, dict[str, str]] = {}
        for row in reader:
            key = (row.get(key_column) or "").strip()
            if key:
                latest[key] = row
    return latest


# Load text record.
def load_text_record(path: Path) -> dict[str, Any]:
    record = json.loads(path.read_text(encoding="utf-8"))
    record["_path"] = str(path)
    return record


# Collect text paths.
def collect_text_paths(input_dir: Path, paper_ids: list[str], limit: int) -> list[Path]:
    paths = sorted(input_dir.glob("*.json"))
    if paper_ids:
        wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
        paths = [path for path in paths if path.stem in wanted]
    if limit and limit > 0:
        paths = paths[:limit]
    return paths


# Build marker hits.
def marker_hits(text: str, markers: tuple[str, ...]) -> list[str]:
    return [marker for marker in markers if marker in text]


# Build count patient labels.
def count_patient_labels(text: str) -> int:
    return len(set(PATIENT_LABEL_RE.findall(text)))


# Parse count token.
def parse_count_token(token: str) -> int:
    stripped = token.strip().lower().replace("-", " ")
    if stripped.isdigit():
        return int(stripped)
    if stripped in NUMBER_WORDS:
        return NUMBER_WORDS[stripped]
    parts = stripped.split()
    if len(parts) == 2 and parts[0] in TENS_WORDS and parts[1] in NUMBER_WORDS and NUMBER_WORDS[parts[1]] < 10:
        return TENS_WORDS[parts[0]] + NUMBER_WORDS[parts[1]]
    return 0


def split_text_units(text: str) -> list[str]:
    return [unit for unit in re.split(r"[.!?;\n]+", text or "") if unit.strip()]


def mentions_sps_context(text: str) -> bool:
    padded = f" {text} "
    return any(marker in padded for marker in SPS_CONTEXT_MARKERS)


def count_sps_mentions(text: str) -> int:
    return len(re.findall(r"\b(?:stiff person syndrome|stiff man syndrome|sps|sms|spsd)\b", text or ""))


def score_count_candidate(
    unit: str,
    match: re.Match[str],
    *,
    count: int,
    title_mentions_sps: bool,
    source_weight: int,
) -> int:
    start, end = match.span()
    window = unit[max(0, start - 48) : min(len(unit), end + 128)]
    local_window = unit[max(0, start - 24) : min(len(unit), end + 48)]
    score = source_weight
    if count >= 1900 and count <= CURRENT_YEAR + 1:
        score -= 10
    elif count > 500:
        score -= 8
    if title_mentions_sps:
        score += 1
    if mentions_sps_context(window):
        score += 5
    if any(marker in window for marker in COUNT_POSITIVE_CONTEXT_MARKERS):
        score += 2
    if any(marker in window for marker in COUNT_NEGATIVE_CONTEXT_MARKERS):
        score -= 6
    if COUNT_RANGE_RE.search(local_window):
        score -= 6
    if "percent" in local_window:
        score -= 6
    if "percent patients" in local_window or "percent of patients" in local_window:
        score -= 6
    if re.search(r"\b(?:igg|igm|iga|nmol|microg|ng|iu|mg|ml)\b", local_window) and "patients" not in match.group(0):
        score -= 6
    if re.search(r"\b(?:less than|fewer than|more than|up to|approximately|about)\s+\d+\s+cases?\b", window):
        score -= 5
    if re.search(r"\b(?:of|among)\s+\d+\s+patients?\b", window) and not mentions_sps_context(window):
        score -= 2
    return score


# Parse page span.
def parse_page_span(pages: str) -> int:
    text = (pages or "").strip()
    if not text:
        return 0
    normalized = text.replace("–", "-").replace("—", "-")
    match = re.match(r"^[A-Za-z]?(?P<start>\d+)-[A-Za-z]?(?P<end>\d+)$", normalized)
    if match:
        start = int(match.group("start"))
        end = int(match.group("end"))
        if end >= start:
            return (end - start) + 1
        # Handle abbreviated end pages: "1588-92" means 1588-1592.
        end_str = match.group("end")
        start_str = match.group("start")
        if len(end_str) < len(start_str):
            expanded_end = int(start_str[: len(start_str) - len(end_str)] + end_str)
            if expanded_end >= start:
                return (expanded_end - start) + 1
    single = re.match(r"^[A-Za-z]?(?P<page>\d+)$", normalized)
    if single:
        return 1
    return 0


# Check whether individual demographic signal.
def has_individual_demographic_signal(text: str) -> bool:
    lowered = (text or "").lower()
    if "year old" in lowered:
        return True
    return bool(
        re.search(r"\b(?:a|one)\s+(?:male|female|man|woman|boy|girl)\b", lowered)
        or re.search(r"\b(?:male|female|man|woman|boy|girl)\s+patient\b", lowered)
    )


# Build record text window.
def record_text_window(record: dict[str, Any], *, use_all_pages: bool) -> str:
    pages = record.get("pages") or []
    selected = pages if use_all_pages else pages[:5]
    return "\n".join(str(page.get("text") or "") for page in selected)


# Build leading text.
def leading_text(text: str, limit: int = 1200) -> str:
    stripped = (text or "").strip()
    return stripped[:limit]


# Build confidence label.
def confidence_label(value: float, gap: float) -> str:
    if value >= 4.0 and gap >= 1.5:
        return "high"
    if value >= 2.5 and gap >= 0.75:
        return "medium"
    return "low"


# Classify record.
def classify_record(
    *,
    reference_row: dict[str, str],
    text_record: dict[str, Any],
    preferred_record: dict[str, Any],
    preferred_path: Path,
    trim_row: dict[str, str],
) -> dict[str, str]:
    title = (reference_row.get("Title") or "").strip()
    abstract = (reference_row.get("Abstract") or "").strip()
    authors = (reference_row.get("Authors") or "").strip()
    journal = (reference_row.get("Journal") or "").strip()
    volume = (reference_row.get("Volume") or "").strip()
    issue = (reference_row.get("Issue") or "").strip()
    notes = (reference_row.get("Notes") or "").strip()
    tags = (reference_row.get("Tags") or "").strip()
    pages = (reference_row.get("Pages") or "").strip()
    doi = (reference_row.get("DOI") or "").strip()
    normalized_title = normalize_text(title)
    title_mentions_sps = mentions_sps_context(normalized_title)
    normalized_journal = normalize_text(journal)
    normalized_issue = normalize_text(issue)
    normalized_doi = normalize_text(doi)
    normalized_tags = normalize_text(tags)

    trimmed_used = preferred_path.parent == TEXT_TRIMMED_DIR
    early_body_text = "\n".join(str(p.get("text") or "") for p in (preferred_record.get("pages") or [])[:3])
    meta_source_text = " ".join([title, abstract, tags, pages])
    meta_text = normalize_text(meta_source_text)
    full_text_window = normalize_text(record_text_window(text_record, use_all_pages=False))
    text_window = normalize_text(record_text_window(preferred_record, use_all_pages=trimmed_used))
    header_text = leading_text(full_text_window, 1500)
    case_signal_text = normalize_text(" ".join([title, leading_text(abstract)]))
    # When metadata is sparse, fall back to extracted text for case signal detection.
    if len(case_signal_text) < 80:
        early_body = normalize_text(early_body_text)
        case_signal_text = normalize_text(" ".join([case_signal_text, leading_text(early_body, 1500)]))
    combined = " ".join(part for part in [meta_text, text_window] if part).strip()

    conference_hits = marker_hits(meta_text, CONFERENCE_MARKERS)
    conference_metadata_hits = marker_hits(meta_text, CONFERENCE_METADATA_MARKERS)
    header_conference_hits = marker_hits(header_text, CONFERENCE_MARKERS)
    review_source_text = meta_text if len(meta_text) >= 80 else combined
    review_hits = marker_hits(review_source_text, REVIEW_MARKERS)
    case_report_hits = marker_hits(case_signal_text, CASE_REPORT_MARKERS)
    multi_case_hits = marker_hits(case_signal_text, MULTI_CASE_MARKERS)
    observational_hits = marker_hits(combined, OBSERVATIONAL_MARKERS)
    interventional_hits = marker_hits(combined, INTERVENTIONAL_MARKERS)
    # Search metadata first; fall back to combined text for lab markers when
    # metadata is sparse (many papers lack abstracts in the reference export).
    non_clinical_hits = marker_hits(meta_text, NON_CLINICAL_MARKERS)
    lab_method_hits = marker_hits(meta_text, LAB_METHOD_MARKERS)
    translational_hits = marker_hits(combined, TRANSLATIONAL_CLINICAL_MARKERS)
    if len(meta_text) < 120:
        non_clinical_hits = marker_hits(combined, NON_CLINICAL_MARKERS)
        lab_method_hits = marker_hits(combined, LAB_METHOD_MARKERS)
    structured_abstract_hits = marker_hits(meta_text, ABSTRACT_STRUCTURE_MARKERS)
    singular_patient_hits = marker_hits(case_signal_text, SINGULAR_PATIENT_MARKERS)
    weak_case_hits = marker_hits(case_signal_text, WEAK_CASE_MARKERS)

    count_estimate = estimate_sps_case_count(
        title=title,
        abstract=abstract,
        early_body_text=early_body_text,
    )
    count_hint = count_estimate.likely_case_count
    # Restrict patient_label_count to first 3 pages to avoid reference-list labels.
    early_text_for_labels = normalize_text(early_body_text)
    patient_label_count = count_patient_labels(early_text_for_labels)
    proceedings_detected = (trim_row.get("proceedings_detected") or "").strip().lower() == "true"
    trim_status = (trim_row.get("trim_status") or "").strip()
    trim_match_score = float((trim_row.get("match_score") or "0").strip() or 0)
    page_span = parse_page_span(pages)
    abstract_word_count = len(normalize_text(abstract).split())
    preferred_page_count = int(preferred_record.get("n_pages") or len(preferred_record.get("pages") or []) or 0)
    full_page_count = int(text_record.get("n_pages") or len(text_record.get("pages") or []) or preferred_page_count or 0)
    # Detect supplement-style pages (e.g. "S123", "S45-S47").
    supplement_page = bool(re.match(r"^[Ss]\d+", pages)) if pages else False
    electronic_single_page = bool(re.match(r"^[Ee]\d+$", pages)) if pages else False
    supplement_issue = any(marker in normalized_issue for marker in SUPPLEMENT_REFERENCE_MARKERS)
    conference_doi_signal = "conference" in normalized_doi or "meetingabstracts" in normalized_doi
    header_only_proceedings = proceedings_detected and trim_status == "header_only_source"
    short_source_document = 0 < full_page_count <= 2
    short_abstract_like = 0 < abstract_word_count <= 450
    short_source_abstract_like = short_source_document and short_abstract_like
    full_article_header = any(marker in header_text for marker in FULL_ARTICLE_HEADER_MARKERS)
    explicit_conference_signal = bool(
        conference_hits
        or conference_metadata_hits
        or header_conference_hits
        or supplement_page
        or supplement_issue
        or conference_doi_signal
    )
    large_proceedings_volume = proceedings_detected and full_page_count >= 20 and trim_status in {
        "trimmed_auto",
        "manual_review_required",
        "header_only_source",
    }
    full_article_veto = full_article_header or (full_page_count >= 4 and not large_proceedings_volume)
    usable_proceedings_signal = proceedings_detected and not full_article_header and (
        explicit_conference_signal or short_source_document or large_proceedings_volume
    )
    conference_like_metadata = (
        supplement_page
        or supplement_issue
        or conference_doi_signal
        or bool(conference_hits)
        or bool(conference_metadata_hits)
        or bool(header_conference_hits)
        or (not page_span and short_source_abstract_like and len(structured_abstract_hits) >= 3)
        or (
            page_span
            and page_span <= 2
            and short_source_abstract_like
            and len(structured_abstract_hits) >= 3
            and (explicit_conference_signal or usable_proceedings_signal)
        )
        or (electronic_single_page and short_source_abstract_like and (explicit_conference_signal or usable_proceedings_signal))
        or short_source_abstract_like
        or (usable_proceedings_signal and short_source_document)
        or (page_span == 1 and "abstract" in meta_text and short_source_document)
    )
    if full_article_veto and not explicit_conference_signal:
        conference_like_metadata = False
    sps_focus_count = count_sps_mentions(meta_text)
    low_sps_focus = not title_mentions_sps and sps_focus_count <= 1
    strong_translational_signal = len(translational_hits) >= 2
    strong_lab_signal = len(non_clinical_hits) >= 2 or len(lab_method_hits) >= 2 or strong_translational_signal
    original_study_signal = bool(
        structured_abstract_hits
        or observational_hits
        or interventional_hits
        or lab_method_hits
        or patient_label_count > 0
    )

    # Check demographic signal in both metadata and extracted text.
    demographic_single_case = (
        has_individual_demographic_signal(case_signal_text)
        or has_individual_demographic_signal(early_text_for_labels)
    )
    explicit_single_case = bool(case_report_hits or singular_patient_hits or demographic_single_case)
    title_case_count_signal = bool(re.search(r"\b(?:two|three|four|five|six|seven|eight|nine|ten|\d+)\s+cases\b", normalized_title))
    quantified_multi_case_signal = bool(
        count_hint >= 2
        and count_estimate.count_confidence in {"high", "medium"}
        and count_estimate.count_basis in {"title_count_signal", "abstract_count_signal"}
    )
    quantified_large_group_signal = quantified_multi_case_signal and count_hint >= 12
    explicit_multi_case = bool(
        "case series" in multi_case_hits
        or patient_label_count >= 2
        or title_case_count_signal
        or quantified_multi_case_signal
    )
    strong_original_cohort_signal = (
        title_mentions_sps and (
            bool(observational_hits) or explicit_multi_case or len(structured_abstract_hits) >= 2
        )
    ) or (
        strong_translational_signal and quantified_multi_case_signal
    )
    broad_review_shape = bool(review_hits) and not title_mentions_sps and not explicit_single_case and not explicit_multi_case

    scores = {
        "conference_abstract": 0.0,
        "review_article": 0.0,
        "lab_heavy_clinical_or_translational": 0.0,
        "non_clinical_basic_science": 0.0,
        "interventional_study": 0.0,
        "observational_group_study": 0.0,
        "case_series_or_multi_case": 0.0,
        "single_case_report": 0.0,
        "unclear_manual_review": 0.0,
    }

    scores["conference_abstract"] += len(conference_hits) * 1.2
    scores["conference_abstract"] += len(conference_metadata_hits) * 1.2
    scores["conference_abstract"] += len(header_conference_hits) * 1.4
    if supplement_page:
        scores["conference_abstract"] += 2.5
    if supplement_issue:
        scores["conference_abstract"] += 2.5
    if conference_doi_signal:
        scores["conference_abstract"] += 3.0
    if electronic_single_page and short_source_abstract_like and not full_article_header:
        scores["conference_abstract"] += 1.0
    if len(structured_abstract_hits) >= 3 and page_span and page_span <= 2:
        scores["conference_abstract"] += 3.0
    if not page_span and full_page_count == 1 and short_abstract_like and len(structured_abstract_hits) >= 3:
        scores["conference_abstract"] += 2.5
    if short_source_abstract_like and not full_article_header:
        scores["conference_abstract"] += 1.8
    if conference_like_metadata:
        scores["conference_abstract"] += 2.0
    if usable_proceedings_signal:
        scores["conference_abstract"] += 2.0
    if trim_status == "trimmed_auto" and usable_proceedings_signal:
        scores["conference_abstract"] += 1.0
    if trim_status == "manual_review_required" and usable_proceedings_signal:
        scores["conference_abstract"] += 1.5
    if full_article_veto and not explicit_conference_signal:
        scores["conference_abstract"] -= 4.0
    if header_only_proceedings and full_page_count > 3:
        scores["conference_abstract"] -= 3.0
    if header_only_proceedings and short_source_document:
        scores["conference_abstract"] += 2.0

    # Only suppress review scoring when there are strong case markers (not just
    # weak ones like "we present") and the paper clearly describes individual cases.
    strong_case_signal = bool(case_report_hits or singular_patient_hits)
    if not (strong_case_signal and not explicit_multi_case):
        scores["review_article"] += len(review_hits) * 1.8
    if "review article" in normalized_tags:
        scores["review_article"] += 0.5 if original_study_signal else 2.5
    if original_study_signal:
        scores["review_article"] -= 1.0
    if review_hits and low_sps_focus and not conference_like_metadata:
        scores["review_article"] += 2.5
        scores["case_series_or_multi_case"] -= 1.0
        scores["lab_heavy_clinical_or_translational"] -= 1.0
        scores["observational_group_study"] -= 1.0

    if explicit_single_case:
        scores["single_case_report"] += 2.5
    if explicit_single_case and not explicit_multi_case:
        scores["single_case_report"] += 1.5
    scores["single_case_report"] += len(case_report_hits) * 1.5
    scores["single_case_report"] += len(singular_patient_hits) * 0.5
    if strong_translational_signal and case_report_hits == ["a patient with"] and not demographic_single_case:
        scores["single_case_report"] -= 2.5
    # Weak case markers contribute less; suppressed when conference-like metadata is present.
    if not conference_like_metadata:
        scores["single_case_report"] += len(weak_case_hits) * 0.5
    # Short papers (1-3 pages) that are not conference-like are likely case reports.
    if page_span and 1 <= page_span <= 3 and not conference_like_metadata:
        scores["single_case_report"] += 1.0

    if explicit_multi_case:
        scores["case_series_or_multi_case"] += 2.5
    if quantified_multi_case_signal and not observational_hits and not quantified_large_group_signal:
        scores["case_series_or_multi_case"] += 1.5
    if quantified_large_group_signal and patient_label_count < 2 and "case series" not in multi_case_hits:
        scores["case_series_or_multi_case"] -= 1.5
    if patient_label_count >= 2:
        scores["case_series_or_multi_case"] += 2.0
    scores["case_series_or_multi_case"] += len(multi_case_hits) * 1.2

    scores["observational_group_study"] += len(observational_hits) * 1.4
    if observational_hits and not explicit_single_case:
        scores["observational_group_study"] += 1.8
    if quantified_multi_case_signal and (observational_hits or len(structured_abstract_hits) >= 2):
        scores["observational_group_study"] += 1.5
    if quantified_large_group_signal and patient_label_count < 2:
        scores["observational_group_study"] += 2.0
    if "patients with" in multi_case_hits:
        scores["observational_group_study"] += 0.8

    if interventional_hits and (observational_hits or explicit_multi_case or "controlled study" in interventional_hits):
        scores["interventional_study"] += len(interventional_hits) * 1.6

    has_clinical_signal = (
        explicit_single_case
        or explicit_multi_case
        or bool(observational_hits)
        or bool(interventional_hits)
    )
    scores["lab_heavy_clinical_or_translational"] += len(non_clinical_hits) * 1.0
    scores["lab_heavy_clinical_or_translational"] += len(lab_method_hits) * 1.6
    scores["lab_heavy_clinical_or_translational"] += len(translational_hits) * 1.3
    scores["non_clinical_basic_science"] += len(non_clinical_hits) * 1.8
    scores["non_clinical_basic_science"] += len(lab_method_hits) * 1.2
    if strong_lab_signal:
        scores["lab_heavy_clinical_or_translational"] += 2.0
        scores["non_clinical_basic_science"] += 1.0
    if not has_clinical_signal:
        scores["non_clinical_basic_science"] += 2.0
    if observational_hits or "patients with" in multi_case_hits or explicit_multi_case:
        scores["lab_heavy_clinical_or_translational"] += 2.0
    if translational_hits and (observational_hits or explicit_multi_case):
        scores["lab_heavy_clinical_or_translational"] += 2.0
    if strong_translational_signal and quantified_multi_case_signal:
        scores["lab_heavy_clinical_or_translational"] += 1.5
    if conference_like_metadata and strong_lab_signal:
        scores["lab_heavy_clinical_or_translational"] += 1.0

    scores["unclear_manual_review"] = 1.0

    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    winner, winner_score = sorted_scores[0]
    runner_up_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0

    manual_review_required = False
    category = winner
    subtype = ""
    contains_individual = False
    contains_group = False
    split_candidate = False
    preferred_langextract_mode = "manual_review"
    langextract_eligible = False
    recommended_next_action = "manual_source_review"

    if usable_proceedings_signal and trim_status == "manual_review_required":
        category = "conference_abstract"
        subtype = "proceedings_manual_review"
        manual_review_required = True
        preferred_langextract_mode = "manual_review"
        recommended_next_action = "trim_or_review_proceedings"
    elif broad_review_shape or (
        scores["review_article"] >= 3.0
        and (
            (low_sps_focus and not (strong_translational_signal and quantified_multi_case_signal))
            or (not strong_case_signal and not strong_original_cohort_signal)
        )
    ):
        category = "review_article"
        subtype = "tagged_review_article" if "review article" in normalized_tags else "narrative_or_systematic_review"
        preferred_langextract_mode = "skip"
        recommended_next_action = "skip_langextract"
    elif header_only_proceedings and short_source_document and not abstract.strip():
        category = "conference_abstract"
        subtype = "group_conference_abstract"
        contains_group = True
        manual_review_required = True
        preferred_langextract_mode = "manual_review"
        langextract_eligible = False
        recommended_next_action = "trim_or_review_proceedings"
    elif scores["conference_abstract"] >= 3.0:
        category = "conference_abstract"
        if explicit_multi_case:
            subtype = "multi_case_conference_abstract"
            contains_individual = True
            contains_group = True
            split_candidate = True
            preferred_langextract_mode = "individual_and_group"
            langextract_eligible = True
            recommended_next_action = "split_cases_then_langextract"
        elif explicit_single_case:
            subtype = "single_case_conference_abstract"
            contains_individual = True
            preferred_langextract_mode = "individual"
            langextract_eligible = trim_status != "manual_review_required"
            recommended_next_action = "run_langextract_individual"
        else:
            subtype = "group_conference_abstract"
            contains_group = True
            preferred_langextract_mode = "group"
            langextract_eligible = trim_status == "trimmed_auto" or not proceedings_detected
            recommended_next_action = "run_langextract_group"
            if proceedings_detected and trim_status != "trimmed_auto":
                manual_review_required = True
                preferred_langextract_mode = "manual_review"
                langextract_eligible = False
                recommended_next_action = "trim_or_review_proceedings"
    elif (
        explicit_single_case
        and not explicit_multi_case
        and not (strong_translational_signal and case_report_hits == ["a patient with"] and not demographic_single_case)
    ):
        category = "single_case_report"
        subtype = "case_report"
        contains_individual = True
        preferred_langextract_mode = "individual"
        langextract_eligible = True
        recommended_next_action = "run_langextract_individual"
    elif (
        scores["lab_heavy_clinical_or_translational"] >= 5.0
        and strong_lab_signal
        and (observational_hits or "patients with" in multi_case_hits or explicit_multi_case or strong_translational_signal)
    ):
        category = "lab_heavy_clinical_or_translational"
        subtype = "group_or_frequency_focused_lab_clinical_study"
        contains_group = True
        preferred_langextract_mode = "group"
        langextract_eligible = True
        recommended_next_action = "run_langextract_group"
        if conference_like_metadata and not proceedings_detected:
            subtype = "lab_heavy_group_abstract"
    elif scores["non_clinical_basic_science"] >= 4.5 and strong_lab_signal and not conference_like_metadata:
        category = "non_clinical_basic_science"
        subtype = "basic_science_or_mechanistic"
        preferred_langextract_mode = "skip"
        recommended_next_action = "skip_langextract"
    elif scores["interventional_study"] >= 3.0:
        category = "interventional_study"
        subtype = "controlled_or_therapeutic_group_study"
        contains_group = True
        preferred_langextract_mode = "group"
        langextract_eligible = True
        recommended_next_action = "run_langextract_group"
    elif scores["case_series_or_multi_case"] >= 3.0:
        category = "case_series_or_multi_case"
        subtype = "case_series"
        contains_individual = True
        contains_group = True
        split_candidate = True
        preferred_langextract_mode = "individual_and_group"
        langextract_eligible = True
        recommended_next_action = "split_cases_then_langextract"
    elif scores["observational_group_study"] >= 2.5:
        category = "observational_group_study"
        subtype = "retrospective_or_cohort_group_study"
        contains_group = True
        preferred_langextract_mode = "group"
        langextract_eligible = True
        recommended_next_action = "run_langextract_group"
    elif scores["single_case_report"] >= 2.0:
        category = "single_case_report"
        subtype = "case_report"
        contains_individual = True
        preferred_langextract_mode = "individual"
        langextract_eligible = True
        recommended_next_action = "run_langextract_individual"
    else:
        category = "unclear_manual_review"
        subtype = "unclear"
        manual_review_required = True

    if trim_status == "manual_review_required" and category != "conference_abstract":
        manual_review_required = True
        recommended_next_action = "review_proceedings_or_source_type"

    if category == "unclear_manual_review":
        manual_review_required = True

    confidence = confidence_label(winner_score, winner_score - runner_up_score)
    if manual_review_required and confidence == "high":
        confidence = "medium"
    if confidence == "low" and category in {
        "lab_heavy_clinical_or_translational",
        "conference_abstract",
        "case_series_or_multi_case",
    }:
        manual_review_required = True
        if recommended_next_action.startswith("run_langextract"):
            recommended_next_action = "review_source_category_then_langextract"
        elif recommended_next_action == "split_cases_then_langextract":
            recommended_next_action = "review_source_category_then_split"

    reasons: list[str] = []
    if proceedings_detected:
        reasons.append(f"proceedings_detected={proceedings_detected}")
    if trim_status:
        reasons.append(f"trim_status={trim_status}")
    if trim_match_score:
        reasons.append(f"trim_match_score={trim_match_score:.4f}")
    if case_report_hits:
        reasons.append(f"case_markers={'; '.join(case_report_hits[:3])}")
    if multi_case_hits:
        reasons.append(f"multi_case_markers={'; '.join(multi_case_hits[:3])}")
    if observational_hits:
        reasons.append(f"observational_markers={'; '.join(observational_hits[:3])}")
    if interventional_hits:
        reasons.append(f"interventional_markers={'; '.join(interventional_hits[:3])}")
    if review_hits:
        reasons.append(f"review_markers={'; '.join(review_hits[:3])}")
    if non_clinical_hits:
        reasons.append(f"non_clinical_markers={'; '.join(non_clinical_hits[:3])}")
    if lab_method_hits:
        reasons.append(f"lab_method_markers={'; '.join(lab_method_hits[:3])}")
    if translational_hits:
        reasons.append(f"translational_markers={'; '.join(translational_hits[:3])}")
    if conference_hits:
        reasons.append(f"conference_markers={'; '.join(conference_hits[:3])}")
    if conference_metadata_hits:
        reasons.append(f"conference_metadata_markers={'; '.join(conference_metadata_hits[:3])}")
    if header_conference_hits:
        reasons.append(f"header_conference_markers={'; '.join(header_conference_hits[:3])}")
    if supplement_issue:
        reasons.append("supplement_issue=true")
    if conference_doi_signal:
        reasons.append("conference_doi=true")
    if electronic_single_page:
        reasons.append("electronic_single_page=true")
    if structured_abstract_hits:
        reasons.append(f"structured_abstract_markers={'; '.join(structured_abstract_hits[:4])}")
    if count_hint:
        reasons.append(f"likely_case_count={count_hint}")
    if patient_label_count:
        reasons.append(f"patient_label_count={patient_label_count}")
    if page_span:
        reasons.append(f"page_span={page_span}")
    if full_page_count:
        reasons.append(f"full_page_count={full_page_count}")
    if demographic_single_case:
        reasons.append("individual_demographic_signal=true")

    return {
        "paper_id": str(text_record.get("paper_id") or Path(str(text_record.get("_path") or "")).stem),
        "covidence_id": (reference_row.get("Covidence") or "").strip(),
        "title": title,
        "authors": authors,
        "published_year": (reference_row.get("Published Year") or "").strip(),
        "journal": journal,
        "tags": tags,
        "notes": notes,
        "text_json_path": relative_to_repo(Path(str(text_record["_path"]))),
        "preferred_text_json_path": relative_to_repo(preferred_path),
        "preferred_text_source": "trimmed" if trimmed_used else "full_text",
        "proceedings_detected": bool_text(proceedings_detected),
        "trim_status": trim_status,
        "source_category": category,
        "source_subtype": subtype,
        "classification_confidence": confidence,
        "likely_case_count": str(count_hint or ""),
        "contains_individual_level_data": bool_text(contains_individual),
        "contains_group_level_data": bool_text(contains_group),
        "case_series_split_candidate": bool_text(split_candidate),
        "preferred_langextract_mode": preferred_langextract_mode,
        "langextract_eligible": bool_text(langextract_eligible),
        "manual_review_required": bool_text(manual_review_required),
        "recommended_next_action": recommended_next_action,
        "conference_marker_hits": str(len(conference_hits)),
        "review_marker_hits": str(len(review_hits)),
        "case_report_marker_hits": str(len(case_report_hits)),
        "multi_case_marker_hits": str(len(multi_case_hits)),
        "observational_marker_hits": str(len(observational_hits)),
        "interventional_marker_hits": str(len(interventional_hits)),
        "non_clinical_marker_hits": str(len(non_clinical_hits)),
        "translational_marker_hits": str(len(translational_hits)),
        "patient_label_count": str(patient_label_count),
        "categorisation_reason": " | ".join(reasons),
        "categorisation_version": "heuristic_v2",
        "categorised_at_utc": now_utc_iso(),
    }


# Write rows.
def write_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    fieldnames = [
        "paper_id",
        "covidence_id",
        "title",
        "authors",
        "published_year",
        "journal",
        "tags",
        "notes",
        "text_json_path",
        "preferred_text_json_path",
        "preferred_text_source",
        "proceedings_detected",
        "trim_status",
        "source_category",
        "source_subtype",
        "classification_confidence",
        "likely_case_count",
        "contains_individual_level_data",
        "contains_group_level_data",
        "case_series_split_candidate",
        "preferred_langextract_mode",
        "langextract_eligible",
        "manual_review_required",
        "recommended_next_action",
        "conference_marker_hits",
        "review_marker_hits",
        "case_report_marker_hits",
        "multi_case_marker_hits",
        "observational_marker_hits",
        "interventional_marker_hits",
        "non_clinical_marker_hits",
        "translational_marker_hits",
        "patient_label_count",
        "categorisation_reason",
        "categorisation_version",
        "categorised_at_utc",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# Build refresh artifact registry.
def refresh_artifact_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )


# Parse command-line arguments.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Categorise extracted SPS sources for downstream routing and case-splitting."
    )
    parser.add_argument("--references-csv", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--input-dir", type=Path, default=TEXT_DIR)
    parser.add_argument("--trimmed-dir", type=Path, default=TEXT_TRIMMED_DIR)
    parser.add_argument("--trim-registry-path", type=Path, default=TEXT_TRIM_REGISTRY_PATH)
    parser.add_argument("--output-path", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--paper-id", action="append", default=[], help="Paper ID to process.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of papers to process.")
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after categorisation.",
    )
    return parser.parse_args()


# Run the pipeline entrypoint.
def main() -> None:
    args = parse_args()
    reference_rows = load_reference_rows(args.references_csv)
    trim_rows = load_csv_rows_by_id(args.trim_registry_path, "paper_id")

    rows: list[dict[str, str]] = []
    for text_path in collect_text_paths(args.input_dir, args.paper_id, args.limit):
        paper_id = text_path.stem
        preferred_path = args.trimmed_dir / text_path.name
        if not preferred_path.exists():
            preferred_path = text_path
        text_record = load_text_record(text_path)
        preferred_record = load_text_record(preferred_path)
        rows.append(
            classify_record(
                reference_row=reference_rows.get(paper_id, {}),
                text_record=text_record,
                preferred_record=preferred_record,
                preferred_path=preferred_path,
                trim_row=trim_rows.get(paper_id, {}),
            )
        )

    write_rows(rows, args.output_path)
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Wrote {len(rows)} rows to {args.output_path}")


if __name__ == "__main__":
    main()
