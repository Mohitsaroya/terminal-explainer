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


def test_full_path_to_the_program_still_matches():
    assert verdict("/bin/rm -rf /") == "danger"


def test_other_spellings_of_everything_are_danger():
    for cmd in ("rm -rf ./*", "rm -rf ./", "rm -rf ~/*", "rm -rf ../", "rm -rf ${HOME}"):
        assert verdict(cmd) == "danger", cmd


def test_broken_or_empty_rules_file_gives_no_rules(tmp_path, monkeypatch):
    for text in ("", "rules: [unclosed", "just a string"):
        bad = tmp_path / "rules.yaml"
        bad.write_text(text)
        monkeypatch.setattr(rules.rules, "rulesYaml", str(bad))
        assert rules.rules.checker(["rm", "-rf", "/"]) == ("safe", "not in the rules")
