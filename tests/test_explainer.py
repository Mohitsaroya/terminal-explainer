from explain import context, explainer


def test_glossary_entries_are_found():
    out = explainer.explain("rm -rf ./*")
    assert out["risk"] == "danger"
    assert out["summary"].startswith("Permanently deletes")
    assert "-r: also deletes folders and everything inside them" in out["steps"]


def test_sudo_explains_the_inner_command():
    out = explainer.explain("sudo -u bob rm -rf /tmp/x")
    assert out["summary"].startswith("As administrator: permanently deletes")
    assert out["reversible"] is False


def test_fd_numbers_are_not_arguments():
    cmds = explainer.quick_parse("rm x 2>/dev/null; echo hi 2>&1 > out.txt")
    assert cmds == [{"program": "rm", "args": ["x"]}, {"program": "echo", "args": ["hi"]}]


def test_sudo_targets_are_measured(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    cmds = explainer.quick_parse("sudo rm a.txt")
    ctx = context.resolve(cmds, cwd=str(tmp_path))
    assert ctx.total_files == 1


def test_cd_dash_does_not_go_home(tmp_path):
    cmds = explainer.quick_parse("cd - && rm a.txt")
    ctx = context.resolve(cmds, cwd=str(tmp_path))
    assert ctx.targets[0].cwd == str(tmp_path)


# ---------------------------------------------------------------- quick_parse
def programs(line):
    return [c["program"] for c in explainer.quick_parse(line)]


def test_newlines_separate_commands():
    # a pasted two-line command must not hide the second line inside the first
    assert explainer.quick_parse("ls\nrm -rf ~") == [
        {"program": "ls", "args": []}, {"program": "rm", "args": ["-rf", "~"]}]


def test_backslash_newline_joins_lines():
    assert explainer.quick_parse("ls \\\n -la") == [{"program": "ls", "args": ["-la"]}]


def test_pipe_with_stderr_and_subshells_are_split():
    assert programs("ls |& rm -rf ~") == ["ls", "rm"]
    assert programs("(cd /tmp && rm -rf *)") == ["cd", "rm"]


def test_hash_is_not_a_comment():
    # zsh prints "#" unless interactivecomments is on, so the rm still runs
    assert programs("ls # ; rm -rf ~") == ["ls", "rm"]
    assert explainer.quick_parse("rm a#b") == [{"program": "rm", "args": ["a#b"]}]


def test_substitutions_are_found_and_come_first():
    cmds = explainer.quick_parse("ls $(rm -rf ~)")
    assert cmds == [{"program": "rm", "args": ["-rf", "~"], "in_substitution": True},
                    {"program": "ls", "args": ["$(...)"]}]
    assert programs("echo `rm x`") == ["rm", "echo"]
    assert programs("cat <(rm x)") == ["rm", "cat"]
    assert programs("a $(b $(c))") == ["c", "b", "a"]


def test_substitution_in_double_quotes_runs_but_single_quotes_do_not():
    cmds = explainer.quick_parse("echo \"$(rm x)\" '$(rm y)'")
    assert cmds[0] == {"program": "rm", "args": ["x"], "in_substitution": True}
    assert cmds[1] == {"program": "echo", "args": ["$(...)", "$(rm y)"]}


def test_arithmetic_and_parameter_expansion_run_nothing():
    assert programs("echo $((1 + 2))") == ["echo"]
    assert explainer.quick_parse("rm -rf ${HOME}") == [{"program": "rm", "args": ["-rf", "${HOME}"]}]
    assert programs("echo ${(U)name}") == ["echo"]
    # but a substitution hidden inside ${...} is still found
    assert programs("echo ${x:-$(rm -rf ~)}")[0] == "rm"


def test_shell_keywords_and_assignments_are_not_programs():
    assert programs("for f in *; do rm -rf $f; done") == ["rm"]
    assert programs("if true; then rm x; fi") == ["true", "rm"]
    assert explainer.quick_parse("FOO=1 rm x") == [{"program": "rm", "args": ["x"]}]
    assert programs("x=5") == []


def test_unclosed_quote_raises():
    import pytest
    with pytest.raises(ValueError):
        explainer.quick_parse('echo "unclosed')


# ---------------------------------------------------------------- wrappers
def test_wrappers_are_unwrapped():
    assert context.strip_wrappers("env", ["FOO=1", "rm", "x"]) == ("rm", ["x"])
    assert context.strip_wrappers("xargs", ["-n", "1", "rm", "-rf"]) == ("rm", ["-rf"])
    assert context.strip_wrappers("nice", ["-n", "10", "nohup", "rm", "x"]) == ("rm", ["x"])
    assert context.strip_wrappers("sudo", ["sudo", "rm", "x"]) == ("rm", ["x"])
    # nothing to run, or only a lookup: left alone
    assert context.strip_wrappers("command", ["-v", "rm"]) == ("command", ["-v", "rm"])
    assert context.strip_wrappers("sudo", ["-i"]) == ("sudo", ["-i"])


def test_wrapped_commands_are_explained():
    out = explainer.explain("xargs rm")
    assert out["summary"].startswith("Permanently deletes")
    assert out["risk"] == "danger" and out["reversible"] is False
    # sudo anywhere in the chain still says "As administrator", once
    assert explainer.explain("env sudo rm x")["summary"].startswith("As administrator: permanently")
    assert explainer.explain("sudo sudo rm x")["summary"].count("As administrator") == 1


# ---------------------------------------------------------------- side effects
def test_redirects_to_dev_null_or_fds_are_not_files():
    effects = explainer.explain("rm x 2>/dev/null >&2 > out.txt")["side_effects"]
    assert "out.txt is replaced: anything already in it is lost" in effects
    assert not any("/dev/null" in e or e.startswith("2 ") for e in effects)


def test_git_status_is_read_from_the_target_folder(tmp_path):
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "new.txt").write_text("x")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    # run from a folder that is not a repository
    ctx = context.resolve(explainer.quick_parse(f"rm -r {repo}"), cwd=str(elsewhere))
    assert ctx.in_git_repo is True
    assert ctx.git_dirty_files == 1


def test_wrapped_targets_are_measured(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    ctx = context.resolve(explainer.quick_parse("env FOO=1 rm a.txt"), cwd=str(tmp_path))
    assert ctx.total_files == 1


def test_cd_inside_a_line_moves_later_substitutions(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    ctx = context.resolve(explainer.quick_parse(f"cd {tmp_path} && echo $(rm a.txt)"), cwd="/")
    assert ctx.total_files == 1
