from __future__ import annotations

# imports


import os 
import re 
import sys
import time

# importing rich 

from rich.console import Console, Group
from rich.live import Live 
from rich.panel import Panel 
from rich.table import Table
from rich.text import Text



styles = { 
    "safe": ("green", "SAFE"),
    "caution": ("yellow", "WARNING"),
    "danger": ("red",   "DANGER")
}
hints = {
    "caution": "Run: type yes + Enter | Cancel: Esc | Edit: type e + Enter",
    "danger": "Run: type the word + Enter | Cancel: Esc | Edit: type e + Enter"
}

SAFE_ONE_LINER = True # if false = print nothing

console = Console(stderr=True)

# Safety Helpers
# Private variables and functions 

# -- String Cleanup 
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _clean(string) -> str: 
    """
    Purpose: this functions strips character from the input of the user
    Parameter: string
    Return: returns the stripped characters.
    """
    return _CONTROL.sub(" ", str(string))

# -- Building the panel --

def build_panel(rec: dict): 
    """
    purpose: This functions purposes is to build the panel, this panel involves the following features:
        1. Header
        2. Body
        3. Effects
        4. Colour labeling
    parameter: Uses a dictionary for the panel
    return:
    """
    if rec.get("risk") in styles:
        risk = rec.get("risk")
    else:
        risk = "caution"
    color, label = styles[risk]


    body = []

    head = Text()
    head.append(f" {label}", style=f"bold white on {color}")
    head.append("  $ ", style="dim")
    head.append(_clean(rec.get("command", "")), style="bold")
    body += [head, Text("")]

    summary = rec.get("summary")
    body.append(Text(_clean(summary), style="bold") if summary else Text("Explaining..", style="dim italic"))

    for msg in rec.get("rule_messages") or []:
        body.append(Text.assemble(("! ", "bold yellow"), _clean(msg)))

    segsm = rec.get("segments") or []

    if len(segsm) > 1: 
        grid = Table.grid(padding=(0,1))
        for seg in segsm:
            c, lab = styles.get(seg.get("risk"), styles["caution"])
            grid.add_row(Text("- ", style=c), Text(lab, style=f"bold {c}"),
                         Text(_clean(seg.get("command",""))))
        body += [Text(""), grid]

# displays the step by step of what the command does
    steps = rec.get("steps") or []
    if steps:
        body += [Text(""), Text("Step by step", style="dim")]
        for i, s in enumerate(steps, 1):
            body.append(Text.assemble((f"{i}. ", "dim"), _clean(s)))

    # Potential effects           
    effects = rec.get("side_effects") or []
    reversible = rec.get("reversible")

    if effects or reversible is not None: 
        body.append(Text(""))
    for e in effects: 
        body.append(Text.assemble(("- ", "dim"), _clean(e)))
    # this section determines whether or not the actions can be undo'd
    if reversible is False:
        body.append(Text("X cannot be undo'd, action is not reversible", style="bold red"))
    elif reversible is True:
        body.append(Text("! Reversible", style="green"))

    hint = hints.get(risk)
    word = _confirmation_word(rec)
    if risk in ("caution", "danger"):
        hint = f"Run: type {word} + Enter | Cancel: Esc | Edit: type e + Enter"
    return Panel(Group(*body), title="EXPLANATION", title_align="center", border_style=color, subtitle=hint, subtitle_align="center", padding=(1,2))

# -- Confirmation

