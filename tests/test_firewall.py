"""
Tests for firewall manager.
"""

import pytest
from unittest.mock import patch, MagicMock
import subprocess

from deadlock_server_picker.firewall import FirewallManager, FirewallError
from deadlock_server_picker.models import Server, ServerRelay, ServerStatus


class TestFirewallManager:
    """Tests for FirewallManager."""

    @pytest.fixture
    def manager(self):
        """Create a firewall manager in dry-run mode."""
        return FirewallManager(use_sudo=False, dry_run=True)

    @pytest.fixture
    def server(self):
        """Create a test server."""
        return Server(
            name="Singapore",
            code="sgp",
            relays=[
                ServerRelay(ipv4="103.28.54.1"),
                ServerRelay(ipv4="103.28.54.2")
            ]
        )

    @pytest.fixture
    def mock_run(self):
        """Create mock for subprocess.run."""
        with patch("subprocess.run") as mock:
            mock.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            yield mock

    def test_init_defaults(self):
        """Test default initialization."""
        manager = FirewallManager()
        assert manager.use_sudo is True
        assert manager.dry_run is False

    def test_init_custom(self):
        """Test custom initialization."""
        manager = FirewallManager(use_sudo=False, dry_run=True)
        assert manager.use_sudo is False
        assert manager.dry_run is True

    def test_get_rule_name(self, manager):
        """Test rule name generation."""
        rule = manager._get_rule_name("Singapore (sgp)")
        assert rule == "DEADLOCK_SERVER_PICKER_Singapore_sgp"
        
        # Test with spaces and special chars
        rule = manager._get_rule_name("US East (iad)")
        assert rule == "DEADLOCK_SERVER_PICKER_US_East_iad"

    def test_dry_run_block(self, manager, server, capsys):
        """Test dry-run mode doesn't execute commands."""
        manager.block_server(server)
        
        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out

    def test_dry_run_unblock(self, manager, server, capsys):
        """Test dry-run unblock."""
        manager.unblock_server(server)
        
        captured = capsys.readouterr()
        # In dry run, nothing happens (server not blocked)
        assert "DRY RUN" in captured.out or captured.out == ""

    def test_is_server_blocked_dry_run(self, manager, server):
        """Test is_server_blocked in dry-run mode."""
        result = manager.is_server_blocked(server)
        assert result is False  # In dry-run, always returns False

    def test_block_servers_multiple(self, manager):
        """Test blocking multiple servers."""
        servers = [
            Server(name="Server1", code="s1", relays=[ServerRelay(ipv4="1.1.1.1")]),
            Server(name="Server2", code="s2", relays=[ServerRelay(ipv4="2.2.2.2")])
        ]
        
        blocked, already = manager.block_servers(servers)
        # In dry-run, both are "blocked"
        assert blocked == 2
        assert already == 0

    def test_unblock_servers_multiple(self, manager):
        """Test unblocking multiple servers."""
        servers = [
            Server(name="Server1", code="s1", relays=[ServerRelay(ipv4="1.1.1.1")]),
            Server(name="Server2", code="s2", relays=[ServerRelay(ipv4="2.2.2.2")])
        ]
        
        unblocked, not_blocked = manager.unblock_servers(servers)
        # In dry-run, none are blocked so none unblocked
        assert unblocked == 0
        assert not_blocked == 2

    def test_get_blocked_servers_empty(self, manager):
        """Test getting blocked servers when none are blocked."""
        blocked = manager.get_blocked_servers()
        assert blocked == []

    def test_clear_all_rules_dry_run(self, manager):
        """Test clearing all rules in dry-run."""
        count = manager.clear_all_rules()
        # Returns 1 in dry-run since we assume success
        assert count == 1

    def test_reset_firewall_dry_run(self, manager, capsys):
        """Test reset firewall in dry-run."""
        manager.reset_firewall()
        
        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out

    def test_check_permissions_dry_run(self, manager):
        """Test permission check in dry-run."""
        has_perm, msg = manager.check_permissions()
        assert has_perm is True
        assert "OK" in msg


