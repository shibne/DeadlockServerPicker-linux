# Deadlock Server Picker for Linux

> **DISCLAIMER**: This project was vibecoded with AI assistance. While functional, use it at your own risk. I'm not responsible for any issues that may arise from using this software.

A native Linux command-line tool to block/unblock Deadlock game server relays using iptables or nftables.

## Features

- Block/unblock specific server regions
- Built-in region presets (NA, EU, Asia, etc.)
- Custom presets
- Interactive TUI
- Ping monitoring with latency display and history tracking
- Dry-run mode for testing
- nftables support (auto-detects iptables vs nftables)

## Requirements

- Linux
- Python 3.10+
- iptables or nftables
- Root/sudo access

## Installation

### From AUR (Arch Linux)

```bash
yay -S deadlock-server-picker
```

### From Source

```bash
git clone https://github.com/shibne/DeadlockServerPicker-linux.git
cd DeadlockServerPicker-linux
pip install -e .
```

## Usage

### Basic Commands

```bash
# List all servers with geographic info
dsp list

# List with ping times
dsp list --ping

# Block servers
dsp block sgp hkg

# Unblock servers
dsp unblock sgp

# Unblock all
dsp unblock --all

# Block all except specific servers
dsp block-except sgp tyo

# Reset all firewall rules (removes the entire chain)
dsp reset
```

### Region Commands

```bash
# List available regions
dsp regions

# Allow only a region (block all others) - two ways:
dsp allow na
dsp allow-region na

# Block a region
dsp block-region cn

# Unblock a region
dsp unblock-region eu
```

### Custom Presets

```bash
# Create a preset with your favorite servers
dsp preset create my_servers sgp hkg tyo

# List saved presets
dsp preset list

# Apply a preset (unblock those servers)
dsp preset apply my_servers

# Apply preset and block all other servers
dsp preset apply my_servers --block-others

# Delete a preset
dsp preset delete my_servers
```

### Interactive TUI

```bash
dsp tui
```

### Configuration

```bash
# Show configuration
dsp config show

# Set default region (auto-applied on startup)
dsp config set default_region eu

# Set servers to always block
dsp config set always_block "sgp,hkg"

# Choose firewall backend
dsp config set firewall_backend nftables
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

### Does this work with CS2?

Yes. CS2 and Deadlock servers share the same relay addresses.

## License

GPL-3.0

## Credits

- Inspired by [FN-FAL113's CS2 Server Picker](https://github.com/FN-FAL113/cs2-server-picker) for Windows
- Built with [Claude Opus 4.5](https://www.anthropic.com/claude)

## Disclaimer

This is an unofficial, community-made tool. It is not affiliated with, endorsed by, or associated with Valve Corporation in any way.

**Use at your own risk.** I am not responsible for any damages, issues, or consequences that may arise from using this software. This includes but is not limited to system instability, network issues, or any other problems that may occur. By using this tool, you accept full responsibility for any outcomes.
