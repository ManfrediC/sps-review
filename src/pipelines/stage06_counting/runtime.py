from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover - only used in incomplete environments.
    requests = None  # type: ignore[assignment]

try:
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        NotFoundError,
        OpenAI,
        OpenAIError,
        PermissionDeniedError,
        RateLimitError,
    )
except ModuleNotFoundError:  # pragma: no cover - only used in incomplete environments.
    OpenAI = None  # type: ignore[assignment]

    class OpenAIError(Exception):
        pass

    class APIConnectionError(OpenAIError):
        pass

    class APIStatusError(OpenAIError):
        pass

    class APITimeoutError(OpenAIError):
        pass

    class AuthenticationError(OpenAIError):
        pass

    class BadRequestError(OpenAIError):
        pass

    class NotFoundError(OpenAIError):
        pass

    class PermissionDeniedError(OpenAIError):
        pass

    class RateLimitError(OpenAIError):
        pass

from src.pipelines.stage06_counting.local_ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OPENAI_ENV_FILE = REPO_ROOT / "env" / "openai_api_key.env"
DEFAULT_OPENAI_PREFLIGHT_PROMPT = "Reply with OK."
DEFAULT_OPENAI_PREFLIGHT_MAX_OUTPUT_TOKENS = 16
DEFAULT_OLLAMA_STARTUP_TIMEOUT_SECONDS = 90.0
DEFAULT_OLLAMA_PROBE_TIMEOUT_SECONDS = 5.0
DEFAULT_OLLAMA_STARTUP_POLL_SECONDS = 1.0

OPENAI_DEPENDENCY_EXCEPTIONS = (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    PermissionDeniedError,
    NotFoundError,
    RateLimitError,
    BadRequestError,
    APIStatusError,
    OpenAIError,
)
REQUEST_DEPENDENCY_EXCEPTIONS = (
    requests.RequestException if requests is not None else OSError,
)


class Stage06DependencyError(RuntimeError):
    """Raised when stage-06 runtime dependencies are unavailable or unhealthy."""


class Stage06ConfigurationError(Stage06DependencyError):
    """Raised when stage-06 runtime configuration is invalid."""


@dataclass(frozen=True)
class OllamaPreflightResult:
    status: str
    base_url: str
    model: str
    auto_started: bool
    executable_path: str
    available_models: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OpenAIPreflightResult:
    status: str
    model: str
    credential_source: str
    env_file_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Stage06PreflightResult:
    ollama: OllamaPreflightResult
    openai: OpenAIPreflightResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "ollama": self.ollama.to_dict(),
            "openai": self.openai.to_dict(),
        }


def _strip_wrapping_quotes(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1].strip()
    return text


def _parse_openai_api_key_env_file(path: Path) -> str:
    if not path.exists():
        raise Stage06ConfigurationError(
            f"Stage 06 requires an OpenAI key at {path.as_posix()}, but that file does not exist."
        )
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("OPENAI_API_KEY="):
            continue
        _, value = line.split("=", 1)
        key = _strip_wrapping_quotes(value)
        if key:
            return key
        break
    raise Stage06ConfigurationError(
        f"Stage 06 requires OPENAI_API_KEY=... in {path.as_posix()}, but no usable value was found."
    )


def resolve_openai_api_key(
    api_key: str | None = None,
    *,
    env: dict[str, str] | None = None,
    env_file: Path = DEFAULT_OPENAI_ENV_FILE,
) -> str:
    del env
    explicit_key = str(api_key or "").strip()
    if explicit_key:
        return explicit_key
    return _parse_openai_api_key_env_file(env_file)


def is_openai_dependency_error(exc: BaseException) -> bool:
    return isinstance(exc, OPENAI_DEPENDENCY_EXCEPTIONS)


