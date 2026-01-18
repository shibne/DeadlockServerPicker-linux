"""
Configuration management for Deadlock Server Picker.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Config:
    """Configuration settings."""
    
    # Whether user has accepted the disclaimer
    disclaimer_accepted: bool = False
    
    # Default region to use for allow-region command
    default_region: Optional[str] = None
    
    # Whether to auto-reset firewall rules on exit
    auto_reset_on_exit: bool = True
    
    # Default ping timeout in seconds
    ping_timeout: float = 2.0
    
    # Whether to use clustered server view by default
    clustered: bool = False
    
    # Whether to use sudo (set False if running as root)
    use_sudo: bool = True
    
    # Firewall backend: 'auto', 'iptables', or 'nftables'
    firewall_backend: str = "auto"
    
    # Favorite servers (codes)
    favorites: list[str] = field(default_factory=list)
    
    # Servers to always block
    always_block: list[str] = field(default_factory=list)
    
    # Servers to never block
    never_block: list[str] = field(default_factory=list)


class ConfigManager:
    """Manages configuration file."""
    
    DEFAULT_CONFIG_DIR = "~/.config/deadlock-server-picker"
    CONFIG_FILENAME = "config.json"
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize config manager.
        
        Args:
            config_dir: Custom config directory path.
        """
        if config_dir:
            self.config_dir = os.path.expanduser(config_dir)
        else:
            self.config_dir = os.path.expanduser(self.DEFAULT_CONFIG_DIR)
        
        self.config_path = os.path.join(self.config_dir, self.CONFIG_FILENAME)
        self._config: Optional[Config] = None
    
    def _ensure_config_dir(self) -> None:
        """Ensure config directory exists."""
        os.makedirs(self.config_dir, exist_ok=True)
    
    def load(self) -> Config:
        """
        Load configuration from file.
        
        Returns:
            Config object with loaded or default settings.
        """
        if self._config is not None:
            return self._config
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                self._config = Config(**data)
            except (json.JSONDecodeError, TypeError, KeyError):
                # Invalid config, use defaults
                self._config = Config()
        else:
            self._config = Config()
        
        return self._config
    
    def save(self, config: Optional[Config] = None) -> None:
        """
        Save configuration to file.
        
        Args:
            config: Config to save. Uses current config if None.
        """
        if config is not None:
            self._config = config
        
        if self._config is None:
            self._config = Config()
        
        self._ensure_config_dir()
        
        with open(self.config_path, 'w') as f:
            json.dump(asdict(self._config), f, indent=2)
    
    def get(self, key: str, default=None):
        """
        Get a config value.
        
        Args:
            key: Config key name.
            default: Default value if key not found.
            
        Returns:
            Config value or default.
        """
        config = self.load()
        if not hasattr(config, key):
            return default
        return getattr(config, key, default)
    
    def set(self, key: str, value) -> None:
        """
        Set a config value and save.
        
        Args:
            key: Config key name.
            value: Value to set.
            
        Raises:
            ValueError: If key is not a valid config option.
        """
        config = self.load()
        if not hasattr(config, key):
            raise ValueError(f"Invalid config key: {key}")
        
        # Type conversion based on field type
        current_value = getattr(config, key)
        
        if isinstance(current_value, bool):
            # Convert string to bool
            if isinstance(value, str):
                value = value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(current_value, float):
            # Convert string to float
            if isinstance(value, str):
                value = float(value)
        elif isinstance(current_value, list):
            # Convert comma-separated string to list
            if isinstance(value, str):
                if value.strip():
                    value = [v.strip() for v in value.split(',')]
                else:
                    value = []
        
        setattr(config, key, value)
        self.save(config)
    
    def reset(self) -> None:
        """Reset configuration to defaults."""
        self._config = Config()
        self.save()
    
    @property
    def config(self) -> Config:
        """Get current config."""
        return self.load()
