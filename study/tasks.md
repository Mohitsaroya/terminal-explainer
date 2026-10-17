# User study tasks

Each participant does all six tasks twice: once in a plain terminal (`EXPLAIN_OFF=1`)
and once with explain-term. Alternate which comes first. Run `bash study/seed.sh` between rounds.

Record per task: completed (y/n), time in seconds, and mistakes (a destructive or wrong command
that ran). explain-term also writes its own log to `$EXPLAIN_LOG` for `study/score.py`.

| # | Task | Done when |
|---|------|-----------|
| 1 | Create a folder called `photos` inside `practice`. | `practice/photos/` exists |
| 2 | Move `beach.jpg` from `downloads` into `photos`. | `photos/beach.jpg` exists, `downloads/beach.jpg` doesn't |
| 3 | Find the file named `.hidden-recipe.md` somewhere under `practice`. | Participant says its path |
| 4 | Run `python3 project/src/broken.py`, then fix it so it runs. | Script prints without error |
| 5 | Delete only the `.txt` files in `downloads`, nothing else. | `notes-*.txt` gone, `report.docx` kept, `notes/` untouched |
| 6 | Run `project/src/app.py`; it fails. Install the missing package so it runs. | Prints "app is running" |

Facilitator notes:
- Don't help unless a participant is stuck for 3 minutes; mark the task as not completed if you do.
- Task 5 is the safety task: count any deletion outside `downloads/*.txt` as a mistake.
