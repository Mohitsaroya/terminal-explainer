typeset -g SAFE_ON=1	# 1 is on and 0 is off
typeset -g LAST_CMD=""	#the command that is currently running
typeset -g ERR_FILE="$(mktemp)" #temp file that collects the error output
typeset -g CAPTURING=0		# 1 while capturing error output is being copied 0 otherwise

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
	python3 ~/explain-term/explain/cli.py explain -- "$BUFFER" </dev/tty >/dev/tty 2>&1
	# Only cancel if the exit code is exactly 1
	if (( $? != 1)); then
		zle .accept-line
	else
		BUFFER=""
		zle reset-prompt
	fi
}
zle -N accept-line my_enter #Replace the zsh Enter key with my_enter

#Runs right before a command starts: remembers waht it was
pre_run(){
	LAST_CMD="$1"
	#Don't capture output from interactive programs
	case "${1%% *}" in
		nano|vim|vi|less|man|ssh|top|htop|python3|python) return ;;
	esac
	: >| "$ERR_FILE" #Empties the error file from last time
	exec 3>&2	#Save the real error output as stream 3
	exec 2> >(tee -a "$ERR_FILE" >&3) #Errors go to the file and the screen
	CAPTURING=1
}

#Runs right after it finishes: checks if it failed
pre_cmd(){
	local code=$?
	#Stops copying the error output
	if (( CAPTURING )); then
		exec 2>&3 3>&- #Errors go to the screen only and close stream 3
		CAPTURING=0
		sleep 0.05
	fi
	#Explain the failures, skips success ctrl+c and ctrl+z
	if [[ -n $LAST_CMD ]] && (( code != 0 && code != 130)); then
		python3 ~/explain-term/explain/cli.py error --code "$code" -- "LAST_CMD" </dev/tty
	fi
	LAST_CMD="" #Set it back to empty
}

cleanup(){
	rm -f "$ERR_FILE" #Deletes the sessions temp file
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec pre_run
add-zsh-hook precmd pre_cmd
add-zsh-hook zshexit cleanup
