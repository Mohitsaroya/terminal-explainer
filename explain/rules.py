"""Decide whether a command is safe, worth a warning, or dangerous.

check_danger("rm -rf project/")
    -> {"level": "dangerous", "reason": "...", "files": ["project/a.txt", ...]}
"""

from __future__ import annotations

import glob
import os
import re
from functools import lru_cache
from pathlib import Path

import yaml

from explain.parser import parse_command

LEVELS = ["safe", "caution", "dangerous"]
RULES_PATH = Path(__file__).with_name("rules.yaml")
MAX_FILES = 200


@lru_cache(maxsize=None)
def load_rules(path: str | os.PathLike = RULES_PATH) -> tuple[dict, ...]:
    with open(path) as f:
        return tuple(yaml.safe_load(f)["rules"])


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def rule_matches(rule: dict, segment: dict, cmd: str) -> bool:
    programs = _as_list(rule.get("program"))
    if programs and segment["program"] not in programs:
        return False
    flags = set(segment["flags"])
    if rule.get("any_flags") and not flags & set(rule["any_flags"]):
        return False
    if rule.get("all_flags") and not set(rule["all_flags"]) <= flags:
        return False
    if rule.get("targets") and not set(segment["targets"]) & set(map(str, rule["targets"])):
        return False
    if rule.get("sudo") and not segment.get("sudo"):
        return False
    if rule.get("pattern") and not re.search(rule["pattern"], cmd):
        return False
    return True


def affected_files(targets: list[str], cwd: str | None = None) -> list[str]:
    """List the files a command would touch, expanding globs and walking folders."""
    cwd = cwd or os.getcwd()
    files: list[str] = []
    for target in targets:
        pattern = os.path.expanduser(os.path.expandvars(target))
        matches = glob.glob(os.path.join(cwd, pattern)) or []
        for match in matches:
            if os.path.isdir(match) and not os.path.islink(match):
                for root, _dirs, names in os.walk(match):
                    files.extend(os.path.join(root, n) for n in names)
                    if len(files) >= MAX_FILES:
                        break
            else:
                files.append(match)
            if len(files) >= MAX_FILES:
                break
    return [os.path.relpath(f, cwd) for f in files[:MAX_FILES]]


def check_danger(cmd: str, cwd: str | None = None, rules=None) -> dict:
    rules = load_rules() if rules is None else rules
    parsed = parse_command(cmd)
    result = {"level": "safe", "reason": "", "files": []}
    for segment in parsed["segments"] or [parsed]:
        for rule in rules:
            if not rule_matches(rule, segment, cmd):
                continue
            if LEVELS.index(rule["level"]) > LEVELS.index(result["level"]):
                result["level"] = rule["level"]
                result["reason"] = rule["reason"]
                if rule.get("files"):
                    result["files"] = affected_files(segment["targets"], cwd)
            break  # first matching rule per segment decides that segment
    return result
