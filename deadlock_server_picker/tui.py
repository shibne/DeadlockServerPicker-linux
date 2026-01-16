"""
TUI (Text User Interface) for Deadlock Server Picker.
Interactive terminal interface with color-coded server status.
"""

import os
import subprocess
import sys
from typing import Optional

from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED
from rich.layout import Layout
from rich.live import Live
from rich.columns import Columns

from .models import Server, ServerStatus
from .server_fetcher import ServerDataFetcher
from .firewall import FirewallManager
from .ping_service import PingService
from .preset_manager import PresetManager
from .regions import REGION_PRESETS, REGION_ALIASES, get_region_servers


class ServerPickerTUI:
    """Interactive TUI for Deadlock Server Picker."""
    
    def __init__(self, dry_run: bool = False):
        self.console = Console()
        self.fetcher = ServerDataFetcher()
        self.firewall = FirewallManager(dry_run=dry_run)
        self.ping_service = PingService()
        self.preset_manager = PresetManager()
        self.dry_run = dry_run
        self.servers: list[Server] = []
        self.server_status: dict[str, bool] = {}  # code -> blocked
        self.ping_results: dict[str, Optional[float]] = {}  # code -> latency
        self.output_lines: list[Text] = []  # Dynamic output buffer
        self.max_output_lines = 20  # Max lines to keep in output buffer
    
    def _check_sudo_access(self) -> bool:
        """
        Check and cache sudo access before starting TUI.
        This prompts for password in a visible way.
        """
        if self.dry_run:
            return True
        
        self.console.print("[cyan]Checking sudo access for firewall management...[/]")
        self.console.print("[dim]You may be prompted for your password.[/]\n")
        
        # Run a simple sudo command to cache credentials
        # Using sys.stdout/stderr to ensure password prompt is visible
        try:
            result = subprocess.run(
                ["sudo", "-v"],
                check=False,
            )
            if result.returncode == 0:
                self.console.print("[green]✓ Sudo access granted[/]\n")
                return True
            else:
                self.console.print("[red]✗ Sudo access denied[/]")
                return False
        except Exception as e:
            self.console.print(f"[red]Error checking sudo: {e}[/]")
            return False
    
    def initialize(self):
        """Load servers and check their status."""
        with self.console.status("[bold blue]Fetching server list from Steam...[/]"):
            self.fetcher.fetch()
            self.servers = list(self.fetcher.get_servers().values())
        
        with self.console.status("[bold blue]Checking firewall status...[/]"):
            blocked_names = self.firewall.get_blocked_servers()
            for server in self.servers:
                # Check if server is in blocked list
                is_blocked = any(
                    server.code in name or server.name.replace(" ", "_") in name
                    for name in blocked_names
                )
                self.server_status[server.code] = is_blocked
    
    def _create_status_indicator(self, blocked: bool) -> Text:
        """Create a colored status indicator."""
        if blocked:
            return Text("● BLOCKED", style="bold red")
        else:
            return Text("● ALLOWED", style="bold green")
    
    def _create_server_table(self, servers: list[Server], title: str = "Servers") -> Table:
        """Create a table showing server status."""
        table = Table(
            title=title,
            box=ROUNDED,
            show_header=True,
            header_style="bold cyan",
            border_style="blue",
        )
        
        table.add_column("Code", style="cyan", width=8)
        table.add_column("Name", style="white", width=35)
        table.add_column("Status", width=12)
        table.add_column("Ping", justify="right", width=10)
        table.add_column("IPs", justify="right", width=5)
        
        for server in servers:
            blocked = self.server_status.get(server.code, False)
            status = self._create_status_indicator(blocked)
            
            ping = self.ping_results.get(server.code)
            # Check if ping is a valid number (handles Mock objects in tests)
            if ping is not None and isinstance(ping, (int, float)):
                if ping < 50:
                    ping_text = Text(f"{ping:.0f}ms", style="green")
                elif ping < 100:
                    ping_text = Text(f"{ping:.0f}ms", style="yellow")
                else:
                    ping_text = Text(f"{ping:.0f}ms", style="red")
            else:
                ping_text = Text("-", style="dim")
            
            table.add_row(
                server.code,
                server.name,
                status,
                ping_text,
                str(len(server.relays)),
            )
        
        return table
    
    def _create_region_table(self) -> Table:
        """Create a table showing available regions."""
        table = Table(
            title="Available Regions",
            box=ROUNDED,
            show_header=True,
            header_style="bold magenta",
            border_style="magenta",
        )
        
        table.add_column("Alias", style="yellow", width=8)
        table.add_column("Region", style="white", width=20)
        table.add_column("Description", style="dim", width=35)
        table.add_column("Servers", justify="right", width=8)
        
        shown_regions = set()
        for alias, region_name in sorted(REGION_ALIASES.items()):
            if region_name not in shown_regions:
                shown_regions.add(region_name)
                region_data = REGION_PRESETS[region_name]
                table.add_row(
                    alias,
                    region_name,
                    region_data["description"],
                    str(len(region_data["servers"])),
                )
        
        return table
    
    def _get_summary_text(self) -> Text:
        """Get summary statistics as Text."""
        total = len(self.servers)
        blocked = sum(1 for s in self.servers if self.server_status.get(s.code, False))
        allowed = total - blocked
        
        summary = Text()
        summary.append("Servers: ", style="bold")
        summary.append(f"{total}", style="cyan")
        summary.append(" | ")
        summary.append("Allowed: ", style="bold")
        summary.append(f"{allowed}", style="bold green")
        summary.append(" | ")
        summary.append("Blocked: ", style="bold")
        summary.append(f"{blocked}", style="bold red")
        
        if self.dry_run:
            summary.append(" | ")
            summary.append("DRY RUN", style="bold yellow")
        
        return summary
    
    def _get_blocked_servers_list(self) -> Text:
        """Get a compact list of blocked servers."""
        blocked = [s for s in self.servers if self.server_status.get(s.code, False)]
        
        if not blocked:
            return Text("None", style="dim green")
        
        result = Text()
        codes = [s.code for s in blocked[:12]]  # Show max 12
        result.append(", ".join(codes), style="red")
        if len(blocked) > 12:
            result.append(f" +{len(blocked) - 12} more", style="dim red")
        
        return result
    
    def _create_static_header(self) -> Panel:
        """Create the static header panel with current status."""
        # Build the status display
        content = Text()
        
        # Title line
        content.append("DEADLOCK SERVER PICKER", style="bold blue")
        if self.dry_run:
            content.append("  [DRY RUN]", style="bold yellow")
        content.append("\n\n")
        
        # Stats line
        total = len(self.servers)
        blocked = sum(1 for s in self.servers if self.server_status.get(s.code, False))
        allowed = total - blocked
        
        content.append("Total: ", style="bold")
        content.append(f"{total}", style="cyan")
        content.append("  │  ", style="dim")
        content.append("Allowed: ", style="bold")
        content.append(f"{allowed}", style="bold green")
        content.append("  │  ", style="dim")
        content.append("Blocked: ", style="bold")
        content.append(f"{blocked}", style="bold red")
        content.append("\n")
        
        # Blocked servers line
        content.append("Blocked: ", style="bold")
        content.append_text(self._get_blocked_servers_list())
        
        return Panel(
            content,
            border_style="blue",
            padding=(0, 1),
        )
    
    def _add_output(self, text: str, style: str = "white"):
        """Add a line to the output buffer."""
        line = Text(text, style=style)
        self.output_lines.append(line)
        # Trim to max lines
        if len(self.output_lines) > self.max_output_lines:
            self.output_lines = self.output_lines[-self.max_output_lines:]
    
    def _clear_output(self):
        """Clear the output buffer."""
        self.output_lines = []
    
    def _get_output_panel(self) -> Panel:
        """Get the dynamic output panel."""
        if not self.output_lines:
            content = Text("Type 'help' for commands, 'quit' to exit", style="dim")
        else:
            content = Text()
            for i, line in enumerate(self.output_lines):
                content.append_text(line)
                if i < len(self.output_lines) - 1:
                    content.append("\n")
        
        return Panel(
            content,
            title="Output",
            border_style="green",
            padding=(0, 1),
        )
    
    def _print_header(self):
        """Print the TUI header with status bar."""
        # Clear screen for fresh display
        self.console.clear()
        
        # Header
        header = Text("Deadlock Server Picker", style="bold blue", justify="center")
        self.console.print(Panel(header, border_style="blue"))
        
        # Status bar
        self.console.print(self._get_summary_text())
        self.console.print()
    
    def _print_help(self):
        """Print help commands (legacy, for tests)."""
        self._show_help()
    
    def _show_help(self):
        """Show help commands in output panel."""
        self._clear_output()
        self._add_output("─── Available Commands ───", "green")
        
        help_lines = [
            ("list [region]", "Show servers (optionally filter by region)"),
            ("regions", "Show available region presets"),
            ("block <code>", "Block a server by code"),
            ("unblock <code>", "Unblock a server by code"),
            ("allow <region>", "Allow only servers in region"),
            ("block-region <region>", "Block all servers in region"),
            ("unblock-region <region>", "Unblock all servers in region"),
            ("ping [region]", "Ping servers and show latency"),
            ("status", "Show current status"),
            ("reset", "Unblock all servers"),
            ("clear", "Clear output"),
            ("help", "Show this help"),
            ("quit", "Exit"),
        ]
        
        for cmd, desc in help_lines:
            self._add_output(f"  {cmd:25} {desc}", "yellow")
    
    def show_servers(self, filter_region: Optional[str] = None) -> bool:
        """Display server list. Returns True if successful."""
        if filter_region:
            region_servers = get_region_servers(filter_region)
            if not region_servers:
                self._add_output(f"Unknown region: {filter_region}", "red")
                self._add_output("Use 'regions' to see available regions", "dim")
                return False
            filtered = [s for s in self.servers if s.code in region_servers]
            title = f"Servers in {filter_region.upper()}"
        else:
            filtered = self.servers
            title = "All Servers"
        
        if not filtered:
            self._add_output("No servers found", "yellow")
            return False
        
        # Clear output and add server list
        self._clear_output()
        self._add_output(f"─── {title} ({len(filtered)}) ───", "cyan")
        
        for server in filtered:
            blocked = self.server_status.get(server.code, False)
            ping = self.ping_results.get(server.code)
            
            status_icon = "●" if blocked else "○"
            status_color = "red" if blocked else "green"
            
            if ping is not None and isinstance(ping, (int, float)):
                ping_str = f"{ping:.0f}ms"
            else:
                ping_str = "-"
            
            self._add_output(f"  {status_icon} {server.code:8} {server.name:30} {ping_str:>8}", status_color)
        
        self._add_output(f"─── ● = blocked, ○ = allowed ───", "dim")
        return True
    
    def show_regions(self) -> bool:
        """Display available regions. Returns True."""
        self._clear_output()
        self._add_output("─── Available Regions ───", "magenta")
        
        shown_regions = set()
        for alias, region_name in sorted(REGION_ALIASES.items()):
            if region_name not in shown_regions:
                shown_regions.add(region_name)
                region_data = REGION_PRESETS[region_name]
                server_count = len(region_data["servers"])
                self._add_output(f"  {alias:6} {region_name:15} ({server_count} servers) - {region_data['description']}", "yellow")
        
        return True
    
    def block_server(self, code: str) -> bool:
        """Block a single server by code. Returns True if successful."""
        server = self.fetcher.get_server_by_name(code)
        if not server:
            self._add_output(f"Server not found: {code}", "red")
            return False
        
        if self.server_status.get(server.code, False):
            self._add_output(f"Server {code} is already blocked", "yellow")
            return True
        
        blocked, _ = self.firewall.block_servers([server])
        
        if blocked > 0:
            self.server_status[server.code] = True
            self._add_output(f"✓ Blocked {server.name}", "green")
            return True
        else:
            self._add_output(f"✗ Failed to block {server.name}", "red")
            return False
    
    def unblock_server(self, code: str) -> bool:
        """Unblock a single server by code. Returns True if successful."""
        server = self.fetcher.get_server_by_name(code)
        if not server:
            self._add_output(f"Server not found: {code}", "red")
            return False
        
        if not self.server_status.get(server.code, False):
            self._add_output(f"Server {code} is not blocked", "yellow")
            return True
        
        unblocked, _ = self.firewall.unblock_servers([server])
        
        if unblocked > 0:
            self.server_status[server.code] = False
            self._add_output(f"✓ Unblocked {server.name}", "green")
            return True
        else:
            self._add_output(f"✗ Failed to unblock {server.name}", "red")
            return False
    
    def allow_only_region(self, region: str) -> bool:
        """Block all servers except those in the specified region. Returns True if successful."""
        region_servers = get_region_servers(region)
        if not region_servers:
            self._add_output(f"Unknown region: {region}", "red")
            self._add_output("Use 'regions' to see available regions", "dim")
            return False
        
        to_block = [s for s in self.servers if s.code not in region_servers]
        to_unblock = [s for s in self.servers if s.code in region_servers]
        
        self._add_output(f"Allowing only {region.upper()} ({len(to_unblock)} servers)", "cyan")
        
        # First unblock region servers
        if to_unblock:
            self.firewall.unblock_servers(to_unblock)
            for server in to_unblock:
                self.server_status[server.code] = False
        
        # Then block others
        if to_block:
            self.firewall.block_servers(to_block)
            for server in to_block:
                self.server_status[server.code] = True
        
        blocked = sum(1 for s in self.servers if self.server_status.get(s.code, False))
        self._add_output(f"✓ Done! {blocked} servers blocked", "green")
        return True
    
    def block_region(self, region: str) -> bool:
        """Block all servers in a region. Returns True if successful."""
        region_servers = get_region_servers(region)
        if not region_servers:
            self._add_output(f"Unknown region: {region}", "red")
            return False
        
        to_block = [s for s in self.servers if s.code in region_servers]
        
        self.firewall.block_servers(to_block)
        for server in to_block:
            self.server_status[server.code] = True
        
        self._add_output(f"✓ Blocked {len(to_block)} servers in {region.upper()}", "green")
        return True
    
    def unblock_region(self, region: str) -> bool:
        """Unblock all servers in a region. Returns True if successful."""
        region_servers = get_region_servers(region)
        if not region_servers:
            self._add_output(f"Unknown region: {region}", "red")
            return False
        
        to_unblock = [s for s in self.servers if s.code in region_servers]
        
        self.firewall.unblock_servers(to_unblock)
        for server in to_unblock:
            self.server_status[server.code] = False
        
        self._add_output(f"✓ Unblocked {len(to_unblock)} servers in {region.upper()}", "green")
        return True
    
    def ping_servers(self, region: Optional[str] = None) -> bool:
        """Ping all servers and display results. Returns True."""
        if region:
            region_servers = get_region_servers(region)
            if not region_servers:
                self._add_output(f"Unknown region: {region}", "red")
                return False
            servers_to_ping = [s for s in self.servers if s.code in region_servers]
        else:
            servers_to_ping = self.servers
        
        total = len(servers_to_ping)
        timeout = getattr(self.ping_service, 'timeout', 2.0)
        
        self._clear_output()
        self._add_output(f"Pinging {total} servers (timeout: {timeout}s)...", "cyan")
        
        # Ping each server with verbose output
        success_count = 0
        fail_count = 0
        
        for i, server in enumerate(servers_to_ping, 1):
            # Ping this server
            latency = self.ping_service.ping_server(server)
            self.ping_results[server.code] = latency
            
            # Check if latency is a valid number (handles Mock objects in tests)
            if latency is not None and isinstance(latency, (int, float)):
                success_count += 1
                if latency < 50:
                    style = "green"
                elif latency < 100:
                    style = "yellow"
                else:
                    style = "red"
                self._add_output(f"  [{i}/{total}] {server.code:8} {latency:.0f}ms", style)
            else:
                fail_count += 1
                self._add_output(f"  [{i}/{total}] {server.code:8} TIMEOUT", "red")
        
        # Summary
        self._add_output(f"─── {success_count} successful, {fail_count} failed ───", "dim")
        return True
    
    def reset_all(self) -> bool:
        """Unblock all servers. Returns True."""
        self._add_output("Unblocking ALL servers...", "yellow")
        
        self.firewall.reset_firewall()
        
        # Update status
        for server in self.servers:
            self.server_status[server.code] = False
        
        self._add_output("✓ All servers unblocked", "green")
        return True
    
    def show_status(self) -> bool:
        """Show current status. Returns True."""
        total = len(self.servers)
        blocked = sum(1 for s in self.servers if self.server_status.get(s.code, False))
        allowed = total - blocked
        
        self._clear_output()
        self._add_output("═══════════ SERVER STATUS ═══════════", "blue")
        self._add_output(f"  Total Servers:   {total}", "cyan")
        self._add_output(f"  Allowed:         {allowed}", "green")
        self._add_output(f"  Blocked:         {blocked}", "red")
        
        if self.dry_run:
            self._add_output(f"  Mode:            DRY RUN", "yellow")
        
        # Show blocked servers
        blocked_servers = [s for s in self.servers if self.server_status.get(s.code, False)]
        if blocked_servers:
            self._add_output("", "white")
            self._add_output("Blocked servers:", "bold red")
            for server in blocked_servers[:10]:
                self._add_output(f"  • {server.code}: {server.name}", "red")
            if len(blocked_servers) > 10:
                self._add_output(f"  ... and {len(blocked_servers) - 10} more", "dim")
        
        self._add_output("═════════════════════════════════════", "blue")
        return True
    
    def handle_command(self, command: str) -> tuple[bool, bool]:
        """
        Handle a user command.
        
        Returns:
            Tuple of (continue_running, command_successful)
        """
        parts = command.strip().split()
        if not parts:
            return True, True
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        if cmd in ("quit", "q", "exit"):
            return False, True
        
        elif cmd in ("list", "l", "ls"):
            region = args[0] if args else None
            success = self.show_servers(region)
            return True, success
        
        elif cmd in ("regions", "r"):
            success = self.show_regions()
            return True, success
        
        elif cmd == "block":
            if not args:
                self._add_output("Usage: block <server_code>", "red")
                return True, False
            success = self.block_server(args[0])
            return True, success
        
        elif cmd == "unblock":
            if not args:
                self._add_output("Usage: unblock <server_code>", "red")
                return True, False
            success = self.unblock_server(args[0])
            return True, success
        
        elif cmd in ("allow", "allow-only"):
            if not args:
                self._add_output("Usage: allow <region>", "red")
                return True, False
            success = self.allow_only_region(args[0])
            return True, success
        
        elif cmd == "block-region":
            if not args:
                self._add_output("Usage: block-region <region>", "red")
                return True, False
            success = self.block_region(args[0])
            return True, success
        
        elif cmd == "unblock-region":
            if not args:
                self._add_output("Usage: unblock-region <region>", "red")
                return True, False
            success = self.unblock_region(args[0])
            return True, success
        
        elif cmd == "ping":
            region = args[0] if args else None
            success = self.ping_servers(region)
            return True, success
        
        elif cmd == "reset":
            success = self.reset_all()
            return True, success
        
        elif cmd in ("status", "s"):
            success = self.show_status()
            return True, success
        
        elif cmd in ("help", "h", "?"):
            self._show_help()
            return True, True
        
        elif cmd in ("clear", "cls", "c"):
            self._clear_output()
            return True, True
        
        else:
            self._add_output(f"Unknown command: {cmd}", "red")
            self._add_output("Type 'help' for available commands", "dim")
            return True, False
    
    def run(self):
        """Main TUI loop."""
        # Check sudo access first with visible password prompt
        if not self._check_sudo_access():
            self.console.print("[red]Cannot proceed without sudo access.[/]")
            self.console.print("[dim]Run with --dry-run to test without firewall changes.[/]")
            return
        
        # Now initialize
        self.initialize()
        
        # Track interrupt count for double Ctrl+C exit
        interrupt_count = 0
        
        # Main loop
        running = True
        while running:
            try:
                # Reset interrupt count on successful command
                interrupt_count = 0
                
                # Clear screen and show static header
                self.console.clear()
                self.console.print(self._create_static_header())
                
                # Show output panel if there's output
                if self.output_lines:
                    self.console.print(self._get_output_panel())
                else:
                    self.console.print("[dim]Type 'help' for commands, 'quit' to exit[/]\n")
                
                # Get command input
                command = self.console.input("[bold cyan]>>> [/]")
                running, _ = self.handle_command(command)
            except KeyboardInterrupt:
                interrupt_count += 1
                if interrupt_count >= 2:
                    self._add_output("Force quit...", "yellow")
                    running = False
                else:
                    self._add_output("Press Ctrl+C again to force quit, or type 'quit' to exit cleanly", "yellow")
            except EOFError:
                running = False
            except Exception as e:
                self._add_output(f"Error: {e}", "red")
        
        # Cleanup on exit
        self._cleanup_on_exit()
        self.console.print("\n[cyan]Goodbye![/]\n")
    
    def _cleanup_on_exit(self):
        """Reset firewall rules when exiting."""
        blocked_count = sum(1 for s in self.servers if self.server_status.get(s.code, False))
        
        if blocked_count > 0 and not self.dry_run:
            self.console.print(f"\n[yellow]Resetting {blocked_count} blocked servers...[/]")
            try:
                self.firewall.reset_firewall()
                self.console.print("[green]✓ Firewall rules cleaned up[/]")
            except Exception as e:
                self.console.print(f"[red]Warning: Failed to reset firewall: {e}[/]")
                self.console.print("[dim]Run 'deadlock-server-picker reset' manually to clean up[/]")


def run_tui(dry_run: bool = False):
    """Entry point for TUI."""
    tui = ServerPickerTUI(dry_run=dry_run)
    tui.run()


def main():
    """CLI entry point for TUI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deadlock Server Picker TUI")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually modify firewall rules"
    )
    
    args = parser.parse_args()
    run_tui(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
