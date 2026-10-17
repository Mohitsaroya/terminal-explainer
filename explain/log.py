"""Append one JSON line per event, for the user study (study/score.py reads it)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path


def log_path() -> Path:
    if "EXPLAIN_LOG" in os.environ:
        return Path(os.environ["EXPLAIN_LOG"])
    state = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    return Path(state) / "explain-term" / "log.jsonl"


def record(event: str, **fields) -> None:
    if os.environ.get("EXPLAIN_NO_LOG"):
        return
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps({"ts": time.time(), "event": event, **fields}) + "\n")
    except OSError:
        pass  # logging must never block a command


def read(path: str | os.PathLike | None = None) -> list[dict]:
    path = Path(path) if path else log_path()
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]
