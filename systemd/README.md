# Systemd Service for Deadlock Server Picker

This directory contains systemd service files for automatically applying
server blocking rules on system boot.

## Installation

### System Service (Recommended)

For a system-wide service that applies rules at boot:

```bash
# Copy the service file
sudo cp deadlock-server-picker.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable the service (start at boot)
sudo systemctl enable deadlock-server-picker

# Start it now
sudo systemctl start deadlock-server-picker

# Check status
sudo systemctl status deadlock-server-picker
```

### User Service (Alternative)

If you prefer a user service (runs when you log in):

```bash
# Create user systemd directory
mkdir -p ~/.config/systemd/user/

# Copy the user service file
cp deadlock-server-picker.user.service ~/.config/systemd/user/deadlock-server-picker.service

# Reload user systemd
systemctl --user daemon-reload

# Enable the service
systemctl --user enable deadlock-server-picker

# Start it now
systemctl --user start deadlock-server-picker
```

Note: User services require polkit configuration for passwordless sudo.

## Configuration

Before enabling the service, configure your preferred region:

```bash
# Set your default region
deadlock-server-picker config set default_region eu

# Or add servers to always block
deadlock-server-picker config set always_block "sgp,hkg,tyo"
```

The service will apply these rules on boot.

## Uninstallation

```bash
# Stop and disable
sudo systemctl stop deadlock-server-picker
sudo systemctl disable deadlock-server-picker

# Remove the service file
sudo rm /etc/systemd/system/deadlock-server-picker.service

# Reload systemd
sudo systemctl daemon-reload
```

## Troubleshooting

### Check service logs
```bash
journalctl -u deadlock-server-picker
```

### Check if rules are applied
```bash
sudo iptables -L DEADLOCK_SERVER_PICKER -n
# or for nftables
sudo nft list table inet deadlock_server_picker
```

### Manual apply/reset
```bash
deadlock-server-picker apply
deadlock-server-picker reset
```
