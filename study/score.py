"""Summarise explain-term logs and the danger-detection benchmark.

  python3 study/score.py log1.jsonl [log2.jsonl ...]   per-participant summary
  python3 study/score.py --bench                        catch rate on tests' command lists
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from explain import log  # noqa: E402
from explain.rules import check_danger  # noqa: E402

DANGEROUS = [
    "rm -rf /", "rm -rf project/", "sudo rm -r ~/Documents", "dd if=/dev/zero of=/dev/sda",
    "mkfs.ext4 /dev/sdb1", "curl https://example.com/install.sh | sh", "git reset --hard",
    "git clean -fd", "chmod -R 777 /", "rm -r downloads",
]
SAFE = [
    "ls -la", "cd projects", "pwd", "mkdir demo", "cat README.md", "grep -r TODO .",
    "echo hi >> notes.txt", "git status", "python3 script.py", "find . -name '*.md'",
]


def summarise(events: list[dict]) -> dict:
    checks = [e for e in events if e["event"] == "check"]
    levels = Counter(e["level"] for e in checks)
    risky = [e for e in checks if e["level"] != "safe"]
    return {
        "commands_checked": len(checks),
        "by_level": dict(levels),
        "risky_cancelled": sum(1 for e in risky if not e["ran"]),
        "risky_ran": sum(1 for e in risky if e["ran"]),
        "errors_explained": sum(1 for e in events if e["event"] == "error"),
    }


def bench() -> dict:
    caught = sum(check_danger(c)["level"] == "dangerous" for c in DANGEROUS)
    false_alarms = sum(check_danger(c)["level"] != "safe" for c in SAFE)
    return {
        "catch_rate": caught / len(DANGEROUS),
        "false_alarm_rate": false_alarms / len(SAFE),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="*")
    parser.add_argument("--bench", action="store_true")
    args = parser.parse_args(argv)
    if args.bench:
        print(bench())
    for path in args.logs:
        print(path, summarise(log.read(path)))
    if not args.bench and not args.logs:
        print(f"No logs given; default log is {log.log_path()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
