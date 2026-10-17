"""Print explanations and warnings. Uses rich when installed, plain text otherwise."""

from __future__ import annotations

import sys

from explain.rules import MAX_FILES

try:
    from rich.console import Console
    from rich.panel import Panel
except ImportError:  # rich is optional
    Console = None

COLORS = {"safe": "green", "caution": "yellow", "dangerous": "red"}
LABELS = {"safe": "Safe", "caution": "Caution", "dangerous": "DANGEROUS"}
SHOWN_FILES = 10


def _out():
    # Write to the terminal, not stdout, so the hook can still pipe stdout around.
    try:
        return open("/dev/tty", "w")
    except OSError:
        return sys.stderr


def format_check(cmd: str, explanation: str, danger: dict) -> str:
    lines = [f"$ {cmd}", "", explanation]
    if danger["level"] != "safe":
        lines += ["", f"{LABELS[danger['level']]}: {danger['reason']}"]
    files = danger.get("files") or []
    if files:
        count = f"{MAX_FILES}+" if len(files) >= MAX_FILES else str(len(files))
        lines += ["", f"This would affect {count} file(s):"]
        lines += [f"  {f}" for f in files[:SHOWN_FILES]]
        if len(files) > SHOWN_FILES:
            lines.append(f"  ... and {len(files) - SHOWN_FILES} more")
    return "\n".join(lines)


def format_error(result: dict) -> str:
    return "\n".join([
        f"What went wrong: {result['problem']}",
        f"Why: {result['cause']}",
        f"Try: {result['fix']}",
    ])


def show(text: str, level: str = "safe", title: str = "explain") -> None:
    out = _out()
    if Console is not None:
        Console(file=out).print(Panel(text, title=title, border_style=COLORS.get(level, "blue")))
    else:
        bar = "=" * 60
        print(f"{bar}\n[{title}]\n{text}\n{bar}", file=out)
    out.flush()


def ask(question: str, default: bool = False) -> bool:
    """Ask y/n on the terminal; anything but y/yes counts as no unless default is True."""
    out = _out()
    suffix = " [Y/n] " if default else " [y/N] "
    print(question + suffix, end="", file=out, flush=True)
    try:
        with open("/dev/tty") as tty:
            answer = tty.readline().strip().lower()
    except OSError:
        answer = input().strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")
