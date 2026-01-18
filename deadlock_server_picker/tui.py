"""
TUI (Text User Interface) for Deadlock Server Picker.
Interactive terminal interface with color-coded server status.
"""

import os
import subprocess
import sys
import threading
import time
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
from .nftables import create_firewall_manager, detect_firewall_backend
from .ping_service import PingService
from .preset_manager import PresetManager
from .regions import REGION_PRESETS, REGION_ALIASES, get_region_servers
from .config import ConfigManager
from .latency_history import LatencyHistoryManager
from .wine_detect import check_deadlock_status
from .geolocation import get_server_location, format_location_table


class ServerPickerTUI:
    """Interactive TUI for Deadlock Server Picker."""
    
    def __init__(self, dry_run: bool = False):
        self.console = Console()
        self.fetcher = ServerDataFetcher()
        self.config_manager = ConfigManager()
        self.dry_run = dry_run
        
        # Initialize firewall based on config
        config = self.config_manager.load()
        backend = config.firewall_backend if config.firewall_backend != "auto" else None
        self.firewall = create_firewall_manager(
            backend=backend, 
            dry_run=dry_run, 
            use_sudo=config.use_sudo
        )
        self.firewall_backend = detect_firewall_backend() if backend is None else backend
        
        self.ping_service = PingService()
        self.preset_manager = PresetManager()
        self.latency_history = LatencyHistoryManager()
        self.servers: list[Server] = []
        self.server_status: dict[str, bool] = {}  # code -> blocked
        self.ping_results: dict[str, Optional[float]] = {}  # code -> latency
        self.output_lines: list[Text] = []  # Dynamic output buffer
        self.max_output_lines = 50  # Max lines to keep in output buffer
        
        # Sudo refresh thread
        self._sudo_refresh_thread: Optional[threading.Thread] = None
        self._sudo_refresh_stop = threading.Event()
    
    def _start_sudo_refresh(self):
        """Start background thread to keep sudo credentials alive."""
        if self.dry_run:
            return
        
        def refresh_loop():
            while not self._sudo_refresh_stop.wait(timeout=60):  # Refresh every 60 seconds
                try:
                    subprocess.run(
                        ["sudo", "-v"],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception:
                    pass
        
        self._sudo_refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
        self._sudo_refresh_thread.start()
    
    def _stop_sudo_refresh(self):
        """Stop the sudo refresh thread."""
        if self._sudo_refresh_thread is not None:
            self._sudo_refresh_stop.set()
            self._sudo_refresh_thread.join(timeout=1)
    
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
        """Load servers, check status, and apply config preferences."""
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
        
        # Apply config preferences
        config = self.config_manager.load()
        auto_applied = []
        
        # Auto-apply always_block servers from config
        if config.always_block:
            for code in config.always_block:
                server = self.fetcher.get_server_by_name(code)
                if server and not self.server_status.get(server.code, False):
                    blocked, _ = self.firewall.block_servers([server])
                    if blocked > 0:
                        self.server_status[server.code] = True
                        auto_applied.append(f"blocked {code}")
        
        # Auto-apply never_block servers (unblock if blocked)
        if config.never_block:
            for code in config.never_block:
                server = self.fetcher.get_server_by_name(code)
                if server and self.server_status.get(server.code, False):
                    unblocked, _ = self.firewall.unblock_servers([server])
                    if unblocked > 0:
                        self.server_status[server.code] = False
                        auto_applied.append(f"unblocked {code}")
        
        # Apply last used region if set
        if config.default_region:
            region_servers = get_region_servers(config.default_region)
            if region_servers:
                to_block = [s for s in self.servers if s.code not in region_servers 
                           and s.code not in config.never_block]
                to_unblock = [s for s in self.servers if s.code in region_servers
                             and s.code not in config.always_block]
                
                if to_unblock:
                    self.firewall.unblock_servers(to_unblock)
                    for server in to_unblock:
                        self.server_status[server.code] = False
                
                if to_block:
                    self.firewall.block_servers(to_block)
                    for server in to_block:
                        self.server_status[server.code] = True
                
                auto_applied.append(f"applied region {config.default_region}")
        
        if auto_applied:
            self._add_output(f"Auto-applied: {', '.join(auto_applied)}", "cyan")
    
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
        
        # Title line with backend info
        content.append("DEADLOCK SERVER PICKER", style="bold blue")
        if self.dry_run:
            content.append("  [DRY RUN]", style="bold yellow")
        content.append(f"  [{self.firewall_backend}]", style="dim cyan")
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
    
    def _add_output_markup(self, markup: str):
        """Add a line with Rich markup to the output buffer."""
        line = Text.from_markup(markup)
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
            ("list [region|server]", "Show servers by location (filter by region/server)"),
            ("regions", "Show available region presets"),
            ("block <code>", "Block a server by code"),
            ("unblock <code>", "Unblock a server by code"),
            ("allow <region>", "Allow only servers in region"),
            ("block-region <region>", "Block all servers in region"),
            ("unblock-region <region>", "Unblock all servers in region"),
            ("ping [region]", "Ping servers and show latency"),
            ("history [server]", "Show latency history"),
            ("best", "Show servers with best latency"),
            ("wine", "Show Wine/Proton status"),
            ("status", "Show current status"),
            ("reset", "Unblock all servers"),
            ("clear", "Clear output"),
            ("help", "Show this help"),
            ("quit", "Exit"),
        ]
        
        # Alternating colors (pastel cyan and magenta)
        alt_colors = ["cyan", "magenta"]
        for i, (cmd, desc) in enumerate(help_lines):
            row_color = alt_colors[i % 2]
            self._add_output(f"  {cmd:25} {desc}", row_color)
    
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
        
        # Clear output and add server list in compact multi-column format
        self._clear_output()
        self._add_output(f"─── {title} ({len(filtered)}) ───", "cyan")
        
        # Build compact server entries with index for alternating colors
        entries = []
        for i, server in enumerate(filtered):
            blocked = self.server_status.get(server.code, False)
            ping = self.ping_results.get(server.code)
            
            status_icon = "●" if blocked else "○"
            
            if ping is not None and isinstance(ping, (int, float)):
                ping_str = f"{ping:.0f}ms"
            else:
                ping_str = ""
            
            # Compact format: icon code (ping)
            if ping_str:
                entry = f"{status_icon} {server.code:6} {ping_str:>5}"
            else:
                entry = f"{status_icon} {server.code:6}      "
            entries.append((entry, blocked, i))
        
        # Display in 4 columns with alternating colors per row
        cols = 4
        col_width = 18
        rows = (len(entries) + cols - 1) // cols
        alt_colors = ["cyan", "magenta"]
        
        for row in range(rows):
            line_parts = []
            for col in range(cols):
                idx = row + col * rows
                if idx < len(entries):
                    entry, blocked, entry_idx = entries[idx]
                    line_parts.append(f"{entry:<{col_width}}")
                else:
                    line_parts.append(" " * col_width)
            
            # Alternating row colors
            line = "  ".join(line_parts)
            row_color = alt_colors[row % 2]
            self._add_output(line, row_color)
        
        self._add_output(f"─── ● = blocked, ○ = allowed ───", "dim")
        return True
    
    def show_regions(self) -> bool:
        """Display available regions. Returns True."""
        self._clear_output()
        self._add_output("─── Available Regions ───", "magenta")
        
        # Alternating colors (pastel cyan and magenta)
        alt_colors = ["cyan", "magenta"]
        row_idx = 0
        
        shown_regions = set()
        for alias, region_name in sorted(REGION_ALIASES.items()):
            if region_name not in shown_regions:
                shown_regions.add(region_name)
                region_data = REGION_PRESETS[region_name]
                server_count = len(region_data["servers"])
                row_color = alt_colors[row_idx % 2]
                self._add_output(f"  {alias:6} {region_name:20} ({server_count} servers) - {region_data['description']}", row_color)
                row_idx += 1
        
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
        
        # In dry_run mode or when firewall operation succeeds, update status
        self.firewall.unblock_servers([server])
        self.server_status[server.code] = False
        self._add_output(f"✓ Unblocked {server.name}", "green")
        return True
    
    def allow_only_region(self, region: str) -> bool:
        """Block all servers except those in the specified region. Returns True if successful."""
        region_servers = get_region_servers(region)
        if not region_servers:
            self._add_output(f"Unknown region: {region}", "red")
            self._add_output("Use 'regions' to see available regions", "dim")
            return False
        
        config = self.config_manager.load()
        to_block = [s for s in self.servers if s.code not in region_servers
                   and s.code not in config.never_block]
        to_unblock = [s for s in self.servers if s.code in region_servers
                     and s.code not in config.always_block]
        
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
        
        # Save region preference to config
        self.config_manager.set("default_region", region)
        
        blocked = sum(1 for s in self.servers if self.server_status.get(s.code, False))
        self._add_output(f"✓ Done! {blocked} servers blocked, region preference saved", "green")
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
        """Ping all servers in parallel and display results. Returns True."""
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
        self._add_output(f"Pinging {total} servers in parallel (timeout: {timeout}s)...", "cyan")
        
        # Use concurrent ping for speed
        results = self.ping_service.ping_servers(servers_to_ping)
        
        # Handle None result (e.g., from mocks in tests)
        if results is None:
            results = {}
        
        # Save to history
        self.latency_history.record_batch({
            code: int(lat) if lat is not None else None 
            for code, lat in results.items()
        })
        
        # Store and display results
        success_count = 0
        fail_count = 0
        
        # Sort by latency (successes first, then timeouts)
        sorted_servers = sorted(
            servers_to_ping,
            key=lambda s: (results.get(s.code) is None, results.get(s.code) or 9999)
        )
        
        for server in sorted_servers:
            latency = results.get(server.code)
            self.ping_results[server.code] = latency
            
            # Get history summary for this server
            hist = self.latency_history.get_summary(server.code)
            hist_str = ""
            if hist and hist['avg_latency']:
                hist_str = f" (avg: {hist['avg_latency']:.0f}ms)"
            
            # Check if latency is a valid number (handles Mock objects in tests)
            if latency is not None and isinstance(latency, (int, float)):
                success_count += 1
                if latency < 50:
                    style = "green"
                elif latency < 100:
                    style = "yellow"
                else:
                    style = "red"
                self._add_output(f"  {server.code:8} {latency:.0f}ms{hist_str}", style)
            else:
                fail_count += 1
                self._add_output(f"  {server.code:8} TIMEOUT{hist_str}", "red")
        
        # Summary
        self._add_output(f"─── {success_count} successful, {fail_count} failed ───", "dim")
        return True
    
    def show_history(self, server_code: Optional[str] = None) -> bool:
        """Show latency history for a server or summary for all. Returns True."""
        self._clear_output()
        
        if server_code:
            # Show detailed history for specific server
            summary = self.latency_history.get_summary(server_code)
            if not summary:
                self._add_output(f"No history for server: {server_code}", "yellow")
                self._add_output("Run 'ping' first to collect data.", "dim")
                return False
            
            self._add_output(f"─── Latency History: {server_code.upper()} ───", "cyan")
            self._add_output(f"  Measurements:   {summary['measurements']}", "white")
            self._add_output(f"  Average:        {summary['avg_latency']:.0f}ms", "white")
            self._add_output(f"  Min:            {summary['min_latency']}ms", "green")
            self._add_output(f"  Max:            {summary['max_latency']}ms", "red")
            self._add_output(f"  Success Rate:   {summary['success_rate']}%", "white")
        else:
            # Show summary for all servers
            histories = self.latency_history.get_all_histories()
            if not histories:
                self._add_output("No latency history recorded yet.", "yellow")
                self._add_output("Run 'ping' first to collect data.", "dim")
                return False
            
            self._add_output("─── Latency History Summary ───", "cyan")
            self._add_output(f"  Servers tracked: {len(histories)}", "white")
            
            # Sort by avg latency
            sorted_servers = sorted(
                [(code, hist.avg_latency) for code, hist in histories.items() if hist.avg_latency],
                key=lambda x: x[1]
            )
            
            self._add_output("", "white")
            self._add_output("Top 10 by average latency:", "white")
            for code, avg in sorted_servers[:10]:
                if avg < 50:
                    style = "green"
                elif avg < 100:
                    style = "yellow"
                else:
                    style = "red"
                self._add_output(f"  {code:8} {avg:.0f}ms", style)
        
        return True
    
    def show_best_servers(self, count: int = 10) -> bool:
        """Show servers with best latency. Returns True."""
        best = self.latency_history.get_best_servers(count)
        
        self._clear_output()
        
        if not best:
            self._add_output("No latency data available.", "yellow")
            self._add_output("Run 'ping' first to collect data.", "dim")
            return False
        
        self._add_output(f"─── Best {len(best)} Servers by Latency ───", "cyan")
        
        for i, (code, avg) in enumerate(best, 1):
            if avg < 50:
                style = "green"
            elif avg < 100:
                style = "yellow"
            else:
                style = "red"
            blocked = "●" if self.server_status.get(code, False) else "○"
            self._add_output(f"  {i:2}. {blocked} {code:8} avg: {avg:.0f}ms", style)
        
        self._add_output("", "white")
        self._add_output("● = blocked, ○ = allowed", "dim")
        return True
    
    def show_wine_status(self) -> bool:
        """Show Wine/Proton detection status. Returns True."""
        self._clear_output()
        self._add_output("─── Wine/Proton Status ───", "cyan")
        
        status = check_deadlock_status()
        
        # Components
        self._add_output("", "white")
        self._add_output("Installed Components:", "white")
        for comp, installed in status['components'].items():
            icon = "✓" if installed else "✗"
            style = "green" if installed else "red"
            self._add_output(f"  {icon} {comp}", style)
        
        # Running processes
        self._add_output("", "white")
        if status['deadlock_running']:
            self._add_output(f"Deadlock Running: Yes ({len(status['processes'])} process(es))", "green")
            for proc in status['processes']:
                self._add_output(f"  • {proc.description}", "cyan")
        else:
            self._add_output("Deadlock Running: No", "yellow")
        
        # Firewall note
        self._add_output("", "white")
        self._add_output("Firewall Note:", "white")
        if status['proton_installed'] or status['wine_installed']:
            self._add_output("  FORWARD chain is enabled for Wine/Proton compatibility", "green")
        else:
            self._add_output("  Wine/Proton not detected - using OUTPUT chain only", "dim")
        
        return True
    
    def show_geo(self, filter_arg: Optional[str] = None) -> bool:
        """Show server geographic locations. Returns True."""
        self._clear_output()
        
        # Check if filter_arg is a specific server code
        if filter_arg:
            # First check if it's a server code
            loc = get_server_location(filter_arg)
            if loc:
                # Show specific server location details
                blocked = self.server_status.get(filter_arg, False)
                status = "BLOCKED" if blocked else "ALLOWED"
                status_style = "red" if blocked else "green"
                ping = self.ping_results.get(filter_arg)
                
                self._add_output(f"─── Server: {filter_arg.upper()} ───", "cyan")
                self._add_output(f"  City:      {loc.city}", "white")
                self._add_output(f"  Country:   {loc.country}", "white")
                self._add_output(f"  Region:    {loc.region}", "white")
                self._add_output(f"  Coords:    {loc.latitude:.4f}, {loc.longitude:.4f}", "dim")
                self._add_output(f"  Status:    {status}", status_style)
                if ping is not None and isinstance(ping, (int, float)):
                    self._add_output(f"  Latency:   {ping:.0f}ms", "white")
                return True
            
            # Otherwise treat as region filter
            region_servers = get_region_servers(filter_arg)
            if not region_servers:
                self._add_output(f"Unknown server or region: {filter_arg}", "red")
                self._add_output("Use 'regions' to see available regions", "dim")
                return False
            filtered = [s for s in self.servers if s.code in region_servers]
            title = f"Servers in {filter_arg.upper()}"
        else:
            filtered = self.servers
            title = "All Servers"
        
        if not filtered:
            self._add_output("No servers found", "yellow")
            return False
        
        self._add_output(f"─── {title} ({len(filtered)}) ───", "cyan")
        
        # Group servers by geographic region
        regions: dict[str, list[tuple[str, str, bool, Optional[float]]]] = {}
        for server in filtered:
            loc = get_server_location(server.code)
            if loc:
                region = loc.region
                if region not in regions:
                    regions[region] = []
                blocked = self.server_status.get(server.code, False)
                ping = self.ping_results.get(server.code)
                regions[region].append((server.code, loc.city, blocked, ping))
            else:
                # Unknown location - use server name as identifier
                if "Unknown" not in regions:
                    regions["Unknown"] = []
                blocked = self.server_status.get(server.code, False)
                ping = self.ping_results.get(server.code)
                # Use server name or code as city placeholder
                display = server.name[:12] if server.name else server.code
                regions["Unknown"].append((server.code, display, blocked, ping))
        
        # Display each region in compact multi-column format
        for region in sorted(regions.keys()):
            self._add_output(f"{region}:", "yellow")
            
            # Build entries for this region
            entries = []
            for code, city, blocked, ping in sorted(regions[region], key=lambda x: x[1]):
                icon = "●" if blocked else "○"
                if ping is not None and isinstance(ping, (int, float)):
                    entry = f"{icon} {code:6} {city[:12]:12} {ping:>4.0f}ms"
                else:
                    entry = f"{icon} {code:6} {city[:12]:12}      "
                entries.append(entry)
            
            # Display in 3 columns
            cols = 3
            col_width = 28
            rows = (len(entries) + cols - 1) // cols
            
            for row in range(rows):
                line_parts = []
                for col in range(cols):
                    idx = row + col * rows
                    if idx < len(entries):
                        line_parts.append(entries[idx])
                
                line = "  ".join(f"{p:<{col_width}}" for p in line_parts)
                self._add_output(f"  {line}", "white")
        
        self._add_output(f"─── ● = blocked, ○ = allowed ───", "dim")
        return True
    
    def reset_all(self) -> bool:
        """Unblock all servers. Returns True."""
        self._add_output("Unblocking ALL servers...", "yellow")
        
        self.firewall.reset_firewall()
        
        # Clear default_region so it doesn't re-apply on next start
        config = self.config_manager.load()
        if config.default_region:
            config.default_region = None
            self.config_manager.save(config)
            self._add_output("  Cleared default region preference", "dim")
        
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
            filter_arg = args[0] if args else None
            success = self.show_geo(filter_arg)
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
        
        elif cmd == "history":
            server = args[0] if args else None
            success = self.show_history(server)
            return True, success
        
        elif cmd == "best":
            success = self.show_best_servers()
            return True, success
        
        elif cmd == "wine":
            success = self.show_wine_status()
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
    
    def _set_terminal_title(self, title: str):
        """Set the terminal window title."""
        # ANSI escape sequence to set window title
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()
    
    def run(self):
        """Main TUI loop."""
        # Check sudo access first with visible password prompt
        if not self._check_sudo_access():
            self.console.print("[red]Cannot proceed without sudo access.[/]")
            self.console.print("[dim]Run with --dry-run to test without firewall changes.[/]")
            return
        
        # Start background sudo refresh to keep credentials alive
        self._start_sudo_refresh()
        
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
                
                # Update terminal title with status
                blocked = sum(1 for s in self.servers if self.server_status.get(s.code, False))
                self._set_terminal_title(f"Deadlock Server Picker - {blocked} blocked")
                
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
        # Stop sudo refresh thread
        self._stop_sudo_refresh()
        
        blocked_count = sum(1 for s in self.servers if self.server_status.get(s.code, False))
        
        if blocked_count > 0 and not self.dry_run:
            self.console.print(f"\n[yellow]Resetting {blocked_count} blocked servers...[/]")
            try:
                self.firewall.reset_firewall()
                self.console.print("[green]✓ Firewall rules cleaned up[/]")
            except Exception as e:
                self.console.print(f"[red]Warning: Failed to reset firewall: {e}[/]")
                self.console.print("[dim]Run 'deadlock-server-picker reset' manually to clean up[/]")


