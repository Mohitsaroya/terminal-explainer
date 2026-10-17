import pytest

from explain.llm import explain_error, redact
from explain.parser import parse_command
from explain.rules import check_danger


def test_parse_splits_combined_flags():
    assert parse_command("rm -rf project/")["program"] == "rm"
    assert parse_command("rm -rf project/")["flags"] == ["-r", "-f"]
    assert parse_command("rm -rf project/")["targets"] == ["project/"]


def test_parse_handles_sudo_and_pipes():
    parsed = parse_command("sudo apt install tree && ls | wc -l")
    assert parsed["program"] == "apt"
    assert parsed["sudo"] is True
    assert [s["program"] for s in parsed["segments"]] == ["apt", "ls", "wc"]


@pytest.mark.parametrize("cmd", [
    "rm -rf /",
    "rm -rf project/",
    "sudo rm -r ~/Documents",
    "dd if=/dev/zero of=/dev/sda",
    "mkfs.ext4 /dev/sdb1",
    "curl https://example.com/install.sh | sh",
    ":(){ :|:& };:",
    "git reset --hard",
    "git clean -fd",
    "chmod -R 777 /",
    "ls && rm -rf build",
])
def test_dangerous(cmd):
    assert check_danger(cmd)["level"] == "dangerous", cmd


@pytest.mark.parametrize("cmd", [
    "rm notes.txt",
    "mv a.txt b.txt",
    "echo hi > notes.txt",
    "sudo apt update",
    "git push --force",
    "kill 1234",
])
def test_caution(cmd):
    assert check_danger(cmd)["level"] == "caution", cmd


@pytest.mark.parametrize("cmd", [
    "ls -la",
    "cd projects",
    "pwd",
    "mkdir demo",
    "cat README.md",
    "grep -r TODO .",
    "echo hi >> notes.txt",
    "python3 script.py 2>&1",
    "git status",
])
def test_safe(cmd):
    assert check_danger(cmd)["level"] == "safe", cmd


def test_lists_affected_files(tmp_path):
    (tmp_path / "project").mkdir()
    for name in ("a.txt", "b.txt"):
        (tmp_path / "project" / name).write_text("x")
    result = check_danger("rm -rf project/", cwd=str(tmp_path))
    assert sorted(result["files"]) == ["project/a.txt", "project/b.txt"]


def test_glob_files(tmp_path):
    for name in ("a.txt", "b.txt", "keep.py"):
        (tmp_path / name).write_text("x")
    assert sorted(check_danger("rm *.txt", cwd=str(tmp_path))["files"]) == ["a.txt", "b.txt"]


def test_redacts_secrets():
    text = redact("export API_KEY=abc123 and token: ghp_abcdefghijklmnop")
    assert "abc123" not in text and "ghp_abcdefghijklmnop" not in text


def test_fake_error_explanation():
    result = explain_error("python3 app.py", 1, "ModuleNotFoundError: No module named 'requests'")
    assert result["fix"] == "pip install requests"
    assert explain_error("pyhton3 app.py", 127)["problem"].startswith("The shell couldn't find")
