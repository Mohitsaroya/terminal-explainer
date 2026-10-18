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

    if rule_messages:
        rec["rule_messages"] = rule_messages
    if len(segments) > 1:
        rec["segments"] = segments

    decision = render.show(rec)
    if decision == "ran":
        return RUN
    if decision == "edited":
        return EDIT
    return CANCEL


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
