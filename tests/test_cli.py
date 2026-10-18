import subprocess
import sys
from pathlib import Path

from explain import cli, render

CLI = Path(__file__).parent.parent / "explain-term" / "explain" / "cli.py"


def run(*args, stdin=""):
    return subprocess.run([sys.executable, str(CLI), *args], input=stdin,
                          capture_output=True, text=True)


def test_safe_command_runs():
    assert run("explain", "--", "ls").returncode == 0


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
