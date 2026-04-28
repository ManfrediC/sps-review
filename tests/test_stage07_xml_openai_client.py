from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINES_DIR = REPO_ROOT / "src" / "pipelines"
if str(PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINES_DIR))

from stage07_XML import core, openai_client  # noqa: E402


class FakeResponse:
    def __init__(
        self,
        *,
        output_text: str = '{"targets":[],"segments":[]}',
        status: str = "completed",
        incomplete_details: dict[str, str] | None = None,
    ) -> None:
        self.id = "resp_test"
        self.model = "gpt-test"
        self.output_text = output_text
        self.status = status
        self.incomplete_details = incomplete_details
        self.usage = {"input_tokens": 10, "output_tokens": 5}

    def model_dump_json(self, indent: int = 2) -> str:
        return "{}"


class FakeResponses:
    def create(self, **kwargs: object) -> FakeResponse:
        FakeOpenAI.last_create_kwargs = kwargs
        return FakeOpenAI.response


class FakeOpenAI:
    response = FakeResponse()
    last_create_kwargs: dict[str, object] | None = None

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.responses = FakeResponses()


class TestStage07OpenAIClient(unittest.TestCase):
    def setUp(self) -> None:
        self.original_openai = openai_client.OpenAI
        openai_client.OpenAI = FakeOpenAI
        FakeOpenAI.response = FakeResponse()
        FakeOpenAI.last_create_kwargs = None

    def tearDown(self) -> None:
        openai_client.OpenAI = self.original_openai

    def prepared_source(self) -> core.PreparedSource:
        return core.PreparedSource(
            paper_id="9001",
            source_text="Case text.",
            source_sha256="sha",
            source_text_json_path="text/9001.json",
            source_filename="9001.pdf",
            source_record_sha256="record_sha",
            blocks=[
                core.SourceBlock(
                    block_id="b0001",
                    text="Case text.",
                    source_start=0,
                    source_end=10,
                    page_index=0,
                )
            ],
        )

    def test_openai_call_uses_strict_schema_and_configurable_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = openai_client.annotate_with_openai(
                prepared_source=self.prepared_source(),
                targets=[core.Target("p1", "patient", "Patient 1", "test")],
                model="gpt-test",
                api_key="test-key",
                trace_dir=Path(tmp_dir),
                max_output_tokens=26000,
                reasoning_effort="high",
                strict_json_schema=True,
            )

            self.assertEqual(result, {"targets": [], "segments": []})
            self.assertIn("targets", openai_client.STAGE07_RESPONSE_SCHEMA["required"])
            request = FakeOpenAI.last_create_kwargs or {}
            self.assertEqual(request["reasoning"], {"effort": "high"})
            self.assertEqual(request["max_output_tokens"], 26000)
            text_config = request["text"]  # type: ignore[index]
            self.assertTrue(text_config["format"]["strict"])
            self.assertTrue((Path(tmp_dir) / "9001.response.meta.json").exists())

    def test_incomplete_openai_response_raises_before_parsing(self) -> None:
        FakeOpenAI.response = FakeResponse(
            output_text='{"targets":[],"segments":[]}',
            status="incomplete",
            incomplete_details={"reason": "max_output_tokens"},
        )

        with self.assertRaisesRegex(RuntimeError, "max_output_tokens"):
            openai_client.annotate_with_openai(
                prepared_source=self.prepared_source(),
                targets=[core.Target("p1", "patient", "Patient 1", "test")],
                model="gpt-test",
                api_key="test-key",
            )


if __name__ == "__main__":
    unittest.main()
