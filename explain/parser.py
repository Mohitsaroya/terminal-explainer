"""Break a command line into parts.

parse_command("rm -rf project/")
    -> {"program": "rm", "flags": ["-r", "-f"], "targets": ["project/"]}

A line with pipes or && / || / ; is split into segments, each parsed on its own.
Uses shlex for now; bashlex can replace it later without changing the contract.
"""

from __future__ import annotations

import shlex

OPERATORS = {"|", "||", "&&", ";", "&"}
WRAPPERS = {"sudo", "doas", "nohup", "time", "env", "command", "builtin"}


def split_segments(cmd: str) -> list[list[str]]:
    """Split a command line into token lists, one per simple command."""
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:  # unbalanced quotes: fall back to plain whitespace split
        tokens = cmd.split()

    segments: list[list[str]] = [[]]
    for tok in tokens:
        if tok in OPERATORS:
            if segments[-1]:
                segments.append([])
        else:
            segments[-1].append(tok)
    return [s for s in segments if s]


def _expand_flags(tok: str) -> list[str]:
    if tok.startswith("--") or len(tok) <= 2:
        return [tok]
    # -rf -> -r -f, but leave -9 style numeric flags and -n5 style values alone
    if tok[1:].isalpha():
        return [f"-{c}" for c in tok[1:]]
    return [tok]


def parse_tokens(tokens: list[str]) -> dict:
    sudo = False
    i = 0
    while i < len(tokens) and (tokens[i] in WRAPPERS or "=" in tokens[i] and not tokens[i].startswith("-")):
        if tokens[i] in ("sudo", "doas"):
            sudo = True
        i += 1
    program = tokens[i] if i < len(tokens) else ""
    flags: list[str] = []
    targets: list[str] = []
    end_of_flags = False
    for tok in tokens[i + 1:]:
        if tok == "--":
            end_of_flags = True
        elif not end_of_flags and tok.startswith("-") and tok != "-":
            flags.extend(_expand_flags(tok))
        else:
            targets.append(tok)
    return {"program": program, "flags": flags, "targets": targets, "sudo": sudo}


def parse_command(cmd: str) -> dict:
    """Parse the first simple command; the full list of segments is under "segments"."""
    segments = [parse_tokens(t) for t in split_segments(cmd)]
    first = segments[0] if segments else {"program": "", "flags": [], "targets": [], "sudo": False}
    return {**first, "segments": segments}
