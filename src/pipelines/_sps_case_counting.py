from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone


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
SINGULAR_PATIENT_MARKERS = (
    "an individual",
    "individual with",
    "our patient",
    "a patient",
    "single patient",
    "one patient",
    "a woman",
    "a man",
    "a child",
    "a boy",
    "a girl",
    "woman with",
    "man with",
    "child with",
    "boy with",
    "girl with",
    "female patient",
    "male patient",
)
TITLE_COMPARISON_MARKERS = (
    " vs ",
    " versus ",
    " compared with ",
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
    "patients were treated",
    "participants were treated",
    "patients were enrolled",
    "participants were enrolled",
    "patients were included",
    "participants were included",
    "patients were identified",
    "participants were identified",
    "new patients were identified",
    "new patients were",
    "we included",
    "we enrolled",
    "we treated",
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
    "reported in the literature",
    "reported in literature",
    "cases have been reported",
    "patients have been reported",
    "previously reported cases",
    "previously reported patients",
    "reported cases",
    "review article",
    "rare condition",
    "rare disorder",
)
BACKGROUND_MARKERS = (
    "background",
    "introduction",
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
COUNT_NOUN_PATTERN = (
    r"(?:patients|patient|cases|case subjects|subjects|participants|participant|"
    r"women|men|children|people|individuals)"
)
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
    rf"\b{COUNT_TOKEN_PATTERN}(?!\s*%)\s+{COUNT_FILLER_PATTERN}{{0,4}}?(?:cases|patients|participants)\b",
    re.IGNORECASE,
)
PATIENT_LABEL_RE = re.compile(r"\b(?:patient|case)\s*(?:#\s*)?(?:\d+|i|ii|iii|iv|v|vi|vii|viii|ix|x)\b")


@dataclass(frozen=True)
class CaseCountEstimate:
    likely_case_count: int
    count_confidence: str
    count_basis: str
    manual_review_required: bool


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


def marker_hits(text: str, markers: tuple[str, ...]) -> list[str]:
    return [marker for marker in markers if marker in text]


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


def count_patient_labels(text: str) -> int:
    return len(set(PATIENT_LABEL_RE.findall(text)))


