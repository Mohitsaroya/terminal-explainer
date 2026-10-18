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
import sys
from pathlib import Path

# Run as a plain script by the hook, so the project packages are importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUN, CANCEL, EDIT = 0, 1, 3

# Programs that delete files. One hidden inside $(...) or `...` is always danger,
# because the line looks like it only prints or lists something.
REMOVALS = {"rm", "unlink", "shred", "rmdir"}

# Common exit codes and what they mean for a beginner.
EXIT_CODES = {
    126: "The file exists but is not allowed to run (check its permissions).",
    127: "The command was not found. Check the spelling, or install the program.",
}


def parse_args(argv):
    """Read the hook's arguments. The command line is joined back into one string."""
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
    """Explain `line`, ask before risky commands, and return RUN, CANCEL or EDIT."""
    from explain import context, explainer, render

    try:
        cmds = explainer.quick_parse(line)
    except ValueError:
        # An unclosed quote: we can't tell what would run, so ask instead of guessing.
        return _decision_to_exit(render.show(_unreadable_record(line)))

    # Sourcing the hook itself (or any script) is let through without a panel.
    if len(cmds) == 1 and os.path.basename(cmds[0].get("program", "")) in {"source", "."}:
        return RUN

    ctx = context.resolve(cmds)
    rec = explainer.explain(line, cmds, ctx)
    rec["command"] = line
    rec["confirm_word"] = ctx.confirm_word()

    # Each simple command is checked against rules.yaml, and the riskiest verdict
    # wins for the whole line: `touch a && rm -rf *` is as risky as `rm -rf *`.
    rule_messages = []
    segments = []
    for cmd in cmds:
        program = cmd.get("program", "")
        args = cmd.get("args", [])
        rule_risk, reason = _check_rules(program, args)
        command = " ".join([program, *args])
        segment = explainer.explain("", [cmd])
        segment_risk = explainer.merge_risk(segment["risk"], rule_risk)
        rec["risk"] = explainer.merge_risk(rec["risk"], rule_risk)
        if cmd.get("in_substitution"):
            command += " (inside command substitution)"
            if context.strip_wrappers(os.path.basename(program), args)[0] in REMOVALS:
                # `echo $(rm -rf *)` looks harmless but deletes files.
                segment_risk = rec["risk"] = "danger"
                rec["reversible"] = False
                reason = "A command substitution runs a file-removal command."
                rule_risk = "danger"
        segments.append({"command": command, "risk": segment_risk})
        if rule_risk != "safe" and reason not in rule_messages:
            rule_messages.append(reason)

    if rule_messages:
        rec["rule_messages"] = rule_messages
    if len(segments) > 1:
        rec["segments"] = segments

    decision = render.show(rec)
    if decision == "ran":
        # The hook prints this one-line summary for safe commands just before they run.
        safe_summary_file = os.environ.get("EXPLAIN_SAFE_SUMMARY_FILE")
        if rec["risk"] == "safe" and safe_summary_file and rec.get("summary"):
            Path(safe_summary_file).write_text(rec["summary"], encoding="utf-8")
    return _decision_to_exit(decision)


def _check_rules(program, args):
    """rules.yaml verdict for one command, also looking through sudo, env, xargs, ...

    `env rm -rf /` is checked as `rm -rf /`, and the riskier verdict is kept.
    """
    from explain import context, explainer
    from rules.rules import checker

    name = os.path.basename(program)
    if explainer.help_request(name, args) or name.startswith("-"):
        return "safe", ""                           # `rm --help` only prints help
    risk, reason = checker([program, *args])
    inner, inner_args = context.strip_wrappers(name, args)
    if inner != name and not explainer.help_request(inner, inner_args):
        inner_risk, inner_reason = checker([inner, *inner_args])
        if explainer.merge_risk(risk, inner_risk) != risk:
            risk, reason = inner_risk, inner_reason
    return risk, reason


def _unreadable_record(line):
    """Panel data for a line that can't be split into words (an unclosed quote)."""
    return {
        "command": line,
        "risk": "caution",
        "summary": "This line has a quote that is never closed, so B-UNIX can't tell what it would run.",
        "rule_messages": ["Check that every ' and \" has a matching closing quote."],
    }


def _decision_to_exit(decision):
    """render.show()'s answer -> the exit code the hook expects."""
    if decision == "ran":
        return RUN
    if decision == "edited":
        return EDIT
    return CANCEL


def error_mode(line, code, errfile):
    """Explain why `line` failed: its exit code, a hint for common codes, and the
    last few lines of error output the hook saved in `errfile`. Always returns 0."""
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
    """Run one mode and return the exit code. Never raises (see the module docstring)."""
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
