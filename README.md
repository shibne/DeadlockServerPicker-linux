# Deadlock Server Picker for Linux

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A native Linux command-line tool to block/unblock Deadlock (Deadlock) game server relays using iptables. This is a Linux port inspired by [FN-FAL113's Deadlock Server Picker](https://github.com/FN-FAL113/deadlock-server-picker) for Windows.

## Features

- 🌍 **Server Management**: Block/unblock specific Deadlock server regions
- �️ **Region Presets**: Built-in presets for NA, EU, Asia, and more
- 🖥️ **Interactive TUI**: Color-coded terminal interface
- �📊 **Ping Monitoring**: Measure latency to all servers
- 🔧 **Preset System**: Save and load server configurations
- 🔄 **Clustered Mode**: Group related servers (e.g., all China servers)
- 🛡️ **iptables Integration**: Native Linux firewall management
- 📝 **Dry-Run Mode**: Test commands without making changes
- 🎨 **Colored Output**: Easy-to-read terminal output

## How It Works

The tool fetches Deadlock server relay data from Valve's Steam API and allows you to block specific server regions using iptables firewall rules. When you block a server:

1. An iptables OUTPUT rule is created that drops packets to the server's IP addresses
2. Deadlock will skip these servers when matchmaking
3. You'll be routed to unblocked servers instead

**Note**: This blocks relay IPs, not actual game servers. Steam Datagram Relay may still route you to nearby servers in some cases.

## Requirements

- Linux (tested on Ubuntu, Debian, Arch, Fedora)
- Python 3.10 or higher
- iptables
- Root/sudo access (for firewall management)

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/your-username/deadlock-server-picker.git
cd deadlock-server-picker

# Install in development mode
pip install -e .

# Or install normally
pip install .
```

### Manual Installation

```bash
# Clone and add to PATH
git clone https://github.com/your-username/deadlock-server-picker.git
cd deadlock-server-picker
chmod +x deadlock_server_picker/cli.py
export PATH="$PATH:$(pwd)/deadlock_server_picker"
```

## Usage

### Basic Commands

```bash
# List all available servers
deadlock-server-picker list

# List servers with ping times
deadlock-server-picker list --ping

# Block specific servers
deadlock-server-picker block "Singapore" "Hong Kong"

# Unblock specific servers
deadlock-server-picker unblock "Singapore"

# Unblock all servers
deadlock-server-picker unblock --all

# Block all except specific servers
deadlock-server-picker block-except "Singapore" "Tokyo"

# Block all servers
deadlock-server-picker block-all

# Ping specific servers
deadlock-server-picker ping "Singapore" "Tokyo"

# Show status
deadlock-server-picker status

# Reset all firewall rules
deadlock-server-picker reset
```

### Preset Management

```bash
# List all presets
deadlock-server-picker preset list

# Create a preset
deadlock-server-picker preset create "Asia Low Ping" sgp hkg tyo

# Delete a preset
deadlock-server-picker preset delete "Asia Low Ping"

# Apply a preset (unblock preset servers)
deadlock-server-picker preset apply "Asia Low Ping"

# Apply a preset and block all other servers
deadlock-server-picker preset apply "Asia Low Ping" --block-others
```

### Options

```bash
# Use clustered server view (groups related servers)
deadlock-server-picker --clustered list

# Don't use sudo (if running as root)
deadlock-server-picker --no-sudo block "Singapore"

# Dry-run mode (simulate without changes)
deadlock-server-picker --dry-run block "Singapore"

# Custom config directory
deadlock-server-picker --config-dir /path/to/config list
```

### Region Commands

Built-in region presets make it easy to control server access by geographic area:

```bash
# List available regions
deadlock-server-picker regions

# Available regions: na, sa, eu, euw, eue, asia, apac, cn, india, japan, korea, oce, me, af

# Allow only North American servers (block all others)
deadlock-server-picker allow-region na

# Block all Chinese servers
deadlock-server-picker block-region cn

# Unblock all European servers
deadlock-server-picker unblock-region eu

# List servers in a specific region
deadlock-server-picker list-region asia
deadlock-server-picker list-region na --ping
```

### Interactive TUI Mode

Launch the interactive terminal user interface for a visual server management experience:

```bash
# Start TUI
deadlock-server-picker tui

# Or use the dedicated command
deadlock-server-picker-tui

# TUI with dry-run mode
deadlock-server-picker tui --dry-run
```

**TUI Features:**
- 🟢 Green = Server allowed
- 🔴 Red = Server blocked
- Real-time status updates
- Easy region-based blocking
- Built-in help system

**TUI Commands:**
- `list` / `l` - Show all servers
- `list <region>` - Show servers in region
- `regions` / `r` - Show available regions
- `block <code>` - Block a server
- `unblock <code>` - Unblock a server
- `allow <region>` - Allow only region (block others)
- `block-region <region>` - Block entire region
- `ping` - Ping all servers
- `reset` - Unblock all servers
- `quit` / `q` - Exit

## Examples

### Block all servers except SEA region
```bash
deadlock-server-picker block-except sgp sea hkg
```

### Create and use a preset for competitive play
```bash
# Create preset with low-ping servers
deadlock-server-picker preset create "Competitive" sgp sea

# Apply preset before playing
deadlock-server-picker preset apply "Competitive" --block-others

# After playing, unblock all
deadlock-server-picker unblock --all
```

### Check current status
```bash
$ deadlock-server-picker status
Deadlock Server Picker Status
----------------------------------------
Firewall access: OK
Server mode: unclustered
Dry run: disabled

Blocked servers: 3
  - US East iad
  - EU West fra
  - South America gru

Saved presets: 2
```

## Configuration

Configuration files are stored in `~/.config/deadlock-server-picker/`:

- `presets.json` - Saved server presets

## FAQ

### Will I get banned for using this?

No. This tool only adds firewall rules to your system - it doesn't modify any game files. Valve cannot detect or ban you for managing your own firewall.

### Why am I still getting routed to blocked servers?

Steam Datagram Relay works by routing you through relay points. If all nearby relays are blocked, SDR may still find a path through other relays. For best results, only block servers you definitely don't want.

### Why does it need root/sudo access?

iptables requires elevated privileges to add or remove firewall rules. The tool uses sudo by default but can run directly as root with `--no-sudo`.

### Does this work for Deadlock?

Possibly! Deadlock and Deadlock share some of the same server infrastructure, so blocking Deadlock relays may affect Deadlock matchmaking too.

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=deadlock_server_picker

# Run specific test file
pytest tests/test_firewall.py

# Run excluding integration tests
pytest -m "not integration"
```

### Project Structure

```
deadlock-server-picker/
├── deadlock_server_picker/
│   ├── __init__.py
│   ├── cli.py              # Command-line interface
│   ├── firewall.py         # iptables management
│   ├── models.py           # Data models
│   ├── ping_service.py     # Server ping functionality
│   ├── preset_manager.py   # Preset management
│   ├── regions.py          # Region preset definitions
│   ├── server_fetcher.py   # Steam API client
│   └── tui.py              # Interactive TUI
├── tests/
│   ├── test_cli.py
│   ├── test_firewall.py
│   ├── test_models.py
│   ├── test_ping_service.py
│   ├── test_preset_manager.py
│   ├── test_regions.py
│   └── test_server_fetcher.py
├── pyproject.toml
└── README.md
```

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This project is not affiliated with, authorized, maintained, sponsored, or endorsed by Valve Corporation or any of its affiliates or subsidiaries. This is an independent and unofficial tool.

## Credits

- Inspired by [FN-FAL113's Deadlock Server Picker](https://github.com/FN-FAL113/deadlock-server-picker) for Windows
- Server data provided by Valve's Steam API
