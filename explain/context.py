"""Facts about where the command runs, passed to the LLM and the log."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess


def git_branch(cwd: str) -> str | None:
    if not shutil.which("git"):
        return None
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def gather(cwd: str | None = None) -> dict:
    cwd = cwd or os.getcwd()
    try:
        listing = sorted(os.listdir(cwd))[:30]
    except OSError:
        listing = []
    return {
        "cwd": cwd,
        "os": platform.system(),
        "shell": os.path.basename(os.environ.get("SHELL", "")),
        "git_branch": git_branch(cwd),
        "files_here": listing,
    }
