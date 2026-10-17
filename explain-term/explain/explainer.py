"""Plain-English explanations without any AI.

    from explain import explainer
    out = explainer.explain("rm -rf ./*", cmds, ctx)

Where the words come from, in order:
  1. demo_cache.json   hand-written text for the rehearsed demo commands (exact match)
  2. glossary.yaml     a sentence per program, plus the meaning of each flag
  3. a generic line    "Runs the program X" for anything we never wrote up

File counts and sizes always come from context.py, never from the text files, so they are
always true for the folder you are in.

Returns a dict with: summary, steps, side_effects, reversible, risk, explainer, explain_ms.
Never raises: a broken glossary or a strange command still gives a usable answer.

Try it:  uv run python -m explain.explainer "rm -rf ./*"
"""
from __future__ import annotations

import json
import os
import shlex
import time
from pathlib import Path

import yaml

HERE = Path(__file__).parent
RISK_ORDER = {"safe": 0, "caution": 1, "danger": 2}
NO_UNDO = {"rm", "shred", "dd", "truncate", "unlink"}      # rm on macOS skips the Trash
MAX_LEN, MAX_STEPS, MAX_EFFECTS = 160, 6, 5
SEPARATORS = {"&&", "||", ";", "|", "&"}
REDIRECTS = {">", ">>", "<", "2>", "&>"}


# ---------------------------------------------------------------- public API
def merge_risk(a: str, b: str) -> str:
    """The higher of two risk levels. Unknown or missing values count as caution."""
    a = a if a in RISK_ORDER else "caution"
    b = b if b in RISK_ORDER else "caution"
    return a if RISK_ORDER[a] >= RISK_ORDER[b] else b


def explain(line: str, cmds=None, ctx=None) -> dict:
    t0 = time.monotonic()
    try:
        cmds = list(cmds) if cmds else quick_parse(line)
    except ValueError:                       # e.g. an unclosed quote
        cmds = []
    progs = [_prog(c) for c in cmds]

    try:
        out, source = _from_cache(line), "cache"
        if out is None:
            out, source = _from_glossary(line, cmds), "glossary"
    except Exception:  # noqa: BLE001 - the terminal must keep working
        out, source = {"summary": "Could not work out what this command does.", "risk": "caution"}, "glossary"

    effects = _impact_lines(progs, ctx) + _redirect_lines(line) + list(out.get("side_effects", []))
    reversible = bool(out.get("reversible", True)) and not any(p in NO_UNDO for p in progs)
    return {
        "summary": _cut(out.get("summary")) or "No explanation available.",
        "steps": [_cut(s) for s in out.get("steps", []) if str(s).strip()][:MAX_STEPS],
        "side_effects": [_cut(s) for s in effects if str(s).strip()][:MAX_EFFECTS],
        "reversible": reversible,
        "risk": out.get("risk") if out.get("risk") in RISK_ORDER else "caution",
        "explainer": source,
        "explain_ms": int((time.monotonic() - t0) * 1000),
    }


# ---------------------------------------------------------------- 1. demo cache
_cache: dict | None = None


def _norm(line: str) -> str:
    return " ".join(line.split())


def _from_cache(line: str):
    global _cache
    if _cache is None:
        path = Path(os.environ.get("EXPLAIN_CACHE", HERE / "demo_cache.json"))
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            _cache = {_norm(k): v for k, v in raw.get("commands", {}).items() if isinstance(v, dict)}
        except (OSError, ValueError):
            _cache = {}
    entry = _cache.get(_norm(line))
    return dict(entry) if entry and entry.get("summary") else None


# ---------------------------------------------------------------- 2. glossary
_glossary: dict | None = None


def glossary() -> dict:
    global _glossary
    if _glossary is None:
        path = Path(os.environ.get("EXPLAIN_GLOSSARY", HERE / "glossary.yaml"))
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            _glossary = {str(k): v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}
        except (OSError, yaml.YAMLError):
            _glossary = {}
    return _glossary


def _from_glossary(line: str, cmds: list) -> dict:
    parts, worst, undo = [], "safe", True
    for c in cmds:
        summary, flags, risk, can_undo = _describe(_prog(c), [str(a) for a in (_get(c, "args") or [])])
        if summary:
            parts.append((summary, flags))
            worst = merge_risk(worst, risk)
            undo = undo and can_undo
    if not parts:
        return {"summary": "Could not work out what this command does.", "risk": "caution"}
    if len(parts) == 1:
        summary, flags = parts[0]
        return {"summary": summary, "steps": flags, "risk": worst, "reversible": undo}
    steps = [s + (f" ({'; '.join(f)})" if f else "") for s, f in parts]
    joiner = "one after another" if "|" not in line else "passing output from one to the next"
    return {"summary": f"Runs {len(parts)} commands, {joiner}.", "steps": steps, "risk": worst,
            "reversible": undo}