class TestFirewallManagerWithMock:
    """Tests for FirewallManager with mocked subprocess."""

    @pytest.fixture
    def manager(self):
        """Create manager with mocked iptables path."""
        with patch("shutil.which", return_value="/sbin/iptables"):
            return FirewallManager(use_sudo=False, dry_run=False)

    @pytest.fixture
    def server(self):
        """Create a test server."""
        return Server(
            name="Singapore",
            code="sgp",
            relays=[ServerRelay(ipv4="103.28.54.1")]
        )

    def test_block_server_executes_iptables(self, manager, server):
        """Test that block_server executes correct iptables command."""
        with patch("subprocess.run") as mock_run:
            # First call: check if blocked (returns not found)
            # Second call: check chain exists
            # Third call: create chain or add rule
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="No chain/target/match by that name"
            )
            
            manager.block_server(server)
            
            # Should have called subprocess.run
            assert mock_run.called

    def test_unblock_server_updates_status(self, manager, server):
        """Test that unblock updates server status."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
            
            server.status = ServerStatus.BLOCKED
            manager.unblock_server(server)
            
            assert server.status == ServerStatus.AVAILABLE

    def test_block_server_updates_status(self, manager, server):
        """Test that block updates server status."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            
            manager.block_server(server)
            
            assert server.status == ServerStatus.BLOCKED

    def test_is_server_blocked_checks_iptables(self, manager, server):
        """Test is_server_blocked queries iptables."""
        rule_name = manager._get_rule_name(server.display_name)
        
        with patch("subprocess.run") as mock_run:
            # Return rule name in output to simulate blocked server
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=f"1 DROP 0 -- 0.0.0.0/0 103.28.54.1 /* {rule_name} */", stderr=""
            )
            
            result = manager.is_server_blocked(server)
            assert result is True

    def test_get_blocked_servers_parses_output(self, manager):
        """Test parsing blocked servers from iptables output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="1 DROP 0 -- 0.0.0.0/0 1.1.1.1 /* DEADLOCK_SERVER_PICKER_Singapore_sgp */\n"
                       "2 DROP 0 -- 0.0.0.0/0 2.2.2.2 /* DEADLOCK_SERVER_PICKER_Hong_Kong_hkg */",
                stderr=""
            )
            
            blocked = manager.get_blocked_servers()
            
            assert len(blocked) == 2
            assert "Singapore sgp" in blocked
            assert "Hong Kong hkg" in blocked

    def test_firewall_error_handling(self, manager, server):
        """Test error handling for firewall operations."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="Permission denied"
            )
            
            with pytest.raises(FirewallError):
                manager._run_command(["/sbin/iptables", "-L"], check=True)

    def test_check_permissions_success(self, manager):
        """Test permission check when access is granted."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Chain INPUT ...", stderr=""
            )
            
            has_perm, msg = manager.check_permissions()
            assert has_perm is True

    def test_check_permissions_denied(self, manager):
        """Test permission check when access is denied."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="Permission denied"
            )
            
            has_perm, msg = manager.check_permissions()
            assert has_perm is False
            assert "Permission denied" in msg


class TestFirewallManagerFindIptables:
    """Tests for iptables path finding."""

    def test_find_iptables_in_path(self):
        """Test finding iptables in PATH."""
        with patch("shutil.which", return_value="/usr/sbin/iptables"):
            manager = FirewallManager(dry_run=True)
            assert manager._iptables_path == "/usr/sbin/iptables"

    def test_find_iptables_fallback(self):
        """Test fallback paths for iptables."""
        def which_side_effect(path):
            if path == "iptables":
                return None
            elif path == "/sbin/iptables":
                return "/sbin/iptables"
            return None
        
        with patch("shutil.which", side_effect=which_side_effect):
            manager = FirewallManager(dry_run=True)
            assert "/sbin/iptables" in manager._iptables_path

    def test_iptables_not_found(self):
        """Test error when iptables is not found."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(FirewallError) as exc_info:
                FirewallManager(dry_run=True)
            
            assert "iptables not found" in str(exc_info.value)
