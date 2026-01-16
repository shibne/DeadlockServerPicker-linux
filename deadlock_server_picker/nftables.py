"""
nftables firewall backend for Deadlock Server Picker.
Modern alternative to iptables with optimized batch operations.
"""

import subprocess
import shutil
import tempfile
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
        self._blocked_cache: Optional[set[str]] = None
    
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
    
    def _run_batch(self, script: str) -> subprocess.CompletedProcess:
        """
        Run a batch nftables script atomically.
        
        Args:
            script: nft script content.
            
        Returns:
            CompletedProcess with output.
        """
        if self.dry_run:
            return subprocess.CompletedProcess([], 0, "", "")
        
        # Write script to temp file and execute with -f
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nft', delete=False) as f:
            f.write(script)
            script_path = f.name
        
        try:
            cmd = [self._nft_path, "-f", script_path]
            if self.use_sudo:
                cmd = ["sudo"] + cmd
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result
        finally:
            import os
            os.unlink(script_path)
    
    def _get_rule_comment(self, server_name: str) -> str:
        """Get a comment identifier for a server rule."""
        sanitized = server_name.replace(" ", "_").replace("(", "").replace(")", "")
        return f"dsp_{sanitized}"
    
    def _invalidate_cache(self):
        """Invalidate the blocked servers cache."""
        self._blocked_cache = None
    
    def _get_blocked_set(self) -> set[str]:
        """Get set of blocked server comments (cached)."""
        if self._blocked_cache is not None:
            return self._blocked_cache
        
        result = self._run_command([
            self._nft_path, "list", "table", "inet", self.TABLE_NAME
        ], check=False)
        
        if result.returncode != 0:
            self._blocked_cache = set()
            return self._blocked_cache
        
        blocked = set()
        for line in result.stdout.splitlines():
            if 'comment "dsp_' in line:
                start = line.find('comment "dsp_') + 9
                end = line.find('"', start + 1)
                if start > 9 and end > start:
                    comment = line[start:end]
                    blocked.add(comment)
        
        self._blocked_cache = blocked
        return self._blocked_cache
    
    def ensure_table_exists(self) -> None:
        """Ensure the nftables table and chains exist."""
        # Use add which is idempotent (won't fail if exists)
        self._run_command([
            self._nft_path, "add", "table", "inet", self.TABLE_NAME
        ], check=False)
        
        self._run_command([
            self._nft_path, "add", "chain", "inet", self.TABLE_NAME, self.CHAIN_NAME,
            "{ type filter hook output priority 0; policy accept; }"
        ], check=False)
        
        self._run_command([
            self._nft_path, "add", "chain", "inet", self.TABLE_NAME, "forward_block",
            "{ type filter hook forward priority 0; policy accept; }"
        ], check=False)
    
    def is_server_blocked(self, server: Server) -> bool:
        """Check if a server is currently blocked."""
        comment = self._get_rule_comment(server.display_name)
        return comment in self._get_blocked_set()
    
    def block_server(self, server: Server) -> bool:
        """
        Block a server by adding nftables rules.
        
        Returns:
            True if server was blocked, False if already blocked.
        """
        comment = self._get_rule_comment(server.display_name)
        
        if comment in self._get_blocked_set():
            return False
        
        self.ensure_table_exists()
        
        # Build batch script for atomic operation
        lines = []
        for ip in server.ip_addresses:
            lines.append(
                f'add rule inet {self.TABLE_NAME} {self.CHAIN_NAME} '
                f'ip daddr {ip} drop comment "{comment}"'
            )
            lines.append(
                f'add rule inet {self.TABLE_NAME} forward_block '
                f'ip daddr {ip} drop comment "{comment}"'
            )
        
        script = "\n".join(lines)
        self._run_batch(script)
        
        self._invalidate_cache()
        server.status = ServerStatus.BLOCKED
        return True
    
    def unblock_server(self, server: Server) -> bool:
        """
        Unblock a server by removing nftables rules.
        
        Returns:
            True if server was unblocked, False if not blocked.
        """
        comment = self._get_rule_comment(server.display_name)
        
        if comment not in self._get_blocked_set():
            server.status = ServerStatus.AVAILABLE
            return False
        
        # Get rule handles to delete
        result = self._run_command([
            self._nft_path, "-a", "list", "table", "inet", self.TABLE_NAME
        ], check=False)
        
        if result.returncode == 0:
            # Find handles to delete
            handles_to_delete = []
            current_chain = None
            
            for line in result.stdout.splitlines():
                line_stripped = line.strip()
                if line_stripped.startswith("chain "):
                    current_chain = line_stripped.split()[1]
                elif comment in line and "handle" in line:
                    parts = line.split("handle")
                    if len(parts) > 1:
                        handle = parts[1].strip().split()[0]
                        handles_to_delete.append((current_chain, handle))
            
            # Batch delete rules
            if handles_to_delete:
                lines = []
                for chain, handle in handles_to_delete:
                    lines.append(
                        f'delete rule inet {self.TABLE_NAME} {chain} handle {handle}'
                    )
                script = "\n".join(lines)
                self._run_batch(script)
        
        self._invalidate_cache()
        server.status = ServerStatus.AVAILABLE
        return True
    
    def block_servers(self, servers: list[Server]) -> tuple[int, int]:
        """Block multiple servers in a single batch operation."""
        # Get currently blocked set once
        blocked_set = self._get_blocked_set()
        
        to_block = []
        already_blocked = 0
        
        for server in servers:
            comment = self._get_rule_comment(server.display_name)
            if comment in blocked_set:
                already_blocked += 1
            else:
                to_block.append(server)
        
        if not to_block:
            return 0, already_blocked
        
        self.ensure_table_exists()
        
        # Build batch script for all servers
        lines = []
        for server in to_block:
            comment = self._get_rule_comment(server.display_name)
            for ip in server.ip_addresses:
                lines.append(
                    f'add rule inet {self.TABLE_NAME} {self.CHAIN_NAME} '
                    f'ip daddr {ip} drop comment "{comment}"'
                )
                lines.append(
                    f'add rule inet {self.TABLE_NAME} forward_block '
                    f'ip daddr {ip} drop comment "{comment}"'
                )
        
        script = "\n".join(lines)
        self._run_batch(script)
        
        # Update server status
        for server in to_block:
            server.status = ServerStatus.BLOCKED
        
        self._invalidate_cache()
        return len(to_block), already_blocked
    
    def unblock_servers(self, servers: list[Server]) -> tuple[int, int]:
        """Unblock multiple servers in a single batch operation."""
        # Get currently blocked set once
        blocked_set = self._get_blocked_set()
        
        to_unblock = []
        not_blocked = 0
        
        for server in servers:
            comment = self._get_rule_comment(server.display_name)
            if comment not in blocked_set:
                server.status = ServerStatus.AVAILABLE
                not_blocked += 1
            else:
                to_unblock.append((server, comment))
        
        if not to_unblock:
            return 0, not_blocked
        
        # Get all handles at once
        result = self._run_command([
            self._nft_path, "-a", "list", "table", "inet", self.TABLE_NAME
        ], check=False)
        
        if result.returncode != 0:
            return 0, not_blocked + len(to_unblock)
        
        # Build set of comments to delete
        comments_to_delete = {comment for _, comment in to_unblock}
        
        # Find all handles to delete
        handles_to_delete = []
        current_chain = None
        
        for line in result.stdout.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("chain "):
                current_chain = line_stripped.split()[1]
            elif "handle" in line:
                for comment in comments_to_delete:
                    if comment in line:
                        parts = line.split("handle")
                        if len(parts) > 1:
                            handle = parts[1].strip().split()[0]
                            handles_to_delete.append((current_chain, handle))
                        break
        
        # Batch delete all rules
        if handles_to_delete:
            lines = []
            for chain, handle in handles_to_delete:
                lines.append(
                    f'delete rule inet {self.TABLE_NAME} {chain} handle {handle}'
                )
            script = "\n".join(lines)
            self._run_batch(script)
        
        # Update server status
        for server, _ in to_unblock:
            server.status = ServerStatus.AVAILABLE
        
        self._invalidate_cache()
        return len(to_unblock), not_blocked
    
    def get_blocked_servers(self) -> list[str]:
        """Get list of currently blocked server names."""
        blocked_set = self._get_blocked_set()
        
        # Convert comments back to names
        blocked_names = []
        for comment in blocked_set:
            # Remove dsp_ prefix and convert underscores back
            if comment.startswith("dsp_"):
                name = comment[4:].replace("_", " ")
                blocked_names.append(name)
        
        return blocked_names
    
    def clear_all_rules(self) -> int:
        """Remove all rules from our table. Returns rule count removed."""
        # Flush both chains at once
        script = f"""
flush chain inet {self.TABLE_NAME} {self.CHAIN_NAME}
flush chain inet {self.TABLE_NAME} forward_block
"""
        self._run_batch(script)
        self._invalidate_cache()
        return 1
    
    def reset_firewall(self) -> None:
        """Remove all rules and delete the table entirely."""
        self._run_command([
            self._nft_path, "delete", "table", "inet", self.TABLE_NAME
        ], check=False)
        self._invalidate_cache()
    
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
