"""
Tests for ping service.
"""

import pytest
from unittest.mock import patch, MagicMock
import socket

from deadlock_server_picker.ping_service import (
    PingService, ping_host, tcp_ping, udp_ping,
    _calculate_checksum, _create_icmp_packet
)
from deadlock_server_picker.models import Server, ServerRelay, ServerStatus


class TestICMPHelpers:
    """Tests for ICMP helper functions."""

    def test_calculate_checksum(self):
        """Test ICMP checksum calculation."""
        data = b"\x08\x00\x00\x00\x00\x01\x00\x01"
        checksum = _calculate_checksum(data)
        assert isinstance(checksum, int)
        assert 0 <= checksum <= 0xFFFF

    def test_calculate_checksum_odd_length(self):
        """Test checksum with odd-length data."""
        data = b"\x08\x00\x00"  # 3 bytes
        checksum = _calculate_checksum(data)
        assert isinstance(checksum, int)

    def test_create_icmp_packet(self):
        """Test ICMP packet creation."""
        packet = _create_icmp_packet(seq_num=1)
        
        # Should be at least 8 bytes (ICMP header)
        assert len(packet) >= 8
        
        # First byte should be type 8 (echo request)
        assert packet[0] == 8
        
        # Second byte should be code 0
        assert packet[1] == 0


class TestPingHost:
    """Tests for ping_host function."""

    def test_ping_host_icmp_permission_error(self):
        """Test fallback when ICMP fails with permission error."""
        with patch("socket.socket") as mock_socket:
            # First call (ICMP) raises PermissionError
            mock_socket.side_effect = PermissionError("Operation not permitted")
            
            with patch("deadlock_server_picker.ping_service.tcp_ping", return_value=50.0):
                result = ping_host("8.8.8.8", timeout=1.0)
            
            # Should fallback to TCP ping
            assert result == 50.0

    def test_ping_host_socket_error(self):
        """Test handling socket errors."""
        with patch("socket.socket") as mock_socket:
            mock_socket.side_effect = socket.error("Connection failed")
            
            result = ping_host("8.8.8.8", timeout=1.0)
            assert result is None


