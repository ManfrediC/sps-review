from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PIPELINE_DIR = Path(__file__).resolve().parents[1] / "src" / "pipelines"
READY_HELPER_PATH = PIPELINE_DIR / "_proceedings_ready.py"


def load_module(script_path: Path, module_name: str):
    if str(PIPELINE_DIR) not in sys.path:
        sys.path.insert(0, str(PIPELINE_DIR))
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class TestProceedingsReadyHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module(READY_HELPER_PATH, "_proceedings_ready")

    def test_looks_like_full_article_frontmatter_detects_web_article(self) -> None:
        record = {
            "paper_id": "1391",
            "source_filename": "1391.pdf",
            "n_pages": 2,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "Progressive encephalomyelitis with rigidity and myoclonus: A new",
                            "This information is current as of April 2, 2014",
                            "http://www.neurology.org/content/82/17/1521.full.html",
                            "located on the World Wide Web at:",
                            "The online version of this article, along with updated information and services, is",
                            "Neurology is the official journal of the American Academy of Neurology.",
                        ]
                    ),
                },
                {
                    "page_index": 1,
                    "text": "\n".join(
                        [
                            "Correspondence to",
                            "Dr. Balint:",
                            "ABSTRACT",
                            "Objective: To describe a novel PERM variant.",
                            "GLOSSARY",
                        ]
                    ),
                },
            ],
        }

        self.assertTrue(self.module.looks_like_full_article_frontmatter(record))

    def test_refine_ready_start_index_uses_numeric_code_before_title(self) -> None:
        record = {
            "paper_id": "12473",
            "source_filename": "12473.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 131,
                    "text": "\n".join(
                        [
                            "Other: Autoimmune movement disorders",
                            "307",
                            "Stiff-person syndrome - a 15-year review at a tertiary hospital",
                            "R. Rodrigues, L. Sousa, R. Samoes",
                            "Objective: Clinical characterization of stiff-person syndrome.",
                            "Conclusions: Prompt diagnosis allows treatment.",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        refined = self.module.refine_ready_start_index(
            lines,
            start_index=0,
            end_index_exclusive=6,
            matched_code="",
            matched_title="Stiff-person syndrome - a 15-year review at a tertiary hospital",
        )

        self.assertEqual(refined, 1)

    def test_refine_ready_start_index_matches_wrapped_title_cluster(self) -> None:
        record = {
            "paper_id": "8296",
            "source_filename": "8296.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "3. To evaluate the safety of ITB in the above clinical setting.",
                            "Conflict of Interest Disclosures and Acknowledgements:",
                            "I do not have any relevant financial relationships.",
                            "e173",
                            "ABSTRACT",
                            "www.neuromodulationjournal.com Neuromodulation 2013; 16: e157-e214",
                            "1640-1650",
                            "Neurorehabilitation/FES/",
                            "NEURAL PROSTHETICS",
                            "12 June-033. INTRATHECAL BACLOFEN",
                            "PUMP IMPLANTATION IN 2 CASES OF",
                            "STIFF-PERSON SYNDROME",
                            "Vadim Bikmullin, PhD, Anton Tolstyh, MD, Victor Rudenko, PhD",
                            "Introduction: Stiff-person or stiff-limb syndrome is a rare progressive disease.",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        refined = self.module.refine_ready_start_index(
            lines,
            start_index=0,
            end_index_exclusive=14,
            matched_code="",
            matched_title="12 June-033. INTRATHECAL BACLOFEN PUMP IMPLANTATION IN 2 CASES OF STIFF-PERSON SYNDROME",
        )

        self.assertEqual(refined, 9)

    def test_refine_ready_end_index_trims_footer_metadata_lines(self) -> None:
        record = {
            "paper_id": "12473",
            "source_filename": "12473.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "307",
                            "Stiff-person syndrome - a 15-year review at a tertiary hospital",
                            "R. Rodrigues, L. Sousa, R. Samoes",
                            "Objective: Clinical characterization of stiff-person syndrome.",
                            "Results: Four patients were identified over 15 years.",
                            "Conclusions: Prompt diagnosis allows treatment.",
                            "Movement Disorders, Vol. 36, Suppl. 1,",
                            "S132 ABSTRACTS",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        refined = self.module.refine_ready_end_index(
            lines,
            start_index=0,
            end_index_exclusive=8,
        )

        self.assertEqual(refined, 6)

    def test_build_span_record_groups_lines_by_page(self) -> None:
        record = {
            "paper_id": "2001",
            "source_filename": "2001.pdf",
            "source_sha256": "abc123",
            "n_pages": 2,
            "pages": [
                {"page_index": 0, "text": "Title\nObjective: First page text."},
                {"page_index": 1, "text": "Methods: Second page text.\nConclusion: End."},
            ],
        }

        payload = self.module.build_span_record(
            source_record=record,
            source_path=Path("data/extraction_json/text/2001.json"),
            start_index=0,
            end_index_exclusive=4,
            base_payload={"trim_status": "trimmed_auto"},
            ready_source_kind="llm_decision_rebuilt",
            ready_text_mode="trimmed_abstract",
            ready_source_detail="llm_decision_span",
            ready_reason="Rebuilt from the LLM-selected boundary.",
        )

        self.assertEqual(payload["paper_id"], "2001")
        self.assertEqual(payload["trim_status"], "trimmed_auto")
        self.assertEqual(payload["n_pages"], 2)
        self.assertEqual(len(payload["pages"]), 2)
        self.assertEqual(payload["proceedings_ready_source_kind"], "llm_decision_rebuilt")


if __name__ == "__main__":
    unittest.main()
