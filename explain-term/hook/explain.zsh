typeset -g SAFE_ON=1

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
