"""
Tests for data models.
"""

import pytest
from deadlock_server_picker.models import (
    Server, ServerRelay, ServerStatus, Preset, ServerCluster, DEFAULT_CLUSTERS
)


class TestServerRelay:
    """Tests for ServerRelay model."""

    def test_create_relay(self):
        """Test creating a server relay."""
        relay = ServerRelay(ipv4="192.168.1.1")
        assert relay.ipv4 == "192.168.1.1"
        assert relay.port_range is None

    def test_create_relay_with_port(self):
        """Test creating a relay with port range."""
        relay = ServerRelay(ipv4="10.0.0.1", port_range="27015-27020")
        assert relay.ipv4 == "10.0.0.1"
        assert relay.port_range == "27015-27020"

    def test_relay_str(self):
        """Test relay string representation."""
        relay = ServerRelay(ipv4="192.168.1.1")
        assert str(relay) == "192.168.1.1"


class TestServer:
    """Tests for Server model."""

    def test_create_server(self):
        """Test creating a server."""
        server = Server(name="Singapore", code="sgp")
        assert server.name == "Singapore"
        assert server.code == "sgp"
        assert server.relays == []
        assert server.latency_ms is None
        assert server.status == ServerStatus.UNKNOWN

    def test_server_with_relays(self):
        """Test server with relay IPs."""
        relays = [
            ServerRelay(ipv4="192.168.1.1"),
            ServerRelay(ipv4="192.168.1.2")
        ]
        server = Server(name="Singapore", code="sgp", relays=relays)
        
        assert len(server.relays) == 2
        assert server.ip_addresses == ["192.168.1.1", "192.168.1.2"]

    def test_server_display_name(self):
        """Test server display name."""
        server = Server(name="Singapore", code="sgp")
        assert server.display_name == "Singapore (sgp)"

    def test_server_str_basic(self):
        """Test server string representation."""
        server = Server(name="Singapore", code="sgp")
        assert str(server) == "Singapore (sgp)"

    def test_server_str_with_latency(self):
        """Test server string with latency."""
        server = Server(name="Singapore", code="sgp", latency_ms=25)
        assert "25ms" in str(server)

    def test_server_str_with_status(self):
        """Test server string with status."""
        server = Server(name="Singapore", code="sgp", status=ServerStatus.BLOCKED)
        assert "blocked" in str(server)

    def test_server_status_values(self):
        """Test all server status values."""
        assert ServerStatus.UNKNOWN.value == "unknown"
        assert ServerStatus.AVAILABLE.value == "available"
        assert ServerStatus.BLOCKED.value == "blocked"
        assert ServerStatus.TIMEOUT.value == "timeout"


class TestPreset:
    """Tests for Preset model."""

    def test_create_preset(self):
        """Test creating a preset."""
        preset = Preset(name="My Preset", servers=["sgp", "hkg"])
        assert preset.name == "My Preset"
        assert preset.servers == ["sgp", "hkg"]
        assert preset.clustered is False

    def test_preset_clustered(self):
        """Test clustered preset."""
        preset = Preset(name="Test", servers=["China"], clustered=True)
        assert preset.clustered is True

    def test_preset_str(self):
        """Test preset string representation."""
        preset = Preset(name="Asia", servers=["sgp", "hkg", "tyo"])
        assert str(preset) == "Asia (3 servers)"


class TestServerCluster:
    """Tests for ServerCluster model."""

    def test_create_cluster(self):
        """Test creating a server cluster."""
        cluster = ServerCluster(name="China", keywords=["Perfect", "Hong Kong"])
        assert cluster.name == "China"
        assert cluster.keywords == ["Perfect", "Hong Kong"]
        assert cluster.servers == []

    def test_cluster_with_servers(self):
        """Test cluster with servers."""
        server1 = Server(
            name="Hong Kong 1",
            code="hkg",
            relays=[ServerRelay(ipv4="1.1.1.1")]
        )
        server2 = Server(
            name="Hong Kong 2",
            code="hkg2",
            relays=[ServerRelay(ipv4="2.2.2.2")]
        )
        
        cluster = ServerCluster(
            name="China",
            keywords=["Hong Kong"],
            servers=[server1, server2]
        )
        
        assert len(cluster.servers) == 2
        assert cluster.all_ip_addresses == ["1.1.1.1", "2.2.2.2"]


class TestDefaultClusters:
    """Tests for default cluster configuration."""

    def test_default_clusters_exist(self):
        """Test that default clusters are defined."""
        assert "China" in DEFAULT_CLUSTERS
        assert "Japan" in DEFAULT_CLUSTERS
        assert "Stockholm (Sweden)" in DEFAULT_CLUSTERS
        assert "India" in DEFAULT_CLUSTERS

    def test_china_cluster_keywords(self):
        """Test China cluster has correct keywords."""
        china = DEFAULT_CLUSTERS["China"]
        assert "Perfect" in china
        assert "Hong Kong" in china
        assert "Alibaba" in china
        assert "Tencent" in china

    def test_japan_cluster_keywords(self):
        """Test Japan cluster keywords."""
        assert "Tokyo" in DEFAULT_CLUSTERS["Japan"]

    def test_india_cluster_keywords(self):
        """Test India cluster keywords."""
        india = DEFAULT_CLUSTERS["India"]
        assert "Chennai" in india
        assert "Mumbai" in india
