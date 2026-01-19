"""
Ping service - measures latency to Deadlock servers.
"""

import asyncio
import socket
import struct
import time
import os
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from .models import Server, ServerStatus


class PingError(Exception):
    """Raised when ping operations fail."""
    pass


def _calculate_checksum(data: bytes) -> int:
    """Calculate ICMP checksum."""
    if len(data) % 2:
        data += b'\x00'
    
    checksum = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        checksum += word
    
    checksum = (checksum >> 16) + (checksum & 0xffff)
    checksum += checksum >> 16
    
    return ~checksum & 0xffff


def _create_icmp_packet(seq_num: int = 1) -> bytes:
    """Create an ICMP echo request packet."""
    icmp_type = 8  # Echo request
    icmp_code = 0
    checksum = 0
    packet_id = os.getpid() & 0xFFFF
    
    # Create header with zero checksum
    header = struct.pack('!BBHHH', icmp_type, icmp_code, checksum, packet_id, seq_num)
    data = b'DeadlockServerPicker' + struct.pack('d', time.time())
    
    # Calculate checksum
    checksum = _calculate_checksum(header + data)
    header = struct.pack('!BBHHH', icmp_type, icmp_code, checksum, packet_id, seq_num)
    
    return header + data


def ping_host(host: str, timeout: float = 2.0) -> Optional[float]:
    """
    Ping a host and return the round-trip time in milliseconds.
    
    Args:
        host: IP address or hostname to ping.
        timeout: Timeout in seconds.
        
    Returns:
        Round-trip time in milliseconds, or None if ping failed.
    """
    # Try subprocess ping first (most reliable, works without raw socket perms)
    result = subprocess_ping(host, timeout)
    if result is not None:
        return result
    
    # Try raw ICMP ping (requires root/sudo)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        sock.settimeout(timeout)
        
        packet = _create_icmp_packet()
        start_time = time.time()
        
        sock.sendto(packet, (host, 0))
        
        while True:
            ready = sock.recv(1024)
            elapsed = (time.time() - start_time) * 1000
            
            if elapsed > timeout * 1000:
                sock.close()
                return None
            
            # Extract ICMP header (skip IP header, usually 20 bytes)
            icmp_header = ready[20:28]
            icmp_type, _, _, packet_id, _ = struct.unpack('!BBHHH', icmp_header)
            
            # Check if this is our echo reply
            if icmp_type == 0 and packet_id == (os.getpid() & 0xFFFF):
                sock.close()
                return elapsed
                
    except PermissionError:
        pass
    except socket.error:
        pass
    except Exception:
        pass
    finally:
        try:
            sock.close()
        except Exception:
            pass
    
    # Fall back to TCP ping
    result = tcp_ping(host, timeout)
    if result is not None:
        return result
    
    return None


def subprocess_ping(host: str, timeout: float = 2.0) -> Optional[float]:
    """
    Ping using system ping command (most reliable).
    
    Args:
        host: IP address or hostname to ping.
        timeout: Timeout in seconds.
        
    Returns:
        Round-trip time in milliseconds, or None if ping failed.
    """
    import subprocess
    import re
    
    try:
        # Use system ping command with count=1
        result = subprocess.run(
            ['ping', '-c', '1', '-W', str(int(timeout)), host],
            capture_output=True,
            text=True,
            timeout=timeout + 1
        )
        
        if result.returncode == 0:
            # Parse time from output like "time=12.3 ms"
            match = re.search(r'time[=<](\d+\.?\d*)\s*ms', result.stdout)
            if match:
                return float(match.group(1))
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass
    except Exception:
        pass
    
    return None


def tcp_ping(host: str, timeout: float = 2.0, port: int = 27015) -> Optional[float]:
    """
    Perform a TCP ping by measuring connection time.
    
    Args:
        host: IP address or hostname.
        timeout: Timeout in seconds.
        port: Port to connect to (default: Steam game server port).
        
    Returns:
        Connection time in milliseconds, or None if failed.
    """
    # Try common Steam/Deadlock ports
    ports_to_try = [27015, 27016, 27017, 27018, 27019, 27020]
    
    for test_port in ports_to_try:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            start_time = time.time()
            result = sock.connect_ex((host, test_port))
            elapsed = (time.time() - start_time) * 1000
            
            sock.close()
            
            # If connection succeeded or was refused (port is responding)
            if result == 0 or result == 111:  # 111 = Connection refused
                return elapsed
                
        except socket.error:
            continue
        except Exception:
            continue
        finally:
            try:
                sock.close()
            except Exception:
                pass
    
    # Last resort: try UDP
    return udp_ping(host, timeout)


