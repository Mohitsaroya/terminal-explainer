test = "rm -i test.txt"

#splits the command then calls programs() to group programs with their options+flags
def parse(cmd=test):
    try:
        parsed = cmd.split()
        return parsed
    except:
        return -1