# Deadlock Server Picker for Linux

A native Linux command-line tool to block/unblock Deadlock game server relays using iptables or nftables.

## Features

- Block/unblock specific server regions
- Built-in region presets (NA, EU, Asia, etc.)
- Interactive TUI with color-coded status
- Ping monitoring with latency display and history tracking
- Custom preset system
- Dry-run mode for testing
- **nftables support** (auto-detects iptables vs nftables)
- **Wine/Proton detection** for game process monitoring
- **Server geolocation data** with geographic info
- **Systemd service** for auto-start at boot
- **Auto-apply preferences** on startup (always_block, never_block, last region)

## Requirements

- Linux
- Python 3.10+
- iptables or nftables
- Root/sudo access

## Installation

```bash
git clone https://github.com/shibne/DeadlockServerPicker-linux.git
cd DeadlockServerPicker-linux
pip install -e .
```

## Usage

### Basic Commands

```bash
# List all servers with geographic info
deadlock-server-picker list

# List with ping times
deadlock-server-picker list --ping

# Block servers
deadlock-server-picker block sgp hkg

# Unblock servers
deadlock-server-picker unblock sgp

# Unblock all
deadlock-server-picker unblock --all

# Block all except specific servers
deadlock-server-picker block-except sgp tyo

# Reset all firewall rules (removes the entire chain)
deadlock-server-picker reset
```

### Region Commands

```bash
# List available regions
deadlock-server-picker regions

# Allow only a region (block all others) - two ways:
deadlock-server-picker allow na
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

Commands: `list`, `regions`, `block <code>`, `unblock <code>`, `allow <region>`, `ping`, `history`, `best`, `wine`, `reset`, `quit`

### Configuration

```bash
# Show configuration
deadlock-server-picker config show

# Set default region (auto-applied on startup)
deadlock-server-picker config set default_region eu

# Set servers to always block
deadlock-server-picker config set always_block "sgp,hkg"

# Choose firewall backend
deadlock-server-picker config set firewall_backend nftables
```

### Systemd Service (Auto-start)

```bash
# Enable system service
sudo systemctl enable --now deadlock-server-picker

# Or enable user service
systemctl --user enable --now deadlock-server-picker
```

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

This is an unofficial, community-made tool. It is not affiliated with, endorsed by, or associated with Valve Corporation in any way.

**Use at your own risk.** I am not responsible for any damages, issues, or consequences that may arise from using this software. This includes but is not limited to system instability, network issues, or any other problems that may occur. By using this tool, you accept full responsibility for any outcomes.
