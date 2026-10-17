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
Max_Len, Max_Steps, Max_Effefts = 160, 6, 5
Separators =  {"&&", "||", ";", "|", "&"}
Redirects = {">", ">>", "<", "2>", "&>"}

# -- Public API for other files to use

def merge_risk(a, b):
    """
    Purpose
    Paramater: String
    Return:
    """