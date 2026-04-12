from __future__ import annotations

import os
import re
import tempfile
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pytest
import _pytest.pathlib as pytest_pathlib
import _pytest.tmpdir as pytest_tmpdir
from _pytest.warning_types import PytestWarning


WORKSPACE_TMP_DIRNAME = "pytest_workspace_tmp"
_WORKSPACE_SESSION_ROOT: Path | None = None


def _run_slug() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{os.getpid()}"


def _safe_name(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._")
    return cleaned or "tmp"


class WorkspaceTmpPathFactory:
    def __init__(self, base: Path) -> None:
        self._base = base
        self._counters: dict[str, int] = {}

    def getbasetemp(self) -> Path:
        return self._base

    def mktemp(self, basename: str, numbered: bool = True) -> Path:
        stem = _safe_name(basename)
        if not numbered:
            path = self._base / stem
            path.mkdir(parents=True, exist_ok=True)
            return path

        counter = self._counters.get(stem, 0)
        while True:
            path = self._base / f"{stem}_{counter:03d}"
            counter += 1
            if path.exists():
                continue
            path.mkdir(parents=True, exist_ok=False)
            self._counters[stem] = counter
            return path


def _workspace_session_root(rootpath: Path) -> Path:
    root = rootpath / WORKSPACE_TMP_DIRNAME / _run_slug()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_mkdtemp(suffix: str | None = None, prefix: str | None = None, dir: str | None = None) -> str:
    if dir is not None:
        base = Path(dir)
    elif _WORKSPACE_SESSION_ROOT is not None:
        base = _WORKSPACE_SESSION_ROOT / "tempfile"
    else:
        base = Path.cwd() / WORKSPACE_TMP_DIRNAME / "fallback_tempfile"

    base.mkdir(parents=True, exist_ok=True)
    stem = prefix if prefix is not None else "tmp"
    tail = suffix if suffix is not None else ""
    while True:
        candidate = base / f"{stem}{uuid.uuid4().hex}{tail}"
        try:
            candidate.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            continue
        return str(candidate)


def pytest_configure(config: pytest.Config) -> None:
    global _WORKSPACE_SESSION_ROOT
    _WORKSPACE_SESSION_ROOT = _workspace_session_root(Path(str(config.rootpath)))
    default_temp_root = _WORKSPACE_SESSION_ROOT / "tempfile_default"
    default_temp_root.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(default_temp_root)
    tempfile.mkdtemp = _safe_mkdtemp
    os.environ["TMP"] = str(default_temp_root)
    os.environ["TEMP"] = str(default_temp_root)

    original_cleanup = pytest_pathlib.cleanup_dead_symlinks

    def _safe_cleanup_dead_symlinks(root: Path) -> None:
        try:
            original_cleanup(root)
        except PermissionError as exc:
            warnings.warn(
                PytestWarning(f"Ignoring Windows PermissionError while finalising pytest temp dir {root}: {exc}"),
                stacklevel=1,
            )

    pytest_pathlib.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
    pytest_tmpdir.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks


@pytest.fixture(scope="session")
def tmp_path_factory(pytestconfig: pytest.Config) -> WorkspaceTmpPathFactory:
    root = (_WORKSPACE_SESSION_ROOT or _workspace_session_root(Path(str(pytestconfig.rootpath)))) / "tmp_path"
    root.mkdir(parents=True, exist_ok=True)
    return WorkspaceTmpPathFactory(root)


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest, tmp_path_factory: WorkspaceTmpPathFactory) -> Path:
    return tmp_path_factory.mktemp(request.node.name, numbered=True)
