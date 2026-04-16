from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pipelines._sps_case_counting import (
    CaseCountEstimate,
    estimate_sps_case_count,
    has_explicit_multi_case_signal,
    has_single_case_signal,
    parse_count_token,
)
from src.pipelines._proceedings_ready import (
    TEXT_PROCEEDINGS_READY_DIR,
    TEXT_PROCEEDINGS_READY_REGISTRY_PATH,
    load_ready_rows_by_id,
    preferred_proceedings_text_source,
)
from src.pipelines.stage06_counting.models import CountCandidate, CountCandidatePackage


REPO_ROOT = Path(__file__).resolve().parents[2]
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
HEURISTIC_VERSION = "heuristic_v2"
ADMINISTRATIVE_DATASET_MARKERS = (
    "nationwide readmission study",
    "nationwide study",
    "national inpatient sample",
    "inpatient care",
    "readmission study",
    "administrative database",
    "hospital discharge database",
    "claims database",
)
CONFIDENCE_SCORES = {
    "high": 90,
    "medium": 70,
    "low": 45,
}
AMBIGUOUS_BASES = {
    "source_single_case_default",
    "source_single_case_override",
    "single_case_text_signal",
    "early_body_count_signal",
    "patient_label_count",
    "no_reliable_count_signal",
}
LLM_EVIDENCE_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
LLM_EVIDENCE_COUNT_RE = re.compile(
    r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b",
    re.IGNORECASE,
)
LLM_EVIDENCE_CONTEXT_RE = re.compile(
    r"\b(?:patient|patients|case|cases|participant|participants|subject|subjects|individual|individuals|"
    r"cohort|series|report|reported|describe|described|identified|included|enrolled|treated)\b",
    re.IGNORECASE,
)
LLM_EVIDENCE_LABEL_RE = re.compile(
    r"\b(?:patient|case|subject|participant|twin)\s*(?:#\s*)?(?:\d+|i|ii|iii|iv|v|vi|vii|viii|ix|x|[a-z])\b",
    re.IGNORECASE,
)
LLM_EVIDENCE_SPS_RE = re.compile(
    r"\b(?:stiff person syndrome|stiff-person syndrome|stiff man syndrome|stiff-man syndrome|sps|sms|spsd)\b",
    re.IGNORECASE,
)
LLM_EVIDENCE_POSITIVE_MARKERS = (
    "we report",
    "we reported",
    "we describe",
    "we described",
    "we identified",
    "we included",
    "we enrolled",
    "we treated",
    "results",
)
COUNT_TOKEN_TEXT_PATTERN = (
    r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"thirty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"forty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"fifty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"sixty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"seventy(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"eighty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"ninety(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?)"
)
SPS_DIAGNOSIS_CANONICAL_BY_ALIAS = {
    "stiff person syndrome": "stiff person syndrome",
    "stiff-person syndrome": "stiff person syndrome",
    "stiff man syndrome": "stiff person syndrome",
    "stiff-man syndrome": "stiff person syndrome",
    "sps": "stiff person syndrome",
    "sms": "stiff person syndrome",
    "spsd": "stiff person syndrome",
    "classic sps": "classic sps",
    "classic stiff person syndrome": "classic sps",
    "atypical sps": "atypical sps",
    "atypical stiff person syndrome": "atypical sps",
    "jerking sps": "jerking sps",
    "jerking stiff person syndrome": "jerking sps",
    "stiff limb syndrome": "stiff limb syndrome",
    "stiff-limb syndrome": "stiff limb syndrome",
    "stiff leg syndrome": "stiff limb syndrome",
    "stiff-leg syndrome": "stiff limb syndrome",
    "progressive encephalomyelitis with rigidity and myoclonus": "perm",
    "progressive encephalomyelitis with myoclonus and rigidity": "perm",
    "perm": "perm",
}
SPS_SUBGROUP_DIAGNOSIS_PATTERN = "|".join(
    sorted((re.escape(alias) for alias in SPS_DIAGNOSIS_CANONICAL_BY_ALIAS), key=len, reverse=True)
)
SPS_SUBGROUP_PAIR_RE = re.compile(
    rf"\b(?P<count>{COUNT_TOKEN_TEXT_PATTERN})\b\s+"
    rf"(?:patients?\s+|cases?\s+)?"
    rf"(?:(?:were\s+classified\s+as|were\s+diagnosed\s+with|diagnosed\s+with|classified\s+as|presented\s+with|had|with|as)\s+)?"
    rf"(?P<diagnosis>{SPS_SUBGROUP_DIAGNOSIS_PATTERN})\b",
    re.IGNORECASE,
)
SPS_SUBGROUP_SUFFIX_RE = re.compile(
    rf"\b(?P<diagnosis>{SPS_SUBGROUP_DIAGNOSIS_PATTERN})\b\s*\(\s*(?P<count>{COUNT_TOKEN_TEXT_PATTERN})\b"
    rf"(?=(?:\s+(?:with|case|cases|patient|patients|who|and|or))|\s*[\);:]|$)",
    re.IGNORECASE,
)
PATIENT_CASE_LABEL_RE = re.compile(
    r"\b(?:patient|case)\s*(?P<label>\d+|i|ii|iii|iv|v|vi|vii|viii|ix|x)\b",
    re.IGNORECASE,
)
DESCRIPTIVE_PATIENT_LABEL_RE = re.compile(
    r"\b(?:the\s+)?(?P<label>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|male|female)\s+patient\b",
    re.IGNORECASE,
)
SPS_SCORE_CONTEXT_RE = re.compile(
    r"\bsps(?:-adl|\s+(?:activity|activities|score|scores|scale|scales|ones))\b",
    re.IGNORECASE,
)
DIRECT_SPS_COHORT_RE = re.compile(
    rf"\b(?P<count>{COUNT_TOKEN_TEXT_PATTERN})\s+patients?\s+"
    rf"(?:affected\s+by|with|had|diagnosed\s+with|treated\s+for)\b[\s\S]{{0,120}}?"
    rf"\b(?:{SPS_SUBGROUP_DIAGNOSIS_PATTERN})\b",
    re.IGNORECASE,
)
NAMED_SPS_COHORT_RE = re.compile(
    rf"\b(?:group|cohort|arm|series)\s*(?:\d+|[ivx]+)?\b[\s\S]{{0,60}}?"
    rf"(?:consisted\s+of|comprised|included|contained|enrolled|described)\s+"
    rf"(?P<count>{COUNT_TOKEN_TEXT_PATTERN})\s+patients?\b[\s\S]{{0,160}}?"
    rf"\b(?:{SPS_SUBGROUP_DIAGNOSIS_PATTERN})\b",
    re.IGNORECASE,
)
TABLE_SPS_COHORT_RE = re.compile(
    rf"\btable\s+\d+\b[\s\S]{{0,80}}?\b(?P<count>{COUNT_TOKEN_TEXT_PATTERN})\s+patients?\b"
    rf"[\s\S]{{0,120}}?\b(?:{SPS_SUBGROUP_DIAGNOSIS_PATTERN})\b",
    re.IGNORECASE,
)
DIRECT_SPS_COHORT_POSITIVE_MARKERS = (
    "we report",
    "we describe",
    "in this study",
    "participants",
    "we present",
    "our patients",
)
DIRECT_SPS_COHORT_NEGATIVE_MARKERS = (
    "retrospective cohort",
    "screening cohort",
    "identified in a retrospective cohort",
    "samples were also identified",
)
MIXED_DIAGNOSIS_SUBGROUP_CONTEXT_MARKERS = (
    "broader spectrum of symptoms",
    "coexisting autoimmune disorders",
    "control patients",
    "control group",
    "disease control groups",
    "were classified as",
)
ENUMERATED_SPS_SUBGROUP_MARKERS = (
    "among those patients",
    "among these patients",
    "among the patients",
)
CONTROL_GROUP_UNCERTAINTY_MARKERS = (
    "control patients",
    "healthy controls",
    "disease control groups",
)
CONTROL_GROUP_SPS_CONTEXT_RE = re.compile(
    rf"\b(?:control patients?|healthy controls?|disease control groups?)\b"
    rf"[\s\S]{{0,260}}?\b(?:{SPS_SUBGROUP_DIAGNOSIS_PATTERN})\b",
    re.IGNORECASE,
)
EXPLICIT_PATIENT_SPS_ACTION_RE = re.compile(
    rf"\b(?:diagnosed\s+with|treated\s+for|had|has|with|affected\s+by|who\s+had)\b[\s\S]{{0,80}}?"
    rf"\b(?:{SPS_SUBGROUP_DIAGNOSIS_PATTERN})\b",
    re.IGNORECASE,
)
SPS_STATUS_SUBSET_UNCERTAINTY_RE = re.compile(
    rf"\bonly\s+(?P<count>{COUNT_TOKEN_TEXT_PATTERN})\s+patients?\s+had\s+"
    r"(?:clinical\s+)?(?:rigidity|stiffness|spasm|spasms|myoclonus|hyperekplexia|startle)\b",
    re.IGNORECASE,
)
SPS_STATUS_SINGLE_PATIENT_OCR_UNCERTAINTY_RE = re.compile(
    r"\bonly\s+(?:1|one|i|l)\s+patient\s+had\s+"
    r"(?:clinical\s+)?(?:rigidity|stiffness|spasm|spasms|myoclonus|hyperekplexia|startle)\b",
    re.IGNORECASE,
)
NON_SPS_MIXED_DIAGNOSIS_MARKERS = (
    "encephalitis",
    "myelitis",
    "ataxia",
    "neuropathy",
    "limbic encephalitis",
    "epileptic encephalopathy",
    "visual loss",
    "paresthesia",
    "cramp",
    "brainstem",
    "optic neuropath",
)
NON_ORIGINAL_COHORT_SIGNAL_RE = re.compile(
    r"\b(?:previously|earlier|prior(?:ly)?)\s+(?:described|reported|published|identified)\b|"
    r"\b(?:described|reported|published|identified)\s+(?:previously|earlier)\b|"
    r"\bour most recent case\b|"
    r"\b[A-Za-z][A-Za-z-]+\s+et\s+al\.\s*(?:\(\d+\))?\b|"
    r"\bet\s+al\.\s*\(\d+\)\b",
    re.IGNORECASE,
)
DONOR_MATERIAL_SIGNAL_RE = re.compile(
    r"\b(?:sera?|serum|csf|igg(?:\s+fraction)?|gad65-?ab|antibod(?:y|ies)|specimen|sample|samples)\b"
    r"[\s\S]{0,80}?\bfrom\s+(?:a|an|the|one)?\s*"
    r"(?:(?:patient\s+with\s+|patients?\s+with\s+)"
    r"(?:stiff[- ]person syndrome|stiff[- ]man syndrome|sps|sms|perm|stiff limb syndrome)|"
    r"(?:stiff[- ]person syndrome|stiff[- ]man syndrome|sps|sms|perm|stiff limb syndrome)\s+patients?)\b",
    re.IGNORECASE,
)
SUSPECTED_SPS_COHORT_SIGNAL_RE = re.compile(
    r"\b(?:suspected|clinically suspected|referred specifically for)\b"
    r"[\s\S]{0,60}?"
    r"\b(?:stiff[- ]person syndrome|stiff[- ]man syndrome|sps|sms)\b",
    re.IGNORECASE,
)
CONFIRMED_SPS_CONTEXT_RE = re.compile(
    r"\b(?:icc-confirmed|confirmed)\s+(?:stiff[- ]person syndrome|stiff[- ]man syndrome|sps|sms)\b|"
    r"\bcharacteristic\s+of\s+icc-confirmed\s+(?:stiff[- ]person syndrome|sps)\b",
    re.IGNORECASE,
)
DIAGNOSIS_SUPPORTED_SUBSET_RE = re.compile(
    rf"\b(?:there\s+(?:were|was)\s+)?(?P<count>{COUNT_TOKEN_TEXT_PATTERN})\s+patients?\s+"
    r"(?:positive|confirmed)\b[\s\S]{0,80}?\b(?:by|with)\s+"
    r"(?:immunocytochemistr(?:y|ic)|icc|western blot|validated diagnostic criteria|diagnostic criteria)\b",
    re.IGNORECASE,
)
TABLE_ROW_SPS_COUNT_RE = re.compile(
    rf"\b(?P<diagnosis>{SPS_SUBGROUP_DIAGNOSIS_PATTERN})\b\s+"
    rf"(?P<count>{COUNT_TOKEN_TEXT_PATTERN})\b"
    rf"(?P<trailing>(?:\s+[0-9][0-9()/.-]*){{3,8}})",
    re.IGNORECASE,
)
TABLE_ROW_CONTEXT_MARKERS = (
    "table",
    "diagnosis",
    "no. of the patients",
    "no of the patients",
    "mean age",
    "sex (",
)
SERIES_COHORT_RE = re.compile(
    rf"\b(?:in\s+our\s+series|our\s+series\s+of|we\s+studied|we\s+examined|we\s+report(?:ed)?|"
    rf"we\s+described|we\s+identified)\b[\s,;:-]{{0,12}}"
    rf"(?P<count>{COUNT_TOKEN_TEXT_PATTERN})\s+(?:consecutive\s+)?patients?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SubgroupSignal:
    count: int
    count_basis: str
    count_confidence: str
    evidence_units: tuple[str, ...]


def count_eligibility_status(source_category: str) -> str:
    if source_category in {
        "single_case_report",
        "case_series_or_multi_case",
        "observational_group_study",
        "interventional_study",
        "lab_heavy_clinical_or_translational",
        "conference_abstract",
        "review_format_with_embedded_original_cohort",
    }:
        return "extractable"
    if source_category == "unclear_manual_review":
        return "uncertain"
    return "not_extractable"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def record_text_window(record: dict[str, Any], *, use_all_pages: bool) -> str:
    pages = record.get("pages") or []
    selected = pages if use_all_pages else pages[:5]
    return "\n".join(str(page.get("text") or "") for page in selected)


def title_localised_window(
    text: str,
    title: str,
    *,
    min_prefix_skip: int = 1200,
    leading_chars: int = 200,
    trailing_chars: int = 4500,
) -> str:
    normalized_text = normalize_text(text)
    normalized_title = normalize_text(title)
    if not normalized_text or not normalized_title:
        return normalized_text

    title_tokens = normalized_title.split()
    for anchor_size in (12, 10, 8, 6):
        if len(title_tokens) < anchor_size:
            continue
        anchor = " ".join(title_tokens[:anchor_size])
        index = normalized_text.find(anchor)
        if index < 0:
            continue
        if index < min_prefix_skip:
            return normalized_text
        start = max(0, index - leading_chars)
        end = min(len(normalized_text), index + len(anchor) + trailing_chars)
        return normalized_text[start:end]
    return normalized_text


def _clean_signal_text(text: str) -> str:
    joined = re.sub(r"(?<=\w)-\s+(?=\w)", "", str(text or ""))
    return " ".join(joined.split())


def _raw_evidence_units(text: str) -> list[str]:
    units: list[str] = []
    seen: set[str] = set()
    for raw_unit in re.split(r"\n+|(?<=[.!?])\s+", text or ""):
        unit = _clean_signal_text(raw_unit)
        if len(unit) < 20:
            continue
        normalized = normalize_text(unit)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        units.append(unit[:420])
    return units


def _matches_evidence_snippet(unit: str, evidence_units: tuple[str, ...] | list[str]) -> bool:
    normalized_unit = normalize_text(_clean_signal_text(unit))
    if not normalized_unit:
        return False
    for evidence_unit in evidence_units:
        normalized_evidence = normalize_text(_clean_signal_text(evidence_unit))
        if not normalized_evidence:
            continue
        if (
            normalized_unit.startswith(normalized_evidence)
            or normalized_evidence.startswith(normalized_unit)
            or normalized_evidence in normalized_unit
        ):
            return True
    return False


def _contains_subgroup_count_signal(unit: str, subgroup_signal: SubgroupSignal | None) -> bool:
    if subgroup_signal is None:
        return False
    return any(count == subgroup_signal.count for _, count in _subgroup_pairs_from_unit(unit))


def _is_non_original_case_context(unit: str) -> bool:
    return bool(NON_ORIGINAL_COHORT_SIGNAL_RE.search(_clean_signal_text(unit)))


def _canonicalize_subgroup_diagnosis(text: str) -> str:
    cleaned = normalize_text(_clean_signal_text(text))
    for alias, canonical in SPS_DIAGNOSIS_CANONICAL_BY_ALIAS.items():
        if cleaned == normalize_text(alias):
            return canonical
    return cleaned


def _subgroup_pairs_from_unit(unit: str) -> list[tuple[str, int]]:
    pairs: list[tuple[str, int]] = []
    cleaned = _clean_signal_text(unit)
    for match in SPS_SUBGROUP_PAIR_RE.finditer(cleaned):
        count = parse_count_token(match.group("count"))
        if count <= 0:
            continue
        pairs.append((_canonicalize_subgroup_diagnosis(match.group("diagnosis")), count))
    for match in SPS_SUBGROUP_SUFFIX_RE.finditer(cleaned):
        preceding_context = cleaned[max(0, match.start() - 60) : match.start()]
        if re.search(
            rf"\b{COUNT_TOKEN_TEXT_PATTERN}\b\s+"
            rf"(?:patients?\s+|cases?\s+)?"
            rf"(?:(?:were\s+classified\s+as|were\s+diagnosed\s+with|diagnosed\s+with|classified\s+as|"
            rf"presented\s+with|had|with|as)\s+)?$",
            preceding_context,
            re.IGNORECASE,
        ):
            continue
        count = parse_count_token(match.group("count"))
        if count <= 0 or count > 25:
            continue
        pairs.append((_canonicalize_subgroup_diagnosis(match.group("diagnosis")), count))
    return pairs


def _extract_direct_sps_cohort_signal(text: str) -> SubgroupSignal | None:
    best_signal: SubgroupSignal | None = None
    best_score = -1
    for unit in _raw_evidence_units(text):
        normalized = normalize_text(unit)
        if _is_non_original_case_context(unit):
            continue
        if not any(marker in normalized for marker in DIRECT_SPS_COHORT_POSITIVE_MARKERS):
            continue
        if any(marker in normalized for marker in DIRECT_SPS_COHORT_NEGATIVE_MARKERS):
            continue
        for match in DIRECT_SPS_COHORT_RE.finditer(unit):
            count = parse_count_token(match.group("count"))
            if count <= 0:
                continue
            score = count
            signal = SubgroupSignal(
                count=count,
                count_basis="diagnosis_specific_direct_cohort_count",
                count_confidence="high",
                evidence_units=(unit[:420],),
            )
            if score > best_score:
                best_score = score
                best_signal = signal
    return best_signal


def _extract_named_sps_cohort_signal(text: str) -> SubgroupSignal | None:
    best_signal: SubgroupSignal | None = None
    best_score = -1
    for unit in _raw_evidence_units(text):
        normalized = normalize_text(unit)
        if _is_non_original_case_context(unit):
            continue
        if any(marker in normalized for marker in DIRECT_SPS_COHORT_NEGATIVE_MARKERS):
            continue
        for pattern in (NAMED_SPS_COHORT_RE, TABLE_SPS_COHORT_RE):
            for match in pattern.finditer(unit):
                count = parse_count_token(match.group("count"))
                if count <= 0:
                    continue
                score = count + (20 if pattern is NAMED_SPS_COHORT_RE else 10)
                signal = SubgroupSignal(
                    count=count,
                    count_basis="diagnosis_specific_named_cohort_count",
                    count_confidence="high",
                    evidence_units=(unit[:420],),
                )
                if score > best_score:
                    best_score = score
                    best_signal = signal
    return best_signal


def _extract_series_cohort_signal(text: str) -> SubgroupSignal | None:
    best_signal: SubgroupSignal | None = None
    best_score = -1
    cleaned = _clean_signal_text(text)
    if not cleaned:
        return None
    for match in SERIES_COHORT_RE.finditer(cleaned):
        count = parse_count_token(match.group("count"))
        if count <= 0:
            continue
        context_start = max(0, match.start() - 220)
        context_end = min(len(cleaned), match.end() + 140)
        context = cleaned[context_start:context_end]
        if _is_non_original_case_context(context):
            continue
        if not LLM_EVIDENCE_SPS_RE.search(context):
            continue
        signal = SubgroupSignal(
            count=count,
            count_basis="diagnosis_specific_series_cohort_count",
            count_confidence="high",
            evidence_units=(context[:420],),
        )
        score = count
        if score > best_score:
            best_score = score
            best_signal = signal
    return best_signal


def _extract_group_breakdown_subgroup_signal(text: str) -> SubgroupSignal | None:
    cleaned = _clean_signal_text(text)
    if not cleaned:
        return None

    raw_matches: list[tuple[int, int, str, int]] = []
    for match in SPS_SUBGROUP_PAIR_RE.finditer(cleaned):
        count = parse_count_token(match.group("count"))
        if count <= 0:
            continue
        raw_matches.append(
            (
                match.start(),
                match.end(),
                _canonicalize_subgroup_diagnosis(match.group("diagnosis")),
                count,
            )
        )

    if len(raw_matches) < 2:
        return None

    best_signal: SubgroupSignal | None = None
    best_score = -1
    cluster: list[tuple[int, int, str, int]] = []
    max_gap = 140

    def _finalise_cluster(items: list[tuple[int, int, str, int]]) -> None:
        nonlocal best_signal, best_score
        if len(items) < 2:
            return
        subgroup_total = sum(count for _, _, _, count in items)
        snippet_start = items[0][0]
        snippet_end = min(len(cleaned), items[-1][1] + 120)
        snippet = cleaned[snippet_start:snippet_end][:420]
        if _is_non_original_case_context(snippet):
            return
        signal = SubgroupSignal(
            count=subgroup_total,
            count_basis="diagnosis_specific_group_breakdown_count",
            count_confidence="high",
            evidence_units=(snippet,),
        )
        score = (len(items) * 100) + subgroup_total
        if score > best_score:
            best_score = score
            best_signal = signal

    for item in raw_matches:
        if cluster:
            gap_text = cleaned[cluster[-1][1] : item[0]]
        else:
            gap_text = ""
        if cluster and (item[0] - cluster[-1][1] > max_gap or any(marker in gap_text for marker in ".!?")):
            _finalise_cluster(cluster)
            cluster = []
        cluster.append(item)
    _finalise_cluster(cluster)
    return best_signal


def _extract_enumerated_sps_subgroup_signal(text: str) -> SubgroupSignal | None:
    best_signal: SubgroupSignal | None = None
    best_score = -1
    for unit in _raw_evidence_units(text):
        normalized = normalize_text(unit)
        if _is_non_original_case_context(unit):
            continue
        if not any(marker in normalized for marker in ENUMERATED_SPS_SUBGROUP_MARKERS):
            continue
        pairs = _subgroup_pairs_from_unit(unit)
        if len(pairs) < 2:
            continue
        subgroup_total = sum(count for _, count in pairs)
        signal = SubgroupSignal(
            count=subgroup_total,
            count_basis="diagnosis_specific_enumerated_subgroup_count",
            count_confidence="high",
            evidence_units=(unit[:420],),
        )
        score = (len(pairs) * 100) + subgroup_total
        if score > best_score:
            best_score = score
            best_signal = signal
    return best_signal


def _extract_mixed_diagnosis_subgroup_signal(text: str) -> SubgroupSignal | None:
    best_signal: SubgroupSignal | None = None
    best_score = -1
    for unit in _raw_evidence_units(text):
        normalized = normalize_text(unit)
        if _is_non_original_case_context(unit):
            continue
        pairs = _subgroup_pairs_from_unit(unit)
        if len(pairs) != 1:
            continue
        if not (
            any(marker in normalized for marker in MIXED_DIAGNOSIS_SUBGROUP_CONTEXT_MARKERS)
            or normalized.count(" had ") >= 2
            or normalized.count(" as ") >= 2
        ):
            continue
        _, count = pairs[0]
        if count <= 0:
            continue
        confidence = "medium" if any(marker in normalized for marker in CONTROL_GROUP_UNCERTAINTY_MARKERS) else "high"
        score = count + (20 if confidence == "high" else 5)
        signal = SubgroupSignal(
            count=count,
            count_basis="diagnosis_specific_mixed_diagnosis_subgroup_count",
            count_confidence=confidence,
            evidence_units=(unit[:420],),
        )
        if score > best_score:
            best_score = score
            best_signal = signal
    return best_signal


def _extract_suffix_count_subgroup_signal(text: str) -> SubgroupSignal | None:
    best_signal: SubgroupSignal | None = None
    best_score = -1
    for unit in _raw_evidence_units(text):
        cleaned = _clean_signal_text(unit)
        if _is_non_original_case_context(cleaned):
            continue
        for match in SPS_SUBGROUP_SUFFIX_RE.finditer(cleaned):
            count = parse_count_token(match.group("count"))
            if count <= 0 or count > 25:
                continue
            score = 50 - count
            signal = SubgroupSignal(
                count=count,
                count_basis="diagnosis_specific_suffix_count",
                count_confidence="high",
                evidence_units=(unit[:420],),
            )
            if score > best_score:
                best_score = score
                best_signal = signal
    return best_signal


def _extract_table_row_subgroup_signal(text: str) -> SubgroupSignal | None:
    cleaned = _clean_signal_text(text)
    if not cleaned:
        return None

    best_signal: SubgroupSignal | None = None
    best_score = -1
    for match in TABLE_ROW_SPS_COUNT_RE.finditer(cleaned):
        count = parse_count_token(match.group("count"))
        if count <= 0 or count > 25:
            continue
        context_start = max(0, match.start() - 1200)
        context_end = min(len(cleaned), match.end() + 120)
        context_window = cleaned[context_start:context_end]
        snippet_start = max(0, match.start() - 220)
        snippet_end = min(len(cleaned), match.end() + 120)
        snippet = cleaned[snippet_start:snippet_end][:420]
        normalized_context = normalize_text(context_window)
        if _is_non_original_case_context(snippet):
            continue
        if not any(marker in normalized_context for marker in TABLE_ROW_CONTEXT_MARKERS):
            continue
        numeric_tokens = re.findall(r"\b\d+(?:/\d+)?(?:\(\d+\))?\b", match.group("trailing"))
        if len(numeric_tokens) < 3:
            continue
        signal = SubgroupSignal(
            count=count,
            count_basis="diagnosis_specific_table_row_count",
            count_confidence="high",
            evidence_units=(snippet,),
        )
        score = (len(numeric_tokens) * 10) + (30 - count)
        if score > best_score:
            best_score = score
            best_signal = signal
    return best_signal


def _iter_patient_reference_matches(unit: str) -> list[tuple[int, int, str]]:
    matches: list[tuple[int, int, str]] = []
    for pattern in (PATIENT_CASE_LABEL_RE, DESCRIPTIVE_PATIENT_LABEL_RE):
        for match in pattern.finditer(unit):
            matches.append((match.start(), match.end(), match.group("label").lower()))
    return sorted(matches, key=lambda item: item[0])


def _has_explicit_patient_level_sps_signal(window: str) -> bool:
    if not window or SPS_SCORE_CONTEXT_RE.search(window):
        return False
    if EXPLICIT_PATIENT_SPS_ACTION_RE.search(window):
        return True
    normalized = normalize_text(window)
    return bool(LLM_EVIDENCE_SPS_RE.search(window) and len(normalized.split()) <= 8)


def _extract_explicit_patient_case_signal(text: str) -> SubgroupSignal | None:
    cleaned = _clean_signal_text(text)
    if not cleaned:
        return None

    evidence_by_label: dict[str, str] = {}
    for match in EXPLICIT_PATIENT_SPS_ACTION_RE.finditer(cleaned):
        snippet_start = max(0, match.start() - 160)
        snippet_end = min(len(cleaned), match.end() + 100)
        snippet = cleaned[snippet_start:snippet_end]
        if _is_non_original_case_context(snippet):
            continue
        reference_matches = _iter_patient_reference_matches(snippet)
        if not reference_matches:
            continue
        local_match_start = match.start() - snippet_start
        candidate_labels = [
            label
            for start, _, label in reference_matches
            if 0 <= local_match_start - start <= 80
        ]
        if not candidate_labels:
            continue
        label = candidate_labels[-1]
        evidence_by_label[label] = snippet[:420]

    if not evidence_by_label:
        return None

    evidence_units = tuple(evidence_by_label.values())
    return SubgroupSignal(
        count=len(evidence_by_label),
        count_basis="diagnosis_specific_patient_case_count",
        count_confidence="medium",
        evidence_units=evidence_units,
    )


def _extract_patient_label_subgroup_signal(text: str) -> SubgroupSignal | None:
    evidence_by_label: dict[str, str] = {}
    for unit in _raw_evidence_units(text):
        if _is_non_original_case_context(unit):
            continue
        local_matches = _iter_patient_reference_matches(unit)
        if not local_matches:
            continue
        for index, (start, end, label) in enumerate(local_matches):
            next_start = local_matches[index + 1][0] if index + 1 < len(local_matches) else len(unit)
            window = unit[start : min(next_start, end + 100)]
            if not _has_explicit_patient_level_sps_signal(window):
                continue
            evidence_by_label[label] = window[:420]

    if not evidence_by_label:
        return None

    return SubgroupSignal(
        count=len(evidence_by_label),
        count_basis="diagnosis_specific_patient_label_count",
        count_confidence="medium",
        evidence_units=tuple(evidence_by_label.values()),
    )


def extract_explicit_sps_subgroup_signal(*, abstract: str, raw_preferred_text: str) -> SubgroupSignal | None:
    combined_text = "\n".join(part for part in [abstract, raw_preferred_text] if part)
    for extractor in (
        _extract_direct_sps_cohort_signal,
        _extract_series_cohort_signal,
        _extract_diagnosis_supported_subset_signal,
        _extract_named_sps_cohort_signal,
        _extract_group_breakdown_subgroup_signal,
        _extract_enumerated_sps_subgroup_signal,
        _extract_mixed_diagnosis_subgroup_signal,
        _extract_suffix_count_subgroup_signal,
        _extract_table_row_subgroup_signal,
        _extract_explicit_patient_case_signal,
        _extract_patient_label_subgroup_signal,
    ):
        signal = extractor(combined_text)
        if signal is not None:
            return signal
    return None


def extract_non_original_case_signals(*, abstract: str, raw_preferred_text: str) -> list[str]:
    signals: list[str] = []
    seen: set[str] = set()
    combined_text = "\n".join(part for part in [abstract, raw_preferred_text] if part)
    for unit in _raw_evidence_units(combined_text):
        if not _is_non_original_case_context(unit):
            continue
        normalized = normalize_text(unit)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        signals.append(unit[:420])
    return signals[:4]


def _has_confirmed_sps_context(text: str) -> bool:
    return bool(
        SUSPECTED_SPS_COHORT_SIGNAL_RE.search(text)
        or CONFIRMED_SPS_CONTEXT_RE.search(text)
    )


def _extract_diagnosis_supported_subset_signal(text: str) -> SubgroupSignal | None:
    cleaned_text = _clean_signal_text(text)
    if not _has_confirmed_sps_context(cleaned_text):
        return None

    best_signal: SubgroupSignal | None = None
    best_score = -1
    for unit in _raw_evidence_units(cleaned_text):
        if _is_non_original_case_context(unit):
            continue
        if not DIAGNOSIS_SUPPORTED_SUBSET_RE.search(unit):
            continue
        for match in DIAGNOSIS_SUPPORTED_SUBSET_RE.finditer(unit):
            count = parse_count_token(match.group("count"))
            if count <= 0:
                continue
            score = count
            evidence_units = [unit[:420]]
            if CONFIRMED_SPS_CONTEXT_RE.search(cleaned_text):
                evidence_units.append(
                    _clean_signal_text(CONFIRMED_SPS_CONTEXT_RE.search(cleaned_text).group(0))[:420]
                )
            signal = SubgroupSignal(
                count=count,
                count_basis="diagnosis_specific_confirmed_subset_count",
                count_confidence="high",
                evidence_units=tuple(dict.fromkeys(evidence_units)),
            )
            if score > best_score:
                best_score = score
                best_signal = signal
    return best_signal


def extract_confirmed_only_guardrail_signals(*, abstract: str, raw_preferred_text: str) -> list[str]:
    signals: list[str] = []
    seen: set[str] = set()
    combined_text = "\n".join(part for part in [abstract, raw_preferred_text] if part)
    for unit in _raw_evidence_units(combined_text):
        normalized = normalize_text(unit)
        if not normalized or normalized in seen:
            continue
        if DONOR_MATERIAL_SIGNAL_RE.search(unit) or SUSPECTED_SPS_COHORT_SIGNAL_RE.search(unit) or CONFIRMED_SPS_CONTEXT_RE.search(unit):
            seen.add(normalized)
            signals.append(unit[:420])
    return signals[:4]


def extract_sps_status_uncertainty_signals(
    *,
    abstract: str,
    raw_preferred_text: str,
    subgroup_signal: SubgroupSignal | None,
) -> list[str]:
    subgroup_units = tuple(subgroup_signal.evidence_units if subgroup_signal is not None else ())
    signals: list[str] = []
    seen: set[str] = set()
    combined_text = "\n".join(part for part in [abstract, raw_preferred_text] if part)
    cleaned_combined_text = _clean_signal_text(combined_text)

    for pattern in (SPS_STATUS_SUBSET_UNCERTAINTY_RE, SPS_STATUS_SINGLE_PATIENT_OCR_UNCERTAINTY_RE):
        match = pattern.search(cleaned_combined_text)
        if match is None:
            continue
        snippet_start = max(0, match.start() - 120)
        snippet_end = min(len(cleaned_combined_text), match.end() + 120)
        snippet = cleaned_combined_text[snippet_start:snippet_end][:420]
        normalized_snippet = normalize_text(snippet)
        if normalized_snippet and normalized_snippet not in seen:
            seen.add(normalized_snippet)
            signals.append(snippet)

    for match in CONTROL_GROUP_SPS_CONTEXT_RE.finditer(cleaned_combined_text):
        snippet_start = max(0, match.start() - 80)
        snippet_end = min(len(cleaned_combined_text), match.end() + 80)
        snippet = cleaned_combined_text[snippet_start:snippet_end][:420]
        if _matches_evidence_snippet(snippet, subgroup_units) or _contains_subgroup_count_signal(snippet, subgroup_signal):
            continue
        normalized_snippet = normalize_text(snippet)
        if normalized_snippet and normalized_snippet not in seen:
            seen.add(normalized_snippet)
            signals.append(snippet)

    for unit in _raw_evidence_units(combined_text):
        normalized = normalize_text(_clean_signal_text(unit))
        if not normalized or normalized in seen:
            continue
        if _matches_evidence_snippet(unit, subgroup_units) or _contains_subgroup_count_signal(unit, subgroup_signal):
            continue
        has_control_group_uncertainty = bool(
            LLM_EVIDENCE_SPS_RE.search(normalized)
            and any(marker in normalized for marker in CONTROL_GROUP_UNCERTAINTY_MARKERS)
        )
        mixed_context_uncertainty = bool(
            LLM_EVIDENCE_SPS_RE.search(normalized)
            and sum(1 for marker in NON_SPS_MIXED_DIAGNOSIS_MARKERS if marker in normalized) >= 2
            and len(_subgroup_pairs_from_unit(unit)) < 2
        )
        if unit.lower().startswith("keywords:"):
            continue
        if SPS_STATUS_SUBSET_UNCERTAINTY_RE.search(unit) or SPS_STATUS_SINGLE_PATIENT_OCR_UNCERTAINTY_RE.search(unit):
            seen.add(normalized)
            signals.append(unit[:420])
            continue
        if has_control_group_uncertainty:
            seen.add(normalized)
            signals.append(unit[:420])
            continue
        non_sps_hits = sum(1 for marker in NON_SPS_MIXED_DIAGNOSIS_MARKERS if marker in normalized)
        if LLM_EVIDENCE_SPS_RE.search(normalized) and non_sps_hits >= 2 and len(_subgroup_pairs_from_unit(unit)) < 2:
            seen.add(normalized)
            signals.append(unit[:420])
    return signals[:4]


def _llm_evidence_sentences(text: str, *, max_sentences: int) -> list[str]:
    scored: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for index, raw_unit in enumerate(LLM_EVIDENCE_SENTENCE_SPLIT_RE.split(text or "")):
        sentence = " ".join(str(raw_unit or "").split())
        if len(sentence) < 20:
            continue
        normalized = normalize_text(sentence)
        if not normalized or normalized in seen:
            continue
        score = 0
        if LLM_EVIDENCE_COUNT_RE.search(sentence):
            score += 2
        if LLM_EVIDENCE_CONTEXT_RE.search(sentence):
            score += 2
        if LLM_EVIDENCE_LABEL_RE.search(sentence):
            score += 2
        if LLM_EVIDENCE_SPS_RE.search(sentence):
            score += 1
        if any(marker in normalized for marker in LLM_EVIDENCE_POSITIVE_MARKERS):
            score += 2
        if score <= 0:
            continue
        seen.add(normalized)
        scored.append((score, index, sentence[:420]))

    selected = sorted(scored, key=lambda item: (-item[0], item[1]))[:max_sentences]
    return [sentence for _, _, sentence in sorted(selected, key=lambda item: item[1])]


def build_llm_evidence_text(
    *,
    title: str,
    abstract: str,
    early_body_text: str,
    raw_preferred_text: str,
    explicit_sps_subgroup_evidence: tuple[str, ...] | list[str] = (),
    non_original_case_signals: tuple[str, ...] | list[str] = (),
    sps_status_uncertainty_signals: tuple[str, ...] | list[str] = (),
    confirmed_only_guardrail_signals: tuple[str, ...] | list[str] = (),
) -> str:
    parts: list[str] = []
    if title.strip():
        parts.append(f"Title:\n{title.strip()[:500]}")
    if abstract.strip():
        parts.append(f"Metadata abstract:\n{abstract.strip()[:1800]}")

    subgroup_evidence = [snippet for snippet in explicit_sps_subgroup_evidence if str(snippet or "").strip()]
    if subgroup_evidence:
        subgroup_block = "\n".join(f"- {snippet[:420]}" for snippet in subgroup_evidence[:4])
        parts.append(f"Explicit SPS-spectrum subgroup signals:\n{subgroup_block}")

    non_original_block_items = [snippet for snippet in non_original_case_signals if str(snippet or "").strip()]
    if non_original_block_items:
        non_original_block = "\n".join(f"- {snippet[:420]}" for snippet in non_original_block_items[:4])
        parts.append(f"Potential non-original or reused-cohort signals:\n{non_original_block}")

    guardrail_block_items = [snippet for snippet in confirmed_only_guardrail_signals if str(snippet or "").strip()]
    if guardrail_block_items:
        guardrail_block = "\n".join(f"- {snippet[:420]}" for snippet in guardrail_block_items[:4])
        parts.append(f"Confirmed-only guardrail signals:\n{guardrail_block}")

    uncertainty_block_items = [snippet for snippet in sps_status_uncertainty_signals if str(snippet or "").strip()]
    if uncertainty_block_items:
        uncertainty_block = "\n".join(f"- {snippet[:420]}" for snippet in uncertainty_block_items[:4])
        parts.append(f"Potential SPS-status uncertainty signals:\n{uncertainty_block}")

    body_sentences = _llm_evidence_sentences(raw_preferred_text or early_body_text, max_sentences=8)
    if body_sentences:
        body_block = "\n".join(f"- {sentence}" for sentence in body_sentences)
        parts.append(f"Preferred text count-salient snippets:\n{body_block}")
    elif raw_preferred_text.strip():
        parts.append(f"Preferred text excerpt:\n{raw_preferred_text.strip()[:2200]}")
    elif early_body_text.strip():
        parts.append(f"Preferred text excerpt:\n{early_body_text.strip()[:2200]}")

    return "\n\n".join(parts)[:6500]


def prefer_single_case_default(
    *,
    source_category: str,
    source_subtype: str,
    title: str,
    abstract: str,
    early_body_text: str,
) -> bool:
    if source_category == "single_case_report":
        return True
    if source_subtype == "single_case_conference_abstract":
        return True
    explicit_multi_case = has_explicit_multi_case_signal(" ".join([title, abstract, early_body_text[:5000]]))
    if explicit_multi_case:
        return False
    text_for_signal = " ".join([title, abstract, early_body_text[:5000]])
    return has_single_case_signal(text_for_signal)


def adjust_estimate_for_source_context(
    *,
    estimate: CaseCountEstimate,
    title: str,
    abstract: str,
    early_body_text: str,
    source_category: str,
    source_subtype: str,
    preferred_text_source: str,
) -> CaseCountEstimate:
    context_text = " ".join([title, abstract, early_body_text[:1200]]).lower()
    explicit_single_case = has_single_case_signal(context_text)
    if any(marker in context_text for marker in ADMINISTRATIVE_DATASET_MARKERS):
        return CaseCountEstimate(
            likely_case_count=0,
            count_confidence="low",
            count_basis="administrative_dataset_not_extractable",
            manual_review_required=False,
        )

    single_case_default_ok = prefer_single_case_default(
        source_category=source_category,
        source_subtype=source_subtype,
        title=title,
        abstract=abstract,
        early_body_text=early_body_text,
    )

    if source_category == "conference_abstract" and preferred_text_source == "full_text":
        if estimate.count_basis in {"patient_label_count", "early_body_count_signal"}:
            estimate = estimate_sps_case_count(title=title, abstract=abstract, early_body_text="")

    if single_case_default_ok and estimate.likely_case_count == 0:
        if source_category == "lab_heavy_clinical_or_translational":
            return CaseCountEstimate(
                likely_case_count=0,
                count_confidence="low",
                count_basis="lab_context_no_extractable_count",
                manual_review_required=False,
            )
        return CaseCountEstimate(
            likely_case_count=1,
            count_confidence="medium",
            count_basis="source_single_case_default",
            manual_review_required=False,
        )

    if (
        single_case_default_ok
        and estimate.likely_case_count > 1
        and estimate.count_basis in {"abstract_count_signal", "early_body_count_signal", "patient_label_count"}
    ):
        return CaseCountEstimate(
            likely_case_count=1,
            count_confidence="medium",
            count_basis="source_single_case_override",
            manual_review_required=False,
        )

    if source_category == "lab_heavy_clinical_or_translational":
        if estimate.count_basis == "abstract_count_signal":
            body_only_estimate = estimate_sps_case_count(
                title=title,
                abstract="",
                early_body_text=early_body_text,
            )
            if body_only_estimate.likely_case_count > 0 and body_only_estimate.likely_case_count < estimate.likely_case_count:
                estimate = body_only_estimate
        diagnosis_specific_basis = estimate.count_basis.startswith("diagnosis_specific_")
        explicit_multi_case = has_explicit_multi_case_signal(" ".join([title, abstract]))
        strong_group_basis = (
            estimate.count_basis in {
                "title_count_signal",
                "abstract_count_signal",
                "early_body_count_signal",
                "patient_label_count",
            }
            and estimate.likely_case_count >= 3
        )
        if not (diagnosis_specific_basis or (explicit_multi_case and strong_group_basis)):
            return CaseCountEstimate(
                likely_case_count=0,
                count_confidence="low",
                count_basis="lab_context_no_extractable_count",
                manual_review_required=False,
            )

    if source_category == "review_article" and explicit_single_case and estimate.likely_case_count == 1:
        return estimate

    if (
        source_category == "observational_group_study"
        and estimate.count_basis == "patient_label_count"
        and estimate.likely_case_count <= 2
    ):
        title_text = title.lower()
        if not any(marker in title_text for marker in ("stiff", "sps", "sms")) and any(
            marker in context_text for marker in ("autoantigen", "serologic", "serological evaluation")
        ):
            return CaseCountEstimate(
                likely_case_count=0,
                count_confidence="low",
                count_basis="observational_context_no_extractable_sps_count",
                manual_review_required=False,
            )

    return estimate


def count_eligible(source_category: str) -> bool:
    return count_eligibility_status(source_category) != "not_extractable"


def resolve_preferred_text_source(
    *,
    preferred_path: Path,
    paper_id: str,
    ready_rows: dict[str, dict[str, str]] | None = None,
) -> str:
    if preferred_path.parent == TEXT_PROCEEDINGS_READY_DIR:
        ready_registry_rows = (
            ready_rows
            if ready_rows is not None
            else load_ready_rows_by_id(TEXT_PROCEEDINGS_READY_REGISTRY_PATH)
        )
        return preferred_proceedings_text_source(
            paper_id,
            ready_rows=ready_registry_rows,
        )
    return "trimmed" if preferred_path.parent == TEXT_TRIMMED_DIR else "full_text"


def _review_single_case_override(
    *,
    source_category: str,
    title: str,
    abstract: str,
    early_body_text: str,
    estimate: CaseCountEstimate,
) -> bool:
    return (
        source_category == "review_article"
        and estimate.likely_case_count == 1
        and has_single_case_signal(" ".join([title, abstract]))
    )


def finalise_estimate_for_registry(
    *,
    estimate: CaseCountEstimate,
    title: str,
    abstract: str,
    early_body_text: str,
    source_category: str,
    source_subtype: str,
    preferred_text_source: str,
) -> CaseCountEstimate:
    adjusted = adjust_estimate_for_source_context(
        estimate=estimate,
        title=title,
        abstract=abstract,
        early_body_text=early_body_text,
        source_category=source_category,
        source_subtype=source_subtype,
        preferred_text_source=preferred_text_source,
    )
    if source_category in {"review_article", "non_clinical_basic_science"} and not _review_single_case_override(
        source_category=source_category,
        title=title,
        abstract=abstract,
        early_body_text=early_body_text,
        estimate=adjusted,
    ):
        return CaseCountEstimate(
            likely_case_count=0,
            count_confidence="low",
            count_basis="not_count_eligible",
            manual_review_required=False,
        )
    return adjusted


def _candidate_kind_from_estimate(estimate: CaseCountEstimate) -> str:
    if estimate.count_basis.startswith("diagnosis_specific_"):
        return "diagnosis_specific_subset_count"
    if estimate.count_basis in {
        "source_single_case_default",
        "source_single_case_override",
        "single_case_text_signal",
        "case_report_marker_single_case",
    }:
        return "single_case_default"
    if estimate.count_basis in {
        "not_count_eligible",
        "administrative_dataset_not_extractable",
        "lab_context_no_extractable_count",
        "observational_context_no_extractable_sps_count",
    } or estimate.likely_case_count == 0:
        return "forced_zero"
    return "exact_numeric_count"


def _estimate_score(estimate: CaseCountEstimate, *, preferred: bool = False) -> int:
    score = CONFIDENCE_SCORES.get(estimate.count_confidence, 40)
    if preferred:
        score += 20
    if estimate.count_basis.startswith("diagnosis_specific_"):
        score += 12
    if estimate.count_basis in {
        "not_count_eligible",
        "administrative_dataset_not_extractable",
        "lab_context_no_extractable_count",
        "observational_context_no_extractable_sps_count",
    }:
        score += 10
    if estimate.count_basis in {
        "source_single_case_default",
        "source_single_case_override",
        "case_report_marker_single_case",
        "single_case_text_signal",
    }:
        score += 4
    if estimate.manual_review_required:
        score -= 8
    return score


def _estimate_evidence(
    estimate: CaseCountEstimate,
    *,
    title: str,
    abstract: str,
    early_body_text: str,
) -> tuple[str, str]:
    if estimate.count_basis == "title_count_signal":
        return title, "title"
    if estimate.count_basis in {
        "abstract_count_signal",
        "case_report_marker_single_case",
        "single_case_text_signal",
    } and abstract.strip():
        return abstract[:900], "abstract"
    if estimate.count_basis.startswith("diagnosis_specific_") or estimate.count_basis in {
        "early_body_count_signal",
        "patient_label_count",
    }:
        return early_body_text[:1200], "preferred_text_excerpt"
    if estimate.count_basis in {
        "source_single_case_default",
        "source_single_case_override",
    }:
        return " ".join(part for part in [title, abstract, early_body_text[:500]] if part).strip()[:1200], "context"
    return " ".join(part for part in [abstract, early_body_text[:500], title] if part).strip()[:1200], "context"


def _estimate_rationale(
    estimate: CaseCountEstimate,
    *,
    source_category: str,
) -> str:
    parts = [
        f"basis={estimate.count_basis}",
        f"confidence={estimate.count_confidence}",
    ]
    if source_category:
        parts.append(f"source_category={source_category}")
    if estimate.manual_review_required:
        parts.append("heuristic_manual_review=true")
    return " | ".join(parts)


def _build_candidate(
    estimate: CaseCountEstimate,
    *,
    title: str,
    abstract: str,
    early_body_text: str,
    source_category: str,
    preferred: bool = False,
) -> CountCandidate:
    evidence_text, evidence_section = _estimate_evidence(
        estimate,
        title=title,
        abstract=abstract,
        early_body_text=early_body_text,
    )
    blockers: list[str] = []
    if estimate.count_basis in AMBIGUOUS_BASES:
        blockers.append("ambiguous_heuristic_basis")
    if estimate.manual_review_required:
        blockers.append("heuristic_manual_review_required")
    if estimate.count_confidence != "high":
        blockers.append("non_high_confidence")
    return CountCandidate(
        candidate_id="",
        proposed_count=estimate.likely_case_count,
        candidate_kind=_candidate_kind_from_estimate(estimate),
        count_basis=estimate.count_basis,
        count_confidence=estimate.count_confidence,
        manual_review_required=estimate.manual_review_required,
        score=_estimate_score(estimate, preferred=preferred),
        rationale=_estimate_rationale(estimate, source_category=source_category),
        evidence_text=evidence_text,
        evidence_section=evidence_section,
        blockers=blockers,
    )


def _build_subgroup_candidate(
    signal: SubgroupSignal,
    *,
    title: str,
    abstract: str,
    early_body_text: str,
    source_category: str,
) -> CountCandidate:
    estimate = CaseCountEstimate(
        likely_case_count=signal.count,
        count_confidence=signal.count_confidence,
        count_basis=signal.count_basis,
        manual_review_required=signal.count_confidence != "high",
    )
    candidate = _build_candidate(
        estimate,
        title=title,
        abstract=abstract,
        early_body_text=early_body_text,
        source_category=source_category,
    )
    return CountCandidate(
        candidate_id=candidate.candidate_id,
        proposed_count=candidate.proposed_count,
        candidate_kind=candidate.candidate_kind,
        count_basis=candidate.count_basis,
        count_confidence=candidate.count_confidence,
        manual_review_required=candidate.manual_review_required,
        score=candidate.score,
        rationale=candidate.rationale,
        evidence_text=(signal.evidence_units[0] if signal.evidence_units else candidate.evidence_text),
        evidence_section="explicit_sps_subgroup_signal",
        blockers=list(candidate.blockers),
    )


def _with_candidate_ids(candidates: list[CountCandidate]) -> list[CountCandidate]:
    resolved: list[CountCandidate] = []
    for index, candidate in enumerate(candidates, start=1):
        resolved.append(
            CountCandidate(
                candidate_id=f"cand{index:02d}",
                proposed_count=candidate.proposed_count,
                candidate_kind=candidate.candidate_kind,
                count_basis=candidate.count_basis,
                count_confidence=candidate.count_confidence,
                manual_review_required=candidate.manual_review_required,
                score=candidate.score,
                rationale=candidate.rationale,
                evidence_text=candidate.evidence_text,
                evidence_section=candidate.evidence_section,
                blockers=list(candidate.blockers),
            )
        )
    return resolved


def _dedupe_candidates(candidates: list[CountCandidate]) -> list[CountCandidate]:
    deduped: dict[tuple[int, str], CountCandidate] = {}
    for candidate in candidates:
        key = (candidate.proposed_count, candidate.count_basis)
        existing = deduped.get(key)
        if existing is None or candidate.score > existing.score:
            deduped[key] = candidate
    ordered = sorted(
        deduped.values(),
        key=lambda candidate: (-candidate.score, candidate.manual_review_required, candidate.proposed_count, candidate.count_basis),
    )
    return _with_candidate_ids(ordered)


def _fallback_candidate_id(
    candidates: list[CountCandidate],
    *,
    explicit_sps_subgroup_count: int | None = None,
) -> str:
    if explicit_sps_subgroup_count is not None:
        explicit_subgroup_candidates = [
            candidate
            for candidate in candidates
            if candidate.proposed_count == explicit_sps_subgroup_count
            and candidate.count_basis.startswith("diagnosis_specific_")
        ]
        if explicit_subgroup_candidates:
            explicit_subgroup_candidates.sort(
                key=lambda candidate: (-candidate.score, candidate.manual_review_required, candidate.count_basis)
            )
            return explicit_subgroup_candidates[0].candidate_id
    subgroup_candidates = [candidate for candidate in candidates if candidate.count_basis.startswith("diagnosis_specific_")]
    if subgroup_candidates:
        subgroup_candidates.sort(key=lambda candidate: (-candidate.score, candidate.proposed_count))
        return subgroup_candidates[0].candidate_id
    return candidates[0].candidate_id


def _llm_routing_reason(candidates: list[CountCandidate], preferred_text_source: str, source_category: str) -> tuple[bool, str]:
    distinct_counts = {candidate.proposed_count for candidate in candidates}
    top = candidates[0]
    eligibility_status = count_eligibility_status(source_category)
    if eligibility_status == "uncertain":
        return True, "uncertain_source_category"
    if len(distinct_counts) > 1:
        return True, "multiple_candidate_counts"
    if top.manual_review_required:
        return True, "preferred_candidate_manual_review"
    if top.count_confidence != "high":
        return True, "preferred_candidate_non_high_confidence"
    if top.count_basis in AMBIGUOUS_BASES:
        return True, "ambiguous_heuristic_basis"
    if source_category == "conference_abstract" and preferred_text_source == "full_text":
        return True, "conference_abstract_using_full_text"
    if source_category in {
        "lab_heavy_clinical_or_translational",
        "observational_group_study",
        "review_format_with_embedded_original_cohort",
    }:
        return True, "high_risk_source_category"
    return False, "preferred_candidate_clear"


def build_case_count_candidate_package(
    *,
    reference_row: dict[str, str],
    text_record: dict[str, Any],
    preferred_record: dict[str, Any],
    preferred_path: Path,
    source_row: dict[str, str],
    ready_rows: dict[str, dict[str, str]] | None = None,
    heuristic_version: str = HEURISTIC_VERSION,
) -> CountCandidatePackage:
    paper_id = str(text_record.get("paper_id") or Path(str(text_record.get("_path") or "")).stem)
    title = (reference_row.get("Title") or "").strip()
    abstract = (reference_row.get("Abstract") or "").strip()
    authors = (reference_row.get("Authors") or "").strip()
    source_category = (source_row.get("source_category") or "").strip()
    source_subtype = (source_row.get("source_subtype") or "").strip()
    eligibility_status = count_eligibility_status(source_category)
    preferred_text_source = resolve_preferred_text_source(
        preferred_path=preferred_path,
        paper_id=paper_id,
        ready_rows=ready_rows,
    )
    raw_preferred_text = record_text_window(preferred_record, use_all_pages=not abstract.strip())
    early_body_text = title_localised_window(
        raw_preferred_text,
        title,
    )
    subgroup_signal = extract_explicit_sps_subgroup_signal(
        abstract=abstract,
        raw_preferred_text=raw_preferred_text,
    )
    non_original_case_signals = extract_non_original_case_signals(
        abstract=abstract,
        raw_preferred_text=raw_preferred_text,
    )
    confirmed_only_guardrail_signals = extract_confirmed_only_guardrail_signals(
        abstract=abstract,
        raw_preferred_text=raw_preferred_text,
    )
    uncertainty_signals = extract_sps_status_uncertainty_signals(
        abstract=abstract,
        raw_preferred_text=raw_preferred_text,
        subgroup_signal=subgroup_signal,
    )
    provenance_signals = list(non_original_case_signals)
    if source_category == "review_format_with_embedded_original_cohort":
        provenance_signals.insert(
            0,
            "Review-format paper with an embedded original cohort; patient overlap or prior publication status may need confirmation.",
        )
    provenance_uncertain = bool(provenance_signals)

    base_estimate = estimate_sps_case_count(
        title=title,
        abstract=abstract,
        early_body_text=early_body_text,
    )
    final_estimate = finalise_estimate_for_registry(
        estimate=base_estimate,
        title=title,
        abstract=abstract,
        early_body_text=early_body_text,
        source_category=source_category,
        source_subtype=source_subtype,
        preferred_text_source=preferred_text_source,
    )

    abstract_only_estimate = estimate_sps_case_count(
        title=title,
        abstract=abstract,
        early_body_text="",
    )
    abstract_only_final = finalise_estimate_for_registry(
        estimate=abstract_only_estimate,
        title=title,
        abstract=abstract,
        early_body_text="",
        source_category=source_category,
        source_subtype=source_subtype,
        preferred_text_source=preferred_text_source,
    )

    body_only_estimate = estimate_sps_case_count(
        title=title,
        abstract="",
        early_body_text=early_body_text,
    )
    body_only_final = finalise_estimate_for_registry(
        estimate=body_only_estimate,
        title=title,
        abstract="",
        early_body_text=early_body_text,
        source_category=source_category,
        source_subtype=source_subtype,
        preferred_text_source=preferred_text_source,
    )

    candidates: list[CountCandidate] = [
        _build_candidate(
            final_estimate,
            title=title,
            abstract=abstract,
            early_body_text=early_body_text,
            source_category=source_category,
            preferred=True,
        )
    ]
    notes: list[str] = [f"preferred_text_source={preferred_text_source}"]
    suppress_nonzero_alternatives = (
        eligibility_status == "not_extractable" and final_estimate.count_basis == "not_count_eligible"
    )

    if (
        not suppress_nonzero_alternatives
        and (
            base_estimate.likely_case_count != final_estimate.likely_case_count
            or base_estimate.count_basis != final_estimate.count_basis
        )
    ):
        notes.append("source_context_adjusted_primary_estimate")
        candidates.append(
            _build_candidate(
                base_estimate,
                title=title,
                abstract=abstract,
                early_body_text=early_body_text,
                source_category=source_category,
            )
        )

    if (
        not suppress_nonzero_alternatives
        and (
            abstract_only_final.likely_case_count != final_estimate.likely_case_count
            or abstract_only_final.count_basis != final_estimate.count_basis
        )
    ):
        notes.append("abstract_only_candidate_added")
        candidates.append(
            _build_candidate(
                abstract_only_final,
                title=title,
                abstract=abstract,
                early_body_text=early_body_text,
                source_category=source_category,
            )
        )

    if (
        not suppress_nonzero_alternatives
        and (
            body_only_final.likely_case_count != final_estimate.likely_case_count
            or body_only_final.count_basis != final_estimate.count_basis
        )
    ):
        notes.append("body_only_candidate_added")
        candidates.append(
            _build_candidate(
                body_only_final,
                title=title,
                abstract=abstract,
                early_body_text=early_body_text,
                source_category=source_category,
            )
        )

    if not suppress_nonzero_alternatives and subgroup_signal is not None:
        notes.append("explicit_sps_subgroup_candidate_added")
        candidates.append(
            _build_subgroup_candidate(
                subgroup_signal,
                title=title,
                abstract=abstract,
                early_body_text=early_body_text,
                source_category=source_category,
            )
        )

    if (
        source_category not in {"review_article", "non_clinical_basic_science"}
        and prefer_single_case_default(
            source_category=source_category,
            source_subtype=source_subtype,
            title=title,
            abstract=abstract,
            early_body_text=early_body_text,
        )
    ):
        single_case_candidate = CaseCountEstimate(
            likely_case_count=1,
            count_confidence="medium",
            count_basis="source_single_case_default",
            manual_review_required=False,
        )
        if single_case_candidate.likely_case_count != final_estimate.likely_case_count or single_case_candidate.count_basis != final_estimate.count_basis:
            notes.append("single_case_default_candidate_added")
            candidates.append(
                _build_candidate(
                    single_case_candidate,
                    title=title,
                    abstract=abstract,
                    early_body_text=early_body_text,
                    source_category=source_category,
                )
            )

    if eligibility_status == "not_extractable":
        zero_candidate = CaseCountEstimate(
            likely_case_count=0,
            count_confidence="low",
            count_basis="not_count_eligible",
            manual_review_required=False,
        )
        if zero_candidate.count_basis != final_estimate.count_basis:
            notes.append("count_ineligible_zero_candidate_added")
            candidates.append(
                _build_candidate(
                    zero_candidate,
                    title=title,
                    abstract=abstract,
                    early_body_text=early_body_text,
                    source_category=source_category,
                )
            )

    resolved_candidates = _dedupe_candidates(candidates)
    fallback_candidate_id = _fallback_candidate_id(
        resolved_candidates,
        explicit_sps_subgroup_count=None if subgroup_signal is None else subgroup_signal.count,
    )
    llm_routing_recommended, llm_reason = _llm_routing_reason(
        resolved_candidates,
        preferred_text_source=preferred_text_source,
        source_category=source_category,
    )
    notes.append(f"distinct_candidate_counts={sorted({candidate.proposed_count for candidate in resolved_candidates})}")
    if subgroup_signal is not None:
        notes.append(f"explicit_sps_subgroup_count={subgroup_signal.count}")
    if non_original_case_signals:
        notes.append(f"non_original_case_signals={len(non_original_case_signals)}")
    if confirmed_only_guardrail_signals:
        notes.append(f"confirmed_only_guardrail_signals={len(confirmed_only_guardrail_signals)}")
    if uncertainty_signals:
        notes.append(f"sps_status_uncertainty_signals={len(uncertainty_signals)}")
    if provenance_uncertain:
        notes.append("original_cohort_provenance_uncertain=true")

    return CountCandidatePackage(
        paper_id=paper_id,
        covidence_id=(reference_row.get("Covidence") or "").strip(),
        title=title,
        authors=authors,
        source_category=source_category,
        source_subtype=source_subtype,
        preferred_text_json_path=relative_to_repo(preferred_path),
        preferred_text_source=preferred_text_source,
        preferred_text_metadata={
            "preferred_text_json_path": relative_to_repo(preferred_path),
            "preferred_text_source": preferred_text_source,
            "source_filename": str(preferred_record.get("source_filename") or text_record.get("source_filename") or ""),
            "proceedings_ready_source_kind": str(preferred_record.get("proceedings_ready_source_kind") or ""),
            "proceedings_ready_text_mode": str(preferred_record.get("proceedings_ready_text_mode") or ""),
            "proceedings_ready_reason": str(preferred_record.get("proceedings_ready_reason") or ""),
            "source_text_json_path": str(preferred_record.get("source_text_json_path") or ""),
        },
        count_eligible=count_eligible(source_category),
        heuristic_version=heuristic_version,
        abstract_text=abstract,
        early_body_text=early_body_text[:5000],
        llm_evidence_text=build_llm_evidence_text(
            title=title,
            abstract=abstract,
            early_body_text=early_body_text,
            raw_preferred_text=raw_preferred_text,
            explicit_sps_subgroup_evidence=() if subgroup_signal is None else subgroup_signal.evidence_units,
            non_original_case_signals=non_original_case_signals,
            sps_status_uncertainty_signals=uncertainty_signals,
            confirmed_only_guardrail_signals=confirmed_only_guardrail_signals,
        ),
        candidate_generation_notes=[*notes, f"count_eligibility_status={eligibility_status}"],
        candidates=resolved_candidates,
        preferred_candidate_id=resolved_candidates[0].candidate_id,
        fallback_candidate_id=fallback_candidate_id,
        llm_routing_recommended=llm_routing_recommended,
        llm_routing_reason=llm_reason,
        explicit_sps_subgroup_count=None if subgroup_signal is None else subgroup_signal.count,
        explicit_sps_subgroup_basis="" if subgroup_signal is None else subgroup_signal.count_basis,
        explicit_sps_subgroup_evidence=[] if subgroup_signal is None else list(subgroup_signal.evidence_units),
        sps_status_uncertainty_signals=uncertainty_signals,
        original_cohort_provenance_uncertain=provenance_uncertain,
        original_cohort_provenance_signals=provenance_signals[:4],
        confirmed_only_guardrail_signals=confirmed_only_guardrail_signals,
    )


def count_row_from_resolution(
    *,
    package: CountCandidatePackage,
    final_count: int,
    final_confidence: str,
    final_basis: str,
    final_manual_review_required: bool,
    final_reason: str,
    count_version: str,
    count_verification_status: str,
    count_candidate_json_path: str = "",
    count_evidence_json_path: str = "",
    heuristic_fallback_used: bool = False,
    llm_likely_sps_case_count: str = "",
    llm_count_confidence: str = "",
    llm_selected_candidate_id: str = "",
    count_validator_flags: list[str] | None = None,
    count_audit_status: str = "not_run",
) -> dict[str, str]:
    preferred_candidate = package.preferred_candidate()
    effective_manual_review_required = package.count_eligible and (
        final_manual_review_required or package.original_cohort_provenance_uncertain
    )
    return {
        "paper_id": package.paper_id,
        "covidence_id": package.covidence_id,
        "title": package.title,
        "authors": package.authors,
        "source_category": package.source_category,
        "source_subtype": package.source_subtype,
        "preferred_text_json_path": package.preferred_text_json_path,
        "preferred_text_source": package.preferred_text_source,
        "count_eligible": bool_text(package.count_eligible),
        "likely_sps_case_count": str(final_count),
        "count_confidence": final_confidence,
        "count_basis": final_basis,
        "count_manual_review_required": bool_text(effective_manual_review_required),
        "count_original_cohort_provenance_uncertain": bool_text(
            package.original_cohort_provenance_uncertain
        ),
        "count_reason": final_reason,
        "count_version": count_version,
        "heuristic_likely_sps_case_count": str(preferred_candidate.proposed_count),
        "heuristic_count_confidence": preferred_candidate.count_confidence,
        "heuristic_count_basis": preferred_candidate.count_basis,
        "count_candidate_json_path": count_candidate_json_path,
        "heuristic_candidate_count": str(len(package.candidates)),
        "llm_likely_sps_case_count": llm_likely_sps_case_count,
        "llm_count_confidence": llm_count_confidence,
        "llm_selected_candidate_id": llm_selected_candidate_id,
        "heuristic_fallback_used": bool_text(heuristic_fallback_used),
        "count_audit_status": count_audit_status,
        "count_verification_status": count_verification_status,
        "count_validator_flags": "; ".join(count_validator_flags or []),
        "count_evidence_json_path": count_evidence_json_path,
        "counted_at_utc": now_utc_iso(),
    }


def build_case_count_record(
    *,
    reference_row: dict[str, str],
    text_record: dict[str, Any],
    preferred_record: dict[str, Any],
    preferred_path: Path,
    source_row: dict[str, str],
    count_version: str = HEURISTIC_VERSION,
    ready_rows: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    package = build_case_count_candidate_package(
        reference_row=reference_row,
        text_record=text_record,
        preferred_record=preferred_record,
        preferred_path=preferred_path,
        source_row=source_row,
        ready_rows=ready_rows,
        heuristic_version=HEURISTIC_VERSION,
    )
    preferred_candidate = package.preferred_candidate()
    reasons = [
        f"count_basis={preferred_candidate.count_basis}",
        f"count_confidence={preferred_candidate.count_confidence}",
    ]
    if package.source_category:
        reasons.append(f"source_category={package.source_category}")
    if package.candidate_generation_notes:
        reasons.append(f"candidate_notes={'; '.join(package.candidate_generation_notes)}")
    return count_row_from_resolution(
        package=package,
        final_count=preferred_candidate.proposed_count,
        final_confidence=preferred_candidate.count_confidence,
        final_basis=preferred_candidate.count_basis,
        final_manual_review_required=preferred_candidate.manual_review_required,
        final_reason=" | ".join(reasons),
        count_version=count_version,
        count_verification_status="heuristic_only",
    )


def count_row_fieldnames() -> list[str]:
    return [
        "paper_id",
        "covidence_id",
        "title",
        "authors",
        "source_category",
        "source_subtype",
        "preferred_text_json_path",
        "preferred_text_source",
        "count_eligible",
        "likely_sps_case_count",
        "count_confidence",
        "count_basis",
        "count_manual_review_required",
        "count_original_cohort_provenance_uncertain",
        "count_reason",
        "count_version",
        "heuristic_likely_sps_case_count",
        "heuristic_count_confidence",
        "heuristic_count_basis",
        "count_candidate_json_path",
        "heuristic_candidate_count",
        "llm_likely_sps_case_count",
        "llm_count_confidence",
        "llm_selected_candidate_id",
        "heuristic_fallback_used",
        "count_audit_status",
        "count_verification_status",
        "count_validator_flags",
        "count_evidence_json_path",
        "counted_at_utc",
    ]


def write_count_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=count_row_fieldnames())
        writer.writeheader()
        writer.writerows(rows)
