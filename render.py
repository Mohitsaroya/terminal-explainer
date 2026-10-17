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

    summary = rec.get("summary"_)