def udp_ping(host: str, timeout: float = 2.0, port: int = 27015) -> Optional[float]:
    """
    Estimate latency using UDP (less accurate but works without root).
    
    Args:
        host: IP address or hostname.
        timeout: Timeout in seconds.
        port: Port to use.
        
    Returns:
        Estimated latency in milliseconds, or None if failed.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        start_time = time.time()
        
        # Send a small packet
        sock.sendto(b'\xff\xff\xff\xffTSource Engine Query\x00', (host, port))
        
        try:
            # Try to receive response
            sock.recvfrom(1024)
            elapsed = (time.time() - start_time) * 1000
            sock.close()
            return elapsed
        except socket.timeout:
            # No response, but we can estimate based on send time
            elapsed = (time.time() - start_time) * 1000
            sock.close()
            return elapsed if elapsed < timeout * 1000 else None
            
    except Exception:
        return None
    finally:
        try:
            sock.close()
        except Exception:
            pass


class PingService:
    """Service for pinging Deadlock servers to measure latency."""

    def __init__(self, timeout: float = 2.0, max_workers: int = 50):
        """
        Initialize ping service.
        
        Args:
            timeout: Ping timeout in seconds.
            max_workers: Maximum concurrent ping operations.
        """
        self.timeout = timeout
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def ping_server(self, server: Server) -> Optional[int]:
        """
        Ping a server and update its latency.
        
        Args:
            server: Server to ping.
            
        Returns:
            Latency in milliseconds, or None if ping failed.
        """
        # Try only the first IP address for speed
        # (pinging all IPs sequentially is too slow when IPs timeout)
        best_latency = None
        
        ips = server.ip_addresses
        if ips:
            # Try first IP, then only try second if first fails
            latency = ping_host(ips[0], self.timeout)
            if latency is not None:
                best_latency = latency
            elif len(ips) > 1:
                # Fallback to second IP if first fails
                latency = ping_host(ips[1], self.timeout)
                if latency is not None:
                    best_latency = latency
        
        if best_latency is not None:
            server.latency_ms = int(best_latency)
            if server.status != ServerStatus.BLOCKED:
                server.status = ServerStatus.AVAILABLE
        else:
            server.latency_ms = None
            if server.status != ServerStatus.BLOCKED:
                server.status = ServerStatus.TIMEOUT
                
        return server.latency_ms

    def ping_servers(self, servers: list[Server], on_progress: callable = None) -> dict[str, Optional[int]]:
        """
        Ping multiple servers concurrently.
        
        Args:
            servers: List of servers to ping.
            on_progress: Optional callback(completed, total, server_code, latency) for progress updates.
            
        Returns:
            Dictionary mapping server codes to latencies.
        """
        from concurrent.futures import as_completed, TimeoutError as FuturesTimeoutError
        
        results = {}
        futures = {}
        total = len(servers)
        completed = 0
        
        for server in servers:
            future = self._executor.submit(self.ping_server, server)
            futures[future] = server
        
        # Use as_completed for real-time progress updates
        # No timeout - let each future complete naturally
        try:
            for future in as_completed(futures):
                server = futures[future]
                try:
                    latency = future.result(timeout=self.timeout + 1)
                    results[server.code] = latency
                except Exception:
                    results[server.code] = None
                    server.status = ServerStatus.TIMEOUT
                
                completed += 1
                if on_progress:
                    on_progress(completed, total, server.code, results[server.code])
        except FuturesTimeoutError:
            # Handle any remaining futures that timed out
            for future, server in futures.items():
                if server.code not in results:
                    results[server.code] = None
                    server.status = ServerStatus.TIMEOUT
                    completed += 1
                    if on_progress:
                        on_progress(completed, total, server.code, None)
                
        return results

    async def ping_servers_async(self, servers: list[Server]) -> dict[str, Optional[int]]:
        """
        Ping multiple servers asynchronously.
        
        Args:
            servers: List of servers to ping.
            
        Returns:
            Dictionary mapping server codes to latencies.
        """
        loop = asyncio.get_event_loop()
        results = {}
        
        tasks = []
        for server in servers:
            task = loop.run_in_executor(self._executor, self.ping_server, server)
            tasks.append((server, task))
        
        for server, task in tasks:
            try:
                latency = await task
                results[server.code] = latency
            except Exception:
                results[server.code] = None
                server.status = ServerStatus.TIMEOUT
                
        return results

    def shutdown(self) -> None:
        """Shutdown the executor."""
        self._executor.shutdown(wait=False)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
