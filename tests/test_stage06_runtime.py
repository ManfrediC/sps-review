from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests
from openai import OpenAIError

from src.pipelines.stage06_counting import runtime


class TestStage06Runtime(unittest.TestCase):
    def test_resolve_openai_api_key_reads_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            env_file = Path(tmp_dir_text) / "openai_api_key.env"
            env_file.write_text("OPENAI_API_KEY=test-file-key\n", encoding="utf-8")

            resolved = runtime.resolve_openai_api_key(env_file=env_file)

        self.assertEqual(resolved, "test-file-key")

    def test_resolve_openai_api_key_ignores_shell_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            env_file = Path(tmp_dir_text) / "openai_api_key.env"
            env_file.write_text("OPENAI_API_KEY=test-file-key\n", encoding="utf-8")

            resolved = runtime.resolve_openai_api_key(
                env={"OPENAI_API_KEY": "shell-key"},
                env_file=env_file,
            )

        self.assertEqual(resolved, "test-file-key")

    def test_resolve_openai_api_key_raises_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            env_file = Path(tmp_dir_text) / "missing.env"
            with self.assertRaises(runtime.Stage06ConfigurationError):
                runtime.resolve_openai_api_key(env_file=env_file)

    def test_preflight_openai_uses_minimal_live_probe(self) -> None:
        fake_client = mock.Mock()
        with mock.patch.object(runtime, "OpenAI", return_value=fake_client):
            result = runtime.preflight_openai(model="gpt-5.4", api_key="test-key")

        fake_client.responses.create.assert_called_once()
        self.assertEqual(
            fake_client.responses.create.call_args.kwargs["max_output_tokens"],
            runtime.DEFAULT_OPENAI_PREFLIGHT_MAX_OUTPUT_TOKENS,
        )
        self.assertEqual(result.status, "available")
        self.assertEqual(result.model, "gpt-5.4")
        self.assertEqual(result.credential_source, "explicit_api_key")

    def test_preflight_openai_raises_dependency_error(self) -> None:
        fake_client = mock.Mock()
        fake_client.responses.create.side_effect = OpenAIError("network down")
        with mock.patch.object(runtime, "OpenAI", return_value=fake_client):
            with self.assertRaises(runtime.Stage06DependencyError):
                runtime.preflight_openai(model="gpt-5.4", api_key="test-key")

    def test_preflight_ollama_passes_when_model_is_available(self) -> None:
        with mock.patch.object(
            runtime,
            "_ollama_models_payload",
            return_value={"data": [{"id": "gemma4:e4b"}, {"id": "other"}]},
        ):
            result = runtime.preflight_ollama(model="gemma4:e4b", base_url="http://localhost:11434")

        self.assertEqual(result.status, "available")
        self.assertFalse(result.auto_started)
        self.assertEqual(result.available_models, ["gemma4:e4b", "other"])

    def test_preflight_ollama_autostarts_when_initial_probe_fails(self) -> None:
        with (
            mock.patch.object(
                runtime,
                "_ollama_models_payload",
                side_effect=[
                    requests.ConnectionError("down"),
                    {"data": [{"id": "gemma4:e4b"}]},
                ],
            ),
            mock.patch.object(runtime, "discover_ollama_executable", return_value=Path("C:/Ollama/ollama.exe")),
            mock.patch.object(runtime, "start_ollama_server") as mock_start,
            mock.patch.object(runtime.time, "sleep"),
        ):
            result = runtime.preflight_ollama(
                model="gemma4:e4b",
                base_url="http://localhost:11434",
                startup_timeout_seconds=1.0,
            )

        mock_start.assert_called_once()
        self.assertTrue(result.auto_started)
        self.assertEqual(result.executable_path, "C:\\Ollama\\ollama.exe")

    def test_preflight_ollama_raises_when_model_is_missing(self) -> None:
        with mock.patch.object(runtime, "_ollama_models_payload", return_value={"data": [{"id": "other"}]}):
            with self.assertRaises(runtime.Stage06DependencyError):
                runtime.preflight_ollama(model="gemma4:e4b", base_url="http://localhost:11434")

    def test_preflight_ollama_raises_when_autostart_never_recovers(self) -> None:
        with (
            mock.patch.object(
                runtime,
                "_ollama_models_payload",
                side_effect=requests.ConnectionError("still down"),
            ),
            mock.patch.object(runtime, "discover_ollama_executable", return_value=Path("C:/Ollama/ollama.exe")),
            mock.patch.object(runtime, "start_ollama_server"),
            mock.patch.object(runtime.time, "sleep"),
        ):
            with self.assertRaises(runtime.Stage06DependencyError):
                runtime.preflight_ollama(
                    model="gemma4:e4b",
                    base_url="http://localhost:11434",
                    startup_timeout_seconds=0.01,
                    startup_poll_seconds=0.0,
                )


if __name__ == "__main__":
    unittest.main()
