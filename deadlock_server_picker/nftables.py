"""
nftables firewall backend for Deadlock Server Picker.
Modern alternative to iptables.
"""

import subprocess
import shutil
from typing import Optional

from .models import Server, ServerStatus


class NftablesError(Exception):
    """Raised when nftables operations fail."""
    pass


class NftablesManager:
    """Manages nftables rules for blocking Deadlock servers."""
    
    TABLE_NAME = "deadlock_server_picker"
    CHAIN_NAME = "block"
    
    def __init__(self, dry_run: bool = False, use_sudo: bool = True):
        """
        Initialize nftables manager.
        
        Args:
            dry_run: If True, don't actually modify firewall rules.
            use_sudo: If True, use sudo for nft commands.
        """
        self.dry_run = dry_run
        self.use_sudo = use_sudo
        self._nft_path = self._find_nft()
    
    def _find_nft(self) -> str:
        """Find the nft binary path."""
        nft_path = shutil.which("nft")
        if nft_path:
            return nft_path
        
        # Check common paths
        for path in ["/sbin/nft", "/usr/sbin/nft", "/usr/bin/nft"]:
            if shutil.which(path):
                return path
        
        raise NftablesError("nft command not found. Please install nftables.")
    
    def _run_command(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """
        Run an nft command.
        
        Args:
            cmd: Command parts to run.
            check: Whether to raise on non-zero exit.
            
        Returns:
            CompletedProcess with output.
        """
        if self.dry_run:
            # Return empty success for dry run
            return subprocess.CompletedProcess(cmd, 0, "", "")
        
        if self.use_sudo:
            cmd = ["sudo"] + cmd
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if check and result.returncode != 0:
                raise NftablesError(
                    f"Command failed: {' '.join(cmd)}\n"
                    f"stderr: {result.stderr}"
                )
            
            return result
            
        except FileNotFoundError as e:
            raise NftablesError(f"Command not found: {e}") from e
    
    def _get_rule_comment(self, server_name: str) -> str:
        """Get a comment identifier for a server rule."""
        sanitized = server_name.replace(" ", "_").replace("(", "").replace(")", "")
        return f"dsp_{sanitized}"
    
    def ensure_table_exists(self) -> None:
        """Ensure the nftables table and chains exist."""
        # Create table if not exists
        self._run_command([
            self._nft_path, "add", "table", "inet", self.TABLE_NAME
        ], check=False)
        
        # Create chain for OUTPUT (native apps)
        self._run_command([
            self._nft_path, "add", "chain", "inet", self.TABLE_NAME, self.CHAIN_NAME,
            "{ type filter hook output priority 0; policy accept; }"
        ], check=False)
        
        # Create chain for FORWARD (Wine/Proton)
        self._run_command([
            self._nft_path, "add", "chain", "inet", self.TABLE_NAME, "forward_block",
            "{ type filter hook forward priority 0; policy accept; }"
        ], check=False)
    
    def is_server_blocked(self, server: Server) -> bool:
        """Check if a server is currently blocked."""
        comment = self._get_rule_comment(server.display_name)
        
        result = self._run_command([
            self._nft_path, "list", "table", "inet", self.TABLE_NAME
        ], check=False)
        
        if result.returncode != 0:
            return False
        
        return comment in result.stdout
    
    def block_server(self, server: Server) -> bool:
        """
        Block a server by adding nftables rules.
        
        Returns:
            True if server was blocked, False if already blocked.
        """
        if self.is_server_blocked(server):
            return False
        
        self.ensure_table_exists()
        
        comment = self._get_rule_comment(server.display_name)
        
        # Add rule to block OUTPUT traffic
        for ip in server.ip_addresses:
            self._run_command([
                self._nft_path, "add", "rule", "inet", self.TABLE_NAME, self.CHAIN_NAME,
                "ip", "daddr", ip, "drop", "comment", f'"{comment}"'
            ])
            
            # Also add to forward chain for Wine/Proton
            self._run_command([
                self._nft_path, "add", "rule", "inet", self.TABLE_NAME, "forward_block",
                "ip", "daddr", ip, "drop", "comment", f'"{comment}"'
            ])
        
        server.status = ServerStatus.BLOCKED
        return True
    
    def unblock_server(self, server: Server) -> bool:
        """
        Unblock a server by removing nftables rules.
        
        Returns:
            True if server was unblocked, False if not blocked.
        """
        if not self.is_server_blocked(server):
            server.status = ServerStatus.AVAILABLE
            return False
        
        comment = self._get_rule_comment(server.display_name)
        
        # Get rule handles to delete
        result = self._run_command([
            self._nft_path, "-a", "list", "table", "inet", self.TABLE_NAME
        ], check=False)
        
        if result.returncode == 0:
            # Find and delete rules with our comment
            handles_to_delete = []
            current_chain = None
            
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("chain "):
                    current_chain = line.split()[1]
                elif comment in line and "handle" in line:
                    # Extract handle number
                    parts = line.split("handle")
                    if len(parts) > 1:
                        handle = parts[1].strip().split()[0]
                        handles_to_delete.append((current_chain, handle))
            
            # Delete rules
            for chain, handle in handles_to_delete:
                self._run_command([
                    self._nft_path, "delete", "rule", "inet", self.TABLE_NAME,
                    chain, "handle", handle
                ], check=False)
        
        server.status = ServerStatus.AVAILABLE
        return True
    
    def block_servers(self, servers: list[Server]) -> tuple[int, int]:
        """Block multiple servers. Returns (blocked_count, already_blocked_count)."""
        blocked = 0
        already_blocked = 0
        
        for server in servers:
            if self.block_server(server):
                blocked += 1
            else:
                already_blocked += 1
        
        return blocked, already_blocked
    
    def unblock_servers(self, servers: list[Server]) -> tuple[int, int]:
        """Unblock multiple servers. Returns (unblocked_count, not_blocked_count)."""
        unblocked = 0
        not_blocked = 0
        
        for server in servers:
            if self.unblock_server(server):
                unblocked += 1
            else:
                not_blocked += 1
        
        return unblocked, not_blocked
    
    def get_blocked_servers(self) -> list[str]:
        """Get list of currently blocked server names."""
        result = self._run_command([
            self._nft_path, "list", "table", "inet", self.TABLE_NAME
        ], check=False)
        
        if result.returncode != 0:
            return []
        
        blocked = set()
        for line in result.stdout.splitlines():
            if 'comment "dsp_' in line:
                # Extract server name from comment
                start = line.find('comment "dsp_') + 13
                end = line.find('"', start)
                if start > 13 and end > start:
                    server_name = line[start:end].replace("_", " ")
                    blocked.add(server_name)
        
        return list(blocked)
    
    def clear_all_rules(self) -> int:
        """Remove all rules from our table. Returns rule count removed."""
        # Flush the chains
        self._run_command([
            self._nft_path, "flush", "chain", "inet", self.TABLE_NAME, self.CHAIN_NAME
        ], check=False)
        
        self._run_command([
            self._nft_path, "flush", "chain", "inet", self.TABLE_NAME, "forward_block"
        ], check=False)
        
        return 1
    
    def reset_firewall(self) -> None:
        """Remove all rules and delete the table entirely."""
        self._run_command([
            self._nft_path, "delete", "table", "inet", self.TABLE_NAME
        ], check=False)
    
    def check_permissions(self) -> tuple[bool, str]:
        """Check if we have permissions to manage nftables."""
        result = self._run_command([
            self._nft_path, "list", "tables"
        ], check=False)
        
        if result.returncode == 0:
            return True, "nftables access OK"
        
        if "Permission denied" in result.stderr or "Operation not permitted" in result.stderr:
            return False, "Permission denied. Try running with sudo or as root."
        
        return False, f"Unknown error: {result.stderr}"
    
    def get_save_command(self) -> str:
        """Get the command to save nftables rules persistently."""
        import os
        
        if os.path.exists("/etc/nftables.conf"):
            return "sudo nft list ruleset | sudo tee /etc/nftables.conf"
        elif os.path.exists("/etc/sysconfig/nftables.conf"):
            return "sudo nft list ruleset | sudo tee /etc/sysconfig/nftables.conf"
        else:
            return "sudo nft list ruleset > /path/to/rules.backup"


def detect_firewall_backend() -> str:
    """
    Detect which firewall backend is available.
    
    Returns:
        'nftables', 'iptables', or 'none'
    """
    # Check for nftables first (modern)
    if shutil.which("nft"):
        return "nftables"
    
    # Check for iptables
    if shutil.which("iptables"):
        return "iptables"
    
    return "none"


def create_firewall_manager(backend: Optional[str] = None, dry_run: bool = False, use_sudo: bool = True):
    """
    Create appropriate firewall manager based on system.
    
    Args:
        backend: Force specific backend ('nftables' or 'iptables').
        dry_run: If True, don't modify firewall.
        use_sudo: If True, use sudo for commands.
        
    Returns:
        FirewallManager or NftablesManager instance.
    """
    from .firewall import FirewallManager
    
    if backend is None:
        backend = detect_firewall_backend()
    
    if backend == "nftables":
        return NftablesManager(dry_run=dry_run, use_sudo=use_sudo)
    elif backend == "iptables":
        return FirewallManager(dry_run=dry_run, use_sudo=use_sudo)
    else:
        raise NftablesError("No firewall backend available. Install iptables or nftables.")
