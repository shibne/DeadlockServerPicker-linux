"""
Tests for the regions module.
"""

import pytest
from deadlock_server_picker.regions import (
    REGION_PRESETS,
    REGION_ALIASES,
    get_region_servers,
    get_all_regions,
    get_region_description,
)


class TestRegionPresets:
    """Tests for region preset data."""
    
    def test_region_presets_not_empty(self):
        """Region presets should contain data."""
        assert len(REGION_PRESETS) > 0
        
    def test_all_regions_have_required_fields(self):
        """All regions should have description and servers."""
        for name, data in REGION_PRESETS.items():
            assert "description" in data, f"{name} missing description"
            assert "servers" in data, f"{name} missing servers"
            assert isinstance(data["servers"], list), f"{name} servers should be list"
            assert len(data["servers"]) > 0, f"{name} has no servers"
    
    def test_expected_regions_exist(self):
        """Expected regions should exist."""
        expected = ["North America", "Europe", "Asia", "China", "Oceania"]
        for region in expected:
            assert region in REGION_PRESETS, f"Missing region: {region}"
    
    def test_na_servers(self):
        """North America should contain expected servers."""
        na_servers = REGION_PRESETS["North America"]["servers"]
        # US servers
        assert "iad" in na_servers  # Virginia
        assert "ord" in na_servers  # Chicago
        assert "lax" in na_servers  # Los Angeles
    
    def test_europe_servers(self):
        """Europe should contain expected servers."""
        eu_servers = REGION_PRESETS["Europe"]["servers"]
        assert "lhr" in eu_servers  # London
        assert "fra" in eu_servers  # Frankfurt
        assert "sto" in eu_servers  # Stockholm


class TestRegionAliases:
    """Tests for region aliases."""
    
    def test_aliases_not_empty(self):
        """Aliases should exist."""
        assert len(REGION_ALIASES) > 0
    
    def test_all_aliases_point_to_valid_regions(self):
        """All aliases should point to valid regions."""
        for alias, region in REGION_ALIASES.items():
            assert region in REGION_PRESETS, f"Alias {alias} points to invalid region {region}"
    
    def test_common_aliases(self):
        """Common aliases should work."""
        assert REGION_ALIASES["na"] == "North America"
        assert REGION_ALIASES["eu"] == "Europe"
        assert REGION_ALIASES["asia"] == "Asia"
        assert REGION_ALIASES["cn"] == "China"


class TestGetRegionServers:
    """Tests for get_region_servers function."""
    
    def test_get_by_full_name(self):
        """Should get servers by full region name."""
        servers = get_region_servers("North America")
        assert len(servers) > 0
        assert "iad" in servers
    
    def test_get_by_alias(self):
        """Should get servers by alias."""
        servers = get_region_servers("na")
        assert len(servers) > 0
        assert "iad" in servers
    
    def test_case_insensitive(self):
        """Should be case-insensitive."""
        servers1 = get_region_servers("NA")
        servers2 = get_region_servers("na")
        servers3 = get_region_servers("Na")
        assert servers1 == servers2 == servers3
    
    def test_unknown_region_returns_empty(self):
        """Unknown region should return empty list."""
        servers = get_region_servers("Unknown Region")
        assert servers == []
    
    def test_all_regions_return_servers(self):
        """All defined regions should return servers."""
        for region in REGION_PRESETS:
            servers = get_region_servers(region)
            assert len(servers) > 0, f"Region {region} returned no servers"


class TestGetAllRegions:
    """Tests for get_all_regions function."""
    
    def test_returns_copy(self):
        """Should return a copy of the data."""
        regions = get_all_regions()
        regions["Test"] = {"description": "Test", "servers": []}
        assert "Test" not in REGION_PRESETS
    
    def test_contains_all_regions(self):
        """Should contain all regions."""
        regions = get_all_regions()
        assert len(regions) == len(REGION_PRESETS)


class TestGetRegionDescription:
    """Tests for get_region_description function."""
    
    def test_get_description_by_name(self):
        """Should get description by region name."""
        desc = get_region_description("North America")
        assert "US" in desc or "Canada" in desc or "North" in desc.lower()
    
    def test_get_description_by_alias(self):
        """Should get description by alias."""
        desc = get_region_description("na")
        assert len(desc) > 0
    
    def test_unknown_region_returns_empty(self):
        """Unknown region should return empty string."""
        desc = get_region_description("Unknown")
        assert desc == ""


class TestRegionServerCodes:
    """Tests to ensure server codes are valid format."""
    
    def test_server_codes_are_lowercase(self):
        """Server codes should be lowercase."""
        for region, data in REGION_PRESETS.items():
            for code in data["servers"]:
                # Codes can have numbers but letters should be lowercase
                alpha_only = ''.join(c for c in code if c.isalpha())
                assert alpha_only.islower(), f"Server code {code} in {region} should be lowercase"
    
    def test_server_codes_are_short(self):
        """Server codes should be short identifiers."""
        for region, data in REGION_PRESETS.items():
            for code in data["servers"]:
                assert len(code) <= 6, f"Server code {code} in {region} is too long"
    
    def test_no_duplicate_codes_within_region(self):
        """No duplicate server codes within a region."""
        for region, data in REGION_PRESETS.items():
            codes = data["servers"]
            assert len(codes) == len(set(codes)), f"Duplicate codes in {region}"
