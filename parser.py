import shlex

test = "rm -i test.txt"

#splits the command into words, keeping quoted names like "my file.txt" together
#returns -1 if the command can't be split (e.g. an unclosed quote)
def parse(cmd=test):
    try:
        return shlex.split(cmd)
    except ValueError:
        return -1
