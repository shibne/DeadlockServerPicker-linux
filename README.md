# Deadlock Server Picker for Linux

A native Linux command-line tool to block/unblock Deadlock game server relays using iptables.

## Features

- Block/unblock specific server regions
- Built-in region presets (NA, EU, Asia, etc.)
- Interactive TUI with color-coded status
- Ping monitoring with latency display
- Custom preset system
- Dry-run mode for testing

## Requirements

- Linux
- Python 3.10+
- iptables
- Root/sudo access

## Installation

```bash
git clone https://github.com/shibne/DeadlockServerPicker.git
cd DeadlockServerPicker
pip install -e .
```

## Usage

### Basic Commands

```bash
# List all servers
deadlock-server-picker list

# List with ping times
deadlock-server-picker list --ping

# Block servers
deadlock-server-picker block "Singapore" "Hong Kong"

# Unblock servers
deadlock-server-picker unblock "Singapore"

# Unblock all
deadlock-server-picker unblock --all

# Block all except specific servers
deadlock-server-picker block-except "Singapore" "Tokyo"

# Reset all firewall rules
deadlock-server-picker reset
```

### Region Commands

```bash
# List available regions
deadlock-server-picker regions

# Allow only a region (block all others)
deadlock-server-picker allow-region na

# Block a region
deadlock-server-picker block-region cn

# Unblock a region
deadlock-server-picker unblock-region eu
```

### Interactive TUI

```bash
deadlock-server-picker tui
```

Commands: `list`, `regions`, `block <code>`, `unblock <code>`, `allow <region>`, `ping`, `reset`, `quit`

### Options

```bash
--dry-run       # Simulate without making changes
--no-sudo       # Run without sudo (if already root)
--clustered     # Group related servers
```

## How It Works

The tool fetches server relay data from Valve's Steam API and creates iptables rules to block traffic to specific server IPs. Blocked servers are skipped during matchmaking.

Rules are created in a dedicated `DEADLOCK_SERVER_PICKER` chain to avoid interfering with other firewall rules. All rules are automatically cleaned up when exiting the TUI.

## FAQ

### Will I get banned?

No. This tool only manages local firewall rules and does not modify any game files.

### Why am I still connecting to blocked servers?

Steam Datagram Relay may find alternative routes. For best results, only block servers you don't want rather than blocking everything except one region.

### Why does it need sudo?

iptables requires elevated privileges to add or remove firewall rules.

## License

GPL-3.0

## Credits

- Inspired by [FN-FAL113's CS2 Server Picker](https://github.com/FN-FAL113/cs2-server-picker) for Windows
- Built with [Claude Opus 4.5](https://www.anthropic.com/claude)

## Disclaimer

This project is not affiliated with Valve Corporation.
