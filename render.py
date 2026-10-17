from __future__ import annotations

# imports


import os 
import re 
import sys
import time

# importing rich 

from rich import Console, Group
from rich.live import Live 
from rich.panel import Panel 
from rich.table import Table
from rich.text import Text

print("[bold green]hello world[/bold green]")

styles = { 
    "safe": ("green", "SAFE"),
    "caution": ("yellow", "WARNING"),
    "danger": ("red",   )
}
hints = {
    "caution": "Enter = Run | Esc = cancel | e = edit",
    "danger": "Type the word below to run | Enter = cancel"
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

def build_panel(rec: dict) -> Panel: 
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
    body.append(Text(_clean(summary), style="bold") if summary else Text("Explaining..", style="dim italic))"))

    segsm = rec.get("segments") or []

    if len(segsm) > 1: 
        grid = Table.grid(padding=(0,1))
        for seg in segsm:
            c, lab = styles.get(seg.get("risk"), styles["caution"])
            grid.add_row(Text("- ", style=c), Text(lab, style=f"bold {c}")),
            Text(_clean(seg.get("command","")))
        body += [Text(""), Text("Step by step", style="dim")]

    steps = rec.get("steps") or []
    if steps:
        body.append(Text(""))
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
    if risk == "danger":
        hint = f"Type {_clean(rec.get('confirm_word') or 'yes')} to run | Enter = cancel"
    return Panel(Group(*body), title="explain", title_align="left", border_style=color, subtitle=hint, subtitle_align="left", padding=(1,2))
                               




