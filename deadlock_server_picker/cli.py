#!/usr/bin/env python3
"""
Deadlock Server Picker CLI - Command-line interface for managing Deadlock server connections.
"""

import argparse
import sys
import os
from typing import Optional

from . import __version__
from .server_fetcher import ServerDataFetcher, ServerFetchError
from .firewall import FirewallManager, FirewallError
from .ping_service import PingService
from .preset_manager import PresetManager, PresetError
from .models import Server, ServerStatus
from .regions import REGION_PRESETS, REGION_ALIASES, get_region_servers


class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def supports_color() -> bool:
    """Check if terminal supports colors."""
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


def colorize(text: str, color: str) -> str:
    """Apply color to text if supported."""
    if supports_color():
        return f"{color}{text}{Colors.RESET}"
    return text


class DeadlockServerPickerCLI:
    """Command-line interface for Deadlock Server Picker."""

    def __init__(self, use_sudo: bool = True, dry_run: bool = False, 
                 clustered: bool = False, config_dir: Optional[str] = None):
        """
        Initialize CLI.
        
        Args:
            use_sudo: Whether to use sudo for firewall operations.
            dry_run: If True, only simulate firewall operations.
            clustered: Whether to use clustered server view.
            config_dir: Custom configuration directory.
        """
        self.dry_run = dry_run
        self.clustered = clustered
        
        self.fetcher = ServerDataFetcher()
        self.firewall = FirewallManager(use_sudo=use_sudo, dry_run=dry_run)
        self.ping_service = PingService()
        self.preset_manager = PresetManager(config_dir=config_dir)
        
        self._servers_loaded = False

    def _ensure_servers_loaded(self) -> bool:
        """Ensure server data is loaded."""
        if self._servers_loaded:
            return True
            
        try:
            print(colorize("Fetching server data from Steam...", Colors.CYAN))
            revision = self.fetcher.fetch()
            print(colorize(f"Server data loaded (revision: {revision})", Colors.GREEN))
            self._servers_loaded = True
            return True
        except ServerFetchError as e:
            print(colorize(f"Error: {e}", Colors.RED))
            return False

    def _get_servers(self) -> dict[str, Server]:
        """Get servers dictionary based on clustered setting."""
        return self.fetcher.get_servers(clustered=self.clustered)

    def _print_server_table(self, servers: list[Server], show_latency: bool = True) -> None:
        """Print servers in a formatted table."""
        if not servers:
            print(colorize("No servers found.", Colors.YELLOW))
            return

        # Calculate column widths
        max_name = max(len(s.display_name) for s in servers)
        max_name = max(max_name, 30)  # Minimum width

        # Header
        header = f"{'Server':<{max_name}}  {'Status':<12}"
        if show_latency:
            header += f"  {'Latency':<12}"
        header += f"  {'IPs':<5}"
        
        print(colorize(header, Colors.BOLD))
        print("-" * len(header))

        # Rows
        for server in sorted(servers, key=lambda s: (s.status.value, s.latency_ms or 9999)):
            name = server.display_name[:max_name]
            
            # Status with color
            status = server.status.value
            if server.status == ServerStatus.BLOCKED:
                status_str = colorize(f"{status:<12}", Colors.RED)
            elif server.status == ServerStatus.AVAILABLE:
                status_str = colorize(f"{status:<12}", Colors.GREEN)
            elif server.status == ServerStatus.TIMEOUT:
                status_str = colorize(f"{status:<12}", Colors.YELLOW)
            else:
                status_str = f"{status:<12}"

            row = f"{name:<{max_name}}  {status_str}"
            
            if show_latency:
                if server.latency_ms is not None:
                    latency = f"{server.latency_ms}ms"
                    if server.latency_ms < 50:
                        latency_str = colorize(f"{latency:<12}", Colors.GREEN)
                    elif server.latency_ms < 100:
                        latency_str = colorize(f"{latency:<12}", Colors.YELLOW)
                    else:
                        latency_str = colorize(f"{latency:<12}", Colors.RED)
                else:
                    latency_str = colorize(f"{'N/A':<12}", Colors.DIM)
                row += f"  {latency_str}"
                
            row += f"  {len(server.ip_addresses):<5}"
            print(row)

    def cmd_list(self, ping: bool = False, blocked_only: bool = False) -> int:
        """
        List all available servers.
        
        Args:
            ping: Whether to ping servers.
            blocked_only: Only show blocked servers.
            
        Returns:
            Exit code.
        """
        if not self._ensure_servers_loaded():
            return 1

        servers = list(self._get_servers().values())
        
        # Update blocked status
        blocked_names = self.firewall.get_blocked_servers()
        for server in servers:
            # Check if any variation of the name is blocked
            name_variants = [
                server.display_name.replace(" ", "_").replace("(", "").replace(")", ""),
                server.name.replace(" ", "_"),
                server.code
            ]
            for variant in name_variants:
                if variant in " ".join(blocked_names) or any(variant.lower() in b.lower() for b in blocked_names):
                    server.status = ServerStatus.BLOCKED
                    break

        if blocked_only:
            servers = [s for s in servers if s.status == ServerStatus.BLOCKED]
            
        if ping:
            print(colorize("Pinging servers...", Colors.CYAN))
            self.ping_service.ping_servers(servers)

        mode = "clustered" if self.clustered else "unclustered"
        print(colorize(f"\nDeadlock Servers ({mode} mode):", Colors.BOLD))
        self._print_server_table(servers, show_latency=ping)
        
        print(f"\nTotal: {len(servers)} servers")
        blocked_count = sum(1 for s in servers if s.status == ServerStatus.BLOCKED)
        if blocked_count:
            print(colorize(f"Blocked: {blocked_count}", Colors.RED))
            
        return 0

    def cmd_block(self, server_names: list[str]) -> int:
        """
        Block specified servers.
        
        Args:
            server_names: List of server names/codes to block.
            
        Returns:
            Exit code.
        """
        if not self._ensure_servers_loaded():
            return 1

        servers_to_block = []
        for name in server_names:
            server = self.fetcher.get_server_by_name(name, clustered=self.clustered)
            if server:
                servers_to_block.append(server)
            else:
                print(colorize(f"Server not found: {name}", Colors.YELLOW))

        if not servers_to_block:
            print(colorize("No valid servers to block.", Colors.RED))
            return 1

        try:
            blocked, already = self.firewall.block_servers(servers_to_block)
            print(colorize(f"Blocked {blocked} server(s)", Colors.GREEN))
            if already:
                print(colorize(f"Already blocked: {already}", Colors.DIM))
            return 0
        except FirewallError as e:
            print(colorize(f"Error: {e}", Colors.RED))
            return 1

    def cmd_unblock(self, server_names: list[str], all_servers: bool = False) -> int:
        """
        Unblock specified servers.
        
        Args:
            server_names: List of server names/codes to unblock.
            all_servers: If True, unblock all servers.
            
        Returns:
            Exit code.
        """
        if all_servers:
            try:
                self.firewall.reset_firewall()
                print(colorize("All servers unblocked.", Colors.GREEN))
                return 0
            except FirewallError as e:
                print(colorize(f"Error: {e}", Colors.RED))
                return 1

        if not self._ensure_servers_loaded():
            return 1

        servers_to_unblock = []
        for name in server_names:
            server = self.fetcher.get_server_by_name(name, clustered=self.clustered)
            if server:
                servers_to_unblock.append(server)
            else:
                print(colorize(f"Server not found: {name}", Colors.YELLOW))

        if not servers_to_unblock:
            print(colorize("No valid servers to unblock.", Colors.RED))
            return 1

        try:
            unblocked, not_blocked = self.firewall.unblock_servers(servers_to_unblock)
            print(colorize(f"Unblocked {unblocked} server(s)", Colors.GREEN))
            if not_blocked:
                print(colorize(f"Not blocked: {not_blocked}", Colors.DIM))
            return 0
        except FirewallError as e:
            print(colorize(f"Error: {e}", Colors.RED))
            return 1

    def cmd_block_all(self) -> int:
        """Block all servers."""
        if not self._ensure_servers_loaded():
            return 1

        servers = list(self._get_servers().values())
        
        try:
            blocked, already = self.firewall.block_servers(servers)
            print(colorize(f"Blocked {blocked} server(s)", Colors.GREEN))
            if already:
                print(colorize(f"Already blocked: {already}", Colors.DIM))
            return 0
        except FirewallError as e:
            print(colorize(f"Error: {e}", Colors.RED))
            return 1

    def cmd_block_except(self, server_names: list[str]) -> int:
        """
        Block all servers except the specified ones.
        
        Args:
            server_names: List of server names/codes to keep unblocked.
            
        Returns:
            Exit code.
        """
        if not self._ensure_servers_loaded():
            return 1

        # Find servers to keep
        keep_codes = set()
        for name in server_names:
            server = self.fetcher.get_server_by_name(name, clustered=self.clustered)
            if server:
                keep_codes.add(server.code)
            else:
                print(colorize(f"Server not found: {name}", Colors.YELLOW))

        if not keep_codes:
            print(colorize("No valid servers specified to keep.", Colors.RED))
            return 1

        # Block all others
        servers = self._get_servers()
        to_block = [s for code, s in servers.items() if code not in keep_codes]
        
        try:
            # First unblock the ones we want to keep
            to_unblock = [s for code, s in servers.items() if code in keep_codes]
            self.firewall.unblock_servers(to_unblock)
            
            # Then block the rest
            blocked, already = self.firewall.block_servers(to_block)
            print(colorize(f"Blocked {blocked} server(s), keeping {len(keep_codes)} unblocked", Colors.GREEN))
            return 0
        except FirewallError as e:
            print(colorize(f"Error: {e}", Colors.RED))
            return 1

    def cmd_ping(self, server_names: Optional[list[str]] = None) -> int:
        """
        Ping servers to measure latency.
        
        Args:
            server_names: Specific servers to ping (or all if None).
            
        Returns:
            Exit code.
        """
        if not self._ensure_servers_loaded():
            return 1

        servers = self._get_servers()
        
        if server_names:
            to_ping = []
            for name in server_names:
                server = self.fetcher.get_server_by_name(name, clustered=self.clustered)
                if server:
                    to_ping.append(server)
                else:
                    print(colorize(f"Server not found: {name}", Colors.YELLOW))
        else:
            to_ping = list(servers.values())

        if not to_ping:
            print(colorize("No servers to ping.", Colors.RED))
            return 1

        print(colorize(f"Pinging {len(to_ping)} server(s)...", Colors.CYAN))
        self.ping_service.ping_servers(to_ping)
        
        self._print_server_table(to_ping, show_latency=True)
        return 0

    def cmd_preset_list(self) -> int:
        """List all presets."""
        presets = self.preset_manager.list_presets(clustered=self.clustered if self.clustered else None)
        
        if not presets:
            print(colorize("No presets found.", Colors.YELLOW))
            return 0

        print(colorize("Saved Presets:", Colors.BOLD))
        print("-" * 50)
        
        for preset in presets:
            mode = "clustered" if preset.clustered else "unclustered"
            print(f"  {colorize(preset.name, Colors.CYAN)} ({len(preset.servers)} servers, {mode})")
            for server in preset.servers[:5]:  # Show first 5
                print(f"    - {server}")
            if len(preset.servers) > 5:
                print(f"    ... and {len(preset.servers) - 5} more")
                
        return 0

    def cmd_preset_create(self, name: str, servers: list[str]) -> int:
        """
        Create a new preset.
        
        Args:
            name: Preset name.
            servers: List of server names/codes.
            
        Returns:
            Exit code.
        """
        if not self._ensure_servers_loaded():
            return 1

        # Validate servers
        valid_servers = []
        for server_name in servers:
            server = self.fetcher.get_server_by_name(server_name, clustered=self.clustered)
            if server:
                valid_servers.append(server.code)
            else:
                print(colorize(f"Server not found: {server_name}", Colors.YELLOW))

        if not valid_servers:
            print(colorize("No valid servers for preset.", Colors.RED))
            return 1

        try:
            preset = self.preset_manager.add_preset(name, valid_servers, clustered=self.clustered)
            print(colorize(f"Created preset '{preset.name}' with {len(preset.servers)} servers", Colors.GREEN))
            return 0
        except PresetError as e:
            print(colorize(f"Error: {e}", Colors.RED))
            return 1

    def cmd_preset_delete(self, name: str) -> int:
        """
        Delete a preset.
        
        Args:
            name: Preset name to delete.
            
        Returns:
            Exit code.
        """
        if self.preset_manager.delete_preset(name):
            print(colorize(f"Deleted preset '{name}'", Colors.GREEN))
            return 0
        else:
            print(colorize(f"Preset '{name}' not found", Colors.RED))
            return 1

    def cmd_preset_apply(self, name: str, block_others: bool = False) -> int:
        """
        Apply a preset (unblock preset servers, optionally block others).
        
        Args:
            name: Preset name.
            block_others: If True, block all servers not in preset.
            
        Returns:
            Exit code.
        """
        preset = self.preset_manager.get_preset(name)
        if not preset:
            print(colorize(f"Preset '{name}' not found", Colors.RED))
            return 1

        if not self._ensure_servers_loaded():
            return 1

        # Get servers from preset
        servers = self._get_servers()
        preset_servers = []
        
        for code in preset.servers:
            if code in servers:
                preset_servers.append(servers[code])
            else:
                # Try to find by name
                server = self.fetcher.get_server_by_name(code, clustered=self.clustered)
                if server:
                    preset_servers.append(server)

        if block_others:
            return self.cmd_block_except([s.code for s in preset_servers])
        else:
            # Just unblock preset servers
            try:
                unblocked, _ = self.firewall.unblock_servers(preset_servers)
                print(colorize(f"Unblocked {unblocked} server(s) from preset '{name}'", Colors.GREEN))
                return 0
            except FirewallError as e:
                print(colorize(f"Error: {e}", Colors.RED))
                return 1

    def cmd_apply(self) -> int:
        """Apply config preferences (always_block, never_block, default_region)."""
        from .config import ConfigManager
        
        config_manager = ConfigManager()
        config = config_manager.load()
        
        if not self._ensure_servers_loaded():
            return 1
        
        print(colorize("Applying configuration preferences...", Colors.CYAN))
        
        servers = self._get_servers()
        applied = []
        
        # Auto-apply always_block servers
        if config.always_block:
            to_block = []
            for code in config.always_block:
                server = self.fetcher.get_server_by_name(code, clustered=self.clustered)
                if server:
                    to_block.append(server)
            
            if to_block:
                try:
                    blocked, _ = self.firewall.block_servers(to_block)
                    if blocked > 0:
                        applied.append(f"blocked {blocked} always_block servers")
                except FirewallError as e:
                    print(colorize(f"Error blocking: {e}", Colors.RED))
        
        # Auto-apply never_block servers (unblock if blocked)
        if config.never_block:
            to_unblock = []
            for code in config.never_block:
                server = self.fetcher.get_server_by_name(code, clustered=self.clustered)
                if server:
                    to_unblock.append(server)
            
            if to_unblock:
                try:
                    unblocked, _ = self.firewall.unblock_servers(to_unblock)
                    if unblocked > 0:
                        applied.append(f"unblocked {unblocked} never_block servers")
                except FirewallError as e:
                    print(colorize(f"Error unblocking: {e}", Colors.RED))
        
        # Apply default region
        if config.default_region:
            region_servers = get_region_servers(config.default_region)
            if region_servers:
                to_block = [s for code, s in servers.items() 
                           if code not in region_servers and code not in config.never_block]
                to_unblock = [s for code, s in servers.items() 
                             if code in region_servers and code not in config.always_block]
                
                try:
                    if to_unblock:
                        self.firewall.unblock_servers(to_unblock)
                    if to_block:
                        self.firewall.block_servers(to_block)
                    applied.append(f"applied region {config.default_region}")
                except FirewallError as e:
                    print(colorize(f"Error applying region: {e}", Colors.RED))
        
        if applied:
            print(colorize(f"✓ Applied: {', '.join(applied)}", Colors.GREEN))
        else:
            print(colorize("No preferences configured to apply.", Colors.YELLOW))
            print(colorize("Use 'config set default_region <region>' to set preferences.", Colors.DIM))
        
        return 0

    def cmd_status(self) -> int:
        """Show current status and blocked servers."""
        # Check firewall permissions
        has_perm, msg = self.firewall.check_permissions()
        
        print(colorize("Deadlock Server Picker Status", Colors.BOLD))
        print("-" * 40)
        
        # Firewall status
        if has_perm:
            print(f"Firewall access: {colorize('OK', Colors.GREEN)}")
        else:
            print(f"Firewall access: {colorize('DENIED', Colors.RED)}")
            print(f"  {msg}")

        # Mode
        mode = "clustered" if self.clustered else "unclustered"
        print(f"Server mode: {colorize(mode, Colors.CYAN)}")
        
        # Dry run
        if self.dry_run:
            print(f"Mode: {colorize('DRY RUN', Colors.YELLOW)}")

        # Blocked servers
        blocked = self.firewall.get_blocked_servers()
        print(f"\nBlocked servers: {len(blocked)}")
        if blocked:
            for name in blocked[:10]:
                print(f"  - {colorize(name, Colors.RED)}")
            if len(blocked) > 10:
                print(f"  ... and {len(blocked) - 10} more")

        # Presets
        presets = self.preset_manager.list_presets()
        print(f"\nSaved presets: {len(presets)}")
        
        return 0 if has_perm else 1

    def cmd_reset(self) -> int:
        """Reset all firewall rules."""
        try:
            self.firewall.reset_firewall()
            print(colorize("All Deadlock Server Picker firewall rules removed.", Colors.GREEN))
            return 0
        except FirewallError as e:
            print(colorize(f"Error: {e}", Colors.RED))
            return 1

    def cmd_regions(self) -> int:
        """List available regions."""
        print(colorize("Available Region Presets:", Colors.BOLD))
        print("-" * 60)
        
        shown_regions = set()
        for alias, region_name in sorted(REGION_ALIASES.items()):
            if region_name not in shown_regions:
                shown_regions.add(region_name)
                region_data = REGION_PRESETS[region_name]
                alias_str = colorize(f"{alias:<6}", Colors.YELLOW)
                region_str = colorize(f"{region_name:<20}", Colors.CYAN)
                print(f"  {alias_str} {region_str} {region_data['description']} ({len(region_data['servers'])} servers)")
        
        print(f"\nUsage examples:")
        print(f"  deadlock-server-picker allow-region na      # Allow only North America")
        print(f"  deadlock-server-picker block-region cn      # Block China servers")
        print(f"  deadlock-server-picker list-region eu       # List European servers")
        return 0

    def cmd_list_region(self, region: str, ping: bool = False) -> int:
        """List servers in a specific region."""
        region_servers = get_region_servers(region)
        if not region_servers:
            print(colorize(f"Unknown region: {region}", Colors.RED))
            print(colorize("Use 'deadlock-server-picker regions' to see available regions", Colors.DIM))
            return 1
        
        if not self._ensure_servers_loaded():
            return 1
        
        servers = self._get_servers()
        filtered = [s for code, s in servers.items() if code in region_servers]
        
        # Update blocked status
        blocked_names = self.firewall.get_blocked_servers()
        for server in filtered:
            name_variants = [
                server.display_name.replace(" ", "_").replace("(", "").replace(")", ""),
                server.name.replace(" ", "_"),
                server.code
            ]
            for variant in name_variants:
                if variant in " ".join(blocked_names) or any(variant.lower() in b.lower() for b in blocked_names):
                    server.status = ServerStatus.BLOCKED
                    break
        
        if ping:
            print(colorize("Pinging servers...", Colors.CYAN))
            self.ping_service.ping_servers(filtered)
        
        print(colorize(f"\nServers in {region}:", Colors.BOLD))
        self._print_server_table(filtered, show_latency=ping)
        
        blocked_count = sum(1 for s in filtered if s.status == ServerStatus.BLOCKED)
        print(f"\nTotal: {len(filtered)} servers")
        if blocked_count:
            print(colorize(f"Blocked: {blocked_count}", Colors.RED))
        
        return 0

    def cmd_allow_region(self, region: str) -> int:
        """Allow only servers in a specific region (block all others)."""
        region_servers = get_region_servers(region)
        if not region_servers:
            print(colorize(f"Unknown region: {region}", Colors.RED))
            return 1
        
        if not self._ensure_servers_loaded():
            return 1
        
        servers = self._get_servers()
        
        # Block servers NOT in region
        to_block = [s for code, s in servers.items() if code not in region_servers]
        # Unblock servers IN region
        to_unblock = [s for code, s in servers.items() if code in region_servers]
        
        try:
            # First unblock region servers
            if to_unblock:
                self.firewall.unblock_servers(to_unblock)
            
            # Then block others
            blocked, already = self.firewall.block_servers(to_block)
            print(colorize(f"Allowed only {region}: blocked {blocked} servers, {len(to_unblock)} allowed", Colors.GREEN))
            return 0
        except FirewallError as e:
            print(colorize(f"Error: {e}", Colors.RED))
            return 1

    def cmd_block_region(self, region: str) -> int:
        """Block all servers in a specific region."""
        region_servers = get_region_servers(region)
        if not region_servers:
            print(colorize(f"Unknown region: {region}", Colors.RED))
            return 1
        
        if not self._ensure_servers_loaded():
            return 1
        
        servers = self._get_servers()
        to_block = [s for code, s in servers.items() if code in region_servers]
        
        try:
            blocked, already = self.firewall.block_servers(to_block)
            print(colorize(f"Blocked {blocked} servers in {region}", Colors.GREEN))
            if already:
                print(colorize(f"Already blocked: {already}", Colors.DIM))
            return 0
        except FirewallError as e:
            print(colorize(f"Error: {e}", Colors.RED))
            return 1

    def cmd_unblock_region(self, region: str) -> int:
        """Unblock all servers in a specific region."""
        region_servers = get_region_servers(region)
        if not region_servers:
            print(colorize(f"Unknown region: {region}", Colors.RED))
            return 1
        
        if not self._ensure_servers_loaded():
            return 1
        
        servers = self._get_servers()
        to_unblock = [s for code, s in servers.items() if code in region_servers]
        
        try:
            unblocked, not_blocked = self.firewall.unblock_servers(to_unblock)
            print(colorize(f"Unblocked {unblocked} servers in {region}", Colors.GREEN))
            return 0
        except FirewallError as e:
            print(colorize(f"Error: {e}", Colors.RED))
            return 1

    def cmd_config_show(self) -> int:
        """Show current configuration."""
        from .config import ConfigManager
        
        config_mgr = ConfigManager(self.preset_manager.config_dir)
        config = config_mgr.load()
        
        print(colorize("Current Configuration:", Colors.BOLD))
        print("-" * 40)
        print(f"  default_region:     {config.default_region or '(not set)'}")
        print(f"  auto_reset_on_exit: {config.auto_reset_on_exit}")
        print(f"  ping_timeout:       {config.ping_timeout}s")
        print(f"  clustered:          {config.clustered}")
        print(f"  use_sudo:           {config.use_sudo}")
        print(f"  favorites:          {', '.join(config.favorites) or '(none)'}")
        print(f"  always_block:       {', '.join(config.always_block) or '(none)'}")
        print(f"  never_block:        {', '.join(config.never_block) or '(none)'}")
        print(f"\nConfig file: {config_mgr.config_path}")
        return 0

    def cmd_config_set(self, key: str, value: str) -> int:
        """Set a configuration value."""
        from .config import ConfigManager, Config
        
        config_mgr = ConfigManager(self.preset_manager.config_dir)
        config = config_mgr.load()
        
        if not hasattr(config, key):
            print(colorize(f"Unknown config key: {key}", Colors.RED))
            print(colorize("Valid keys: default_region, auto_reset_on_exit, ping_timeout, clustered, use_sudo", Colors.DIM))
            return 1
        
        # Convert value to appropriate type
        current = getattr(config, key)
        try:
            if isinstance(current, bool):
                value = value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(current, float):
                value = float(value)
            elif isinstance(current, int):
                value = int(value)
            elif isinstance(current, list):
                value = [v.strip() for v in value.split(',') if v.strip()]
            
            setattr(config, key, value)
            config_mgr.save(config)
            print(colorize(f"Set {key} = {value}", Colors.GREEN))
            return 0
        except (ValueError, TypeError) as e:
            print(colorize(f"Invalid value for {key}: {e}", Colors.RED))
            return 1

    def cmd_config_reset(self) -> int:
        """Reset configuration to defaults."""
        from .config import ConfigManager
        
        config_mgr = ConfigManager(self.preset_manager.config_dir)
        config_mgr.reset()
        print(colorize("Configuration reset to defaults", Colors.GREEN))
        return 0

    def cmd_config_path(self) -> int:
        """Show configuration file path."""
        from .config import ConfigManager
        
        config_mgr = ConfigManager(self.preset_manager.config_dir)
        print(config_mgr.config_path)
        return 0

    def cmd_save_rules(self) -> int:
        """Show command to persist firewall rules."""
        save_cmd = self.firewall.get_save_command()
        print(colorize("To persist firewall rules across reboots:", Colors.BOLD))
        print()
        print(f"  {save_cmd}")
        print()
        print(colorize("Note: You may need to install iptables-persistent (Debian/Ubuntu)", Colors.DIM))
        print(colorize("      or enable iptables.service (Arch/systemd)", Colors.DIM))
        return 0


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="deadlock-server-picker",
        description="Deadlock Server Picker for Linux - Block/unblock game server relays",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  deadlock-server-picker list                    # List all servers
  deadlock-server-picker list --ping             # List with latency
  deadlock-server-picker block "US East"         # Block a server
  deadlock-server-picker unblock --all           # Unblock all
  deadlock-server-picker block-except sgp sea    # Block all except Singapore and SEA
  deadlock-server-picker preset create my_preset sgp hkg  # Create preset
  deadlock-server-picker preset apply my_preset --block-others  # Apply preset
        """
    )
    
    # Global options
    parser.add_argument("--no-sudo", action="store_true",
                       help="Don't use sudo for firewall commands")
    parser.add_argument("--dry-run", action="store_true",
                       help="Simulate firewall operations without making changes")
    parser.add_argument("--clustered", "-c", action="store_true",
                       help="Use clustered server view")
    parser.add_argument("--config-dir", type=str,
                       help="Custom configuration directory")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List available servers")
    list_parser.add_argument("--ping", "-p", action="store_true",
                            help="Ping servers to show latency")
    list_parser.add_argument("--blocked", "-b", action="store_true",
                            help="Only show blocked servers")

    # Block command
    block_parser = subparsers.add_parser("block", help="Block specified servers")
    block_parser.add_argument("servers", nargs="+", help="Server names or codes to block")

    # Unblock command
    unblock_parser = subparsers.add_parser("unblock", help="Unblock specified servers")
    unblock_parser.add_argument("servers", nargs="*", help="Server names or codes to unblock")
    unblock_parser.add_argument("--all", "-a", action="store_true",
                               help="Unblock all servers")

    # Block-all command
    subparsers.add_parser("block-all", help="Block all servers")

    # Block-except command
    except_parser = subparsers.add_parser("block-except", 
                                          help="Block all servers except specified")
    except_parser.add_argument("servers", nargs="+", help="Servers to keep unblocked")

    # Ping command
    ping_parser = subparsers.add_parser("ping", help="Ping servers")
    ping_parser.add_argument("servers", nargs="*", help="Specific servers to ping")

    # Preset commands
    preset_parser = subparsers.add_parser("preset", help="Manage presets")
    preset_sub = preset_parser.add_subparsers(dest="preset_command")

    preset_sub.add_parser("list", help="List presets")
    
    create_preset = preset_sub.add_parser("create", help="Create preset")
    create_preset.add_argument("name", help="Preset name")
    create_preset.add_argument("servers", nargs="+", help="Servers to include")
    
    delete_preset = preset_sub.add_parser("delete", help="Delete preset")
    delete_preset.add_argument("name", help="Preset name")
    
    apply_preset = preset_sub.add_parser("apply", help="Apply preset")
    apply_preset.add_argument("name", help="Preset name")
    apply_preset.add_argument("--block-others", action="store_true",
                             help="Block all servers not in preset")

    # Status command
    subparsers.add_parser("status", help="Show current status")

    # Reset command
    subparsers.add_parser("reset", help="Reset all firewall rules")

    # Apply command
    subparsers.add_parser("apply", help="Apply config preferences (for systemd service)")

    # Region commands
    subparsers.add_parser("regions", help="List available region presets")
    
    list_region = subparsers.add_parser("list-region", help="List servers in a region")
    list_region.add_argument("region", help="Region name or alias (e.g., na, eu, asia)")
    list_region.add_argument("--ping", "-p", action="store_true",
                            help="Ping servers to show latency")
    
    allow_region = subparsers.add_parser("allow-region", 
                                          help="Allow only specified region (block all others)")
    allow_region.add_argument("region", help="Region name or alias")
    
    block_region = subparsers.add_parser("block-region", help="Block all servers in a region")
    block_region.add_argument("region", help="Region name or alias")
    
    unblock_region = subparsers.add_parser("unblock-region", help="Unblock all servers in a region")
    unblock_region.add_argument("region", help="Region name or alias")

    # TUI command
    subparsers.add_parser("tui", help="Launch interactive TUI interface")

    # Config command
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_sub = config_parser.add_subparsers(dest="config_command")
    config_sub.add_parser("show", help="Show current configuration")
    config_set = config_sub.add_parser("set", help="Set a configuration value")
    config_set.add_argument("key", help="Configuration key")
    config_set.add_argument("value", help="Value to set")
    config_sub.add_parser("reset", help="Reset configuration to defaults")
    config_sub.add_parser("path", help="Show configuration file path")
    
    # Save rules command
    subparsers.add_parser("save-rules", help="Show command to persist firewall rules")

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Create CLI instance
    cli = DeadlockServerPickerCLI(
        use_sudo=not args.no_sudo,
        dry_run=args.dry_run,
        clustered=args.clustered,
        config_dir=args.config_dir
    )

    try:
        # Route to command
        if args.command == "list":
            return cli.cmd_list(ping=args.ping, blocked_only=args.blocked)
        elif args.command == "block":
            return cli.cmd_block(args.servers)
        elif args.command == "unblock":
            if args.all:
                return cli.cmd_unblock([], all_servers=True)
            elif args.servers:
                return cli.cmd_unblock(args.servers)
            else:
                print(colorize("Specify servers to unblock or use --all", Colors.RED))
                return 1
        elif args.command == "block-all":
            return cli.cmd_block_all()
        elif args.command == "block-except":
            return cli.cmd_block_except(args.servers)
        elif args.command == "ping":
            return cli.cmd_ping(args.servers if args.servers else None)
        elif args.command == "preset":
            if args.preset_command == "list":
                return cli.cmd_preset_list()
            elif args.preset_command == "create":
                return cli.cmd_preset_create(args.name, args.servers)
            elif args.preset_command == "delete":
                return cli.cmd_preset_delete(args.name)
            elif args.preset_command == "apply":
                return cli.cmd_preset_apply(args.name, args.block_others)
            else:
                parser.parse_args(["preset", "--help"])
                return 0
        elif args.command == "status":
            return cli.cmd_status()
        elif args.command == "reset":
            return cli.cmd_reset()
        elif args.command == "apply":
            return cli.cmd_apply()
        elif args.command == "regions":
            return cli.cmd_regions()
        elif args.command == "list-region":
            return cli.cmd_list_region(args.region, ping=args.ping)
        elif args.command == "allow-region":
            return cli.cmd_allow_region(args.region)
        elif args.command == "block-region":
            return cli.cmd_block_region(args.region)
        elif args.command == "unblock-region":
            return cli.cmd_unblock_region(args.region)
        elif args.command == "tui":
            from .tui import run_tui
            run_tui(dry_run=args.dry_run)
            return 0
        elif args.command == "config":
            if args.config_command == "show":
                return cli.cmd_config_show()
            elif args.config_command == "set":
                return cli.cmd_config_set(args.key, args.value)
            elif args.config_command == "reset":
                return cli.cmd_config_reset()
            elif args.config_command == "path":
                return cli.cmd_config_path()
            else:
                parser.parse_args(["config", "--help"])
                return 0
        elif args.command == "save-rules":
            return cli.cmd_save_rules()
        else:
            parser.print_help()
            return 0
            
    except KeyboardInterrupt:
        print(colorize("\nOperation cancelled.", Colors.YELLOW))
        return 130
    except Exception as e:
        print(colorize(f"Unexpected error: {e}", Colors.RED))
        return 1


if __name__ == "__main__":
    sys.exit(main())