class TestTcpPing:
    """Tests for TCP ping function."""

    def test_tcp_ping_success(self):
        """Test successful TCP ping."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0  # Connection successful
        
        with patch("socket.socket", return_value=mock_socket):
            result = tcp_ping("127.0.0.1", timeout=1.0)
        
        assert result is not None
        assert result >= 0

    def test_tcp_ping_connection_refused(self):
        """Test TCP ping with connection refused (port is responsive)."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 111  # Connection refused
        
        with patch("socket.socket", return_value=mock_socket):
            result = tcp_ping("127.0.0.1", timeout=1.0)
        
        # Should still return a result since host responded
        assert result is not None

    def test_tcp_ping_timeout(self):
        """Test TCP ping timeout."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.side_effect = socket.timeout("timed out")
        
        with patch("socket.socket", return_value=mock_socket):
            result = tcp_ping("192.0.2.1", timeout=0.1)  # Non-routable IP
        
        # May return None or fallback to UDP
        assert result is None or isinstance(result, float)


class TestUdpPing:
    """Tests for UDP ping function."""

    def test_udp_ping_with_response(self):
        """Test UDP ping when server responds."""
        mock_socket = MagicMock()
        mock_socket.recvfrom.return_value = (b"response", ("8.8.8.8", 27015))
        
        with patch("socket.socket", return_value=mock_socket):
            result = udp_ping("8.8.8.8", timeout=1.0)
        
        assert result is not None
        assert result >= 0

    def test_udp_ping_timeout(self):
        """Test UDP ping timeout."""
        mock_socket = MagicMock()
        mock_socket.recvfrom.side_effect = socket.timeout("timed out")
        
        with patch("socket.socket", return_value=mock_socket):
            result = udp_ping("192.0.2.1", timeout=0.5)
        
        # Should return estimate based on send time or None
        assert result is None or isinstance(result, float)

    def test_udp_ping_error(self):
        """Test UDP ping with error."""
        with patch("socket.socket") as mock_socket:
            mock_socket.side_effect = Exception("Socket error")
            
            result = udp_ping("8.8.8.8", timeout=1.0)
        
        assert result is None


class TestPingService:
    """Tests for PingService class."""

    @pytest.fixture
    def service(self):
        """Create a ping service instance."""
        return PingService(timeout=1.0, max_workers=2)

    @pytest.fixture
    def server(self):
        """Create a test server."""
        return Server(
            name="Test Server",
            code="test",
            relays=[
                ServerRelay(ipv4="127.0.0.1"),
                ServerRelay(ipv4="127.0.0.2")
            ]
        )

    def test_init(self, service):
        """Test service initialization."""
        assert service.timeout == 1.0
        assert service.max_workers == 2

    def test_ping_server_success(self, service, server):
        """Test pinging a single server successfully."""
        with patch("deadlock_server_picker.ping_service.ping_host", return_value=25.5):
            result = service.ping_server(server)
        
        assert result == 25
        assert server.latency_ms == 25
        assert server.status == ServerStatus.AVAILABLE

    def test_ping_server_timeout(self, service, server):
        """Test pinging a server that times out."""
        with patch("deadlock_server_picker.ping_service.ping_host", return_value=None):
            result = service.ping_server(server)
        
        assert result is None
        assert server.latency_ms is None
        assert server.status == ServerStatus.TIMEOUT

    def test_ping_server_picks_best_latency(self, service, server):
        """Test that best latency is selected from multiple relays."""
        call_count = [0]
        
        def mock_ping(host, timeout):
            call_count[0] += 1
            if call_count[0] == 1:
                return 100.0  # First relay - 100ms
            return 25.0  # Second relay - 25ms
        
        with patch("deadlock_server_picker.ping_service.ping_host", side_effect=mock_ping):
            result = service.ping_server(server)
        
        assert result == 25  # Should pick the better latency

    def test_ping_server_blocked_status_preserved(self, service, server):
        """Test that blocked status is preserved after ping."""
        server.status = ServerStatus.BLOCKED
        
        with patch("deadlock_server_picker.ping_service.ping_host", return_value=25.0):
            service.ping_server(server)
        
        # Status should remain blocked even if we could ping
        # (blocked servers shouldn't be pinged in real use)
        assert server.status == ServerStatus.BLOCKED

    def test_ping_servers_multiple(self, service):
        """Test pinging multiple servers."""
        servers = [
            Server(name="Server1", code="s1", relays=[ServerRelay(ipv4="1.1.1.1")]),
            Server(name="Server2", code="s2", relays=[ServerRelay(ipv4="2.2.2.2")])
        ]
        
        with patch("deadlock_server_picker.ping_service.ping_host", return_value=50.0):
            results = service.ping_servers(servers)
        
        assert len(results) == 2
        assert results["s1"] == 50
        assert results["s2"] == 50

    def test_ping_servers_handles_errors(self, service):
        """Test that ping_servers handles individual errors."""
        servers = [
            Server(name="Server1", code="s1", relays=[ServerRelay(ipv4="1.1.1.1")]),
            Server(name="Server2", code="s2", relays=[ServerRelay(ipv4="2.2.2.2")])
        ]
        
        def mock_ping(host, timeout):
            if host == "1.1.1.1":
                return 25.0
            raise Exception("Network error")
        
        with patch("deadlock_server_picker.ping_service.ping_host", side_effect=mock_ping):
            results = service.ping_servers(servers)
        
        # First should succeed, second should fail
        assert results["s1"] == 25
        # Second may be None or have error

    def test_context_manager(self):
        """Test using service as context manager."""
        with PingService(timeout=1.0) as service:
            assert service is not None
        
        # Service should be shut down after context

    def test_shutdown(self, service):
        """Test manual shutdown."""
        service.shutdown()
        # Should not raise any errors


class TestPingServiceAsync:
    """Tests for async ping functionality."""

    @pytest.fixture
    def service(self):
        """Create a ping service instance."""
        return PingService(timeout=1.0, max_workers=2)

    @pytest.mark.asyncio
    async def test_ping_servers_async(self, service):
        """Test async server pinging."""
        servers = [
            Server(name="Server1", code="s1", relays=[ServerRelay(ipv4="1.1.1.1")]),
            Server(name="Server2", code="s2", relays=[ServerRelay(ipv4="2.2.2.2")])
        ]
        
        with patch("deadlock_server_picker.ping_service.ping_host", return_value=30.0):
            results = await service.ping_servers_async(servers)
        
        assert len(results) == 2
        assert results["s1"] == 30
        assert results["s2"] == 30
