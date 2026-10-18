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
    con = Console(record=True, width=100)
    con.print(render.build_panel(rec))
    return con.export_text()


def test_panels_show_label_summary_and_rule_messages():
    for rec in records[1:]:
        text = draw(rec)
        assert rec["summary"] in text
        for msg in rec["rule_messages"]:
            assert msg in text
    assert "Type Documents to run" in draw(records[2])


def test_segments_are_listed():
    text = draw(render.DEMO[2])
    assert "SAFE   cd /tmp/old" in text and "DANGER rm -rf *" in text


def test_safe_runs_without_asking():
    assert render.show(dict(records[0])) == "ran"


def test_no_keyboard_cancels_instead_of_crashing():
    # pytest's stdin is not a terminal
    assert render.confirm(dict(records[1])) == "cancelled"
