typeset -g SAFE_ON=1
typeset -g LAST_CMD=""
typeset -g ERR_FILE="$(mktemp)"
typeset -g CAMPTURING=0

safeon() { SAFE_ON=1; print "Explain-term is ON"; }
safeoff() { SAFE_ON=0; print "Explain-term is OFF"; }

my_enter(){
	local cmd="${BUFFER//[[:space:]]/}"
	if (( ! SAFE_ON )) || [[ -z $cmd || $cmd == safeon || $cmd == safeoff ]]; then
		zle .accept-line
		return
	fi

	zle -I
	python3 ~/explain-term/explain/cli.py explain -- "$BUFFER" </dev/tty >/dev/tty 2>&1

	if (( $? == 0)); then
		zle .accept-line
	else
		BUFFER=""
		zle reset-prompt
	fi
}
zle -N accept-line my_enter

#Runs right before a command starts: remembers waht it was
pre_run(){
	LAST_CMD="$1"
	: >| "$ERR_FILE"
	exec 3>&2
	exec 2> >(tee -a "$ERR_FILE" >&3)
	CAPTURING=1
}

#Runs right after it finishes: checks if it failed
pre_cmd(){
	local code=$?
	if (( CAPTURING )); then
		exec 2>&3 3>&-
		CAPTURING=0
		sleep 0.05
	fi
	if [[ -n $LAST_CMD ]] && (( code != 0 && code != 130)); then
		python3 ~/explain-term/explain/cli.py error --code "$code" -- "LAST_CMD" </dev/tty
	fi
	LAST_CMD=""
}

cleanup(){
	rm -f "$ERR_FILE"
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec pre_run
add-zsh-hook precmd pre_cmd

