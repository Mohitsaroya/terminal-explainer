import os

import yaml

rulesYaml = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.yaml")
#higher number = riskier, used to pick the worse of two verdicts
LEVELS = {"safe": 0, "caution": 1, "danger": 2}

def readYaml():
    with open(rulesYaml) as stream:
        try:
            rules = yaml.safe_load(stream)
            #print(rules)
            return rules
        except yaml.YAMLError as exc:
            print(exc)
            return {"rules": []}

def splitFlags(args):
    #"-rf" -> ["-r", "-f"] so combined flags match the rules; "--force" stays as is
    out = []
    for a in args:
        if a.startswith("-") and not a.startswith("--") and len(a) > 2:
            out += ["-" + ch for ch in a[1:]]
        else:
            out.append(a)
    return out

def match(prg, args, rules):
    #compare prg/args against rules
    #returns a tuple of level and reason
    args = splitFlags(args)
    for r in rules["rules"]:
        if prg == r["program"]:
            if "args" in r:
                for a in args:
                    #check if the arguement is in the list for args key
                    if a in r["args"]:
                        res = (r["level"], r["reason"])
                        return res
            else:
                res = (r["level"], r["reason"])
                return res

    return ("safe", "not in the rules")

def checker(parsedCmd):
    if not parsedCmd:
        return ("safe", "empty command")
    rules = readYaml()
    #for simplicity, commands are assumed to contain only one program (the one at the beginning of the command)
    prg = parsedCmd[0]
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
