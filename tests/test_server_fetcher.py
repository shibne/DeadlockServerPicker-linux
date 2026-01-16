"""
Tests for server data fetcher.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from deadlock_server_picker.server_fetcher import (
    ServerDataFetcher, ServerFetchError, STEAM_SDR_API_URL
)
from deadlock_server_picker.models import Server


# Sample API response for testing
SAMPLE_API_RESPONSE = {
    "revision": 12345,
    "pops": {
        "sgp": {
            "desc": "Singapore",
            "relays": [
                {"ipv4": "103.28.54.1"},
                {"ipv4": "103.28.54.2"}
            ]
        },
        "hkg": {
            "desc": "Hong Kong",
            "relays": [
                {"ipv4": "103.10.124.1", "port_range": "27015-27020"}
            ]
        },
        "tyo": {
            "desc": "Tokyo",
            "relays": [
                {"ipv4": "45.121.184.1"}
            ]
        },
        "pwg": {
            "desc": "Guangzhou (Perfect World)",
            "relays": [
                {"ipv4": "116.251.127.1"}
            ]
        },
        "bom": {
            "desc": "Mumbai",
            "relays": [
                {"ipv4": "180.149.41.1"}
            ]
        },
        "maa": {
            "desc": "Chennai",
            "relays": [
                {"ipv4": "103.152.35.1"}
            ]
        },
        "sto": {
            "desc": "Stockholm",
            "relays": [
                {"ipv4": "146.66.152.1"}
            ]
        },
        "iad": {
            "desc": "US East",
            "relays": [
                {"ipv4": "208.78.164.1"}
            ]
        },
        "no_relays": {
            "desc": "No Relays Server"
            # Missing relays field
        }
    }
}


class TestServerDataFetcher:
    """Tests for ServerDataFetcher."""

    @pytest.fixture
    def fetcher(self):
        """Create a fetcher instance."""
        return ServerDataFetcher()

    @pytest.fixture
    def mock_response(self):
        """Create mock API response."""
        return json.dumps(SAMPLE_API_RESPONSE).encode("utf-8")

    def test_init(self, fetcher):
        """Test fetcher initialization."""
        assert fetcher.api_url == STEAM_SDR_API_URL
        assert fetcher.revision is None
        assert fetcher.servers == {}
        assert fetcher.clustered_servers == {}

    def test_fetch_success(self, fetcher, mock_response):
        """Test successful fetch."""
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=lambda: mock_response))
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_urlopen):
            revision = fetcher.fetch()
        
        assert revision == "12345"
        assert fetcher.revision == "12345"
        assert len(fetcher.servers) > 0

    def test_fetch_parses_servers(self, fetcher, mock_response):
        """Test that fetch parses server data correctly."""
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=lambda: mock_response))
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_urlopen):
            fetcher.fetch()
        
        # Check unclustered servers
        assert "sgp" in fetcher.servers
        assert "hkg" in fetcher.servers
        assert "iad" in fetcher.servers
        
        # Check server has correct data
        sgp = fetcher.servers["sgp"]
        assert sgp.name == "Singapore"
        assert sgp.code == "sgp"
        assert len(sgp.relays) == 2
        assert "103.28.54.1" in sgp.ip_addresses

    def test_fetch_creates_clusters(self, fetcher, mock_response):
        """Test that fetch creates clustered servers."""
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=lambda: mock_response))
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_urlopen):
            fetcher.fetch()
        
        clustered = fetcher.clustered_servers
        
        # China cluster should exist with Hong Kong
        assert "China" in clustered
        china = clustered["China"]
        assert len(china.relays) > 0
        
        # Japan cluster should exist
        assert "Japan" in clustered
        
        # India cluster should exist with Mumbai and Chennai
        assert "India" in clustered

    def test_fetch_skips_servers_without_relays(self, fetcher, mock_response):
        """Test that servers without relays are skipped."""
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=lambda: mock_response))
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_urlopen):
            fetcher.fetch()
        
        assert "no_relays" not in fetcher.servers

    def test_fetch_network_error(self, fetcher):
        """Test fetch handles network errors."""
        import urllib.error
        
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection failed")):
            with pytest.raises(ServerFetchError) as exc_info:
                fetcher.fetch()
        
        assert "Failed to fetch" in str(exc_info.value)

    def test_fetch_invalid_json(self, fetcher):
        """Test fetch handles invalid JSON."""
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=lambda: b"invalid json"))
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_urlopen):
            with pytest.raises(ServerFetchError) as exc_info:
                fetcher.fetch()
        
        assert "Failed to parse" in str(exc_info.value)

    def test_fetch_missing_revision(self, fetcher):
        """Test fetch handles missing revision."""
        data = {"pops": {}}  # Missing revision
        mock_response = json.dumps(data).encode("utf-8")
        
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=lambda: mock_response))
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_urlopen):
            with pytest.raises(ServerFetchError) as exc_info:
                fetcher.fetch()
        
        assert "missing revision" in str(exc_info.value)

    def test_get_servers_unclustered(self, fetcher, mock_response):
        """Test get_servers returns unclustered by default."""
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=lambda: mock_response))
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_urlopen):
            fetcher.fetch()
        
        servers = fetcher.get_servers(clustered=False)
        assert "sgp" in servers
        assert "hkg" in servers

    def test_get_servers_clustered(self, fetcher, mock_response):
        """Test get_servers with clustered option."""
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=lambda: mock_response))
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_urlopen):
            fetcher.fetch()
        
        servers = fetcher.get_servers(clustered=True)
        assert "China" in servers
        assert "Japan" in servers

    def test_get_server_by_name_exact_code(self, fetcher, mock_response):
        """Test finding server by exact code."""
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=lambda: mock_response))
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_urlopen):
            fetcher.fetch()
        
        server = fetcher.get_server_by_name("sgp")
        assert server is not None
        assert server.code == "sgp"

    def test_get_server_by_name_partial_name(self, fetcher, mock_response):
        """Test finding server by partial name."""
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=lambda: mock_response))
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_urlopen):
            fetcher.fetch()
        
        server = fetcher.get_server_by_name("singapore")
        assert server is not None
        assert server.code == "sgp"

    def test_get_server_by_name_not_found(self, fetcher, mock_response):
        """Test finding non-existent server."""
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=lambda: mock_response))
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_urlopen):
            fetcher.fetch()
        
        server = fetcher.get_server_by_name("nonexistent")
        assert server is None

    def test_get_server_by_name_clustered(self, fetcher, mock_response):
        """Test finding server in clustered mode."""
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=lambda: mock_response))
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_urlopen):
            fetcher.fetch()
        
        server = fetcher.get_server_by_name("China", clustered=True)
        assert server is not None
        assert server.name == "China"


class TestServerDataFetcherIntegration:
    """Integration tests that can optionally call the real API."""

    @pytest.fixture
    def fetcher(self):
        """Create a fetcher instance."""
        return ServerDataFetcher()

    @pytest.mark.integration
    @pytest.mark.skipif(True, reason="Skip by default - enable manually for integration testing")
    def test_fetch_real_api(self, fetcher):
        """Test fetching from real Steam API."""
        revision = fetcher.fetch()
        
        assert revision is not None
        assert int(revision) > 0
        assert len(fetcher.servers) > 0
        
        # Should have some common servers
        servers = fetcher.servers
        # Server codes may vary, but there should be servers
        assert len(servers) >= 10
