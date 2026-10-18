import parser

import rules.rules


def verdict(cmd):
    return rules.rules.checker(parser.parse(cmd))[0]


def test_levels():
    assert verdict("rm -rf project/") == "caution"
    assert verdict("rm -r notes") == "caution"
    assert verdict("rm -rf *") == "danger"
    assert verdict("rm -fr /") == "danger"
    assert verdict("sudo rm -rf /") == "danger"
    assert verdict("touch a.txt") == "safe"


def test_empty_and_unparseable():
    assert verdict("") == "safe"
    assert parser.parse('rm "unclosed') == -1
    assert parser.parse('rm "my file.txt"') == ["rm", "my file.txt"]


def test_works_from_any_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert verdict("rm a.txt") == "caution"
