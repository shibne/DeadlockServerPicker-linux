"""
Tests for the TUI module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from deadlock_server_picker.tui import ServerPickerTUI, run_tui
from deadlock_server_picker.models import Server, ServerRelay


# Fixtures
@pytest.fixture
def mock_servers():
    """Create mock servers for testing."""
    return [
        Server(
            code="sgp",
            name="Singapore",
            relays=[ServerRelay(ipv4="1.2.3.4")],
        ),
        Server(
            code="tyo",
            name="Tokyo",
            relays=[ServerRelay(ipv4="5.6.7.8")],
        ),
        Server(
            code="iad",
            name="US East",
            relays=[ServerRelay(ipv4="9.10.11.12")],
        ),
        Server(
            code="fra",
            name="Frankfurt",
            relays=[ServerRelay(ipv4="13.14.15.16")],
        ),
    ]


@pytest.fixture
def tui_dry_run(mock_servers):
    """Create TUI in dry-run mode with mocked components."""
    with patch('deadlock_server_picker.tui.ServerDataFetcher') as mock_fetcher_class, \
         patch('deadlock_server_picker.tui.FirewallManager') as mock_firewall_class, \
         patch('deadlock_server_picker.tui.PingService') as mock_ping_class, \
         patch('deadlock_server_picker.tui.PresetManager') as mock_preset_class:
        
        # Setup fetcher mock
        mock_fetcher = Mock()
        mock_fetcher.fetch.return_value = "12345"
        mock_fetcher.get_servers.return_value = {s.code: s for s in mock_servers}
        mock_fetcher.get_server_by_name.side_effect = lambda name: next(
            (s for s in mock_servers if s.code == name or name.lower() in s.name.lower()),
            None
        )
        mock_fetcher_class.return_value = mock_fetcher
        
        # Setup firewall mock
        mock_firewall = Mock()
        mock_firewall.get_blocked_servers.return_value = []
        mock_firewall.block_servers.return_value = (1, 0)
        mock_firewall.unblock_servers.return_value = (1, 0)
        mock_firewall.reset_firewall.return_value = None
        mock_firewall_class.return_value = mock_firewall
        
        # Setup ping service mock
        mock_ping = Mock()
        mock_ping.ping_servers.return_value = None
        mock_ping_class.return_value = mock_ping
        
        # Setup preset manager mock
        mock_preset = Mock()
        mock_preset_class.return_value = mock_preset
        
        tui = ServerPickerTUI(dry_run=True)
        tui.servers = mock_servers
        tui.server_status = {s.code: False for s in mock_servers}
        
        yield tui


class TestServerPickerTUIInit:
    """Tests for TUI initialization."""
    
    def test_init_dry_run(self):
        """TUI should initialize in dry-run mode."""
        with patch('deadlock_server_picker.tui.ServerDataFetcher'), \
             patch('deadlock_server_picker.tui.FirewallManager'), \
             patch('deadlock_server_picker.tui.PingService'), \
             patch('deadlock_server_picker.tui.PresetManager'):
            tui = ServerPickerTUI(dry_run=True)
            assert tui.dry_run is True
            assert tui.servers == []
            assert tui.server_status == {}
    
    def test_init_default(self):
        """TUI should initialize with default settings."""
        with patch('deadlock_server_picker.tui.ServerDataFetcher'), \
             patch('deadlock_server_picker.tui.FirewallManager'), \
             patch('deadlock_server_picker.tui.PingService'), \
             patch('deadlock_server_picker.tui.PresetManager'):
            tui = ServerPickerTUI()
            assert tui.dry_run is False


class TestHandleCommand:
    """Tests for TUI command handling."""
    
    def test_quit_command(self, tui_dry_run):
        """quit command should return False to stop running."""
        running, success = tui_dry_run.handle_command("quit")
        assert running is False
        assert success is True
    
    def test_quit_q_alias(self, tui_dry_run):
        """q should be alias for quit."""
        running, success = tui_dry_run.handle_command("q")
        assert running is False
        assert success is True
    
    def test_quit_exit_alias(self, tui_dry_run):
        """exit should be alias for quit."""
        running, success = tui_dry_run.handle_command("exit")
        assert running is False
        assert success is True
    
    def test_list_command(self, tui_dry_run):
        """list command should show all servers."""
        running, success = tui_dry_run.handle_command("list")
        assert running is True
        assert success is True
    
    def test_list_l_alias(self, tui_dry_run):
        """l should be alias for list."""
        running, success = tui_dry_run.handle_command("l")
        assert running is True
        assert success is True
    
    def test_list_ls_alias(self, tui_dry_run):
        """ls should be alias for list."""
        running, success = tui_dry_run.handle_command("ls")
        assert running is True
        assert success is True
    
    def test_list_with_region(self, tui_dry_run):
        """list with region should filter servers."""
        running, success = tui_dry_run.handle_command("list na")
        assert running is True
        # May return False if no NA servers in mock data
    
    def test_list_with_invalid_region(self, tui_dry_run):
        """list with invalid region should fail gracefully."""
        running, success = tui_dry_run.handle_command("list invalidregion")
        assert running is True
        assert success is False
    
    def test_regions_command(self, tui_dry_run):
        """regions command should show available regions."""
        running, success = tui_dry_run.handle_command("regions")
        assert running is True
        assert success is True
    
    def test_regions_r_alias(self, tui_dry_run):
        """r should be alias for regions."""
        running, success = tui_dry_run.handle_command("r")
        assert running is True
        assert success is True
    
    def test_block_command(self, tui_dry_run):
        """block command should block a server."""
        running, success = tui_dry_run.handle_command("block sgp")
        assert running is True
        assert success is True
        assert tui_dry_run.server_status["sgp"] is True
    
    def test_block_without_argument(self, tui_dry_run):
        """block without argument should fail."""
        running, success = tui_dry_run.handle_command("block")
        assert running is True
        assert success is False
    
    def test_block_invalid_server(self, tui_dry_run):
        """block with invalid server should fail."""
        running, success = tui_dry_run.handle_command("block invalidserver")
        assert running is True
        assert success is False
    
    def test_unblock_command(self, tui_dry_run):
        """unblock command should unblock a server."""
        # First block the server
        tui_dry_run.server_status["sgp"] = True
        running, success = tui_dry_run.handle_command("unblock sgp")
        assert running is True
        assert success is True
        assert tui_dry_run.server_status["sgp"] is False
    
    def test_unblock_without_argument(self, tui_dry_run):
        """unblock without argument should fail."""
        running, success = tui_dry_run.handle_command("unblock")
        assert running is True
        assert success is False
    
    def test_allow_region_command(self, tui_dry_run):
        """allow command should allow only region servers."""
        running, success = tui_dry_run.handle_command("allow asia")
        assert running is True
        assert success is True
    
    def test_allow_without_argument(self, tui_dry_run):
        """allow without argument should fail."""
        running, success = tui_dry_run.handle_command("allow")
        assert running is True
        assert success is False
    
    def test_allow_invalid_region(self, tui_dry_run):
        """allow with invalid region should fail."""
        running, success = tui_dry_run.handle_command("allow invalidregion")
        assert running is True
        assert success is False
    
    def test_block_region_command(self, tui_dry_run):
        """block-region command should block all servers in region."""
        running, success = tui_dry_run.handle_command("block-region eu")
        assert running is True
        assert success is True
    
    def test_block_region_without_argument(self, tui_dry_run):
        """block-region without argument should fail."""
        running, success = tui_dry_run.handle_command("block-region")
        assert running is True
        assert success is False
    
    def test_unblock_region_command(self, tui_dry_run):
        """unblock-region command should unblock all servers in region."""
        running, success = tui_dry_run.handle_command("unblock-region eu")
        assert running is True
        assert success is True
    
    def test_unblock_region_without_argument(self, tui_dry_run):
        """unblock-region without argument should fail."""
        running, success = tui_dry_run.handle_command("unblock-region")
        assert running is True
        assert success is False
    
    def test_ping_command(self, tui_dry_run):
        """ping command should ping all servers."""
        running, success = tui_dry_run.handle_command("ping")
        assert running is True
        assert success is True
    
    def test_ping_with_region(self, tui_dry_run):
        """ping with region should ping only region servers."""
        running, success = tui_dry_run.handle_command("ping asia")
        assert running is True
        assert success is True
    
    def test_reset_command(self, tui_dry_run):
        """reset command should unblock all servers."""
        # Block some servers first
        tui_dry_run.server_status["sgp"] = True
        tui_dry_run.server_status["tyo"] = True
        
        running, success = tui_dry_run.handle_command("reset")
        assert running is True
        assert success is True
        
        # All servers should be unblocked
        for code in tui_dry_run.server_status:
            assert tui_dry_run.server_status[code] is False
    
    def test_status_command(self, tui_dry_run):
        """status command should show current status."""
        running, success = tui_dry_run.handle_command("status")
        assert running is True
        assert success is True
    
    def test_status_s_alias(self, tui_dry_run):
        """s should be alias for status."""
        running, success = tui_dry_run.handle_command("s")
        assert running is True
        assert success is True
    
    def test_help_command(self, tui_dry_run):
        """help command should show help."""
        running, success = tui_dry_run.handle_command("help")
        assert running is True
        assert success is True
    
    def test_help_h_alias(self, tui_dry_run):
        """h should be alias for help."""
        running, success = tui_dry_run.handle_command("h")
        assert running is True
        assert success is True
    
    def test_help_question_alias(self, tui_dry_run):
        """? should be alias for help."""
        running, success = tui_dry_run.handle_command("?")
        assert running is True
        assert success is True
    
    def test_clear_command(self, tui_dry_run):
        """clear command should clear screen."""
        running, success = tui_dry_run.handle_command("clear")
        assert running is True
        assert success is True
    
    def test_clear_cls_alias(self, tui_dry_run):
        """cls should be alias for clear."""
        running, success = tui_dry_run.handle_command("cls")
        assert running is True
        assert success is True
    
    def test_clear_c_alias(self, tui_dry_run):
        """c should be alias for clear."""
        running, success = tui_dry_run.handle_command("c")
        assert running is True
        assert success is True
    
    def test_unknown_command(self, tui_dry_run):
        """Unknown command should fail gracefully."""
        running, success = tui_dry_run.handle_command("unknowncommand")
        assert running is True
        assert success is False
    
    def test_empty_command(self, tui_dry_run):
        """Empty command should be handled gracefully."""
        running, success = tui_dry_run.handle_command("")
        assert running is True
        assert success is True
    
    def test_whitespace_command(self, tui_dry_run):
        """Whitespace-only command should be handled gracefully."""
        running, success = tui_dry_run.handle_command("   ")
        assert running is True
        assert success is True


class TestShowServers:
    """Tests for show_servers method."""
    
    def test_show_all_servers(self, tui_dry_run):
        """Should show all servers when no filter."""
        result = tui_dry_run.show_servers()
        assert result is True
    
    def test_show_servers_with_valid_region(self, tui_dry_run):
        """Should show servers filtered by region."""
        result = tui_dry_run.show_servers("asia")
        assert result is True
    
    def test_show_servers_with_invalid_region(self, tui_dry_run):
        """Should return False for invalid region."""
        result = tui_dry_run.show_servers("invalidregion")
        assert result is False


class TestShowRegions:
    """Tests for show_regions method."""
    
    def test_show_regions(self, tui_dry_run):
        """Should show available regions."""
        result = tui_dry_run.show_regions()
        assert result is True


class TestBlockServer:
    """Tests for block_server method."""
    
    def test_block_valid_server(self, tui_dry_run):
        """Should block a valid server."""
        result = tui_dry_run.block_server("sgp")
        assert result is True
        assert tui_dry_run.server_status["sgp"] is True
    
    def test_block_invalid_server(self, tui_dry_run):
        """Should return False for invalid server."""
        result = tui_dry_run.block_server("invalidserver")
        assert result is False
    
    def test_block_already_blocked_server(self, tui_dry_run):
        """Should return True for already blocked server."""
        tui_dry_run.server_status["sgp"] = True
        result = tui_dry_run.block_server("sgp")
        assert result is True


class TestUnblockServer:
    """Tests for unblock_server method."""
    
    def test_unblock_blocked_server(self, tui_dry_run):
        """Should unblock a blocked server."""
        tui_dry_run.server_status["sgp"] = True
        result = tui_dry_run.unblock_server("sgp")
        assert result is True
        assert tui_dry_run.server_status["sgp"] is False
    
    def test_unblock_invalid_server(self, tui_dry_run):
        """Should return False for invalid server."""
        result = tui_dry_run.unblock_server("invalidserver")
        assert result is False
    
    def test_unblock_not_blocked_server(self, tui_dry_run):
        """Should return True for not blocked server."""
        tui_dry_run.server_status["sgp"] = False
        result = tui_dry_run.unblock_server("sgp")
        assert result is True


class TestAllowOnlyRegion:
    """Tests for allow_only_region method."""
    
    def test_allow_valid_region(self, tui_dry_run):
        """Should allow only servers in region."""
        result = tui_dry_run.allow_only_region("asia")
        assert result is True
    
    def test_allow_invalid_region(self, tui_dry_run):
        """Should return False for invalid region."""
        result = tui_dry_run.allow_only_region("invalidregion")
        assert result is False


class TestBlockRegion:
    """Tests for block_region method."""
    
    def test_block_valid_region(self, tui_dry_run):
        """Should block all servers in region."""
        result = tui_dry_run.block_region("eu")
        assert result is True
    
    def test_block_invalid_region(self, tui_dry_run):
        """Should return False for invalid region."""
        result = tui_dry_run.block_region("invalidregion")
        assert result is False


class TestUnblockRegion:
    """Tests for unblock_region method."""
    
    def test_unblock_valid_region(self, tui_dry_run):
        """Should unblock all servers in region."""
        result = tui_dry_run.unblock_region("eu")
        assert result is True
    
    def test_unblock_invalid_region(self, tui_dry_run):
        """Should return False for invalid region."""
        result = tui_dry_run.unblock_region("invalidregion")
        assert result is False


class TestPingServers:
    """Tests for ping_servers method."""
    
    def test_ping_all_servers(self, tui_dry_run):
        """Should ping all servers."""
        result = tui_dry_run.ping_servers()
        assert result is True
    
    def test_ping_valid_region(self, tui_dry_run):
        """Should ping servers in region."""
        result = tui_dry_run.ping_servers("asia")
        assert result is True
    
    def test_ping_invalid_region(self, tui_dry_run):
        """Should return False for invalid region."""
        result = tui_dry_run.ping_servers("invalidregion")
        assert result is False


class TestResetAll:
    """Tests for reset_all method."""
    
    def test_reset_all(self, tui_dry_run):
        """Should unblock all servers."""
        # Block some servers first
        tui_dry_run.server_status["sgp"] = True
        tui_dry_run.server_status["tyo"] = True
        
        result = tui_dry_run.reset_all()
        assert result is True
        
        for code in tui_dry_run.server_status:
            assert tui_dry_run.server_status[code] is False


class TestShowStatus:
    """Tests for show_status method."""
    
    def test_show_status(self, tui_dry_run):
        """Should show current status."""
        result = tui_dry_run.show_status()
        assert result is True
    
    def test_show_status_with_blocked_servers(self, tui_dry_run):
        """Should show status with blocked servers."""
        tui_dry_run.server_status["sgp"] = True
        tui_dry_run.server_status["tyo"] = True
        result = tui_dry_run.show_status()
        assert result is True


class TestCheckSudoAccess:
    """Tests for _check_sudo_access method."""
    
    def test_sudo_check_dry_run(self, tui_dry_run):
        """Should skip sudo check in dry-run mode."""
        result = tui_dry_run._check_sudo_access()
        assert result is True
    
    @patch('subprocess.run')
    def test_sudo_check_success(self, mock_run):
        """Should return True when sudo succeeds."""
        mock_run.return_value = Mock(returncode=0)
        
        with patch('deadlock_server_picker.tui.ServerDataFetcher'), \
             patch('deadlock_server_picker.tui.FirewallManager'), \
             patch('deadlock_server_picker.tui.PingService'), \
             patch('deadlock_server_picker.tui.PresetManager'):
            tui = ServerPickerTUI(dry_run=False)
            result = tui._check_sudo_access()
            assert result is True
    
    @patch('subprocess.run')
    def test_sudo_check_failure(self, mock_run):
        """Should return False when sudo fails."""
        mock_run.return_value = Mock(returncode=1)
        
        with patch('deadlock_server_picker.tui.ServerDataFetcher'), \
             patch('deadlock_server_picker.tui.FirewallManager'), \
             patch('deadlock_server_picker.tui.PingService'), \
             patch('deadlock_server_picker.tui.PresetManager'):
            tui = ServerPickerTUI(dry_run=False)
            result = tui._check_sudo_access()
            assert result is False


class TestGetSummaryText:
    """Tests for _get_summary_text method."""
    
    def test_summary_text_all_allowed(self, tui_dry_run):
        """Summary should show all allowed when none blocked."""
        summary = tui_dry_run._get_summary_text()
        text = str(summary)
        assert "4" in text  # Total
        assert "0" in text  # Blocked
    
    def test_summary_text_with_blocked(self, tui_dry_run):
        """Summary should show blocked count."""
        tui_dry_run.server_status["sgp"] = True
        tui_dry_run.server_status["tyo"] = True
        
        summary = tui_dry_run._get_summary_text()
        text = str(summary)
        assert "2" in text  # Blocked count
    
    def test_summary_text_dry_run(self, tui_dry_run):
        """Summary should show DRY RUN in dry-run mode."""
        summary = tui_dry_run._get_summary_text()
        text = str(summary)
        assert "DRY RUN" in text


class TestCreateServerTable:
    """Tests for _create_server_table method."""
    
    def test_create_table_with_servers(self, tui_dry_run):
        """Should create table with server data."""
        table = tui_dry_run._create_server_table(tui_dry_run.servers)
        assert table is not None
        assert table.row_count == 4  # 4 mock servers
    
    def test_create_table_with_blocked_status(self, tui_dry_run):
        """Should show blocked status for blocked servers."""
        tui_dry_run.server_status["sgp"] = True
        table = tui_dry_run._create_server_table(tui_dry_run.servers)
        assert table is not None


class TestCreateRegionTable:
    """Tests for _create_region_table method."""
    
    def test_create_region_table(self, tui_dry_run):
        """Should create table with region data."""
        table = tui_dry_run._create_region_table()
        assert table is not None
        assert table.row_count > 0


class TestRunTui:
    """Tests for run_tui function."""
    
    @patch('deadlock_server_picker.tui.ServerPickerTUI')
    def test_run_tui_dry_run(self, mock_tui_class):
        """Should create TUI with dry_run flag."""
        mock_tui = Mock()
        mock_tui_class.return_value = mock_tui
        
        run_tui(dry_run=True)
        
        mock_tui_class.assert_called_once_with(dry_run=True)
        mock_tui.run.assert_called_once()
    
    @patch('deadlock_server_picker.tui.ServerPickerTUI')
    def test_run_tui_default(self, mock_tui_class):
        """Should create TUI without dry_run flag by default."""
        mock_tui = Mock()
        mock_tui_class.return_value = mock_tui
        
        run_tui()
        
        mock_tui_class.assert_called_once_with(dry_run=False)
        mock_tui.run.assert_called_once()
