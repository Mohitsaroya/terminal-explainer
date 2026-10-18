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
