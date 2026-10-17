from explain import render

"""
this file is to test

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

for rec in records:
    decision = render.show(rec)
    print("decision:", decision, "| took", rec["response_ms"], "ms\n")