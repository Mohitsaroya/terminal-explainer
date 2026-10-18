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

Try it (from the B-UNIX/ folder):  uv run python -m explain.explainer "rm -rf ./*"
"""
from __future__ import annotations

import json
import os
import re
import shlex
import time
from pathlib import Path

import yaml

from .context import human_bytes, strip_wrappers, unwrap_once

HERE = Path(__file__).parent
RISK_ORDER = {"safe": 0, "caution": 1, "danger": 2}
NO_UNDO = {"rm", "shred", "dd", "truncate", "unlink"}      # rm on macOS skips the Trash
MAX_LEN, MAX_STEPS, MAX_EFFECTS = 160, 6, 5
# Characters that end one command and start the next: && || ; | & |& and newlines.
# ( and ) are here too, so `(cd /tmp && rm -rf *)` is read as cd, then rm.
SEPARATOR_CHARS = set(";&|()\n")
# shlex splits "2>&1" into "2", ">&", "1", so the fd number is dropped in quick_parse.
REDIRECTS = {">", ">>", "<", "&>", "&>>", ">&", "<&", ">|", "<<", "<<<"}
# Redirect targets that are not real files, so nothing is "replaced".
NOT_FILES = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty"}
# Shell words that are syntax, not programs: in `for f in *; do rm $f; done` the program is rm.
SHELL_KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "!", "{", "}",
                  "done", "fi", "esac", "time"}
# Loop and case headers (`for f in *`) don't run anything themselves, so they are dropped.
SKIP_HEADERS = {"for", "select", "case", "function"}
# `FOO=1 rm x` sets FOO for rm; the program is still rm.
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


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
    progs = [strip_wrappers(_prog(c), _args(c))[0] for c in cmds]

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
            if isinstance(data, dict) and isinstance(data.get("programs"), dict):
                data = data["programs"]      # glossary.yaml keeps every entry under `programs:`
            _glossary = {str(k): v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}
        except (OSError, yaml.YAMLError):
            _glossary = {}
    return _glossary


def _from_glossary(line: str, cmds: list) -> dict:
    parts, worst, undo = [], "safe", True
    for c in cmds:
        summary, flags, risk, can_undo = _describe(_prog(c), _args(c))
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
    # sudo, env, xargs, time, ... run another command: explain that one instead.
    # One layer at a time, so `env sudo rm x` still says "As administrator".
    inner_prog, inner_args = unwrap_once(prog, args)
    if (inner_prog, inner_args) != (prog, args):
        inner, flags, risk, undo = _describe(inner_prog, inner_args)
        if prog == "sudo" and not inner.startswith("As administrator"):
            inner = f"As administrator: {inner[0].lower()}{inner[1:]}"
        if prog == "sudo":
            return inner, flags, merge_risk("danger", risk), undo
        return inner, flags, risk, undo

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
        line, subs = _pull_substitutions(line)
        toks = [_restore(t, subs)[0] for t in _lexer(line)]
    except ValueError:
        return []
    out = []
    for i, t in enumerate(toks[:-1]):
        target = toks[i + 1]
        if target in NOT_FILES or target.isdigit():   # 2>/dev/null, >&2: no file is touched
            continue
        if t in (">", "&>", ">|"):
            out.append(f"{target} is replaced: anything already in it is lost")
        elif t in (">>", "&>>"):
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


def _args(cmd) -> list:
    return [str(a) for a in (_get(cmd, "args") or [])]


def _prog(cmd) -> str:
    return os.path.basename(str(_get(cmd, "program", "name", "cmd") or ""))


def _lexer(line: str):
    """Shell-like word splitter. Raises ValueError on an unclosed quote."""
    lex = shlex.shlex(line, posix=True, punctuation_chars=";&|<>()\n")
    lex.whitespace_split = True
    lex.whitespace = " \t\r"      # newlines separate commands, so they are punctuation, not spaces
    lex.commenters = ""            # zsh treats # as text by default (`rm a#b` deletes "a#b")
    return lex


def _is_separator(tok: str) -> bool:
    """True for &&, ||, ;, |, &, |&, newlines, ( and ), and runs of them like ";\n"."""
    return bool(tok) and all(ch in SEPARATOR_CHARS for ch in tok)


# Placeholders for command substitutions while the outer line is split.
# \x00 can't be typed at a prompt, so it can never clash with a real word.
_MARK = "\x00{}\x00"
_MARK_RE = re.compile("\x00(\\d+)\x00")


def _closing(line: str, i: int, close: str) -> int:
    """Index of the `close` character that ends a substitution opened just before i.

    Skips quoted text and nested ( ). Returns len(line) if it is never closed.
    """
    depth, quote = 0, None
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\" and quote == '"':
                i += 1
            elif ch == quote:
                quote = None
        elif ch == "\\":
            i += 1
        elif ch in "'\"":
            quote = ch
        elif (close, ch) in ((")", "("), ("}", "{")):
            depth += 1
        elif ch == close:
            if depth == 0:
                return i
            depth -= 1
        i += 1
    return len(line)


def _pull_substitutions(line: str):
    """Swap $(...), `...`, <(...) and >(...) for placeholders.

    These run a command of their own, even inside double quotes:
    `ls "$(rm -rf ~)"` deletes your home folder. Text in single quotes and
    escaped \\$( are left alone, because the shell doesn't run them either.
    Returns (line with placeholders, [(shown text, inner command line or None)]).
    """
    out, subs, i, quote = [], [], 0, None
    while i < len(line):
        ch = line[i]
        if ch == "\\" and quote != "'":            # \$( is literal text
            out.append(line[i:i + 2])
            i += 2
            continue
        if ch == "'" and quote != '"':
            quote = None if quote == "'" else "'"
        elif ch == '"' and quote != "'":
            quote = None if quote == '"' else '"'
        elif quote != "'":
            opener = None
            brace_end = _closing(line, i + 2, "}") if line.startswith("${", i) else -1
            if brace_end >= 0 and not any(m in line[i:brace_end] for m in ("$(", "`")):
                # ${HOME} or zsh's ${(U)name}: one word, and nothing runs. If it holds a
                # $(...) we fall through so that substitution is still found.
                opener, close, shown, runs = "${", "}", line[i:brace_end + 1], False
            elif line.startswith("$((", i):
                opener, close, shown, runs = "$((", ")", "$((...))", False   # arithmetic, not a command
            elif line.startswith("$(", i):
                opener, close, shown, runs = "$(", ")", "$(...)", True
            elif ch == "`":
                opener, close, shown, runs = "`", "`", "`...`", True
            elif line.startswith(("<(", ">("), i) and quote is None:
                opener, close, shown, runs = line[i:i + 2], ")", line[i] + "(...)", True
            if opener:
                start = i + len(opener)
                end = _closing(line, start, close)
                if opener == "$((":                  # skip the second ) of $(( ... ))
                    end = _closing(line, end + 1, ")") if end < len(line) else end
                subs.append((shown, line[start:end] if runs else None))
                mark = _MARK.format(len(subs) - 1)
                # outside quotes, quote the placeholder so ( and ) in it stay one word
                out.append(mark if quote else f"'{mark}'")
                i = end + 1
                continue
        out.append(ch)
        i += 1
    return "".join(out), subs


def _restore(tok: str, subs: list):
    """Put the shown text back into a word; return (word, commands run by its substitutions)."""
    found = []

    def put_back(m):
        shown, inner = subs[int(m.group(1))]
        if inner:
            for cmd in quick_parse(inner):
                cmd["in_substitution"] = True
                found.append(cmd)
        return shown

    return _MARK_RE.sub(put_back, tok), found


def _simple_command(words: list):
    """{"program", "args"} for one simple command, or None if nothing runs."""
    while words and (words[0] in SHELL_KEYWORDS or ASSIGNMENT.match(words[0])):
        words = words[1:]
    if not words or words[0] in SKIP_HEADERS:
        return None
    return {"program": words[0], "args": words[1:]}


def quick_parse(line: str) -> list:
    """Split a command line into simple commands: [{"program": "rm", "args": ["-rf", "x"]}, ...].

    Splits on && || ; | & |& ( ) and newlines, drops redirections and their file
    names, skips shell keywords (do, then, ...) and VAR=value prefixes, and also
    returns the commands inside $(...) and `...`. Those are marked
    "in_substitution": True and come just before the command that contains them,
    because the shell runs them first. Raises ValueError on an unclosed quote.
    """
    line, subs = _pull_substitutions(line.replace("\\\n", ""))   # backslash-newline joins lines
    out, current, inner, skip = [], [], [], False

    def finish():
        out.extend(inner)
        cmd = _simple_command(current)
        if cmd:
            out.append(cmd)
        current.clear()
        inner.clear()

    for tok in _lexer(line):
        tok, found = _restore(tok, subs)
        inner.extend(found)                        # even `> $(rm x)` runs rm
        if skip:
            skip = False
            continue
        if _is_separator(tok):
            finish()
        elif tok in REDIRECTS:
            if len(current) > 1 and current[-1].isdigit():
                current.pop()                          # the 2 in 2>errors.txt
            skip = True                                # the next word is the file name
        else:
            current.append(tok)
    finish()
    return out


if __name__ == "__main__":
    import sys
    from . import context
    line = " ".join(sys.argv[1:]) or "ls -la"
    cmds = quick_parse(line)
    print(json.dumps(explain(line, cmds, context.resolve(cmds)), indent=2, ensure_ascii=False))