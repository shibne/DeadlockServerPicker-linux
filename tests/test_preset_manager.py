"""
Tests for preset manager.
"""

import json
import os
import tempfile
import pytest

from deadlock_server_picker.preset_manager import PresetManager, PresetError
from deadlock_server_picker.models import Preset


class TestPresetManager:
    """Tests for PresetManager."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, temp_dir):
        """Create a preset manager with temp directory."""
        return PresetManager(config_dir=temp_dir)

    def test_init_creates_config_dir(self, temp_dir):
        """Test that initialization creates config directory."""
        config_path = os.path.join(temp_dir, "subdir")
        manager = PresetManager(config_dir=config_path)
        
        assert os.path.exists(config_path)
        assert os.path.exists(os.path.join(config_path, "presets.json"))

    def test_init_creates_empty_presets(self, manager, temp_dir):
        """Test that initialization creates empty presets file."""
        presets_file = os.path.join(temp_dir, "presets.json")
        
        with open(presets_file) as f:
            data = json.load(f)
        
        assert data == {}

    def test_presets_property_empty(self, manager):
        """Test presets property when empty."""
        assert manager.presets == {}

    def test_add_preset(self, manager):
        """Test adding a preset."""
        preset = manager.add_preset("My Preset", ["sgp", "hkg"])
        
        assert preset.name == "My Preset"
        assert preset.servers == ["sgp", "hkg"]
        assert preset.clustered is False

    def test_add_preset_clustered(self, manager):
        """Test adding a clustered preset."""
        preset = manager.add_preset("Asia", ["China", "Japan"], clustered=True)
        
        assert preset.clustered is True

    def test_add_preset_persists(self, manager, temp_dir):
        """Test that added presets are saved to file."""
        manager.add_preset("Test", ["s1", "s2"])
        
        # Read file directly
        with open(os.path.join(temp_dir, "presets.json")) as f:
            data = json.load(f)
        
        assert "Test" in data
        assert data["Test"]["servers"] == ["s1", "s2"]

    def test_add_preset_empty_name(self, manager):
        """Test adding preset with empty name."""
        with pytest.raises(PresetError) as exc_info:
            manager.add_preset("", ["s1"])
        
        assert "cannot be empty" in str(exc_info.value)

    def test_add_preset_whitespace_name(self, manager):
        """Test adding preset with whitespace-only name."""
        with pytest.raises(PresetError) as exc_info:
            manager.add_preset("   ", ["s1"])
        
        assert "cannot be empty" in str(exc_info.value)

    def test_add_preset_special_characters(self, manager):
        """Test adding preset with special characters."""
        with pytest.raises(PresetError) as exc_info:
            manager.add_preset("Test@#$", ["s1"])
        
        assert "letters, numbers, and spaces" in str(exc_info.value)

    def test_add_preset_duplicate(self, manager):
        """Test adding duplicate preset."""
        manager.add_preset("Test", ["s1"])
        
        with pytest.raises(PresetError) as exc_info:
            manager.add_preset("Test", ["s2"])
        
        assert "already exists" in str(exc_info.value)

    def test_add_preset_empty_servers(self, manager):
        """Test adding preset with no servers."""
        with pytest.raises(PresetError) as exc_info:
            manager.add_preset("Test", [])
        
        assert "at least one server" in str(exc_info.value)

    def test_get_preset(self, manager):
        """Test getting a preset by name."""
        manager.add_preset("Test", ["s1", "s2"])
        
        preset = manager.get_preset("Test")
        
        assert preset is not None
        assert preset.name == "Test"
        assert preset.servers == ["s1", "s2"]

    def test_get_preset_not_found(self, manager):
        """Test getting non-existent preset."""
        preset = manager.get_preset("NonExistent")
        assert preset is None

    def test_get_preset_spaces_in_name(self, manager):
        """Test getting preset with spaces in name."""
        manager.add_preset("My Test Preset", ["s1"])
        
        preset = manager.get_preset("My Test Preset")
        assert preset is not None
        assert preset.name == "My Test Preset"

    def test_update_preset_servers(self, manager):
        """Test updating preset servers."""
        manager.add_preset("Test", ["s1"])
        
        preset = manager.update_preset("Test", servers=["s2", "s3"])
        
        assert preset.servers == ["s2", "s3"]

    def test_update_preset_name(self, manager):
        """Test renaming a preset."""
        manager.add_preset("Old Name", ["s1"])
        
        preset = manager.update_preset("Old Name", new_name="New Name")
        
        assert preset.name == "New Name"
        assert manager.get_preset("Old Name") is None
        assert manager.get_preset("New Name") is not None

    def test_update_preset_clustered(self, manager):
        """Test updating clustered flag."""
        manager.add_preset("Test", ["s1"], clustered=False)
        
        preset = manager.update_preset("Test", clustered=True)
        
        assert preset.clustered is True

    def test_update_preset_not_found(self, manager):
        """Test updating non-existent preset."""
        with pytest.raises(PresetError) as exc_info:
            manager.update_preset("NonExistent", servers=["s1"])
        
        assert "does not exist" in str(exc_info.value)

    def test_update_preset_empty_servers(self, manager):
        """Test updating with empty servers."""
        manager.add_preset("Test", ["s1"])
        
        with pytest.raises(PresetError) as exc_info:
            manager.update_preset("Test", servers=[])
        
        assert "at least one server" in str(exc_info.value)

    def test_update_preset_duplicate_name(self, manager):
        """Test renaming to existing name."""
        manager.add_preset("Preset1", ["s1"])
        manager.add_preset("Preset2", ["s2"])
        
        with pytest.raises(PresetError) as exc_info:
            manager.update_preset("Preset1", new_name="Preset2")
        
        assert "already exists" in str(exc_info.value)

    def test_delete_preset(self, manager):
        """Test deleting a preset."""
        manager.add_preset("Test", ["s1"])
        
        result = manager.delete_preset("Test")
        
        assert result is True
        assert manager.get_preset("Test") is None

    def test_delete_preset_not_found(self, manager):
        """Test deleting non-existent preset."""
        result = manager.delete_preset("NonExistent")
        assert result is False

    def test_list_presets_empty(self, manager):
        """Test listing presets when empty."""
        presets = manager.list_presets()
        assert presets == []

    def test_list_presets(self, manager):
        """Test listing all presets."""
        manager.add_preset("Alpha", ["s1"])
        manager.add_preset("Beta", ["s2"])
        manager.add_preset("Gamma", ["s3"])
        
        presets = manager.list_presets()
        
        assert len(presets) == 3
        # Should be sorted by name
        assert presets[0].name == "Alpha"
        assert presets[1].name == "Beta"
        assert presets[2].name == "Gamma"

    def test_list_presets_filter_clustered(self, manager):
        """Test filtering presets by clustered."""
        manager.add_preset("Clustered1", ["s1"], clustered=True)
        manager.add_preset("Clustered2", ["s2"], clustered=True)
        manager.add_preset("Normal", ["s3"], clustered=False)
        
        clustered = manager.list_presets(clustered=True)
        unclustered = manager.list_presets(clustered=False)
        
        assert len(clustered) == 2
        assert len(unclustered) == 1

    def test_export_presets(self, manager, temp_dir):
        """Test exporting presets to file."""
        manager.add_preset("Test1", ["s1"])
        manager.add_preset("Test2", ["s2", "s3"])
        
        export_path = os.path.join(temp_dir, "export.json")
        manager.export_presets(export_path)
        
        with open(export_path) as f:
            data = json.load(f)
        
        assert "Test1" in data
        assert "Test2" in data

    def test_import_presets(self, manager, temp_dir):
        """Test importing presets from file."""
        # Create export file
        export_data = {
            "ImportedPreset": {
                "presetName": "Imported Preset",
                "servers": ["sgp", "hkg"],
                "clustered": False
            }
        }
        
        import_path = os.path.join(temp_dir, "import.json")
        with open(import_path, "w") as f:
            json.dump(export_data, f)
        
        count = manager.import_presets(import_path)
        
        assert count == 1
        preset = manager.get_preset("Imported Preset")
        assert preset is not None
        assert preset.servers == ["sgp", "hkg"]

    def test_import_presets_no_overwrite(self, manager, temp_dir):
        """Test importing presets without overwriting."""
        manager.add_preset("Existing", ["original"])
        
        export_data = {
            "Existing": {
                "presetName": "Existing",
                "servers": ["new"],
                "clustered": False
            }
        }
        
        import_path = os.path.join(temp_dir, "import.json")
        with open(import_path, "w") as f:
            json.dump(export_data, f)
        
        count = manager.import_presets(import_path, overwrite=False)
        
        assert count == 0  # Should not import
        preset = manager.get_preset("Existing")
        assert preset.servers == ["original"]  # Unchanged

    def test_import_presets_with_overwrite(self, manager, temp_dir):
        """Test importing presets with overwrite."""
        manager.add_preset("Existing", ["original"])
        
        export_data = {
            "Existing": {
                "presetName": "Existing",
                "servers": ["new"],
                "clustered": False
            }
        }
        
        import_path = os.path.join(temp_dir, "import.json")
        with open(import_path, "w") as f:
            json.dump(export_data, f)
        
        count = manager.import_presets(import_path, overwrite=True)
        
        assert count == 1
        preset = manager.get_preset("Existing")
        assert preset.servers == ["new"]

    def test_clear_all(self, manager):
        """Test clearing all presets."""
        manager.add_preset("Test1", ["s1"])
        manager.add_preset("Test2", ["s2"])
        manager.add_preset("Test3", ["s3"])
        
        count = manager.clear_all()
        
        assert count == 3
        assert len(manager.list_presets()) == 0


class TestPresetManagerPersistence:
    """Tests for preset manager persistence."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_presets_persist_across_instances(self, temp_dir):
        """Test that presets persist when creating new manager instance."""
        # Create first manager and add presets
        manager1 = PresetManager(config_dir=temp_dir)
        manager1.add_preset("Persistent", ["s1", "s2"])
        
        # Create second manager with same directory
        manager2 = PresetManager(config_dir=temp_dir)
        
        preset = manager2.get_preset("Persistent")
        assert preset is not None
        assert preset.servers == ["s1", "s2"]

    def test_handles_corrupted_file(self, temp_dir):
        """Test handling of corrupted presets file."""
        # Write invalid JSON
        presets_file = os.path.join(temp_dir, "presets.json")
        os.makedirs(temp_dir, exist_ok=True)
        with open(presets_file, "w") as f:
            f.write("invalid json {{{")
        
        with pytest.raises(PresetError) as exc_info:
            PresetManager(config_dir=temp_dir)
        
        assert "Failed to parse" in str(exc_info.value)

    def test_handles_missing_fields(self, temp_dir):
        """Test handling of presets with missing fields."""
        # Write presets with minimal data
        presets_file = os.path.join(temp_dir, "presets.json")
        os.makedirs(temp_dir, exist_ok=True)
        with open(presets_file, "w") as f:
            json.dump({
                "Test": {
                    # Missing presetName, use key as name
                    "servers": ["s1"]
                    # Missing clustered, default to False
                }
            }, f)
        
        manager = PresetManager(config_dir=temp_dir)
        preset = manager.get_preset("Test")
        
        assert preset is not None
        assert preset.name == "Test"
        assert preset.clustered is False
