from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProcessResult:
    exit_code: int
    stdout: str
    stderr: str


class ProcessRunner(Protocol):
    def run(
        self,
        command: Sequence[str],
        *,
        stdin: str,
        cwd: Path,
        timeout_seconds: float,
        environment: Mapping[str, str] | None = None,
    ) -> ProcessResult:
        """Run one bounded process and return captured output."""
        ...


class SubprocessRunner:
    """Thin subprocess boundary used by concrete Code Agent adapters."""

    def run(
        self,
        command: Sequence[str],
        *,
        stdin: str,
        cwd: Path,
        timeout_seconds: float,
        environment: Mapping[str, str] | None = None,
    ) -> ProcessResult:
        completed = subprocess.run(
            tuple(command),
            input=stdin,
            cwd=cwd,
            env=None if environment is None else dict(environment),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout_seconds,
        )
        return ProcessResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
