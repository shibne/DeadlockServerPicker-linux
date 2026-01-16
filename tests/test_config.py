"""Tests for config module."""

import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from deadlock_server_picker.config import Config, ConfigManager


class TestConfig:
    """Tests for Config dataclass."""

    def test_default_values(self):
        """Test Config has correct default values."""
        config = Config()
        assert config.default_region is None
        assert config.auto_reset_on_exit is True
        assert config.ping_timeout == 2.0
        assert config.clustered is False
        assert config.use_sudo is True
        assert config.favorites == []
        assert config.always_block == []
        assert config.never_block == []

    def test_custom_values(self):
        """Test Config with custom values."""
        config = Config(
            default_region="Europe",
            auto_reset_on_exit=False,
            ping_timeout=5.0,
            clustered=False,
            use_sudo=False,
            favorites=["ams", "fra"],
            always_block=["sgp"],
            never_block=["lax"]
        )
        assert config.default_region == "Europe"
        assert config.auto_reset_on_exit is False
        assert config.ping_timeout == 5.0
        assert config.clustered is False
        assert config.use_sudo is False
        assert config.favorites == ["ams", "fra"]
        assert config.always_block == ["sgp"]
        assert config.never_block == ["lax"]


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_init_creates_directory(self):
        """Test that ConfigManager creates config directory on save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            manager = ConfigManager(config_dir=config_dir)
            manager.save(Config())  # Directory is created on save
            assert config_dir.exists()

    def test_load_creates_default_config(self):
        """Test load creates default config if file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            manager = ConfigManager(config_dir=config_dir)
            config = manager.load()
            assert isinstance(config, Config)
            assert config.default_region is None

    def test_save_and_load(self):
        """Test saving and loading config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            manager = ConfigManager(config_dir=config_dir)
            
            # Save custom config
            config = Config(
                default_region="Asia",
                ping_timeout=3.5,
                favorites=["sgp", "hkg"]
            )
            manager.save(config)
            
            # Load and verify
            loaded = manager.load()
            assert loaded.default_region == "Asia"
            assert loaded.ping_timeout == 3.5
            assert loaded.favorites == ["sgp", "hkg"]

    def test_get_value(self):
        """Test getting individual config values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            manager = ConfigManager(config_dir=config_dir)
            manager.save(Config(ping_timeout=4.0))
            
            assert manager.get("ping_timeout") == 4.0
            assert manager.get("default_region") is None

    def test_get_invalid_key(self):
        """Test getting invalid key returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            manager = ConfigManager(config_dir=config_dir)
            assert manager.get("invalid_key") is None

    def test_set_value(self):
        """Test setting individual config values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            manager = ConfigManager(config_dir=config_dir)
            
            manager.set("ping_timeout", 5.0)
            assert manager.get("ping_timeout") == 5.0

    def test_set_invalid_key(self):
        """Test setting invalid key raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            manager = ConfigManager(config_dir=config_dir)
            
            with pytest.raises(ValueError):
                manager.set("invalid_key", "value")

    def test_reset(self):
        """Test resetting config to defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            manager = ConfigManager(config_dir=config_dir)
            
            # Set custom values
            manager.set("ping_timeout", 10.0)
            manager.set("default_region", "Europe")
            
            # Reset
            manager.reset()
            
            # Verify defaults
            config = manager.load()
            assert config.ping_timeout == 2.0
            assert config.default_region is None

    def test_config_path(self):
        """Test getting config file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            manager = ConfigManager(config_dir=config_dir)
            
            expected_path = str(config_dir / "config.json")
            assert manager.config_path == expected_path

    def test_set_bool_from_string(self):
        """Test setting boolean values from strings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            manager = ConfigManager(config_dir=config_dir)
            
            manager.set("auto_reset_on_exit", "false")
            assert manager.get("auto_reset_on_exit") is False
            
            manager.set("auto_reset_on_exit", "true")
            assert manager.get("auto_reset_on_exit") is True
            
            manager.set("use_sudo", "0")
            assert manager.get("use_sudo") is False
            
            manager.set("use_sudo", "1")
            assert manager.get("use_sudo") is True

    def test_set_float_from_string(self):
        """Test setting float values from strings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            manager = ConfigManager(config_dir=config_dir)
            
            manager.set("ping_timeout", "3.5")
            assert manager.get("ping_timeout") == 3.5

    def test_set_list_from_string(self):
        """Test setting list values from strings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            manager = ConfigManager(config_dir=config_dir)
            
            manager.set("favorites", "ams,fra,lhr")
            assert manager.get("favorites") == ["ams", "fra", "lhr"]
            
            manager.set("favorites", "")
            assert manager.get("favorites") == []

    def test_load_invalid_json(self):
        """Test loading invalid JSON returns default config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("invalid json {")
            
            manager = ConfigManager(config_dir=config_dir)
            config = manager.load()
            assert isinstance(config, Config)
            assert config.ping_timeout == 2.0  # Default value