def _describe(prog: str, args: list):
    """-> (summary, [flag meanings], risk, can_undo) for one simple command."""
    if not prog:
        return None, [], "safe", True
    if prog == "sudo" and args:                       # explain the command sudo runs
        inner, flags, risk, undo = _describe(os.path.basename(args[0]), args[1:])
        return f"As administrator: {inner[0].lower()}{inner[1:]}", flags, merge_risk("danger", risk), undo

    entry = glossary().get(prog) or {}
    words = [a for a in args if not a.startswith("-")]
    # programs like git and brew: "git push" uses the 'push' entry
    sub = (entry.get("subcommands") or {}).get(words[0]) if words else None
    if sub:
        words = words[1:]
    chosen = sub or entry

    shown = " ".join(words)
    shown = shown[:40] + "..." if len(shown) > 43 else shown
    template = chosen.get("summary") or f"Runs the program '{prog}'. We don't have an explanation for it yet."
    try:
        summary = template.format(args=shown or "the given items",
                                  where=f"in {shown}" if shown else "in this folder")
    except (KeyError, IndexError, ValueError):       # a typo like {arg} in the glossary
        summary = template
    risk = chosen.get("risk", "safe")
    can_undo = chosen.get("reversible", True) is not False
    return summary, _flag_meanings(args, entry.get("flags") or {}), risk, can_undo


def _flag_meanings(args: list, known: dict) -> list:
    """['-rf'] -> ['-r: also deletes folders...', '-f: never asks...'], in order, no repeats."""
    out, seen = [], set()
    for a in args:
        if not a.startswith("-") or a == "-":
            continue
        if a.startswith("--") or a in known:          # long flag, or listed as-is (e.g. -9)
            pieces = [a.split("=", 1)[0]]
        else:
            pieces = [f"-{ch}" for ch in a[1:]]       # -rf -> -r, -f
        for p in pieces:
            if p in seen:
                continue
            seen.add(p)
            meaning = known.get(p)
            out.append(f"{p}: {meaning}" if meaning else f"{p}: an option we don't have a description for")
    return out


# ---------------------------------------------------------------- side effects
VERBS = {"rm": "permanently deleted", "shred": "destroyed", "unlink": "deleted", "rmdir": "deleted",
         "mv": "moved", "cp": "copied", "chmod": "given new permissions", "chown": "given a new owner"}


def _impact_lines(progs: list, ctx) -> list:
    """Exact numbers from context.py. Empty if there is no context or nothing measurable."""
    if ctx is None:
        return []
    out = []
    try:
        files, dirs = ctx.total_files, ctx.total_dirs
        if files or dirs:
            from .context import human_bytes
            plus = "+" if ctx.truncated else ""
            verb = next((VERBS[p] for p in progs if p in VERBS), "affected")
            what = f"{files:,}{plus} file{'' if files == 1 and not plus else 's'}"
            if dirs:
                what += f" and {dirs:,}{plus} folder{'' if dirs == 1 and not plus else 's'}"
            out.append(f"{what} ({human_bytes(ctx.total_bytes)}{plus}) {verb}")
        keep = ("overwritten", "home folder", "root of the filesystem", "currently in",
                "matches nothing", "does not exist", "git repository")
        out += [f for f in ctx.facts() if any(k in f for k in keep)]
    except Exception:  # noqa: BLE001
        pass
    return out


def _redirect_lines(line: str) -> list:
    """`echo hi > notes.txt` replaces notes.txt; beginners rarely expect that."""
    try:
        toks = list(_lexer(line))
    except ValueError:
        return []
    out = []
    for i, t in enumerate(toks[:-1]):
        target = toks[i + 1]
        if t in (">", "&>"):
            out.append(f"{target} is replaced: anything already in it is lost")
        elif t == ">>":
            out.append(f"Output is added to the end of {target}")
    return out


# ---------------------------------------------------------------- helpers
def _cut(s) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= MAX_LEN else s[:MAX_LEN - 3].rstrip() + "..."


def _get(cmd, *names):
    for n in names:
        v = cmd.get(n) if isinstance(cmd, dict) else getattr(cmd, n, None)
        if v:
            return v
    return None


def _prog(cmd) -> str:
    return os.path.basename(str(_get(cmd, "program", "name", "cmd") or ""))


def _lexer(line: str):
    lex = shlex.shlex(line, posix=True, punctuation_chars=";&|<>")
    lex.whitespace_split = True
    return lex


def quick_parse(line: str) -> list:
    """Small stand-in for parser.py: splits on && || ; | and drops redirections.
    The real pipeline can pass parser.parse() output instead."""
    out, current, skip = [], [], False
    for tok in _lexer(line):
        if skip:
            skip = False
            continue
        if tok in SEPARATORS:
            if current:
                out.append({"program": current[0], "args": current[1:]})
            current = []
        elif tok in REDIRECTS:
            skip = True                                # the next word is the file name
        else:
            current.append(tok)
    if current:
        out.append({"program": current[0], "args": current[1:]})
    return out


if __name__ == "__main__":
    import sys
    from . import context
    line = " ".join(sys.argv[1:]) or "ls -la"
    cmds = quick_parse(line)
    print(json.dumps(explain(line, cmds, context.resolve(cmds)), indent=2, ensure_ascii=False))