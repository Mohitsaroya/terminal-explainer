# explain-term zsh hook.
#
#   source /path/to/terminal-explainer/hook/explain.zsh
#
# Before a command runs, `explain check` shows what it does and asks y/n.
# After a command fails, `explain why` explains the error.
# Set EXPLAIN_OFF=1 to turn it off for the current shell.

: ${EXPLAIN_PYTHON:=python3}
typeset -g EXPLAIN_HOME="${${(%):-%x}:A:h:h}"
typeset -g _explain_last_cmd=""

_explain() {
  PYTHONPATH="$EXPLAIN_HOME${PYTHONPATH:+:$PYTHONPATH}" "$EXPLAIN_PYTHON" -m explain "$@"
}

# Replace Enter: nothing reaches the shell until `explain check` exits 0.
_explain_accept_line() {
  local cmd="$BUFFER"
  if [[ -n "$EXPLAIN_OFF" || -z "${cmd//[[:space:]]/}" ]]; then
    zle .accept-line
    return
  fi
  zle -I
  if _explain check -- "$cmd" </dev/tty; then
    zle .accept-line
  else
    print -s -- "$cmd"   # keep it in history so the user can fix it
    BUFFER=""
    zle .reset-prompt
  fi
}
zle -N accept-line _explain_accept_line

_explain_preexec() {
  _explain_last_cmd="$1"
}

_explain_precmd() {
  local code=$?
  [[ -z "$EXPLAIN_OFF" && -n "$_explain_last_cmd" && $code -ne 0 ]] && \
    _explain why "$code" -- "$_explain_last_cmd"
  _explain_last_cmd=""
  # TODO: capture stderr into $EXPLAIN_STDERR_FILE so `why` can read the real error text.
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec _explain_preexec
add-zsh-hook precmd _explain_precmd
