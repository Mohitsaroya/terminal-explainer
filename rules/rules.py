"""Risk rules from rules.yaml: checker(["rm", "-rf", "/"]) -> ("danger", "reason")."""
import os

import yaml

rulesYaml = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.yaml")
#higher number = riskier, used to pick the worse of two verdicts
LEVELS = {"safe": 0, "caution": 1, "danger": 2}

def readYaml():
    #loads rules.yaml; a broken or empty file gives no rules instead of a crash
    with open(rulesYaml) as stream:
        try:
            rules = yaml.safe_load(stream)
            #print(rules)
        except yaml.YAMLError as exc:
            print(exc)
            return {"rules": []}
    if not isinstance(rules, dict) or not isinstance(rules.get("rules"), list):
        return {"rules": []}
    return rules

def splitFlags(args):
    #"-rf" -> ["-r", "-f"] so combined flags match the rules; "--force" stays as is
    out = []
    for a in args:
        if a.startswith("-") and not a.startswith("--") and len(a) > 2:
            out += ["-" + ch for ch in a[1:]]
        else:
            out.append(a)
    return out

def spellings(arg):
    #"./*" and "*" mean the same folder, as do "~/" and "~"; flags are compared as typed
    if arg.startswith("-"):
        return {arg}
    return {arg, os.path.normpath(arg)}

def match(prg, args, rules):
    #compare prg/args against rules
    #returns a tuple of level and reason
    #the first matching rule wins, so specific rules (with args) go above general ones
    args = splitFlags(args)
    for r in rules["rules"]:
        if prg == r["program"]:
            if "args" in r:
                for a in args:
                    #check if the arguement is in the list for args key
                    if spellings(a) & set(r["args"]):
                        res = (r["level"], r["reason"])
                        return res
            else:
                res = (r["level"], r["reason"])
                return res

    return ("safe", "not in the rules")

def checker(parsedCmd):
    #parsedCmd is one simple command as a list of words, e.g. ["rm", "-rf", "x"]
    if not parsedCmd:
        return ("safe", "empty command")
    rules = readYaml()
    #for simplicity, commands are assumed to contain only one program (the one at the beginning of the command)
    #/bin/rm is still rm
    prg = os.path.basename(parsedCmd[0])
    #remaining args that are not prg
    args = []

    for a in parsedCmd[1::]:
        args.append(a)

    res = match(prg, args, rules)
    #sudo runs another command: check that one too and keep the riskier verdict
    if prg == "sudo" and args:
        inner = checker(args)
        if LEVELS.get(inner[0], 1) > LEVELS.get(res[0], 1):
            res = inner
    return res
