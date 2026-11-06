from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


class SandboxWorkspace:
    """Disposable repository copy used for all mutation and test execution."""

    def __init__(self, source: Path) -> None:
        self.source = source.resolve(strict=True)
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self.root: Path | None = None

    def __enter__(self) -> Path:
        self._temporary = tempfile.TemporaryDirectory(prefix="repopilot-sandbox-")
        self.root = Path(self._temporary.name) / "repo"
        shutil.copytree(
            self.source,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "venv"),
        )
        return self.root

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()
