#Stop with a clear message if this is loaded from bash instead of zsh
[ -n "$ZSH_VERSION" ] || { echo "explain-term needs zsh. Type 'zsh' first."; return 1; }

typeset -g SAFE_ON=1	# 1 is on and 0 is off
typeset -g LAST_CMD=""	#the command that is currently running
typeset -g ERR_FILE="$(mktemp)" #temp file that collects the error output
typeset -g CAPTURING=0		# 1 while error output is being copied, 0 otherwise
#cli.py next to this hook, wherever the repo was cloned (%x is this file, :A:h:h is explain-term/)
typeset -g EXPLAIN_CLI="${${(%):-%x}:A:h:h}/explain/cli.py"
#the repo's virtual environment (made by `uv sync`), which has rich and pyyaml installed
typeset -g EXPLAIN_VENV_PY="${${(%):-%x}:A:h:h:h}/.venv/bin/python"

#Python to run cli.py with: the repo's .venv if it exists, otherwise the system python3
explain_py(){
	if [[ -x $EXPLAIN_VENV_PY ]]; then
		"$EXPLAIN_VENV_PY" "$@"
	else
		python3 "$@"
	fi
}

#Controls if safe mode is on or off
safeon() { SAFE_ON=1; print "Explain-term is ON"; }
safeoff() { SAFE_ON=0; print "Explain-term is OFF"; }

my_enter(){
	#What the user types, removes spaces
	local cmd="${BUFFER//[[:space:]]/}"
	#Checks if explain-term is off, line is empty or if safeon/off is typed
	if (( ! SAFE_ON )) || [[ -z $cmd || $cmd == safeon || $cmd == safeoff ]]; then
		zle .accept-line
		return
	fi

	zle -I
	#Pass to cli.py
	explain_py "$EXPLAIN_CLI" explain -- "$BUFFER" </dev/tty >/dev/tty 2>&1
	# 1 = user said no, 3 = user wants to edit the command, anything else runs it.
	# If Python crashes, run the command anyway so a bug never locks the user out.
	case $? in
		1) BUFFER=""; zle reset-prompt ;;
		3) zle reset-prompt ;;	#keeps the typed command so it can be changed
		*) zle .accept-line ;;
	esac
}
zle -N accept-line my_enter #Replace the zsh Enter key with my_enter

#Runs right before a command starts: remembers what it was
pre_run(){
	LAST_CMD="$1"
	: >| "$ERR_FILE" #Empties the error file from last time (before any early return, so old errors never leak through)

	#Don't capture output from interactive programs
	case "${1%% *}" in
		nano|vim|vi|less|man|ssh|top|htop) return ;;
	esac
	#python on its own opens an interactive prompt; "python3 app.py" still gets captured
	[[ "$1" == python3 || "$1" == python ]] && return

	exec 3>&2	#Save the real error output as stream 3
	exec 2> >(tee -a "$ERR_FILE" >&3) #Errors go to the file and the screen
	CAPTURING=1
}

#Runs right after it finishes: checks if it failed
pre_cmd(){
	local code=$?	#MUST be the first line, or the exit code is lost
	#Stops copying the error output
	if (( CAPTURING )); then
		exec 2>&3 3>&- #Errors go to the screen only and close stream 3
		CAPTURING=0
		sleep 0.05	#Give tee a moment to finish writing the file
	fi
	#Explain the failures, skips success (0), ctrl+c (130) and ctrl+z (148)
	if [[ -n $LAST_CMD ]] && (( code != 0 && code != 130 && code != 148 )); then
		explain_py "$EXPLAIN_CLI" error --code "$code" --errfile "$ERR_FILE" -- "$LAST_CMD" </dev/tty
	fi
	LAST_CMD="" #Set it back to empty
}

cleanup(){
	rm -f "$ERR_FILE" #Deletes the session's temp file
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec pre_run
add-zsh-hook precmd pre_cmd
add-zsh-hook zshexit cleanup
