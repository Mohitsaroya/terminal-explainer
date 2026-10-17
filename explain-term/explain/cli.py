import sys

def main():
	command = sys.argv[3]
	print(f'[explain-term] You typed: {command}')

	if command.startswith("rm"):
		answer = input("This can delete files. Would you like to run it? (y/n) ")
		print()
		if answer.lower == "y":
			return 0
		return 1
	return 0

sys.exit(main())