def _read_confirmation_input(con: Console, prompt: Text):
    con.print(prompt, end="")
    if not sys.stdin.isatty():
        return None

    answer = bytearray()
    if os.name == "nt":
        import msvcrt

        while True:
            char = msvcrt.getwch()
            if char == "\x1b":
                con.print()
                return None
            if char in ("\r", "\n"):
                con.print()
                return answer.decode(errors="replace")
            if char in ("\x03", "\x04"):
                con.print()
                return None
            if char in ("\b", "\x7f"):
                if _erase_last_character(answer):
                    con.file.write("\b \b")
                    con.file.flush()
                continue
            encoded = char.encode()
            answer.extend(encoded)
            con.file.write(char)
            con.file.flush()

    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            char = os.read(fd, 1)
            if char == b"\x1b":
                con.print()
                return None
            if char in (b"\r", b"\n"):
                con.print()
                return answer.decode(errors="replace")
            if char in (b"\x03", b"\x04"):
                con.print()
                return None
            if char in (b"\x08", b"\x7f"):
                if _erase_last_character(answer):
                    con.file.write("\b \b")
                    con.file.flush()
                continue
            answer.extend(char)
            con.file.write(char.decode(errors="replace"))
            con.file.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _erase_last_character(answer: bytearray) -> bool:
    if not answer:
        return False
    char = answer.pop()
    if char & 0xC0 == 0x80:
        while answer and answer[-1] & 0xC0 == 0x80:
            answer.pop()
        if answer and answer[-1] & 0xC0 == 0xC0:
            answer.pop()
    return True


def _confirmation_word(rec: dict) -> str:
    if rec.get("risk") == "danger":
        return _clean(rec.get("confirm_word") or "yes")
    return "yes"


def confirm(rec: dict, con: Console = None):
    con = con or console
    risk = rec.get("risk")
    if risk == "safe":
        return "ran"
 
    word = _confirmation_word(rec)
    prompt = Text("Confirm: ")
    try:
        answer = _read_confirmation_input(con, prompt)
    except (EOFError, KeyboardInterrupt):
        return "cancelled"
    if answer is None:
        return "cancelled"
    answer = answer.strip().casefold()
    if answer in ("e", "edit"):
        return "edited"
    if answer == word.casefold():
        return "ran"
    return "cancelled"
 
 
def show(rec: dict, con: Console = None, *, panel_printed: bool = False):
    """Display the explanation, ask for confirmation, return the decision."""
    con = con or console
    risk = rec.get("risk")
 
    if risk == "safe":
        if SAFE_ONE_LINER and not panel_printed and rec.get("summary"):
            con.print(Text.assemble(("✓ ", "green"), (_clean(rec["summary"]), "dim")))
        rec["decision"], rec["response_ms"] = "ran", 0
        return "ran"
 
    if not panel_printed:
        con.print(build_panel(rec))
    t0 = time.monotonic()
    decision = confirm(rec, con)
    rec["decision"] = decision
    rec["response_ms"] = int((time.monotonic() - t0) * 1000)
    return decision
 
 
# ---------------------------------------------------------------- preview
DEMO = [
    {"command": "ls -la", "risk": "safe", "summary": "Lists files in this folder, including hidden ones."},
    {"command": "mv report.docx archive/", "risk": "caution",
     "summary": "Moves report.docx into the archive folder.",
     "steps": ["Finds report.docx in the current folder", "Moves it into archive/"],
     "side_effects": ["report.docx will no longer be in this folder"], "reversible": True,
     "rule_messages": ["mv can overwrite a file with the same name"]},
    {"command": "cd /tmp/old && rm -rf *", "risk": "danger", "confirm_word": "old",
     "summary": "Permanently deletes everything inside /tmp/old.",
     "rule_messages": ["rm -rf with a wildcard deletes recursively and skips the Trash"],
     "segments": [{"command": "cd /tmp/old", "risk": "safe"},
                  {"command": "rm -rf *", "risk": "danger"}],
     "steps": ["Moves into /tmp/old", "Expands * to 1,203 items", "Deletes each one, skipping the Trash"],
     "side_effects": ["1,150 files and 53 folders (4.2 GB) removed"], "reversible": False},
]
 
if __name__ == "__main__":
    for r in DEMO:
        if "--confirm" in sys.argv:
            console.print(f"[dim]decision: {show(dict(r))}[/dim]\n")
        else:
            console.print(build_panel(r))
            console.print()