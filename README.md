# explain-term

A terminal that explains commands before they run, stops dangerous ones, and explains errors.
Built for beginners: see the *Safe Terminal: Team Explainer* doc for the full idea.

This is the first skeleton. The LLM answers are canned (`EXPLAIN_LLM=fake`), so everything
can be built and tested before the real model is picked.

## Installing dependencies

You need **Python 3.12 or newer**. Check with `python3 --version`.

The project depends on:

| Package | What it's for |
|---|---|
| `rich` | Coloured panels and the live y/n prompt in the terminal |
| `pyyaml` | Reading the danger rules from `rules.yaml` |
| `bashlex` | Parsing shell commands properly (pipes, quotes, `&&`) |
| `pydantic` | Checking that rules and results have the right shape |
| `pytest` | Running the tests (dev only) |

### Option 1: uv (recommended)

The repo has a `uv.lock`, so `uv` installs the exact same versions everyone else on the team has.

```sh
# install uv once (macOS)
brew install uv            # or: curl -LsSf https://astral.sh/uv/install.sh | sh

# from the terminal-explainer folder
uv sync                    # creates .venv and installs everything, including pytest
source .venv/bin/activate  # or prefix commands with `uv run`, e.g. `uv run pytest`
```

To add a new package later: `uv add <package>` (or `uv add --dev <package>` for dev tools).
This updates `pyproject.toml` and `uv.lock`, so commit both.

### Option 2: pip

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install bashlex pydantic pyyaml rich pytest
```

This works, but it won't use the pinned versions in `uv.lock`.

### Check it worked

```sh
python3 -c "import rich, yaml, bashlex, pydantic; print('all good')"
```

If you get `ModuleNotFoundError`, the virtual environment probably isn't active. Run
`source .venv/bin/activate` again (you need to do this in every new terminal window).

## Try it

```sh
# after installing dependencies (above):
python3 -m explain rules -- "rm -rf project/"     # danger verdict as JSON
python3 -m explain check -- "rm -rf project/"     # explanation + y/n (exit 0 = run)
python3 -m explain why 127 -- "pyhton3 app.py"    # explain a failure

source hook/explain.zsh             # turn it on in your zsh; EXPLAIN_OFF=1 turns it off
pytest
```

The CLI checks each parsed command against `rules/rules.yaml` using `rules/rules.py`.
For compound commands, the highest risk from the glossary or any matching rule is used,
and matching rule reasons are shown in the explanation panel.

## Layout

```
hook/explain.zsh        zsh hook: runs `explain check` on Enter, `explain why` after a failure
explain/cli.py          entry point (check / why / rules)
explain/parser.py       parse_command(cmd) -> {program, flags, targets, segments}
explain/rules.py        check_danger(cmd) -> {level, reason, files}
explain/rules.yaml      the danger rules, editable without touching Python
explain/context.py      cwd, OS, shell, git branch, files here (sent to the LLM)
explain/llm.py          explain_command / explain_error, secret redaction (fake backend for now)
explain/render.py       panels (rich if installed) and the y/n prompt
explain/log.py          JSON-lines event log for the study
study/                  Dockerfile sandbox, seed.sh practice folder, tasks.md, score.py
tests/test_rules.py     parser, rules, redaction and fake-LLM tests
```

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `EXPLAIN_OFF` | unset | Set to skip the hook in this shell |
| `EXPLAIN_LLM` | `fake` | LLM backend; only `fake` exists so far |
| `EXPLAIN_AUTO_SAFE` | unset | `1` runs safe commands without asking |
| `EXPLAIN_LOG` | `~/.local/state/explain-term/log.jsonl` | Where events are logged |
| `EXPLAIN_NO_LOG` | unset | Set to turn logging off |

## Not done yet

- Real LLM backend (hosted API or Ollama) in `explain/llm.py`
- Capturing stderr in the hook so `why` sees the actual error text
- tldr pages for offline explanations; bashlex instead of shlex
- Undo (stretch goal)
