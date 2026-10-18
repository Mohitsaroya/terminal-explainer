import os
from io import StringIO

from rich.console import Console

from explain import render

"""
this file is to test render.py without a keyboard: panels are drawn into a string
"""

records = [
    {"command": "ls", "risk": "safe", "summary": "Lists files in this folder."},
    {"command": "mv notes.txt old/", "risk": "caution",
     "summary": "Moves notes.txt into the old folder.",
     "rule_messages": ["mv can overwrite a file with the same name"],
     "steps": ["Finds notes.txt", "Moves it into old/"],
     "reversible": True},
    {"command": "rm -rf ./*", "risk": "danger", "confirm_word": "Documents",
     "summary": "Permanently deletes everything in this folder.",
     "rule_messages": ["Recursive delete with a wildcard"],
     "side_effects": ["5 files and 1 folder (400 B) permanently deleted"],
     "reversible": False},
]


def draw(rec):
    con = Console(record=True, width=render.MAX_EXPLANATION_WIDTH)
    con.print(render.build_panel(rec))
    return con.export_text()


def test_panels_show_label_summary_and_rule_messages():
    for rec in records[1:]:
        text = draw(rec)
        assert rec["summary"] in text
        for msg in rec["rule_messages"]:
            assert msg in text
    text = draw(records[2])
    assert "Run: type Documents + Enter" in text
    assert "Cancel: Esc" in text
    assert "Edit: type e + Enter" in text
    caution_text = draw(records[1])
    assert "Run: type yes + Enter" in caution_text
    assert "Cancel: Esc" in caution_text
    assert "Edit: type e + Enter" in caution_text


def test_explanation_panel_uses_the_target_width():
    lines = draw(records[2]).splitlines()

    assert max(map(len, lines)) == render.MAX_EXPLANATION_WIDTH


def test_segments_are_listed():
    text = draw(render.DEMO[2])
    assert "SAFE   cd /tmp/old" in text and "DANGER rm -rf *" in text


def test_safe_runs_without_asking():
    output = StringIO()
    con = Console(file=output)

    assert render.show(dict(records[0]), con) == "ran"
    assert output.getvalue() == ""


def test_explanation_width_is_capped_but_fits_narrower_terminals(monkeypatch):
    monkeypatch.setattr(render.os, "get_terminal_size", lambda fd: os.terminal_size((160, 24)))
    assert render._explanation_width() == render.MAX_EXPLANATION_WIDTH
    assert render._new_console().width == render.MAX_EXPLANATION_WIDTH

    monkeypatch.setattr(render.os, "get_terminal_size", lambda fd: os.terminal_size((80, 24)))
    assert render._explanation_width() == 80
    assert render._new_console().width == 80


def test_no_keyboard_cancels_instead_of_crashing(monkeypatch):
    # pytest's stdin is not a terminal
    monkeypatch.setattr(render, "_read_confirmation_input", lambda con, prompt: None)
    assert render.confirm(dict(records[1])) == "cancelled"


def test_danger_requires_confirmation_word(monkeypatch):
    monkeypatch.setattr(render, "_read_confirmation_input", lambda con, prompt: "Documents")
    assert render.confirm(dict(records[2])) == "ran"


def test_danger_edit_shortcut_returns_to_prompt(monkeypatch):
    monkeypatch.setattr(render, "_read_confirmation_input", lambda con, prompt: "e")
    assert render.confirm(dict(records[2])) == "edited"


def test_escape_cancels_danger_confirmation(monkeypatch):
    monkeypatch.setattr(render, "_read_confirmation_input", lambda con, prompt: None)
    assert render.confirm(dict(records[2])) == "cancelled"


def test_wrong_danger_confirmation_word_cancels(monkeypatch):
    monkeypatch.setattr(render, "_read_confirmation_input", lambda con, prompt: "document")
    assert render.confirm(dict(records[2])) == "cancelled"


def test_caution_confirmation_requires_yes(monkeypatch):
    monkeypatch.setattr(render, "_read_confirmation_input", lambda con, prompt: "yes")
    assert render.confirm(dict(records[1])) == "ran"


def test_caution_edit_shortcut_returns_to_prompt(monkeypatch):
    monkeypatch.setattr(render, "_read_confirmation_input", lambda con, prompt: "e")
    assert render.confirm(dict(records[1])) == "edited"


def test_caution_confirmation_wrong_word_cancels(monkeypatch):
    monkeypatch.setattr(render, "_read_confirmation_input", lambda con, prompt: "y")
    assert render.confirm(dict(records[1])) == "cancelled"


def test_escape_cancels_caution_confirmation(monkeypatch):
    monkeypatch.setattr(render, "_read_confirmation_input", lambda con, prompt: None)
    assert render.confirm(dict(records[1])) == "cancelled"


def test_danger_confirmation_prompt_does_not_repeat_panel_instructions():
    output = StringIO()
    con = Console(file=output)

    assert render.confirm(dict(records[2]), con) == "cancelled"
    assert output.getvalue() == "Confirm: "
