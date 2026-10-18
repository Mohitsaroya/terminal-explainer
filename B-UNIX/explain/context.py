"""context.py - real facts about what a command will touch.

Turns "rm -rf ./*" into "matches 1,203 items in /Users/you/Documents: 1,150 files,
53 folders, 4.2 GB". The rule engine, the explainer and the warning panel all use
these numbers, so this module must be fast and must never crash the terminal.

Public API
    resolve(cmds, cwd=None) -> Context
    Context.facts()          -> list[str]   plain-English lines (UI + explainer)
    Context.confirm_word()   -> str | None  what the user must type to confirm danger
    Context.to_dict()        -> dict        plain data (for debugging or saving)

`cmds` comes from explainer.quick_parse(): a list of {"program": ..., "args": [...]}
dicts (objects with `.program` and `.args` also work). Anything in args that starts
with "-" is treated as a flag and skipped.
"""
from __future__ import annotations

import glob
import os
import stat
import subprocess
import time
from dataclasses import asdict, dataclass, field

# Programs whose path arguments are things they change, move or remove.
# Anything else (ls, echo, cd, grep, ...) skips all filesystem work: the hook runs on
# every Enter, so unrelated commands must cost ~nothing.
PATH_PROGRAMS = {
    "rm", "rmdir", "unlink", "shred", "trash", "mv", "cp", "ln", "rsync",
    "chmod", "chown", "chgrp", "truncate", "touch", "mkdir", "dd",
    "tar", "zip", "unzip",
}
# For these, the LAST path argument is the destination, the rest are sources.
HAS_DEST = {"mv", "cp", "ln", "rsync"}
# sudo options that take a value: `sudo -u bob rm x` runs `rm x`.
SUDO_VALUE_OPTS = {"-u", "-g", "-C", "-D", "-h", "-p", "-R", "-T", "-U"}
# Programs that run another command given after them, and their options that take a
# value. `xargs -n 1 rm` runs rm, so rm is what the rules and the counts must look at.
WRAPPERS = {
    "sudo": SUDO_VALUE_OPTS,
    "doas": {"-u", "-C"},
    "env": {"-u", "-C", "-S"},
    "nice": {"-n"},
    "nohup": set(),
    "time": set(),
    "command": set(),
    "exec": {"-a"},
    "xargs": {"-n", "-I", "-P", "-L", "-d", "-s", "-E", "-a"},
}

MAX_ENTRIES = 20_000   # stop counting after this many files ("20,000+")
TIME_BUDGET = 0.5      # seconds for all filesystem walking in one resolve()


# ---------------------------------------------------------------- data model
@dataclass
class Target:
    pattern: str                       # exactly as the user typed it
    role: str = "target"               # "target" | "source" | "dest"
    cwd: str = ""                      # directory it was resolved against
    exists: bool = False
    n_matches: int = 0                 # how many paths the glob expanded to
    matches: list = field(default_factory=list)   # first few absolute paths
    files: int = 0
    dirs: int = 0
    bytes: int = 0
    truncated: bool = False            # hit MAX_ENTRIES or the time budget
    is_dir: bool = False               # single match that is a real directory
    is_cwd: bool = False
    is_home: bool = False
    is_root: bool = False