def has_age_context(text: str, count: int) -> bool:
    count_text = str(count)
    patterns = (
        rf"\b{count_text}\s*(?:y|yr|yrs|year|years|month|months|week|weeks|day|days)\s*old\b",
        rf"\b{count_text}\s*(?:y|yr|yrs|year|years)\b(?=\s+(?:old|male|female|woman|man|child|boy|girl|patient))",
        rf"\baged\s+{count_text}\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def has_current_series_signal(text: str) -> bool:
    return any(marker in text for marker in COUNT_POSITIVE_CONTEXT_MARKERS)


def has_literature_count_context(text: str, count: int) -> bool:
    count_text = str(count)
    if any(marker in text for marker in COUNT_NEGATIVE_CONTEXT_MARKERS):
        return True
    patterns = (
        rf"\b(?:less than|fewer than|more than|about|approximately|over)\s+{count_text}\s+cases?\b",
        rf"\b{count_text}\s+cases?\s+(?:have been\s+)?reported\b",
        rf"\b{count_text}\s+patients?\s+(?:have been\s+)?reported\b",
        rf"\btotal\s+{count_text}\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def has_single_case_signal(text: str) -> bool:
    normalized = normalize_text(text)
    if marker_hits(normalized, CASE_REPORT_MARKERS):
        return True
    if any(marker in normalized for marker in SINGULAR_PATIENT_MARKERS):
        return True
    return bool(
        re.search(
            r"\b(?:our|the|a|one)\s+(?:\d+\s+(?:y|yr|year)\s+old\s+)?"
            r"(?:female|male|woman|man|child|boy|girl|patient)\b",
            normalized,
        )
    )


def is_comparison_title_with_count(title: str) -> bool:
    padded = f" {normalize_text(title)} "
    if not any(marker in padded for marker in TITLE_COMPARISON_MARKERS):
        return False
    return bool(TITLE_CASE_COUNT_RE.search(padded))


def has_explicit_multi_case_signal(text: str) -> bool:
    normalized = normalize_count_text(text)
    if "case series" in normalized:
        return True
    for pattern in (TITLE_CASE_COUNT_RE, CONTEXTUAL_PATIENT_COUNT_RE, PATIENT_COUNT_RE):
        for match in pattern.finditer(normalized):
            count = parse_count_token(match.group("count"))
            if count > 1 and not has_age_context(normalized, count):
                return True
    return False


def score_count_candidate(
    unit: str,
    match: re.Match[str],
    *,
    count: int,
    title_mentions_sps: bool,
    source_weight: int,
    single_case_signal: bool,
) -> int:
    start, end = match.span()
    window = unit[max(0, start - 48) : min(len(unit), end + 128)]
    local_window = unit[max(0, start - 24) : min(len(unit), end + 48)]
    score = source_weight
    if count >= 1900 and count <= CURRENT_YEAR + 1:
        score -= 10
    elif count > 500:
        score -= 8
    if has_age_context(window, count):
        score -= 12
    if title_mentions_sps:
        score += 1
    if mentions_sps_context(window):
        score += 5
    if has_current_series_signal(window):
        score += 4
    if has_literature_count_context(window, count):
        score -= 8
    if any(marker in window for marker in BACKGROUND_MARKERS) and not has_current_series_signal(window):
        score -= 2
    if COUNT_RANGE_RE.search(local_window):
        score -= 6
    if "percent" in local_window:
        score -= 6
    if "percent patients" in local_window or "percent of patients" in local_window:
        score -= 6
    if re.search(r"\b(?:igg|igm|iga|nmol|microg|ng|iu|mg|ml)\b", local_window) and "patients" not in match.group(0):
        score -= 6
    if re.search(r"\b(?:scale|score|grading)\b", window) and not has_current_series_signal(window):
        score -= 6
    if re.search(r"\b(?:less than|fewer than|more than|up to|approximately|about)\s+\d+\s+cases?\b", window):
        score -= 5
    if re.search(r"\bantibody positive\b", window) or re.search(r"\bantibody positive patients\b", window):
        score -= 3
    if re.search(r"\b(?:of|among)\s+\d+\s+patients?\b", window) and not mentions_sps_context(window):
        score -= 2
    if single_case_signal and count > 1 and not has_current_series_signal(window):
        score -= 4
    if single_case_signal and count > 3:
        score -= 4
    return score


def estimate_sps_case_count(*, title: str, abstract: str, early_body_text: str) -> CaseCountEstimate:
    normalized_title = normalize_text(title)
    title_mentions_sps = mentions_sps_context(normalized_title)
    title_and_abstract = normalize_text(" ".join([title, abstract]))
    single_case_signal = has_single_case_signal(" ".join([title, abstract]))
    explicit_multi_case_signal = has_explicit_multi_case_signal(" ".join([title, abstract]))
    title_candidates: list[tuple[int, int]] = []
    abstract_candidates: list[tuple[int, int]] = []
    body_candidates: list[tuple[int, int]] = []

    for match in TITLE_CASE_COUNT_RE.finditer(normalized_title):
        count = parse_count_token(match.group("count"))
        if count > 0:
            score = 6 if title_mentions_sps else 3
            if any(marker in normalized_title for marker in COUNT_NEGATIVE_CONTEXT_MARKERS):
                score -= 3
            if is_comparison_title_with_count(title):
                score -= 5
            title_candidates.append((score, count))

    if title_candidates:
        best_score, best_count = sorted(title_candidates, key=lambda item: (-item[0], -item[1]))[0]
        if best_score > 0:
            confidence = "high" if best_score >= 6 else "medium"
            return CaseCountEstimate(
                likely_case_count=best_count,
                count_confidence=confidence,
                count_basis="title_count_signal",
                manual_review_required=confidence == "medium",
            )

    for unit in split_text_units(abstract):
        normalized_unit = normalize_count_text(unit)
        if not normalized_unit:
            continue
        for pattern in (SPS_DIRECT_COUNT_RE, CONTEXTUAL_PATIENT_COUNT_RE, PATIENT_COUNT_RE):
            for match in pattern.finditer(normalized_unit):
                count = parse_count_token(match.group("count"))
                if count <= 0:
                    continue
                score = score_count_candidate(
                    normalized_unit,
                    match,
                    count=count,
                    title_mentions_sps=title_mentions_sps,
                    source_weight=4 if pattern is SPS_DIRECT_COUNT_RE else 3,
                    single_case_signal=single_case_signal,
                )
                if score >= 4:
                    abstract_candidates.append((score, count))

    if abstract_candidates:
        best_score, best_count = sorted(abstract_candidates, key=lambda item: (-item[0], -item[1]))[0]
        confidence = "high" if best_score >= 8 else "medium"
        return CaseCountEstimate(
            likely_case_count=best_count,
            count_confidence=confidence,
            count_basis="abstract_count_signal",
            manual_review_required=confidence != "high",
        )

    if marker_hits(title_and_abstract, CASE_REPORT_MARKERS):
        return CaseCountEstimate(
            likely_case_count=1,
            count_confidence="medium",
            count_basis="case_report_marker_single_case",
            manual_review_required=False,
        )

    if single_case_signal and not explicit_multi_case_signal:
        return CaseCountEstimate(
            likely_case_count=1,
            count_confidence="medium",
            count_basis="single_case_text_signal",
            manual_review_required=False,
        )

    for unit in split_text_units(early_body_text):
        normalized_unit = normalize_count_text(unit)
        if not normalized_unit:
            continue
        has_strong_body_context = any(marker in normalized_unit for marker in COUNT_POSITIVE_CONTEXT_MARKERS) or bool(
            re.search(r"\b(?:patient|case)\s*[12]\b", normalized_unit)
        )
        if not has_strong_body_context:
            continue
        for pattern in (SPS_DIRECT_COUNT_RE, CONTEXTUAL_PATIENT_COUNT_RE, PATIENT_COUNT_RE):
            for match in pattern.finditer(normalized_unit):
                count = parse_count_token(match.group("count"))
                if count <= 0:
                    continue
                score = score_count_candidate(
                    normalized_unit,
                    match,
                    count=count,
                    title_mentions_sps=title_mentions_sps,
                    source_weight=2 if pattern is SPS_DIRECT_COUNT_RE else 1,
                    single_case_signal=single_case_signal,
                )
                if score >= 5:
                    body_candidates.append((score, count))

    if body_candidates:
        best_score, best_count = sorted(body_candidates, key=lambda item: (-item[0], -item[1]))[0]
        return CaseCountEstimate(
            likely_case_count=best_count,
            count_confidence="medium",
            count_basis="early_body_count_signal",
            manual_review_required=best_score < 8,
        )

    patient_label_count = count_patient_labels(normalize_text(early_body_text))
    if patient_label_count >= 2:
        return CaseCountEstimate(
            likely_case_count=patient_label_count,
            count_confidence="medium",
            count_basis="patient_label_count",
            manual_review_required=False,
        )

    return CaseCountEstimate(
        likely_case_count=0,
        count_confidence="low",
        count_basis="no_reliable_count_signal",
        manual_review_required=False,
    )
