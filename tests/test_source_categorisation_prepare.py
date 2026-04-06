from __future__ import annotations

import unittest

from src.pipelines.source_categorisation.prepare import (
    PaperPayload,
    assemble_payload,
    format_payload_for_llm,
)


class TestSourceCategorisationPrepare(unittest.TestCase):
    def test_format_payload_drops_low_value_metadata_fields(self) -> None:
        payload = PaperPayload(
            paper_id="123",
            metadata={
                "title": "Example title",
                "abstract": "Example abstract.",
                "authors": "Example, A.; Example, B.",
                "journal": "Neurology",
                "published_year": "2024",
                "volume": "12",
                "issue": "SUPPL. 1",
                "pages": "S12-S13",
                "doi": "10.1000/example",
                "tags": "Treatment",
                "notes": "Internal note",
            },
            text_content="Body text.",
            text_source="full_text",
            proceedings_detected=True,
            trim_status="trimmed_auto",
            text_page_count=1,
        )

        rendered = format_payload_for_llm(payload)

        self.assertIn("- journal: Neurology", rendered)
        self.assertIn("- issue: SUPPL. 1", rendered)
        self.assertIn("- pages: S12-S13", rendered)
        self.assertNotIn("- authors:", rendered)
        self.assertNotIn("- published_year:", rendered)
        self.assertNotIn("- volume:", rendered)
        self.assertNotIn("- tags:", rendered)
        self.assertNotIn("- notes:", rendered)

    def test_format_payload_skips_duplicate_abstract(self) -> None:
        abstract = (
            "Introduction: Stiff person syndrome is rare. "
            "We describe a single patient who improved after treatment."
        )
        payload = PaperPayload(
            paper_id="124",
            metadata={
                "title": "Example title",
                "abstract": abstract,
                "journal": "Journal of Neurology",
                "issue": "SUPPL. 1",
                "pages": "S351",
            },
            text_content=(
                "Example title\n"
                "Introduction: Stiff person syndrome is rare.\n"
                "We describe a single patient who improved after treatment.\n"
                "Results: Improvement continued."
            ),
            text_source="trimmed",
            proceedings_detected=True,
            trim_status="trimmed_auto",
            text_page_count=1,
        )

        rendered = format_payload_for_llm(payload)

        self.assertNotIn("- abstract:", rendered)
        self.assertIn("## Extracted text", rendered)

    def test_assemble_payload_truncates_back_matter(self) -> None:
        reference_row = {
            "Title": "Example title",
            "Abstract": "",
            "Journal": "Neurology",
            "Issue": "1",
            "Pages": "1-2",
            "DOI": "",
        }

        for heading in ("REFERENCES", "Acknowledgments"):
            with self.subTest(heading=heading):
                text_record = {
                    "pages": [
                        {
                            "text": (
                                "Main results section.\n"
                                f"{heading}\n"
                                "1. Prior paper\n"
                                "2. Another paper"
                            )
                        }
                    ]
                }

                payload = assemble_payload(
                    paper_id="125",
                    reference_row=reference_row,
                    text_record=text_record,
                    preferred_record=None,
                    preferred_text_source="full_text",
                    trim_row={},
                )

                self.assertEqual(payload.text_content, "Main results section.")


if __name__ == "__main__":
    unittest.main()