def discover_ollama_executable() -> Path:
    discovered = shutil.which("ollama")
    if discovered:
        return Path(discovered)

    candidates: list[Path] = []
    if os.name == "nt":
        local_app_data = Path(os.environ.get("LOCALAPPDATA") or "")
        program_files = Path(os.environ.get("ProgramFiles") or "")
        if local_app_data:
            candidates.append(local_app_data / "Programs" / "Ollama" / "ollama.exe")
        if program_files:
            candidates.append(program_files / "Ollama" / "ollama.exe")
    else:
        candidates.extend(
            [
                Path("/usr/local/bin/ollama"),
                Path("/opt/homebrew/bin/ollama"),
                Path("/usr/bin/ollama"),
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise Stage06ConfigurationError(
        "Stage 06 could not find the Ollama executable. Ensure Ollama is installed and available on PATH."
    )


def _ollama_models_payload(
    *,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    timeout_seconds: float = DEFAULT_OLLAMA_PROBE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if requests is None:
        raise Stage06ConfigurationError(
            "Stage 06 requires the 'requests' package before Ollama can be checked."
        )
    response = requests.get(f"{base_url.rstrip('/')}/v1/models", timeout=timeout_seconds)
    response.raise_for_status()
    return response.json()


def _available_ollama_models(payload: dict[str, Any]) -> list[str]:
    models = sorted({str(item.get("id") or "").strip() for item in payload.get("data") or [] if str(item.get("id") or "").strip()})
    return models


def start_ollama_server(executable_path: Path) -> None:
    creationflags = 0
    if os.name == "nt":
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    subprocess.Popen(
        [str(executable_path), "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        start_new_session=os.name != "nt",
    )


def preflight_ollama(
    *,
    model: str = DEFAULT_OLLAMA_MODEL,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    probe_timeout_seconds: float = DEFAULT_OLLAMA_PROBE_TIMEOUT_SECONDS,
    startup_timeout_seconds: float = DEFAULT_OLLAMA_STARTUP_TIMEOUT_SECONDS,
    startup_poll_seconds: float = DEFAULT_OLLAMA_STARTUP_POLL_SECONDS,
) -> OllamaPreflightResult:
    try:
        payload = _ollama_models_payload(base_url=base_url, timeout_seconds=probe_timeout_seconds)
    except Stage06ConfigurationError:
        raise
    except REQUEST_DEPENDENCY_EXCEPTIONS:
        executable_path = discover_ollama_executable()
        start_ollama_server(executable_path)
        deadline = time.monotonic() + startup_timeout_seconds
        last_error = ""
        while time.monotonic() < deadline:
            try:
                payload = _ollama_models_payload(base_url=base_url, timeout_seconds=probe_timeout_seconds)
                break
            except Stage06ConfigurationError:
                raise
            except REQUEST_DEPENDENCY_EXCEPTIONS as exc:
                last_error = f"{exc.__class__.__name__}: {exc}"
                time.sleep(startup_poll_seconds)
        else:
            raise Stage06DependencyError(
                "Stage 06 could not start Ollama successfully before the timeout elapsed. "
                f"Last probe error: {last_error or 'unreachable local server'}"
            )
        available_models = _available_ollama_models(payload)
        if model not in available_models:
            raise Stage06DependencyError(
                f"Ollama started at {base_url}, but required model '{model}' is unavailable."
            )
        return OllamaPreflightResult(
            status="available",
            base_url=base_url,
            model=model,
            auto_started=True,
            executable_path=str(executable_path),
            available_models=available_models,
        )

    available_models = _available_ollama_models(payload)
    if model not in available_models:
        raise Stage06DependencyError(f"Ollama is reachable at {base_url}, but required model '{model}' is unavailable.")
    return OllamaPreflightResult(
        status="available",
        base_url=base_url,
        model=model,
        auto_started=False,
        executable_path="",
        available_models=available_models,
    )


def preflight_openai(
    *,
    model: str,
    api_key: str | None = None,
    env_file: Path = DEFAULT_OPENAI_ENV_FILE,
) -> OpenAIPreflightResult:
    if OpenAI is None:
        raise Stage06ConfigurationError(
            "Stage 06 requires the 'openai' package before GPT adjudication can be checked."
        )
    resolved_key = resolve_openai_api_key(api_key, env_file=env_file)
    client = OpenAI(api_key=resolved_key)
    try:
        client.responses.create(
            model=model,
            store=False,
            input=[{"role": "user", "content": DEFAULT_OPENAI_PREFLIGHT_PROMPT}],
            max_output_tokens=DEFAULT_OPENAI_PREFLIGHT_MAX_OUTPUT_TOKENS,
        )
    except OPENAI_DEPENDENCY_EXCEPTIONS as exc:
        raise Stage06DependencyError(
            "Stage 06 OpenAI preflight failed before the run started: "
            f"{exc.__class__.__name__}: {exc}"
        ) from exc
    return OpenAIPreflightResult(
        status="available",
        model=model,
        credential_source="explicit_api_key" if api_key else "env/openai_api_key.env",
        env_file_path=str(env_file),
    )


def run_stage06_dependency_preflight(
    *,
    ollama_model: str = DEFAULT_OLLAMA_MODEL,
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL,
    gpt_model: str,
    api_key: str | None = None,
    env_file: Path = DEFAULT_OPENAI_ENV_FILE,
    require_openai: bool = True,
) -> Stage06PreflightResult:
    openai_result = (
        preflight_openai(model=gpt_model, api_key=api_key, env_file=env_file)
        if require_openai
        else OpenAIPreflightResult(
            status="skipped",
            model=gpt_model,
            credential_source="not_required_for_selected_papers",
            env_file_path=str(env_file),
        )
    )
    return Stage06PreflightResult(
        ollama=preflight_ollama(model=ollama_model, base_url=ollama_base_url),
        openai=openai_result,
    )
