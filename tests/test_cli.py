import subprocess
import sys
from pathlib import Path

from explain import cli, render

CLI = Path(__file__).parent.parent / "B-UNIX" / "explain" / "cli.py"


def run(*args, stdin=""):
    return subprocess.run([sys.executable, str(CLI), *args], input=stdin,
                          capture_output=True, text=True)


def test_safe_command_runs():
    result = run("explain", "--", "ls")

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_safe_command_has_no_explainer_output(monkeypatch, capsys):
    shown = []
    monkeypatch.setattr(render, "show", lambda rec: shown.append(rec) or "ran")

    assert cli.explain_mode("ls") == cli.RUN
    assert len(shown) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == ""


def test_safe_command_signals_hook_with_full_explanation(tmp_path, monkeypatch):
    summary_file = tmp_path / "safe-summary"
    monkeypatch.setenv("EXPLAIN_SAFE_SUMMARY_FILE", str(summary_file))

    assert cli.explain_mode("ls") == cli.RUN
    assert summary_file.read_text(encoding="utf-8") == (
        "Lists the files and folders in this folder."
    )


def test_risky_command_does_not_signal_safe_summary(tmp_path, monkeypatch):
    summary_file = tmp_path / "safe-summary"
    monkeypatch.setenv("EXPLAIN_SAFE_SUMMARY_FILE", str(summary_file))
    monkeypatch.setattr(render, "show", lambda rec: "cancelled")

    assert cli.explain_mode("rm notes.txt") == cli.CANCEL
    assert not summary_file.exists()


def test_sourcing_hook_bypasses_explanation(monkeypatch):
    shown = []
    monkeypatch.setattr(render, "show", lambda rec: shown.append(rec) or "ran")

    assert cli.explain_mode("source /path/to/explain.zsh") == cli.RUN
    assert shown == []


def test_unknown_command_remains_safe():
    assert run("explain", "--", "qweilrghqiwle").returncode == 0


def test_echo_removal_is_dangerous(monkeypatch):
    shown = {}
    monkeypatch.setattr(render, "show", lambda rec: shown.update(rec) or "cancelled")

    assert cli.explain_mode("echo $(rm -rf *)") == cli.CANCEL
    assert shown["risk"] == "danger"
    assert shown["reversible"] is False
    assert "A command substitution runs a file-removal command." in shown["rule_messages"]
    assert {"command": "rm -rf * (inside command substitution)", "risk": "danger"} in shown["segments"]


def test_echo_that_quotes_removal_text_is_safe(monkeypatch):
    monkeypatch.setattr(render, "show", lambda rec: rec["risk"] == "safe" and "ran")

    assert cli.explain_mode("echo '$(rm -rf *)'") == cli.RUN


def test_echo_with_file_removal_substitution_is_dangerous():
    result = run("explain", "--", "echo $(rm -rf *)")

    assert result.returncode == 1
    assert "DANGER" in result.stderr
    assert "A command substitution runs a file-removal command" in result.stderr
    assert "rm -rf * (inside command substitution)" in result.stderr


def test_echo_that_only_prints_removal_text_remains_safe():
    assert run("explain", "--", "echo rm -rf *").returncode == 0


def test_risky_command_without_keyboard_is_cancelled():
    assert run("explain", "--", "rm notes.txt").returncode == 1


def test_rule_matched_danger_shows_reason_and_requires_confirmation():
    result = run("explain", "--", "rm -rf *")

    assert result.returncode == 1
    assert "DANGER" in result.stderr
    assert "Deletes everything under a top-level or current folder" in result.stderr


def test_compound_command_keeps_dangerous_segment_risk():
    result = run("explain", "--", "touch harmless.txt && rm -rf *")

    assert result.returncode == 1
    assert "DANGER" in result.stderr
    assert "Deletes everything under a top-level or current folder" in result.stderr
    assert "touch harmless.txt" in result.stderr
    assert "rm -rf *" in result.stderr


def test_edit_decision_returns_edit_exit_code(monkeypatch):
    monkeypatch.setattr(render, "show", lambda rec: "edited")

    assert cli.explain_mode("mv notes.txt old/") == cli.EDIT


def test_error_mode_shows_code_and_error_text(tmp_path):
    err = tmp_path / "err.txt"
    err.write_text("zsh: command not found: pyhton3\n")
    r = run("error", "--code", "127", "--errfile", str(err), "--", "pyhton3 app.py")
    assert r.returncode == 0
    assert "exit code 127" in r.stderr and "command not found: pyhton3" in r.stderr


def test_bad_arguments_never_block_the_command():
    assert run().returncode == 0


def capture(monkeypatch):
    shown = {}
    monkeypatch.setattr(render, "show", lambda rec: shown.update(rec) or "cancelled")
    return shown


def test_second_line_of_a_pasted_command_is_checked(monkeypatch):
    shown = capture(monkeypatch)
    cli.explain_mode("ls\nrm -rf ~")
    assert shown["risk"] == "danger"


def test_removal_inside_any_substitution_is_dangerous(monkeypatch):
    for line in ("ls $(rm -rf ~)", 'ls "$(rm x)"', "cat <(rm x)", "echo $((1+2)) $(rm x)"):
        shown = capture(monkeypatch)
        cli.explain_mode(line)
        assert shown["risk"] == "danger", line
        assert "A command substitution runs a file-removal command." in shown["rule_messages"], line


def test_harmless_substitution_stays_safe(monkeypatch):
    shown = capture(monkeypatch)
    cli.explain_mode("echo $(date)")
    assert shown["risk"] == "safe"


def test_unclosed_quote_asks_instead_of_crashing(monkeypatch):
    shown = capture(monkeypatch)
    assert cli.explain_mode('"; rm -rf ~') == cli.CANCEL
    assert shown["risk"] == "caution"
    assert "quote" in shown["summary"]


def test_unclosed_quote_without_keyboard_is_cancelled():
    result = run("explain", "--", '"; rm -rf ~')
    assert result.returncode == 1
    assert "internal error" not in result.stderr


def test_rules_look_through_wrappers(monkeypatch):
    for line in ("/bin/rm -rf /", "env rm -rf /", "FOO=1 rm -rf ~", "xargs rm -rf /"):
        shown = capture(monkeypatch)
        cli.explain_mode(line)
        assert shown["risk"] == "danger", line
        assert "Deletes everything under a top-level or current folder, with no undo." in shown["rule_messages"], line


def test_command_v_is_only_a_lookup(monkeypatch):
    shown = capture(monkeypatch)
    cli.explain_mode("command -v rm")
    assert shown["risk"] == "safe"
