from __future__ import anotations

import json 
import os
import shlex
import time

from pathlib import Path
import yaml

# Variables here are meant to handle piping, sepearators, commands that
# cannot be undo'd or redirects. 
# it also handles the risk order.

Here = Path(__file__).parent
Risk_Order = {"safe": 0, "caution": 1, "danger": 2}
Cant_Undo = {"rm", "shred", "dd", "truncate", "unlink"}
Max_Len, Max_Steps, Max_Effects = 160, 6, 5
Separators =  {"&&", "||", ";", "|", "&"}
Redirects = {">", ">>", "<", "2>", "&>"}

# -- Helper function(s)

def _cut(string):
    """
    Purpose:
    Parameter
    """


# -- Public API for other files to use

def merge_risk(a, b):
    """
    Purpose: this functions purpose is to merge rsisk levels.
    Paramater: String
    Return: risk value
    """
    if a not in Risk_Order:
        a = "caution"
    if b not in Risk_Order:
        b = "caution"
    return a if Risk_Order[a] >= Risk_Order[b] else b

def explain(line, cmds=None, ctx=None):
    """
    Purpose: this functions purpose is to explain what a command does. 
    Parameter: String, dictionary
    Return: it returns a block of text that describes
    the summary, the steps, side effects, and other options with the commands.
    """
    t0 = time.monotic()
    try: cmds = list(cmds) if cmds else quick_parse(line)

    except ValueError:
        cmds = []
    