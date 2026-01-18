"""
Tests for CLI interface.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys

from deadlock_server_picker.cli import (
    DeadlockServerPickerCLI, create_parser, main, colorize, Colors, supports_color
)
from deadlock_server_picker.models import Server, ServerRelay, ServerStatus


class TestColorFunctions:
    """Tests for color helper functions."""

    def test_colorize_with_color_support(self):
        """Test colorize when colors are supported."""
        with patch("deadlock_server_picker.cli.supports_color", return_value=True):
            result = colorize("test", Colors.RED)
            assert Colors.RED in result
            assert Colors.RESET in result
            assert "test" in result

    def test_colorize_without_color_support(self):
        """Test colorize when colors are not supported."""
        with patch("deadlock_server_picker.cli.supports_color", return_value=False):
            result = colorize("test", Colors.RED)
            assert result == "test"

    def test_supports_color_no_color_env(self):
        """Test NO_COLOR environment variable disables colors."""
        with patch.dict("os.environ", {"NO_COLOR": "1"}):
            assert supports_color() is False

    def test_supports_color_no_tty(self):
        """Test non-TTY disables colors."""
        mock_stdout = MagicMock()
        mock_stdout.isatty.return_value = False
        
        with patch("sys.stdout", mock_stdout):
            assert supports_color() is False


class TestArgumentParser:
    """Tests for argument parser."""

    def test_create_parser(self):
        """Test parser creation."""
        parser = create_parser()
        assert parser is not None

    def test_parser_list_command(self):
        """Test parsing list command."""
        parser = create_parser()
        args = parser.parse_args(["list"])
        
        assert args.command == "list"
        assert args.ping is False
        assert args.blocked is False

    def test_parser_list_with_ping(self):
        """Test parsing list with ping option."""
        parser = create_parser()
        args = parser.parse_args(["list", "--ping"])
        
        assert args.ping is True

    def test_parser_block_command(self):
        """Test parsing block command."""
        parser = create_parser()
        args = parser.parse_args(["block", "sgp", "hkg"])
        
        assert args.command == "block"
        assert args.servers == ["sgp", "hkg"]

    def test_parser_unblock_command(self):
        """Test parsing unblock command."""
        parser = create_parser()
        args = parser.parse_args(["unblock", "sgp"])
        
        assert args.command == "unblock"
        assert args.servers == ["sgp"]
        assert args.all is False

    def test_parser_unblock_all(self):
        """Test parsing unblock --all."""
        parser = create_parser()
        args = parser.parse_args(["unblock", "--all"])
        
        assert args.all is True

    def test_parser_block_except(self):
        """Test parsing block-except command."""
        parser = create_parser()
        args = parser.parse_args(["block-except", "sgp", "hkg"])
        
        assert args.command == "block-except"
        assert args.servers == ["sgp", "hkg"]

    def test_parser_preset_create(self):
        """Test parsing preset create command."""
        parser = create_parser()
        args = parser.parse_args(["preset", "create", "mypreset", "sgp", "hkg"])
        
        assert args.command == "preset"
        assert args.preset_command == "create"
        assert args.name == "mypreset"
        assert args.servers == ["sgp", "hkg"]

    def test_parser_preset_apply(self):
        """Test parsing preset apply command."""
        parser = create_parser()
        args = parser.parse_args(["preset", "apply", "mypreset", "--block-others"])
        
        assert args.preset_command == "apply"
        assert args.name == "mypreset"
        assert args.block_others is True

    def test_parser_global_options(self):
        """Test parsing global options."""
        parser = create_parser()
        args = parser.parse_args(["--no-sudo", "--dry-run", "--clustered", "list"])
        
        assert args.no_sudo is True
        assert args.dry_run is True
        assert args.clustered is True


class TestDeadlockServerPickerCLI:
    """Tests for CLI class."""

    @pytest.fixture
    def cli(self, tmp_path):
        """Create CLI instance with mocks."""
        with patch("shutil.which", return_value="/sbin/iptables"):
            cli = DeadlockServerPickerCLI(
                use_sudo=False,
                dry_run=True,
                config_dir=str(tmp_path)
            )
            return cli

    @pytest.fixture
    def mock_servers(self):
        """Create mock server data."""
        return {
            "sgp": Server(
                name="Singapore",
                code="sgp",
                relays=[ServerRelay(ipv4="1.1.1.1")]
            ),
            "hkg": Server(
                name="Hong Kong",
                code="hkg",
                relays=[ServerRelay(ipv4="2.2.2.2")]
            )
        }

    def test_init(self, cli):
        """Test CLI initialization."""
        assert cli.dry_run is True
        assert cli.clustered is False

    def test_ensure_servers_loaded(self, cli):
        """Test server loading."""
        with patch.object(cli.fetcher, "fetch", return_value="12345"):
            result = cli._ensure_servers_loaded()
            assert result is True
            assert cli._servers_loaded is True

    def test_ensure_servers_loaded_failure(self, cli):
        """Test server loading failure."""
        from deadlock_server_picker.server_fetcher import ServerFetchError
        
        with patch.object(cli.fetcher, "fetch", side_effect=ServerFetchError("Error")):
            result = cli._ensure_servers_loaded()
            assert result is False

    def test_cmd_list(self, cli, mock_servers, capsys):
        """Test list command."""
        with patch.object(cli.fetcher, "fetch", return_value="12345"):
            with patch.object(cli.fetcher, "get_servers", return_value=mock_servers):
                result = cli.cmd_list()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "Singapore" in captured.out or "Server" in captured.out

    def test_cmd_list_with_ping(self, cli, mock_servers, capsys):
        """Test list command with ping."""
        with patch.object(cli.fetcher, "fetch", return_value="12345"):
            with patch.object(cli.fetcher, "get_servers", return_value=mock_servers):
                with patch.object(cli.ping_service, "ping_servers", return_value={"sgp": 25, "hkg": 50}):
                    result = cli.cmd_list(ping=True)
        
        assert result == 0

    def test_cmd_block(self, cli, mock_servers):
        """Test block command."""
        with patch.object(cli.fetcher, "fetch", return_value="12345"):
            with patch.object(cli.fetcher, "get_server_by_name", return_value=mock_servers["sgp"]):
                result = cli.cmd_block(["sgp"])
        
        assert result == 0

    def test_cmd_block_not_found(self, cli, capsys):
        """Test block command with non-existent server."""
        with patch.object(cli.fetcher, "fetch", return_value="12345"):
            with patch.object(cli.fetcher, "get_server_by_name", return_value=None):
                result = cli.cmd_block(["nonexistent"])
        
        assert result == 1

    def test_cmd_unblock(self, cli, mock_servers):
        """Test unblock command."""
        with patch.object(cli.fetcher, "fetch", return_value="12345"):
            with patch.object(cli.fetcher, "get_server_by_name", return_value=mock_servers["sgp"]):
                result = cli.cmd_unblock(["sgp"])
        
        assert result == 0

    def test_cmd_unblock_all(self, cli):
        """Test unblock all command."""
        result = cli.cmd_unblock([], all_servers=True)
        assert result == 0

    def test_cmd_status(self, cli, capsys):
        """Test status command."""
        result = cli.cmd_status()
        
        captured = capsys.readouterr()
        assert "Status" in captured.out
        assert result == 0 or result == 1  # Depends on permissions

    def test_cmd_reset(self, cli, capsys):
        """Test reset command."""
        result = cli.cmd_reset()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "removed" in captured.out or "DRY RUN" in captured.out

    def test_cmd_preset_list_empty(self, cli, capsys):
        """Test preset list when empty."""
        result = cli.cmd_preset_list()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "No presets" in captured.out

    def test_cmd_preset_create(self, cli, mock_servers):
        """Test preset create command."""
        with patch.object(cli.fetcher, "fetch", return_value="12345"):
            with patch.object(cli.fetcher, "get_server_by_name", return_value=mock_servers["sgp"]):
                result = cli.cmd_preset_create("mypreset", ["sgp"])
        
        assert result == 0
        assert cli.preset_manager.get_preset("mypreset") is not None

    def test_cmd_preset_delete(self, cli):
        """Test preset delete command."""
        cli.preset_manager.add_preset("todelete", ["s1"])
        
        result = cli.cmd_preset_delete("todelete")
        
        assert result == 0
        assert cli.preset_manager.get_preset("todelete") is None

    def test_cmd_preset_delete_not_found(self, cli, capsys):
        """Test deleting non-existent preset."""
        result = cli.cmd_preset_delete("nonexistent")
        
        assert result == 1


class TestMainFunction:
    """Tests for main entry point."""

    def test_main_no_command(self, capsys):
        """Test main with no command shows help."""
        with patch("sys.argv", ["deadlock-server-picker"]):
            result = main()
        
        assert result == 0

    def test_main_list_command(self):
        """Test main with list command."""
        with patch("sys.argv", ["deadlock-server-picker", "--dry-run", "list"]):
            with patch("shutil.which", return_value="/sbin/iptables"):
                with patch("deadlock_server_picker.cli.check_disclaimer", return_value=True):
                    with patch.object(DeadlockServerPickerCLI, "cmd_list", return_value=0) as mock_list:
                        result = main()
        
        assert result == 0

    def test_main_keyboard_interrupt(self):
        """Test main handles keyboard interrupt."""
        with patch("sys.argv", ["deadlock-server-picker", "list"]):
            with patch("shutil.which", return_value="/sbin/iptables"):
                with patch("deadlock_server_picker.cli.check_disclaimer", return_value=True):
                    with patch.object(DeadlockServerPickerCLI, "_ensure_servers_loaded", side_effect=KeyboardInterrupt):
                        result = main()
        
        assert result == 130

    def test_main_unexpected_error(self):
        """Test main handles unexpected errors."""
        with patch("sys.argv", ["deadlock-server-picker", "list"]):
            with patch("shutil.which", return_value="/sbin/iptables"):
                with patch("deadlock_server_picker.cli.check_disclaimer", return_value=True):
                    with patch.object(DeadlockServerPickerCLI, "_ensure_servers_loaded", side_effect=RuntimeError("Test error")):
                        result = main()
        
        assert result == 1
