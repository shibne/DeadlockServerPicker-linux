"""
TUI (Text User Interface) for Deadlock Server Picker.
Interactive terminal interface with color-coded server status.
"""

import os
import subprocess
import sys
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED

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
            if ping is not None:
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
        """Print help commands."""
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
            ("clear", "Clear screen"),
            ("help", "Show this help"),
            ("quit", "Exit"),
        ]
        
        table = Table(box=ROUNDED, show_header=True, header_style="bold green", border_style="green")
        table.add_column("Command", style="yellow", width=25)
        table.add_column("Description", style="white")
        
        for cmd, desc in help_lines:
            table.add_row(cmd, desc)
        
        self.console.print(table)
    
    def show_servers(self, filter_region: Optional[str] = None) -> bool:
        """Display server list. Returns True if successful."""
        if filter_region:
            region_servers = get_region_servers(filter_region)
            if not region_servers:
                self.console.print(f"[red]Unknown region: {filter_region}[/]")
                self.console.print("[dim]Use 'regions' to see available regions[/]")
                return False
            filtered = [s for s in self.servers if s.code in region_servers]
            title = f"Servers in {filter_region.upper()}"
        else:
            filtered = self.servers
            title = "All Servers"
        
        if not filtered:
            self.console.print(f"[yellow]No servers found[/]")
            return False
        
        table = self._create_server_table(filtered, title)
        self.console.print(table)
        return True
    
    def show_regions(self) -> bool:
        """Display available regions. Returns True."""
        table = self._create_region_table()
        self.console.print(table)
        return True
    
    def block_server(self, code: str) -> bool:
        """Block a single server by code. Returns True if successful."""
        server = self.fetcher.get_server_by_name(code)
        if not server:
            self.console.print(f"[red]Server not found: {code}[/]")
            return False
        
        if self.server_status.get(server.code, False):
            self.console.print(f"[yellow]Server {code} is already blocked[/]")
            return True
        
        with self.console.status(f"[bold blue]Blocking {server.name}...[/]"):
            blocked, _ = self.firewall.block_servers([server])
        
        if blocked > 0:
            self.server_status[server.code] = True
            self.console.print(f"[green]✓ Blocked {server.name}[/]")
            return True
        else:
            self.console.print(f"[red]✗ Failed to block {server.name}[/]")
            return False
    
    def unblock_server(self, code: str) -> bool:
        """Unblock a single server by code. Returns True if successful."""
        server = self.fetcher.get_server_by_name(code)
        if not server:
            self.console.print(f"[red]Server not found: {code}[/]")
            return False
        
        if not self.server_status.get(server.code, False):
            self.console.print(f"[yellow]Server {code} is not blocked[/]")
            return True
        
        with self.console.status(f"[bold blue]Unblocking {server.name}...[/]"):
            unblocked, _ = self.firewall.unblock_servers([server])
        
        if unblocked > 0:
            self.server_status[server.code] = False
            self.console.print(f"[green]✓ Unblocked {server.name}[/]")
            return True
        else:
            self.console.print(f"[red]✗ Failed to unblock {server.name}[/]")
            return False
    
    def allow_only_region(self, region: str) -> bool:
        """Block all servers except those in the specified region. Returns True if successful."""
        region_servers = get_region_servers(region)
        if not region_servers:
            self.console.print(f"[red]Unknown region: {region}[/]")
            self.console.print("[dim]Use 'regions' to see available regions[/]")
            return False
        
        to_block = [s for s in self.servers if s.code not in region_servers]
        to_unblock = [s for s in self.servers if s.code in region_servers]
        
        self.console.print(f"[cyan]Allowing only {region.upper()} ({len(to_unblock)} servers)[/]")
        self.console.print(f"[cyan]Blocking {len(to_block)} servers from other regions[/]")
        
        with self.console.status("[bold blue]Applying firewall rules...[/]"):
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
        self.console.print(f"[green]✓ Done! {blocked} servers blocked[/]")
        return True
    
    def block_region(self, region: str) -> bool:
        """Block all servers in a region. Returns True if successful."""
        region_servers = get_region_servers(region)
        if not region_servers:
            self.console.print(f"[red]Unknown region: {region}[/]")
            return False
        
        to_block = [s for s in self.servers if s.code in region_servers]
        
        self.console.print(f"[cyan]Blocking {len(to_block)} servers in {region.upper()}[/]")
        
        with self.console.status("[bold blue]Blocking servers...[/]"):
            self.firewall.block_servers(to_block)
            for server in to_block:
                self.server_status[server.code] = True
        
        self.console.print(f"[green]✓ Blocked {region.upper()} servers[/]")
        return True
    
    def unblock_region(self, region: str) -> bool:
        """Unblock all servers in a region. Returns True if successful."""
        region_servers = get_region_servers(region)
        if not region_servers:
            self.console.print(f"[red]Unknown region: {region}[/]")
            return False
        
        to_unblock = [s for s in self.servers if s.code in region_servers]
        
        self.console.print(f"[cyan]Unblocking {len(to_unblock)} servers in {region.upper()}[/]")
        
        with self.console.status("[bold blue]Unblocking servers...[/]"):
            self.firewall.unblock_servers(to_unblock)
            for server in to_unblock:
                self.server_status[server.code] = False
        
        self.console.print(f"[green]✓ Unblocked {region.upper()} servers[/]")
        return True
    
    def ping_servers(self, region: Optional[str] = None) -> bool:
        """Ping all servers and display results. Returns True."""
        if region:
            region_servers = get_region_servers(region)
            if not region_servers:
                self.console.print(f"[red]Unknown region: {region}[/]")
                return False
            servers_to_ping = [s for s in self.servers if s.code in region_servers]
        else:
            servers_to_ping = self.servers
        
        self.console.print(f"[cyan]Pinging {len(servers_to_ping)} servers...[/]")
        
        with self.console.status("[bold blue]Measuring latency...[/]"):
            self.ping_service.ping_servers(servers_to_ping)
        
        for server in servers_to_ping:
            self.ping_results[server.code] = server.latency_ms
        
        # Show results in table
        self.show_servers(region)
        return True
    
    def reset_all(self) -> bool:
        """Unblock all servers. Returns True."""
        self.console.print("[yellow]Unblocking ALL servers...[/]")
        
        with self.console.status("[bold blue]Resetting firewall rules...[/]"):
            self.firewall.reset_firewall()
            
            # Update status
            for server in self.servers:
                self.server_status[server.code] = False
        
        self.console.print("[green]✓ All servers unblocked[/]")
        return True
    
    def show_status(self) -> bool:
        """Show current status. Returns True."""
        total = len(self.servers)
        blocked = sum(1 for s in self.servers if self.server_status.get(s.code, False))
        allowed = total - blocked
        
        status_text = Text()
        status_text.append("\n")
        status_text.append("═" * 50 + "\n", style="blue")
        status_text.append("          SERVER STATUS\n", style="bold blue")
        status_text.append("═" * 50 + "\n", style="blue")
        status_text.append("\n")
        status_text.append("Total Servers:   ", style="bold")
        status_text.append(f"{total}\n", style="cyan")
        status_text.append("Allowed:         ", style="bold")
        status_text.append(f"{allowed}\n", style="bold green")
        status_text.append("Blocked:         ", style="bold")
        status_text.append(f"{blocked}\n", style="bold red")
        status_text.append("\n")
        
        if self.dry_run:
            status_text.append("Mode:            ", style="bold")
            status_text.append("DRY RUN (no changes made)\n", style="bold yellow")
        
        # Show blocked servers
        blocked_servers = [s for s in self.servers if self.server_status.get(s.code, False)]
        if blocked_servers:
            status_text.append("\n")
            status_text.append("Blocked servers:\n", style="bold red")
            for server in blocked_servers[:10]:
                status_text.append(f"  • {server.code}: {server.name}\n", style="red")
            if len(blocked_servers) > 10:
                status_text.append(f"  ... and {len(blocked_servers) - 10} more\n", style="dim red")
        
        self.console.print(status_text)
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
                self.console.print("[red]Usage: block <server_code>[/]")
                return True, False
            success = self.block_server(args[0])
            return True, success
        
        elif cmd == "unblock":
            if not args:
                self.console.print("[red]Usage: unblock <server_code>[/]")
                return True, False
            success = self.unblock_server(args[0])
            return True, success
        
        elif cmd in ("allow", "allow-only"):
            if not args:
                self.console.print("[red]Usage: allow <region>[/]")
                return True, False
            success = self.allow_only_region(args[0])
            return True, success
        
        elif cmd == "block-region":
            if not args:
                self.console.print("[red]Usage: block-region <region>[/]")
                return True, False
            success = self.block_region(args[0])
            return True, success
        
        elif cmd == "unblock-region":
            if not args:
                self.console.print("[red]Usage: unblock-region <region>[/]")
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
            self._print_help()
            return True, True
        
        elif cmd in ("clear", "cls", "c"):
            self._print_header()
            return True, True
        
        else:
            self.console.print(f"[red]Unknown command: {cmd}[/]")
            self.console.print("[dim]Type 'help' for available commands[/]")
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
        
        # Show header
        self._print_header()
        
        self.console.print(f"[green]✓ Loaded {len(self.servers)} servers[/]")
        self.console.print("[dim]Type 'help' for commands, 'quit' to exit[/]\n")
        
        # Main loop
        running = True
        while running:
            try:
                # Simple input prompt that doesn't interfere with display
                self.console.print(self._get_summary_text())
                command = self.console.input("[bold cyan]>>> [/]")
                running, _ = self.handle_command(command)
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Press Ctrl+C again or type 'quit' to exit[/]")
            except EOFError:
                running = False
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/]")
        
        self.console.print("\n[cyan]Goodbye![/]\n")


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
