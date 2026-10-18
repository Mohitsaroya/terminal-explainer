# B-UNIX

A safety net for beginners in the terminal. In Zsh, B-UNIX explains commands before
they run, asks for confirmation for commands classified as risky, and can explain
errors after a command fails.

## Requirements

- macOS or Linux. On Windows, use WSL.
- Zsh.
- Python 3.12 or newer.
- `uv` (recommended) or `pip`.

## Install

From the repository root, install the dependencies into the project virtual
environment:

```sh
uv sync
```

Alternatively, use Python and pip:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install bashlex pydantic pyyaml rich pytest
```

The Zsh hook uses the active environment's Python if one is activated; otherwise it
tries the repository's `.venv/bin/python`, then `python3`.

### WSL

Do not use a Windows-created `.venv` from WSL. Create and activate a Linux virtual
environment (it can live outside the Windows-mounted repository):

```sh
python3 -m venv "$HOME/.venvs/b-unix"
source "$HOME/.venvs/b-unix/bin/activate"
python -m pip install bashlex pydantic pyyaml rich pytest
```

Activate it in each WSL terminal before sourcing the hook.

## Enable the Zsh hook

From the repository root, in a Zsh terminal:

```zsh
source B-UNIX/hook/explain.zsh
```

The hook is active only in the current shell. Use `safeoff` to turn it off and
`safeon` to turn it back on. (These names start with `safe`, not `save`.)
The prompt includes the current directory's full path and updates when you
change directories.

## Try it safely

Use a disposable directory for experiments:

```zsh
demo_dir=$(mktemp -d)
cd "$demo_dir"
touch keep.txt
```

Try `ls`, then `echo $(rm -rf *)`. The latter should display a DANGER panel and wait
for confirmation; press Enter or Esc to cancel. Do not confirm a destructive
command while testing.

## Confirmation behavior

| Risk | Behavior |
|---|---|
| Safe | Shows a green ✓ and its short explanation, then runs the command. No prompt. |
| Warning | Requires typing `yes` and pressing Enter; Esc cancels; type `e` to return to the shell prompt and edit. |
| Danger | Requires the displayed confirmation word and Enter; Esc cancels; type `e` to return to the shell prompt and edit. |

Known destructive commands and configured rules can raise risk. The CLI combines
the highest risk found across parsed commands. Every line of a pasted
multi-line command is checked, and so are commands hidden inside `$(...)`,
backticks, `<(...)`, subshells, loops and wrappers such as `sudo`, `env` and
`xargs`. A command substitution that runs a file-removal command (for example
`echo $(rm -rf *)`) is always classified as DANGER. A line with an unclosed
quote is shown as a WARNING, because B-UNIX can't tell what it would run. This
is not a complete Zsh parser; other unsupported shell syntax may not be fully
understood.

Asking a program for its help page or version (`rm --help`, `git push --help`,
`curl --version`) is always SAFE and is explained as such, because nothing else
runs. Typing an option on its own, like `--help`, explains how to use it.

Unknown commands are not automatically classified as risky just because they are
unknown. The project is an early prototype, and explanations/rules do not cover
every command.

If the CLI encounters an unexpected internal error, the Zsh hook currently fails
open and runs the command. Treat that behavior as a limitation; do not use the
project as the only safety measure for important data.

## Run tests

```sh
uv run pytest -q
```

Or, with the pip environment activated:

```sh
pytest -q
```

## How it works

```text
Enter in Zsh
  -> B-UNIX/hook/explain.zsh
  -> B-UNIX/explain/cli.py
  -> glossary explanation + root rules/rules.py and rules/rules.yaml
  -> B-UNIX/explain/render.py confirmation panel

Failed command
  -> Zsh hook captures error output
  -> CLI explains the exit code and captured error
```

## Project layout

```text
B-UNIX/
  hook/explain.zsh       Zsh Enter hook, mode toggles, and error capture
  explain/cli.py         CLI entry point
  explain/context.py     Working-directory and file context
  explain/explainer.py   Glossary-based explanations and risk summaries
  explain/render.py      Panels and confirmation prompts
  explain/glossary.yaml  Program and flag descriptions
  explain/rules.yaml     Additional rule data (not the active root checker format)
rules/
  rules.py               Active YAML rule checker
  rules.yaml             Active command-risk rules
tests/                   Pytest suite
pyproject.toml           Python dependencies and pytest configuration
uv.lock                  Pinned dependency versions
```
