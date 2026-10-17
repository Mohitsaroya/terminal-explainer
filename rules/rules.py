import yaml

rulesYaml = "rules/rules.yaml"

def readYaml():
    with open(rulesYaml) as stream:
        try:
            rules = yaml.safe_load(stream)
            #print(rules)
            return rules
        except yaml.YAMLError as exc:
            print(exc)

def match(prg, args, rules):
    #compare prg/args against rules
    #returns a tuple of level and reason
    for r in rules["rules"]:
        if prg == r["program"]:
            if len(r) == 4:
                for a in args:
                    #check if the arguement is in the list for args key
                    if a in r["args"]:
                        match = (r["level"], r["reason"])
                        return match
            elif len(r) == 3:
                match = (r["level"], r["reason"])
                return match

    return ("safe", "not in the rules")

def checker(parsedCmd):
    rules = readYaml()
    #for simplicity, commands are assumed to contain only one program (the one at the beginning of the command)
    prg = parsedCmd[0]
    #remaining args that are not prg
    args = []

    for a in parsedCmd[1::]:
        args.append(a)

    res = match(prg, args, rules)
    return res
