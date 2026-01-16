"""
Data models for Deadlock Server Picker.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ServerStatus(Enum):
    """Status of a server."""
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"


@dataclass
class ServerRelay:
    """Represents a single server relay IP address."""
    ipv4: str
    port_range: Optional[str] = None

    def __str__(self) -> str:
        return self.ipv4


@dataclass
class Server:
    """Represents a Deadlock game server region."""
    name: str
    code: str
    relays: list[ServerRelay] = field(default_factory=list)
    latency_ms: Optional[int] = None
    status: ServerStatus = ServerStatus.UNKNOWN

    @property
    def ip_addresses(self) -> list[str]:
        """Get all IP addresses for this server."""
        return [relay.ipv4 for relay in self.relays]

    @property
    def display_name(self) -> str:
        """Get display name with code."""
        return f"{self.name} ({self.code})"

    def __str__(self) -> str:
        status_str = f" [{self.status.value}]" if self.status != ServerStatus.UNKNOWN else ""
        latency_str = f" - {self.latency_ms}ms" if self.latency_ms is not None else ""
        return f"{self.display_name}{latency_str}{status_str}"


@dataclass
class Preset:
    """Represents a saved preset of servers."""
    name: str
    servers: list[str]  # List of server codes
    clustered: bool = False

    def __str__(self) -> str:
        return f"{self.name} ({len(self.servers)} servers)"


@dataclass
class ServerCluster:
    """Represents a cluster of related servers (e.g., all China servers)."""
    name: str
    keywords: list[str]  # Keywords to match server names
    servers: list[Server] = field(default_factory=list)

    @property
    def all_ip_addresses(self) -> list[str]:
        """Get all IP addresses from all servers in cluster."""
        ips = []
        for server in self.servers:
            ips.extend(server.ip_addresses)
        return ips


# Default clusters matching the original tool
DEFAULT_CLUSTERS = {
    "China": ["Perfect", "Hong Kong", "Alibaba", "Tencent"],
    "Japan": ["Tokyo"],
    "Stockholm (Sweden)": ["Stockholm"],
    "India": ["Chennai", "Mumbai"],
}
