"""
Firewall manager - manages iptables rules for blocking/unblocking Deadlock servers on Linux.
"""

import subprocess
import shutil
from typing import Optional

from .models import Server, ServerStatus


class FirewallError(Exception):
    """Raised when firewall operations fail."""
    pass


class FirewallManager:
    """
    Manages iptables firewall rules for blocking Deadlock server relays.
    
    Uses iptables to create OUTPUT chain rules that block traffic to
    specific IP addresses, preventing connection to unwanted servers.
    """

    RULE_PREFIX = "DEADLOCK_SERVER_PICKER"
    CHAIN_NAME = "DEADLOCK_SERVER_PICKER"

    def __init__(self, use_sudo: bool = True, dry_run: bool = False):
        """
        Initialize firewall manager.
        
        Args:
            use_sudo: Whether to use sudo for iptables commands.
            dry_run: If True, only simulate commands without executing.
        """
        self.use_sudo = use_sudo
        self.dry_run = dry_run
        self._iptables_path = self._find_iptables()

    def _find_iptables(self) -> str:
        """Find iptables executable path."""
        iptables = shutil.which("iptables")
        if not iptables:
            # Try common paths
            for path in ["/sbin/iptables", "/usr/sbin/iptables"]:
                if shutil.which(path):
                    return path
            raise FirewallError("iptables not found. Please install iptables.")
        return iptables

    def _run_command(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """
        Run a command with optional sudo.
        
        Args:
            args: Command arguments (without sudo).
            check: Whether to check return code.
            
        Returns:
            CompletedProcess result.
            
        Raises:
            FirewallError: If command fails.
        """
        cmd = []
        if self.use_sudo:
            cmd.append("sudo")
        cmd.extend(args)

        if self.dry_run:
            print(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if check and result.returncode != 0:
                # Some errors are expected (e.g., rule doesn't exist)
                if "No chain/target/match by that name" not in result.stderr:
                    raise FirewallError(
                        f"Command failed: {' '.join(cmd)}\n"
                        f"stdout: {result.stdout}\n"
                        f"stderr: {result.stderr}"
                    )
            
            return result
            
        except FileNotFoundError as e:
            raise FirewallError(f"Command not found: {e}") from e

    def _get_rule_name(self, server_name: str) -> str:
        """
        Get a sanitized rule name for a server.
        
        Args:
            server_name: Server name to sanitize.
            
        Returns:
            Sanitized rule name.
        """
        # Remove spaces and special characters
        sanitized = server_name.replace(" ", "_").replace("(", "").replace(")", "")
        return f"{self.RULE_PREFIX}_{sanitized}"

    def ensure_chain_exists(self) -> None:
        """
        Ensure the Deadlock Server Picker iptables chain exists.
        
        Creates a dedicated chain and hooks it into OUTPUT and FORWARD chains
        for complete traffic blocking (including Wine/Proton games).
        """
        # Check if chain exists
        result = self._run_command(
            [self._iptables_path, "-L", self.CHAIN_NAME, "-n"],
            check=False
        )
        
        if result.returncode != 0:
            # Create the chain
            self._run_command([self._iptables_path, "-N", self.CHAIN_NAME])
            
            # Add jump from OUTPUT to our chain (for native apps)
            self._run_command([
                self._iptables_path, "-I", "OUTPUT", "1",
                "-j", self.CHAIN_NAME,
                "-m", "comment", "--comment", self.RULE_PREFIX
            ])
            
            # Add jump from FORWARD to our chain (for Wine/Proton/VMs)
            # This ensures traffic routed through the system is also blocked
            self._run_command([
                self._iptables_path, "-I", "FORWARD", "1",
                "-j", self.CHAIN_NAME,
                "-m", "comment", "--comment", self.RULE_PREFIX
            ])

    def is_server_blocked(self, server: Server) -> bool:
        """
        Check if a server is currently blocked.
        
        Args:
            server: Server to check.
            
        Returns:
            True if server is blocked, False otherwise.
        """
        rule_name = self._get_rule_name(server.display_name)
        
        result = self._run_command(
            [self._iptables_path, "-L", self.CHAIN_NAME, "-n", "--line-numbers"],
            check=False
        )
        
        if result.returncode != 0:
            return False
            
        return rule_name in result.stdout

    def block_server(self, server: Server) -> bool:
        """
        Block a server by adding iptables rules.
        
        Args:
            server: Server to block.
            
        Returns:
            True if server was blocked, False if already blocked.
            
        Raises:
            FirewallError: If blocking fails.
        """
        if self.is_server_blocked(server):
            return False

        self.ensure_chain_exists()
        
        rule_name = self._get_rule_name(server.display_name)
        ip_list = ",".join(server.ip_addresses)

        self._run_command([
            self._iptables_path, "-A", self.CHAIN_NAME,
            "-d", ip_list,
            "-j", "DROP",
            "-m", "comment", "--comment", rule_name
        ])

        server.status = ServerStatus.BLOCKED
        return True

    def unblock_server(self, server: Server) -> bool:
        """
        Unblock a server by removing iptables rules.
        
        Args:
            server: Server to unblock.
            
        Returns:
            True if server was unblocked, False if not blocked.
            
        Raises:
            FirewallError: If unblocking fails.
        """
        if not self.is_server_blocked(server):
            server.status = ServerStatus.AVAILABLE
            return False

        rule_name = self._get_rule_name(server.display_name)

        # Find and delete rules with our comment
        result = self._run_command(
            [self._iptables_path, "-L", self.CHAIN_NAME, "-n", "--line-numbers"],
            check=False
        )
        
        if result.returncode == 0:
            # Parse line numbers of rules to delete (in reverse order)
            lines_to_delete = []
            for line in result.stdout.splitlines():
                if rule_name in line:
                    parts = line.split()
                    if parts and parts[0].isdigit():
                        lines_to_delete.append(int(parts[0]))
            
            # Delete in reverse order to maintain line numbers
            for line_num in sorted(lines_to_delete, reverse=True):
                self._run_command([
                    self._iptables_path, "-D", self.CHAIN_NAME, str(line_num)
                ])

        server.status = ServerStatus.AVAILABLE
        return True

    def block_servers(self, servers: list[Server]) -> tuple[int, int]:
        """
        Block multiple servers.
        
        Args:
            servers: List of servers to block.
            
        Returns:
            Tuple of (blocked_count, already_blocked_count).
        """
        blocked = 0
        already_blocked = 0
        
        for server in servers:
            if self.block_server(server):
                blocked += 1
            else:
                already_blocked += 1
                
        return blocked, already_blocked

    def unblock_servers(self, servers: list[Server]) -> tuple[int, int]:
        """
        Unblock multiple servers.
        
        Args:
            servers: List of servers to unblock.
            
        Returns:
            Tuple of (unblocked_count, not_blocked_count).
        """
        unblocked = 0
        not_blocked = 0
        
        for server in servers:
            if self.unblock_server(server):
                unblocked += 1
            else:
                not_blocked += 1
                
        return unblocked, not_blocked

    def get_blocked_servers(self) -> list[str]:
        """
        Get list of currently blocked server names.
        
        Returns:
            List of blocked server rule names.
        """
        result = self._run_command(
            [self._iptables_path, "-L", self.CHAIN_NAME, "-n", "-v"],
            check=False
        )
        
        if result.returncode != 0:
            return []
            
        blocked = []
        for line in result.stdout.splitlines():
            if self.RULE_PREFIX in line:
                # Extract the comment (rule name)
                parts = line.split("/*")
                if len(parts) > 1:
                    rule_name = parts[1].split("*/")[0].strip()
                    # Remove prefix to get server name
                    server_name = rule_name.replace(f"{self.RULE_PREFIX}_", "").replace("_", " ")
                    blocked.append(server_name)
                    
        return blocked

    def clear_all_rules(self) -> int:
        """
        Remove all Deadlock Server Picker firewall rules.
        
        Returns:
            Number of rules removed.
        """
        # Flush our custom chain
        result = self._run_command(
            [self._iptables_path, "-F", self.CHAIN_NAME],
            check=False
        )
        
        if result.returncode != 0:
            return 0
            
        # Count could be tracked, but for simplicity return 1 if chain existed
        return 1

    def reset_firewall(self) -> None:
        """
        Remove all Deadlock Server Picker rules and chain.
        
        This is more thorough than clear_all_rules as it removes
        the chain entirely, including references from OUTPUT and FORWARD chains.
        """
        # First flush the chain
        self._run_command(
            [self._iptables_path, "-F", self.CHAIN_NAME],
            check=False
        )
        
        # Remove jump rule from OUTPUT
        self._run_command(
            [self._iptables_path, "-D", "OUTPUT", "-j", self.CHAIN_NAME,
             "-m", "comment", "--comment", self.RULE_PREFIX],
            check=False
        )
        
        # Remove jump rule from FORWARD (for Wine/Proton compatibility)
        self._run_command(
            [self._iptables_path, "-D", "FORWARD", "-j", self.CHAIN_NAME,
             "-m", "comment", "--comment", self.RULE_PREFIX],
            check=False
        )
        
        # Delete the chain
        self._run_command(
            [self._iptables_path, "-X", self.CHAIN_NAME],
            check=False
        )

    def check_permissions(self) -> tuple[bool, str]:
        """
        Check if we have permissions to manage firewall rules.
        
        Returns:
            Tuple of (has_permission, message).
        """
        # Try to list rules
        result = self._run_command(
            [self._iptables_path, "-L", "-n"],
            check=False
        )
        
        if result.returncode == 0:
            return True, "Firewall access OK"
        
        if "Permission denied" in result.stderr or "Operation not permitted" in result.stderr:
            if self.use_sudo:
                return False, "Permission denied. Try running with sudo or as root."
            else:
                return False, "Permission denied. Enable use_sudo or run as root."
        
        return False, f"Unknown error: {result.stderr}"

    def save_rules(self) -> bool:
        """
        Save current iptables rules to persist across reboots.
        
        Uses iptables-save to export rules. User should redirect output
        to appropriate location based on their distro.
        
        Returns:
            True if successful, False otherwise.
        """
        import shutil
        
        iptables_save = shutil.which("iptables-save")
        if not iptables_save:
            for path in ["/sbin/iptables-save", "/usr/sbin/iptables-save"]:
                if shutil.which(path):
                    iptables_save = path
                    break
        
        if not iptables_save:
            return False
        
        result = self._run_command([iptables_save], check=False)
        return result.returncode == 0

    def get_save_command(self) -> str:
        """
        Get the command to save iptables rules persistently.
        
        Returns distro-appropriate command string.
        """
        import os
        
        # Check for common distro configurations
        if os.path.exists("/etc/iptables/rules.v4"):
            # Debian/Ubuntu with iptables-persistent
            return "sudo iptables-save | sudo tee /etc/iptables/rules.v4"
        elif os.path.exists("/etc/sysconfig/iptables"):
            # RHEL/CentOS/Fedora
            return "sudo iptables-save | sudo tee /etc/sysconfig/iptables"
        elif os.path.exists("/etc/iptables"):
            # Arch Linux
            return "sudo iptables-save | sudo tee /etc/iptables/iptables.rules"
        else:
            # Generic
            return "sudo iptables-save > /path/to/rules.backup"
        
        return False, f"Firewall check failed: {result.stderr}"