@dataclass
class Context:
    cwd: str
    targets: list = field(default_factory=list)
    in_git_repo: bool = False
    git_dirty_files: int = 0

    @property
    def total_files(self) -> int:
        return sum(t.files for t in self.targets if t.role != "dest")

    @property
    def total_dirs(self) -> int:
        return sum(t.dirs for t in self.targets if t.role != "dest")

    @property
    def total_bytes(self) -> int:
        return sum(t.bytes for t in self.targets if t.role != "dest")

    @property
    def truncated(self) -> bool:
        return any(t.truncated for t in self.targets)

    # -- what the user must type to confirm a dangerous command -------------
    def confirm_word(self):
        """Folder name if the command clearly acts on one folder, else None (use "yes").

        rm -rf ./*      in /Users/you/Documents -> "Documents"
        rm -rf ~/projects                       -> "projects"
        Typing the name forces the user to read what is about to be deleted.
        """
        real = [t for t in self.targets if t.role != "dest" and t.exists]
        if len(real) != 1:
            return None
        t = real[0]
        if t.n_matches == 1:
            name = os.path.basename(t.matches[0].rstrip("/"))
        else:
            name = os.path.basename(os.path.dirname(t.matches[0]))
        return name or None

    # -- plain-English facts -------------------------------------------------
    def facts(self) -> list:
        out = []
        for t in self.targets:
            has_glob = glob.has_magic(t.pattern)
            if t.role == "dest":
                if t.exists and not t.is_dir:
                    out.append(f"Destination {t.pattern} already exists "
                               f"({human_bytes(t.bytes)}) and will be overwritten.")
                elif t.exists:
                    out.append(f"Destination {t.pattern} is an existing folder; items go inside it.")
                continue
            if not t.exists:
                if has_glob:
                    out.append(f"{t.pattern} matches nothing in {t.cwd} "
                               "(zsh refuses to run a command whose glob matches nothing).")
                else:
                    out.append(f"{t.pattern} does not exist in {t.cwd}.")
                continue
            plus = "+" if t.truncated else ""
            parts = [_plural(t.files, "file", plus)]
            if t.dirs:
                parts.append(_plural(t.dirs, "folder", plus))
            parts.append(human_bytes(t.bytes) + plus)
            what = f"{t.pattern} -> " if has_glob else f"{t.pattern}: "
            if has_glob:
                what += f"{_plural(t.n_matches, 'match', '')} in {t.cwd}: "
            out.append(what + ", ".join(parts) + ".")
            if t.is_root:
                out.append("This is the root of the filesystem.")
            elif t.is_home:
                out.append("This is your home folder.")
            elif t.is_cwd:
                out.append("This is the folder you are currently in.")
        if self.in_git_repo and any(t.exists for t in self.targets):
            if self.git_dirty_files:
                out.append(f"Inside a git repository with {_plural(self.git_dirty_files, 'uncommitted change', '')}.")
            else:
                out.append("Inside a git repository with no uncommitted changes.")
        return out

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(total_files=self.total_files, total_dirs=self.total_dirs,
                 total_bytes=self.total_bytes, truncated=self.truncated,
                 confirm_word=self.confirm_word(), facts=self.facts())
        return d


# ---------------------------------------------------------------- public entry
def resolve(cmds, cwd=None, *, budget: float = TIME_BUDGET) -> Context:
    """Look at the real filesystem and describe what `cmds` would touch.

    `cmds` is the list from parser.parse(). Never raises: on any unexpected problem it
    returns whatever it managed to gather (possibly an empty Context).
    """
    cur = os.path.abspath(cwd or os.getcwd())
    ctx = Context(cwd=cur)
    try:
        _resolve_into(ctx, cmds, cur, budget)
    except Exception:  # noqa: BLE001 - the terminal must keep working
        pass
    return ctx


def _resolve_into(ctx: Context, cmds, cur: str, budget: float) -> None:
    home = os.path.expanduser("~")
    allowance = _Budget(budget)
    for cmd in cmds:
        prog = os.path.basename(str(_get(cmd, "program", "name", "cmd") or ""))
        args = [a for a in (_get(cmd, "args") or []) if isinstance(a, str)]
        prog, args = strip_wrappers(prog, args)

        if prog == "cd":
            # `cd /tmp && rm -rf *` deletes /tmp's contents, not the current folder's.
            # The hook only sees the raw line, so follow cd ourselves.
            dest = [a for a in args if a == "-" or not a.startswith("-")]
            if not dest:
                cur = home
            elif dest[0] != "-":
                p = os.path.expandvars(os.path.expanduser(dest[0]))
                cur = os.path.normpath(p if os.path.isabs(p) else os.path.join(cur, p))
            continue

        if prog not in PATH_PROGRAMS:
            continue

        paths = []
        for a in args:
            if prog == "dd":
                if a.startswith("of="):
                    paths.append(a[3:])
            elif a != "--" and not a.startswith("-"):
                paths.append(a)

        for i, pat in enumerate(paths):
            role = "target"
            if prog in HAS_DEST and len(paths) >= 2:
                role = "dest" if i == len(paths) - 1 else "source"
            ctx.targets.append(_build_target(pat, role, cur, home, allowance))

    first = next((t for t in ctx.targets if t.exists), None)
    if first is not None:
        # Ask git about the folder being changed, not the folder we are in:
        # `rm -rf ~/other-project` is about other-project's repository.
        where = first.matches[0] if first.is_dir else os.path.dirname(first.matches[0])
        ctx.in_git_repo, ctx.git_dirty_files = _git_status(where)


