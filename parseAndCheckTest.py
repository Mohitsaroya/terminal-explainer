import parser, rules.rules

parsedCmd = parser.parse()

if parsedCmd != -1:
    #cmd was able to be parsed
    res = rules.rules.checker(parsedCmd)
    print(res)

