# explain-term

A terminal that explains commands before they run, stops dangerous ones, and explains errors.
Built for beginners: see the *Safe Terminal: Team Explainer* doc for the full idea.

This is the first skeleton. The LLM answers are canned (`EXPLAIN_LLM=fake`), so everything
can be built and tested before the real model is picked.

## Try it

```sh
pip install -e '.[pretty,dev]'      # pyyaml; rich and pytest are optional
python3 -m explain rules -- "rm -rf project/"     # danger verdict as JSON
python3 -m explain check -- "rm -rf project/"     # explanation + y/n (exit 0 = run)
python3 -m explain why 127 -- "pyhton3 app.py"    # explain a failure

source hook/explain.zsh             # turn it on in your zsh; EXPLAIN_OFF=1 turns it off
pytest
```

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