# ---------------------------------------------------------------- helpers
def unwrap_once(prog: str, args: list):
    """("sudo", ["-u", "bob", "rm", "x"]) -> ("rm", ["x"]). Peels off one wrapper only.

    Anything that isn't a wrapper, or a wrapper with no command after it
    (`sudo -i`, bare `env`, `command -v rm`), is returned as is.
    """
    value_opts = WRAPPERS.get(prog)
    if value_opts is None:
        return prog, args
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            i += 1
            break
        if prog == "env" and "=" in a and not a.startswith("-"):
            i += 1                      # env FOO=1 rm x
        elif a.startswith("-"):
            if prog == "command" and a in ("-v", "-V"):
                return prog, args       # only looks the name up, runs nothing
            i += 2 if a in value_opts else 1
        else:
            break
    if i >= len(args):
        return prog, args
    return os.path.basename(args[i]), args[i + 1:]


def strip_wrappers(prog: str, args: list):
    """Peel off every wrapper: ("env", ["sudo", "rm", "x"]) -> ("rm", ["x"])."""
    while True:
        inner = unwrap_once(prog, args)
        if inner == (prog, args):
            return prog, args
        prog, args = inner


def _get(cmd, *names):
    for n in names:
        v = cmd.get(n) if isinstance(cmd, dict) else getattr(cmd, n, None)
        if v:
            return v
    return None


class _Budget:
    """One shared allowance (files counted + seconds) for the whole command line."""

    def __init__(self, seconds: float):
        self.deadline = time.monotonic() + seconds
        self.files = 0

    def spent(self) -> bool:
        return self.files >= MAX_ENTRIES or time.monotonic() > self.deadline


def _build_target(pattern: str, role: str, base: str, home: str, budget: _Budget) -> Target:
    t = Target(pattern=pattern, role=role, cwd=base)
    p = os.path.expandvars(os.path.expanduser(pattern))
    if not os.path.isabs(p):
        p = os.path.join(base, p)
    if glob.has_magic(p):
        # Python's glob skips dotfiles for "*", like zsh. Same answer as the real shell.
        found = sorted({os.path.normpath(m) for m in glob.glob(p)})
    else:
        n = os.path.normpath(p)
        found = [n] if os.path.lexists(n) else []

    t.exists = bool(found)
    t.n_matches = len(found)
    t.matches = found[:5]
    t.is_cwd = base in found
    t.is_home = home in found
    t.is_root = "/" in found
    if len(found) == 1:
        t.is_dir = os.path.isdir(found[0]) and not os.path.islink(found[0])

    for m in found:
        if role == "dest":
            try:
                t.bytes += os.lstat(m).st_size
            except OSError:
                pass
            continue
        f, d, b, trunc = _measure(m, budget)
        t.files += f
        t.dirs += d
        t.bytes += b
        if trunc:
            t.truncated = True
            break
    return t


def _measure(path: str, budget: _Budget):
    """(files, dirs, bytes, truncated) for a file or a whole directory tree.

    Never follows symlinks, so a link to / cannot send it walking the whole disk.
    """
    try:
        st = os.lstat(path)
    except OSError:
        return 0, 0, 0, False
    if not stat.S_ISDIR(st.st_mode):
        budget.files += 1
        return 1, 0, st.st_size, budget.spent()
    files, dirs, size = 0, 1, 0
    for root, dnames, fnames in os.walk(path, followlinks=False):
        dirs += len(dnames)
        for name in fnames:
            files += 1
            budget.files += 1
            try:
                size += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
            if budget.spent():
                return files, dirs, size, True
    return files, dirs, size, False


def _git_status(directory: str):
    try:
        r = subprocess.run(["git", "-C", directory, "status", "--porcelain"],
                           capture_output=True, text=True, timeout=1.0)
    except (OSError, subprocess.TimeoutExpired):
        return False, 0
    if r.returncode != 0:
        return False, 0
    return True, sum(1 for line in r.stdout.splitlines() if line.strip())


def human_bytes(n: int) -> str:
    """Base-1000 sizes, matching what macOS Finder shows."""
    x = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if x < 1000 or unit == "TB":
            return f"{int(x)} B" if unit == "B" else f"{x:.1f} {unit}"
        x /= 1000
    return f"{n} B"


def _plural(n: int, word: str, plus: str) -> str:
    return f"{n:,}{plus} {word}{'' if n == 1 and not plus else 's'}"