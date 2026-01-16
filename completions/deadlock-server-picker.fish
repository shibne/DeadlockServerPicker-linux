# Fish completion for deadlock-server-picker
# Install: copy to ~/.config/fish/completions/

set -l commands list block unblock block-all block-except ping preset status reset regions list-region allow-region block-region unblock-region tui config
set -l regions na sa eu euw eue asia apac cn india japan korea oce me af

# Disable file completion by default
complete -c deadlock-server-picker -f
complete -c dsp -f

# Main commands
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a list -d 'List available servers'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a block -d 'Block servers'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a unblock -d 'Unblock servers'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a block-all -d 'Block all servers'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a block-except -d 'Block all except specified'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a ping -d 'Ping servers'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a preset -d 'Manage presets'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a status -d 'Show status'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a reset -d 'Reset firewall'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a regions -d 'List regions'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a list-region -d 'List servers in region'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a allow-region -d 'Allow only region'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a block-region -d 'Block region'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a unblock-region -d 'Unblock region'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a tui -d 'Interactive TUI'
complete -c deadlock-server-picker -n "not __fish_seen_subcommand_from $commands" -a config -d 'Manage config'

# Global options
complete -c deadlock-server-picker -l help -d 'Show help'
complete -c deadlock-server-picker -l dry-run -d 'Simulate without changes'
complete -c deadlock-server-picker -l no-sudo -d 'Do not use sudo'
complete -c deadlock-server-picker -l clustered -d 'Use clustered view'
complete -c deadlock-server-picker -l config-dir -d 'Custom config directory' -r
complete -c deadlock-server-picker -l version -d 'Show version'

# Region completions
complete -c deadlock-server-picker -n "__fish_seen_subcommand_from list-region allow-region block-region unblock-region" -a "$regions"

# Preset subcommands
complete -c deadlock-server-picker -n "__fish_seen_subcommand_from preset" -a "list create delete apply"

# Config subcommands
complete -c deadlock-server-picker -n "__fish_seen_subcommand_from config" -a "show set reset"

# Alias
complete -c dsp -w deadlock-server-picker