def check_disclaimer_tui(console: Console) -> bool:
    """
    Check if user has accepted the disclaimer. Prompts if not.
    
    Args:
        console: Rich Console instance for output.
        
    Returns:
        True if accepted (now or previously), False if declined.
    """
    config_manager = ConfigManager()
    config = config_manager.load()
    
    if config.disclaimer_accepted:
        return True
    
    # Show disclaimer
    disclaimer_text = """
[bold yellow]⚠️  DISCLAIMER  ⚠️[/bold yellow]

This project was [bold]vibecoded[/bold] with AI assistance.

While functional, [bold red]USE AT YOUR OWN RISK.[/bold red]

I am not responsible for any issues, damages, or consequences that may
arise from using this software. This includes but is not limited to:
  • System instability
  • Network issues  
  • Any other problems that may occur

By continuing, you accept full responsibility for any outcomes.
"""
    
    console.print(Panel(disclaimer_text, title="[bold]Disclaimer[/bold]", border_style="yellow"))
    
    try:
        response = console.input("[bold cyan]Do you accept and wish to continue? [y/N]: [/]")
        if response.strip().lower() in ('y', 'yes'):
            config.disclaimer_accepted = True
            config_manager.save(config)
            console.print("\n[green]✓ Disclaimer accepted. This won't be shown again.[/]\n")
            return True
        else:
            console.print("\n[red]Disclaimer not accepted. Exiting.[/]")
            return False
    except (KeyboardInterrupt, EOFError):
        console.print("\n\n[red]Disclaimer not accepted. Exiting.[/]")
        return False


def run_tui(dry_run: bool = False):
    """Entry point for TUI."""
    # Check disclaimer before creating TUI
    console = Console()
    if not check_disclaimer_tui(console):
        return
    
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
