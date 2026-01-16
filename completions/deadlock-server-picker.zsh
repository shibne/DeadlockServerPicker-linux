#compdef deadlock-server-picker dsp
# Zsh completion for deadlock-server-picker
# Install: add to fpath or source this file

_deadlock_server_picker() {
    local -a commands regions opts
    
    commands=(
        'list:List available servers'
        'block:Block specified servers'
        'unblock:Unblock specified servers'
        'block-all:Block all servers'
        'block-except:Block all except specified'
        'ping:Ping servers'
        'preset:Manage presets'
        'status:Show current status'
        'reset:Reset all firewall rules'
        'regions:List available regions'
        'list-region:List servers in region'
        'allow-region:Allow only region'
        'block-region:Block region'
        'unblock-region:Unblock region'
        'tui:Interactive TUI'
        'config:Manage configuration'
    )
    
    regions=(
        'na:North America'
        'sa:South America'
        'eu:Europe'
        'euw:Western Europe'
        'eue:Eastern Europe'
        'asia:Asia'
        'apac:Asia Pacific'
        'cn:China'
        'india:India'
        'japan:Japan'
        'korea:Korea'
        'oce:Oceania'
        'me:Middle East'
        'af:Africa'
    )
    
    opts=(
        '--help[Show help]'
        '--dry-run[Simulate without changes]'
        '--no-sudo[Do not use sudo]'
        '--clustered[Use clustered view]'
        '--config-dir[Custom config directory]:directory:_files -/'
        '--version[Show version]'
    )
    
    case "${words[2]}" in
        list-region|allow-region|block-region|unblock-region)
            _describe 'region' regions
            ;;
        preset)
            local -a preset_cmds
            preset_cmds=('list' 'create' 'delete' 'apply')
            _describe 'preset command' preset_cmds
            ;;
        config)
            local -a config_cmds
            config_cmds=('show' 'set' 'reset')
            _describe 'config command' config_cmds
            ;;
        *)
            _describe 'command' commands
            _arguments $opts
            ;;
    esac
}

_deadlock_server_picker "$@"
