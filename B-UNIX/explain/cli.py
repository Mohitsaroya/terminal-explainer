"""Entry point the zsh hook calls.

    cli.py explain -- "<command line>"
        Explains the command and asks before risky ones.
        Exit 0 = run it, 1 = cancel, 3 = return to the shell prompt for editing.
    cli.py error --code N [--errfile FILE] -- "<command line>"
        Explains why a command just failed.

Any crash exits 0 so a bug in explain-term never stops a command from running.
"""
import argparse
import os
import re
import sys
from pathlib import Path

# Run as a plain script by the hook, so the project packages are importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUN, CANCEL, EDIT = 0, 1, 3

# Common exit codes and what they mean for a beginner.
EXIT_CODES = {
    126: "The file exists but is not allowed to run (check its permissions).",
    127: "The command was not found. Check the spelling, or install the program.",
}


def parse_args(argv):
    p = argparse.ArgumentParser(prog="explain-term")
    sub = p.add_subparsers(dest="mode", required=True)
    ex = sub.add_parser("explain")
    ex.add_argument("command", nargs="+")
    er = sub.add_parser("error")
    er.add_argument("--code", type=int, required=True)
    er.add_argument("--errfile")
    er.add_argument("command", nargs="+")
    args = p.parse_args(argv)
    args.command = " ".join(args.command)
    return args


def explain_mode(line):
    from explain import context, explainer, render
    from rules.rules import checker

    cmds = explainer.quick_parse(line)
    if len(cmds) == 1 and os.path.basename(cmds[0].get("program", "")) in {"source", "."}:
        return RUN

    ctx = context.resolve(cmds)
    rec = explainer.explain(line, cmds, ctx)
    rec["command"] = line
    rec["confirm_word"] = ctx.confirm_word()

    rule_messages = []
    segments = []
    for cmd in cmds:
        program = cmd.get("program", "")
        args = cmd.get("args", [])
        rule_risk, reason = checker([program, *args])
        command = " ".join([program, *args])
        segment = explainer.explain("", [cmd])
        segment_risk = explainer.merge_risk(segment["risk"], rule_risk)
        rec["risk"] = explainer.merge_risk(rec["risk"], rule_risk)
        segments.append({"command": command, "risk": segment_risk})
        if rule_risk != "safe" and reason not in rule_messages:
            rule_messages.append(reason)

    echo_removals = _echo_removal_commands(line, cmds)
    if echo_removals:
        rec["risk"] = "danger"
        rec["reversible"] = False
        reason = "echo command substitution runs a file-removal command."
        rule_messages.append(reason)
        segments.extend(
            {"command": f"{command} (inside echo substitution)", "risk": "danger"}
            for command in echo_removals
        )

    if rule_messages:
        rec["rule_messages"] = rule_messages
    if len(segments) > 1:
        rec["segments"] = segments

    decision = render.show(rec)
    if decision == "ran":
        safe_summary_file = os.environ.get("EXPLAIN_SAFE_SUMMARY_FILE")
        if rec["risk"] == "safe" and safe_summary_file and rec.get("summary"):
            Path(safe_summary_file).write_text(rec["summary"], encoding="utf-8")
        return RUN
    if decision == "edited":
        return EDIT
    return CANCEL


def _echo_removal_commands(line, cmds):
    """Find removal commands that execute inside an echo substitution."""
    echo_commands = [
        cmd for cmd in cmds
        if os.path.basename(cmd.get("program", "")) == "echo"
    ]
    if not echo_commands:
        return []

    if not any(marker in line for marker in ("$(", "`", "<(", ">(")):
        return []

    try:
        import bashlex
    except ModuleNotFoundError as error:
        if error.name != "bashlex":
            raise
        return _echo_removal_commands_without_parser(line)

    removals = {"rm", "unlink", "shred", "rmdir"}
    found = []
    visited = set()

    def visit(node, in_echo=False, in_substitution=False):
        if not hasattr(node, "kind") or id(node) in visited:
            return
        visited.add(id(node))

        kind = getattr(node, "kind", "")
        if kind == "command":
            words = [part.word for part in getattr(node, "parts", [])
                     if getattr(part, "kind", "") == "word"]
            is_echo = bool(words) and os.path.basename(words[0]) == "echo"
            if in_echo and in_substitution and words:
                program = os.path.basename(words[0])
                if program in removals:
                    start, end = node.pos
                    found.append(line[start:end])
            in_echo = in_echo or is_echo
        elif kind in ("commandsubstitution", "processsubstitution") and in_echo:
            in_substitution = True

        for value in vars(node).values():
            if hasattr(value, "kind"):
                visit(value, in_echo, in_substitution)
            elif isinstance(value, list):
                for child in value:
                    if hasattr(child, "kind"):
                        visit(child, in_echo, in_substitution)

    for node in bashlex.parse(line):
        visit(node)
    return found


def _echo_removal_commands_without_parser(line):
    """Handle direct echo substitutions when the optional shell parser is unavailable."""
    echo = re.match(r"\s*echo\b", line)
    if not echo or not any(marker in line[echo.end():] for marker in ("$(", "`")):
        return []

    body = re.sub(r"'(?:\\.|[^'])*'", "", line[echo.end():])
    substitutions = re.compile(
        r"(?<!\\)\$\((?P<paren>[^)]*)\)|(?<!\\)`(?P<backtick>[^`]*)`"
    )
    removal = re.compile(
        r"(?:^|[;&|]\s*)(?:sudo\s+)*(?:[\w.-]+/)*(?:rm|unlink|shred|rmdir)\b[^\n]*"
    )
    found = []
    for substitution in substitutions.finditer(body):
        commands = substitution.group("paren") or substitution.group("backtick")
        match = removal.search(commands)
        if match:
            found.append(match.group(0).strip())
    return found


def error_mode(line, code, errfile):
    print(f"[explain-term] `{line}` failed with exit code {code}.", file=sys.stderr)
    if code in EXIT_CODES:
        print(EXIT_CODES[code], file=sys.stderr)
    if errfile:
        try:
            with open(errfile, encoding="utf-8", errors="replace") as f:
                lines = [l.rstrip() for l in f if l.strip()]
        except OSError:
            lines = []
        if lines:
            print("The error said:", file=sys.stderr)
            for l in lines[-5:]:
                print(f"  {l}", file=sys.stderr)
    return 0


def main(argv=None):
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
        if args.mode == "explain":
            return explain_mode(args.command)
        return error_mode(args.command, args.code, args.errfile)
    except SystemExit:        # bad arguments: argparse already printed why
        return RUN
    except KeyboardInterrupt:
        return CANCEL
    except Exception as e:   # noqa: BLE001 - never block the user's command
        print(f"[explain-term] internal error, running the command anyway: {e}", file=sys.stderr)
        return RUN


if __name__ == "__main__":
    sys.exit(main())
