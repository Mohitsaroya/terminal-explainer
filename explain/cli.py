"""Command-line entry point, called by hook/explain.zsh.

  explain check -- CMD          explain CMD, warn if risky, ask y/n.
                                exit 0 = run it, exit 1 = cancelled.
  explain why EXIT -- CMD       explain why CMD failed (stderr from EXPLAIN_STDERR_FILE if set).
  explain rules -- CMD          print the danger verdict as JSON (for tests and scripts).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from explain import context, llm, log, render
from explain.rules import check_danger

SKIP_EXIT_CODES = {0, 130}  # success, Ctrl+C


def cmd_check(command: str) -> int:
    danger = check_danger(command)
    explanation = llm.explain_command(command, context.gather())
    auto_safe = os.environ.get("EXPLAIN_AUTO_SAFE") == "1"
    render.show(render.format_check(command, explanation, danger), danger["level"])
    if danger["level"] == "safe" and auto_safe:
        run = True
    else:
        run = render.ask("Run it?", default=danger["level"] == "safe")
    log.record("check", cmd=command, level=danger["level"], files=len(danger["files"]), ran=run)
    return 0 if run else 1


def cmd_why(command: str, exit_code: int) -> int:
    if exit_code in SKIP_EXIT_CODES:
        return 0
    stderr = ""
    path = os.environ.get("EXPLAIN_STDERR_FILE")
    if path and os.path.exists(path):
        with open(path, errors="replace") as f:
            stderr = f.read()[-4000:]
    result = llm.explain_error(command, exit_code, stderr, context.gather())
    render.show(render.format_error(result), "caution", title="what went wrong")
    log.record("error", cmd=command, exit_code=exit_code)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="explain", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    p_check = sub.add_parser("check")
    p_check.add_argument("command", nargs=argparse.REMAINDER)
    p_why = sub.add_parser("why")
    p_why.add_argument("exit_code", type=int)
    p_why.add_argument("command", nargs=argparse.REMAINDER)
    p_rules = sub.add_parser("rules")
    p_rules.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    words = args.command[1:] if args.command[:1] == ["--"] else args.command
    command = " ".join(words).strip()
    if not command:
        return 0
    if args.action == "check":
        return cmd_check(command)
    if args.action == "why":
        return cmd_why(command, args.exit_code)
    print(json.dumps(check_danger(command)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
