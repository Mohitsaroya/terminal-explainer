# explain-term

**A safety net for beginners in the terminal.** Every time you press Enter, explain-term tells you in plain English what the command is about to do. Risky commands need an extra confirmation, and when a command fails it explains why.

```
╭──────────────────────────────── EXPLANATION ─────────────────────────────────╮
│   DANGER  $ rm -rf project/                                                  │
│                                                                              │
│  Permanently deletes project/. Deleted files do not go to the Trash.         │
│                                                                              │
│  Step by step                                                                │
│  1. -r: also deletes folders and everything inside them                      │
│  2. -f: never asks for confirmation and ignores files that don't exist       │
│                                                                              │
│  - 2 files and 1 folder (0 B) permanently deleted                            │
│  X cannot be undo'd, action is not reversible                                │
╰──────────────────── Type project to run | Enter = cancel ────────────────────╯
```

---

## What you need

| Tool | Version | Check with | Notes |
|---|---|---|---|
| **macOS or Linux** | any | | On Windows, use [WSL](https://learn.microsoft.com/windows/wsl/install) |
| **zsh** | any | `zsh --version` | Default shell on macOS. On Ubuntu/Debian: `sudo apt install zsh` |
| **git** | any | `git --version` | |
| **Python** | **3.12 or newer** | `python3 --version` | Not needed if you use uv (below): uv downloads it for you |
| **uv** *(recommended)* | any | `uv --version` | `brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

The Python packages (`rich`, `pyyaml`, and `pytest` for the tests) are installed into a local `.venv` folder by the steps below. Nothing is installed globally.

---

## Quick start (about 2 minutes)

### 1. Clone and install

**With uv (recommended)**, which installs the exact versions in `uv.lock`:

```sh
git clone https://github.com/Mohitsaroya/terminal-explainer.git
cd terminal-explainer
uv sync
```

**Or with plain Python and pip**, if you don't want to install uv:

```sh
git clone https://github.com/Mohitsaroya/terminal-explainer.git
cd terminal-explainer
python3 -m venv .venv
source .venv/bin/activate
pip install rich pyyaml pytest
```

> Either way, the packages must end up in `terminal-explainer/.venv`. The hook looks for that
> folder automatically, so you don't need to activate it again later. Don't skip the venv and
> `pip install` globally: Homebrew's Python refuses that with an `externally-managed-environment` error.

### 2. Turn it on

From the `terminal-explainer` folder, **in zsh** (type `zsh` first if your prompt is bash):

```sh
source explain-term/hook/explain.zsh
```

It stays on for this terminal window only. Close the window, or type `safeoff`, to stop it.

### 3. Try it

Make a throwaway folder so nothing real is at risk, then type these one at a time:

```sh
mkdir -p /tmp/demo/project && touch /tmp/demo/project/a.txt /tmp/demo/project/b.txt
cd /tmp/demo
```

| Type this | What you should see |
|---|---|
| `ls` | A green ✓ line explaining the command, then it runs normally |
| `rm -rf project/` | A red **DANGER** panel showing exactly what would be deleted. Press **Enter** to cancel. Then run `ls`: `project` is still there |
| `pyhton3 app.py` | zsh says "command not found", then explain-term explains exit code 127 and suggests checking the spelling |
| `safeoff` | Turns explain-term off. `safeon` turns it back on |

### 4. Run the tests (optional)

```sh
cd path/to/terminal-explainer   # back to the repo folder
uv run pytest           # with uv
# or, with the pip setup and .venv active:
pytest
```

You should see `16 passed`.

---

## How to answer a prompt

| Level | Colour | What it means | Keys |
|---|---|---|---|
| Safe | green ✓ | A one-line explanation, then the command runs | none |
| Warning | yellow | Could cause trouble | **Enter** run · **Esc** cancel · **e** edit the command |
| Danger | red | Can't be undone | Type the word shown (for example the folder name) to run · **Enter** cancel |

If explain-term itself ever hits a bug, your command still runs, so it can never lock you out of your terminal.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `explain-term needs zsh. Type 'zsh' first.` | You're in bash. Type `zsh`, then run the `source` line again |
| `ModuleNotFoundError: No module named 'rich'` | The packages aren't in `terminal-explainer/.venv`. Re-run step 1 from inside the repo folder |
| `error: externally-managed-environment` | You ran `pip install` outside a venv. Use the `python3 -m venv .venv` steps above, or uv |
| `python3 --version` shows 3.11 or older | Use the uv route: `uv sync` downloads Python 3.12 automatically |
| Nothing happens when I press Enter | The hook is per window. Run the `source` line again in this window, and check you didn't type `safeoff` |

---

## How it works

```
you press Enter
   │
   ▼
explain-term/hook/explain.zsh   replaces zsh's Enter key, sends the command to cli.py
   │
   ▼
explain-term/explain/cli.py     explain mode: shows the panel, asks, returns run / cancel / edit
   ├── context.py               real facts: which files match, how many, how big, git status
   ├── explainer.py             plain-English explanation, using glossary.yaml and rules.yaml
   └── render.py                the coloured panels and key handling (rich)

command fails  →  the hook captures its error output  →  cli.py error mode explains it
```

### Project layout

```
explain-term/
  hook/explain.zsh        zsh hook (Enter key, error capture, safeon / safeoff)
  explain/cli.py          entry point: `explain` and `error` modes
  explain/context.py      what the command will touch (files, sizes, git state)
  explain/explainer.py    builds the explanation and danger level
  explain/render.py       panels and y/n / type-to-confirm prompts
  explain/rules.yaml      danger rules, editable without touching Python
  explain/glossary.yaml   plain-English meanings of programs and flags
parser.py, rules/         standalone command parser and rule checker (used by tests)
tests/                    pytest suite
pyproject.toml, uv.lock   dependencies
```

### Settings

| Variable | Meaning |
|---|---|
| `EXPLAIN_GLOSSARY` | Use a different glossary file instead of `explain/glossary.yaml` |
| `EXPLAIN_CACHE` | Path to a JSON file of hand-written explanations for specific commands |
