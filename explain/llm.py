"""Plain-English explanations of commands and errors.

The backend is picked with EXPLAIN_LLM; only "fake" (canned answers) exists for now,
so everything else can be built and tested before the real model is chosen.

Rules from the design doc:
  * never auto-run a suggested fix; the caller asks first and runs it through check_danger
  * strip anything that looks like a password, token or API key before sending text out
"""

from __future__ import annotations

import os
import re

from explain.parser import parse_command

SECRET_PATTERNS = [
    re.compile(r"(?i)\b(password|passwd|pwd|token|secret|api[_-]?key)\s*[=:]\s*\S+"),
    re.compile(r"\b(sk|pk|ghp|gho|github_pat|xox[abp])[-_][A-Za-z0-9_-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{10,}"),
]

EXIT_CODES = {
    1: ("The command reported a general error.", "Read the error text above for the specific reason."),
    2: ("The command was used the wrong way.", "Check the flags and arguments with `man <command>`."),
    126: ("The file exists but can't be run.", "Make it executable with `chmod +x <file>`, or check permissions."),
    127: ("The shell couldn't find that command.", "Check the spelling, or install the program."),
}

FAKE_EXPLANATIONS = {
    "ls": "Lists the files and folders in the current folder.",
    "cd": "Moves you into another folder.",
    "pwd": "Prints the folder you are currently in.",
    "mkdir": "Creates a new folder.",
    "rm": "Deletes files. They do not go to the trash and cannot be recovered.",
    "mv": "Moves or renames files.",
    "cp": "Copies files.",
    "cat": "Prints a file's contents to the screen.",
    "find": "Searches for files by name, type or other properties.",
    "grep": "Searches for text inside files.",
    "git": "Runs a git version-control command.",
    "pip": "Installs or manages Python packages.",
    "python": "Runs a Python program.",
    "python3": "Runs a Python program.",
}


def redact(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def backend() -> str:
    return os.environ.get("EXPLAIN_LLM", "fake")


def explain_command(cmd: str, context: dict | None = None) -> str:
    if backend() != "fake":
        raise NotImplementedError(f"LLM backend {backend()!r} is not wired up yet")
    parts = []
    for seg in parse_command(cmd)["segments"]:
        base = FAKE_EXPLANATIONS.get(seg["program"], f"Runs the `{seg['program']}` program.")
        if seg["flags"]:
            base += f" Flags: {' '.join(seg['flags'])}."
        if seg["targets"]:
            base += f" Acts on: {' '.join(seg['targets'])}."
        parts.append(base)
    return " Then: ".join(parts) or "Does nothing (empty command)."


def explain_error(cmd: str, exit_code: int, error_text: str = "", context: dict | None = None) -> dict:
    """Return {"problem", "cause", "fix"}; the fix is a suggestion only, never run here."""
    error_text = redact(error_text)
    if backend() != "fake":
        raise NotImplementedError(f"LLM backend {backend()!r} is not wired up yet")
    problem, fix = EXIT_CODES.get(exit_code, (f"The command failed with exit code {exit_code}.", "Read the error text and try again."))
    lowered = error_text.lower()
    if "no such file or directory" in lowered:
        cause = "A file or folder named in the command doesn't exist here."
        fix = "Check the name with `ls`, or use the full path."
    elif "permission denied" in lowered:
        cause = "You don't have permission for that file or folder."
        fix = "Check ownership with `ls -l`; avoid sudo unless you know why it's needed."
    elif "modulenotfounderror" in lowered:
        module = re.search(r"No module named '([^']+)'", error_text)
        cause = "Python can't find a package the script imports."
        fix = f"pip install {module.group(1)}" if module else "pip install <package>"
    elif exit_code == 127:
        cause = f"`{parse_command(cmd)['program']}` isn't installed or is misspelled."
    else:
        cause = error_text.strip().splitlines()[-1] if error_text.strip() else "No error text was captured."
    return {"problem": problem, "cause": cause, "fix": fix}
