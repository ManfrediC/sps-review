from __future__ import annotations

from src.validation.find_missed_proceedings_candidates import (
    assess_row,
    build_snippet,
    build_metadata_markers,
    proceedings_boundary_code,
    strict_author_line,
)


def make_record(lines: list[str]) -> dict[str, object]:
    return {
        "pages": [
            {
                "page_index": 0,
                "text": "\n".join(lines),
            }
        ]
    }


def test_build_metadata_markers_finds_conference_terms() -> None:
    row = {
        "title": "Partial Stiff Person Syndrome as a Stroke Mimic",
        "journal": "Neurology Supplement",
        "tags": "",
        "notes": "Conference paper with potential for data extraction.",
    }

    markers = build_metadata_markers(row)

    assert "journal:supplement" in markers
    assert "notes:conference_paper" in markers


def test_strict_author_line_requires_name_like_patterns() -> None:
    assert strict_author_line("Jane Doe, John Smith, Alice Roe")
    assert not strict_author_line("Objective: describe a rare autoimmune neurological disorder")


def test_proceedings_boundary_code_rejects_section_numbering() -> None:
    assert proceedings_boundary_code("1. Introduction") == ""
    assert proceedings_boundary_code("P13 - Poster Session 13") == ""


def test_assess_row_flags_missed_proceedings_fragment() -> None:
    row = {
        "paper_id": "6271",
        "source_category": "single_case_report",
        "classification_confidence": "high",
        "title": "Dementia in elderly male with Stiff Man Syndrome",
        "authors": "Sheyner, I; Cutillar, M",
        "journal": "Journal of the American Geriatrics Society",
        "notes": "Conference paper in supplement.",
    }
    record = make_record(
        [
            "C14",
            "Dementia in elderly male with Stiff Man Syndrome.",
            "I. Sheyner, M. Cutillar. Internal Medicine, University of South Florida, Tampa, FL.",
            "Abstract: We are presenting the case of a 75 year old male undergoing long term care in the nursing home.",
            "Treatment with diazepam and plasmapheresis provided reasonable control of symptoms.",
            "C15",
            "Guillain-Barre Syndrome in a Nonagenarian.",
            "S. Sultan, L. Smith. Department of Geriatrics, St. Luke's-Roosevelt Hospital Center.",
            "Abstract: Another abstract follows.",
        ]
    )

    assessment = assess_row(row, record, min_candidate_score=6)

    assert assessment is not None
    assert assessment["candidate_level"] == "strong_missed_proceedings"
    assert "notes:conference_paper" in assessment["metadata_markers"]
    assert assessment["next_boundary"] == "coded_boundary"


def test_assess_row_ignores_standard_single_article_without_markers() -> None:
    row = {
        "paper_id": "101",
        "source_category": "single_case_report",
        "classification_confidence": "high",
        "title": "Progressive encephalomyelitis with rigidity responsive to plasmapheresis",
        "authors": "Fogan, L",
        "journal": "Annals of Neurology",
        "notes": "",
    }
    record = make_record(
        [
            "Progressive encephalomyelitis with rigidity responsive to plasmapheresis",
            "L. Fogan",
            "Abstract",
            "Objective: describe one patient.",
            "Methods: case description.",
            "Results: marked clinical improvement after plasmapheresis.",
            "Discussion: this is a full article abstract, not a proceedings fragment.",
        ]
    )

    assessment = assess_row(row, record, min_candidate_score=6)

    assert assessment is None


def test_assess_row_ignores_standalone_short_abstract_page_with_conference_metadata() -> None:
    row = {
        "paper_id": "1935",
        "source_category": "single_case_report",
        "classification_confidence": "high",
        "title": "Stiff limb syndrome: A rare variant of stiff person's syndrome",
        "authors": "Lin, B; Sivakumar, K; Yacoub, H",
        "journal": "Neurology",
        "notes": "Conference paper in supplement.",
    }
    record = {
        "n_pages": 1,
        "pages": [
            {
                "page_index": 0,
                "text": "\n".join(
                    [
                        "Stiff Limb Syndrome: A Rare Variant of Stiff Person's Syndrome",
                        "(4487)",
                        "Benjamin Lin, Keithan Sivakumar, Hussam Yacoub",
                        "First published April 14, 2020,",
                        "Abstract",
                        "Objective: We present an elderly woman with bilateral leg rigidity.",
                        "Methods: Case description and clinical work-up.",
                        "Results: Diazepam and immunotherapy improved symptoms.",
                        "Conclusion: This source is a standalone abstract page rather than a proceedings fragment.",
                    ]
                ),
            }
        ],
    }

    assessment = assess_row(row, record, min_candidate_score=7)

    assert assessment is None


def test_assess_row_ignores_standalone_abstract_with_reference_tail() -> None:
    row = {
        "paper_id": "1784",
        "source_category": "single_case_report",
        "classification_confidence": "high",
        "title": "Stiff-person syndrome and limbic encephalopathy associated with GAD-antibody: A case report",
        "authors": "Li S.L.; Yang Y.M.; Guan H.Z.; Wan X.H.; Ren H.T.",
        "journal": "Movement Disorders",
        "notes": "Conference paper with potential for data extraction.",
    }
    record = make_record(
        [
            "Stiff-Person Syndrome and Limbic",
            "Encephalopathy Associated With GAD-antibody:",
            "A Case Report",
            "SL. Li, YM. Yang, HZ. Guan, XH. Wan, HT. Ren (Peking, China)",
            "Meeting: 2019 International Congress",
            "ABSTRACT NUMBER: 2170",
            "Keywords: Stiff-person syndrome",
            "Objective: To extend the spectrum of glutamic acid decarboxylase associated disorders by reporting a case.",
            "Conclusion: LE and SPS associated with anti-GADA could coexist and respond to immunomodulatory therapy.",
            "References: 1. Damato, V. et al. Mov Disord, 2018. 33(9): p.1376-1389.",
            "2. Incecik, F. et al. Acta Neurol Belg, 2018. 118(3): p. 411-414.",
            "3. Jung, Y.J. et al. J Mov Disord, 2014. 7(1): p.19-21.",
        ]
    )

    assessment = assess_row(row, record, min_candidate_score=7)

    assert assessment is None


def test_build_snippet_uses_candidate_span_only() -> None:
    record = make_record(
        [
            "Previous abstract tail text",
            "C14",
            "Target Abstract Title",
            "Jane Doe, John Smith",
            "Background: target body",
            "Conclusion: target body",
            "C15",
            "Next Abstract Title",
        ]
    )
    lines = [
        line
        for page in record["pages"]
        for line in []
    ]
    from src.pipelines._proceedings_text import flatten_lines

    lines = flatten_lines(record)
    snippet = build_snippet(lines, 1, 6)

    assert "Previous abstract tail text" not in snippet
    assert "Next Abstract Title" not in snippet
    assert "C14" in snippet
    assert "Conclusion: target body" in snippet
