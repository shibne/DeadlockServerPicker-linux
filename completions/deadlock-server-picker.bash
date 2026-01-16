# Bash completion for deadlock-server-picker
# Install: source this file or add to ~/.bash_completion.d/

_deadlock_server_picker() {
    local cur prev opts commands regions
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    commands="list block unblock block-all block-except ping preset status reset regions list-region allow-region block-region unblock-region tui config"
    regions="na sa eu euw eue asia apac cn india japan korea oce me af"
    opts="--help --dry-run --no-sudo --clustered --config-dir --version"
    
    case "${prev}" in
        deadlock-server-picker|dsp)
            COMPREPLY=( $(compgen -W "${commands} ${opts}" -- ${cur}) )
            return 0
            ;;
        list-region|allow-region|block-region|unblock-region)
            COMPREPLY=( $(compgen -W "${regions}" -- ${cur}) )
            return 0
            ;;
        preset)
            COMPREPLY=( $(compgen -W "list create delete apply" -- ${cur}) )
            return 0
            ;;
        config)
            COMPREPLY=( $(compgen -W "show set reset" -- ${cur}) )
            return 0
            ;;
        --config-dir)
            COMPREPLY=( $(compgen -d -- ${cur}) )
            return 0
            ;;
    esac
    
    # Default to commands and options
    if [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
    else
        COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
    fi
}

complete -F _deadlock_server_picker deadlock-server-picker
complete -F _deadlock_server_picker dsp
