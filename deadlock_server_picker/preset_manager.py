"""
Preset manager - manages saved server presets.
"""

import json
import os
from pathlib import Path
from typing import Optional

from .models import Preset


class PresetError(Exception):
    """Raised when preset operations fail."""
    pass


class PresetManager:
    """Manages server presets stored in JSON format."""

    DEFAULT_FILENAME = "presets.json"

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize preset manager.
        
        Args:
            config_dir: Directory to store presets. Defaults to ~/.config/deadlock-server-picker/
        """
        if config_dir is None:
            config_dir = os.path.expanduser("~/.config/deadlock-server-picker")
        
        self.config_dir = Path(config_dir)
        self.presets_file = self.config_dir / self.DEFAULT_FILENAME
        self._presets: dict[str, Preset] = {}
        
        self._ensure_config_dir()
        self._load_presets()

    def _ensure_config_dir(self) -> None:
        """Ensure configuration directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load_presets(self) -> None:
        """Load presets from file."""
        if not self.presets_file.exists():
            self._presets = {}
            self._save_presets()
            return
            
        try:
            with open(self.presets_file, "r") as f:
                data = json.load(f)
                
            self._presets = {}
            for key, value in data.items():
                if isinstance(value, dict):
                    self._presets[key] = Preset(
                        name=value.get("presetName", key),
                        servers=value.get("servers", []),
                        clustered=value.get("clustered", False)
                    )
                    
        except json.JSONDecodeError as e:
            raise PresetError(f"Failed to parse presets file: {e}") from e
        except IOError as e:
            raise PresetError(f"Failed to read presets file: {e}") from e

    def _save_presets(self) -> None:
        """Save presets to file."""
        data = {}
        for key, preset in self._presets.items():
            data[key] = {
                "presetName": preset.name,
                "servers": preset.servers,
                "clustered": preset.clustered
            }
            
        try:
            with open(self.presets_file, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            raise PresetError(f"Failed to save presets: {e}") from e

    def _sanitize_name(self, name: str) -> str:
        """Sanitize preset name for use as key."""
        return name.replace(" ", "")

    @property
    def presets(self) -> dict[str, Preset]:
        """Get all presets."""
        return self._presets.copy()

    def get_preset(self, name: str) -> Optional[Preset]:
        """
        Get a preset by name.
        
        Args:
            name: Preset name.
            
        Returns:
            Preset if found, None otherwise.
        """
        key = self._sanitize_name(name)
        return self._presets.get(key)

    def add_preset(self, name: str, servers: list[str], clustered: bool = False) -> Preset:
        """
        Add a new preset.
        
        Args:
            name: Preset name.
            servers: List of server codes/names.
            clustered: Whether this preset uses clustered servers.
            
        Returns:
            Created preset.
            
        Raises:
            PresetError: If preset already exists or name is invalid.
        """
        # Validate name
        if not name or not name.strip():
            raise PresetError("Preset name cannot be empty")
            
        # Check for special characters
        import re
        if re.search(r'[^a-zA-Z0-9 ]', name):
            raise PresetError("Preset name can only contain letters, numbers, and spaces")
            
        key = self._sanitize_name(name)
        
        if key in self._presets:
            raise PresetError(f"Preset '{name}' already exists")
            
        if not servers:
            raise PresetError("Preset must contain at least one server")
            
        preset = Preset(name=name, servers=servers, clustered=clustered)
        self._presets[key] = preset
        self._save_presets()
        
        return preset

    def update_preset(self, name: str, servers: Optional[list[str]] = None, 
                     new_name: Optional[str] = None, clustered: Optional[bool] = None) -> Preset:
        """
        Update an existing preset.
        
        Args:
            name: Current preset name.
            servers: New list of servers (optional).
            new_name: New name for preset (optional).
            clustered: New clustered value (optional).
            
        Returns:
            Updated preset.
            
        Raises:
            PresetError: If preset doesn't exist or update fails.
        """
        key = self._sanitize_name(name)
        
        if key not in self._presets:
            raise PresetError(f"Preset '{name}' does not exist")
            
        preset = self._presets[key]
        
        # Update fields
        if servers is not None:
            if not servers:
                raise PresetError("Preset must contain at least one server")
            preset.servers = servers
            
        if clustered is not None:
            preset.clustered = clustered
            
        if new_name is not None and new_name != name:
            # Validate new name
            if not new_name or not new_name.strip():
                raise PresetError("Preset name cannot be empty")
                
            import re
            if re.search(r'[^a-zA-Z0-9 ]', new_name):
                raise PresetError("Preset name can only contain letters, numbers, and spaces")
                
            new_key = self._sanitize_name(new_name)
            
            if new_key in self._presets:
                raise PresetError(f"Preset '{new_name}' already exists")
                
            # Remove old and add new
            del self._presets[key]
            preset.name = new_name
            self._presets[new_key] = preset
            
        self._save_presets()
        return preset

    def delete_preset(self, name: str) -> bool:
        """
        Delete a preset.
        
        Args:
            name: Preset name to delete.
            
        Returns:
            True if deleted, False if not found.
        """
        key = self._sanitize_name(name)
        
        if key not in self._presets:
            return False
            
        del self._presets[key]
        self._save_presets()
        return True

    def list_presets(self, clustered: Optional[bool] = None) -> list[Preset]:
        """
        List all presets.
        
        Args:
            clustered: Filter by clustered value (optional).
            
        Returns:
            List of presets.
        """
        presets = list(self._presets.values())
        
        if clustered is not None:
            presets = [p for p in presets if p.clustered == clustered]
            
        return sorted(presets, key=lambda p: p.name)

    def export_presets(self, filepath: str) -> None:
        """
        Export presets to a file.
        
        Args:
            filepath: Path to export file.
        """
        data = {}
        for key, preset in self._presets.items():
            data[key] = {
                "presetName": preset.name,
                "servers": preset.servers,
                "clustered": preset.clustered
            }
            
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def import_presets(self, filepath: str, overwrite: bool = False) -> int:
        """
        Import presets from a file.
        
        Args:
            filepath: Path to import file.
            overwrite: Whether to overwrite existing presets.
            
        Returns:
            Number of presets imported.
        """
        with open(filepath, "r") as f:
            data = json.load(f)
            
        imported = 0
        for key, value in data.items():
            if isinstance(value, dict):
                if key in self._presets and not overwrite:
                    continue
                    
                self._presets[key] = Preset(
                    name=value.get("presetName", key),
                    servers=value.get("servers", []),
                    clustered=value.get("clustered", False)
                )
                imported += 1
                
        self._save_presets()
        return imported

    def clear_all(self) -> int:
        """
        Delete all presets.
        
        Returns:
            Number of presets deleted.
        """
        count = len(self._presets)
        self._presets.clear()
        self._save_presets()
        return count
