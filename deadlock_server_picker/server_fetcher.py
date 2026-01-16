"""
Server data fetcher - retrieves Deadlock server relay data from Steam API.
"""

import json
import urllib.request
import urllib.error
from typing import Optional

from .models import Server, ServerRelay, ServerCluster, DEFAULT_CLUSTERS


STEAM_SDR_API_URL = "https://api.steampowered.com/ISteamApps/GetSDRConfig/v1/?appid=730"
USER_AGENT = "deadlock-server-picker-linux/1.0"


class ServerFetchError(Exception):
    """Raised when server data cannot be fetched."""
    pass


class ServerDataFetcher:
    """Fetches and parses Deadlock server relay data from Steam API."""

    def __init__(self, api_url: str = STEAM_SDR_API_URL):
        self.api_url = api_url
        self._revision: Optional[str] = None
        self._servers: dict[str, Server] = {}
        self._clustered_servers: dict[str, Server] = {}

    @property
    def revision(self) -> Optional[str]:
        """Get the server data revision."""
        return self._revision

    @property
    def servers(self) -> dict[str, Server]:
        """Get unclustered servers."""
        return self._servers

    @property
    def clustered_servers(self) -> dict[str, Server]:
        """Get clustered servers."""
        return self._clustered_servers

    def fetch(self) -> str:
        """
        Fetch server data from Steam API.
        
        Returns:
            The server revision string.
            
        Raises:
            ServerFetchError: If data cannot be fetched or parsed.
        """
        try:
            request = urllib.request.Request(
                self.api_url,
                headers={"User-Agent": USER_AGENT}
            )
            
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                
        except urllib.error.URLError as e:
            raise ServerFetchError(f"Failed to fetch server data: {e}") from e
        except json.JSONDecodeError as e:
            raise ServerFetchError(f"Failed to parse server data: {e}") from e

        return self._parse_server_data(data)

    def _parse_server_data(self, data: dict) -> str:
        """
        Parse the server data from Steam API response.
        
        Args:
            data: Parsed JSON data from API.
            
        Returns:
            The server revision string.
            
        Raises:
            ServerFetchError: If data format is invalid.
        """
        try:
            revision = data.get("revision")
            if not revision:
                raise ServerFetchError("Server data missing revision field")
            
            self._revision = str(revision)
            self._servers.clear()
            self._clustered_servers.clear()

            pops = data.get("pops", {})
            
            for server_code, server_data in pops.items():
                relays = server_data.get("relays")
                if not relays:
                    continue

                server_name = server_data.get("desc", server_code)
                
                # Parse relay IP addresses
                relay_list = []
                for relay in relays:
                    ipv4 = relay.get("ipv4")
                    if ipv4:
                        port_range = relay.get("port_range")
                        relay_list.append(ServerRelay(ipv4=ipv4, port_range=port_range))

                if not relay_list:
                    continue

                server = Server(
                    name=server_name,
                    code=server_code,
                    relays=relay_list
                )

                # Add to unclustered servers
                self._servers[server_code] = server

                # Check if server belongs to a cluster
                self._add_to_clusters(server)

            return self._revision

        except KeyError as e:
            raise ServerFetchError(f"Invalid server data format: missing {e}") from e

    def _add_to_clusters(self, server: Server) -> None:
        """
        Add server to appropriate clusters.
        
        Args:
            server: Server to potentially add to clusters.
        """
        added_to_cluster = False
        
        for cluster_name, keywords in DEFAULT_CLUSTERS.items():
            for keyword in keywords:
                if keyword.lower() in server.name.lower():
                    # Add to or update clustered server
                    if cluster_name not in self._clustered_servers:
                        self._clustered_servers[cluster_name] = Server(
                            name=cluster_name,
                            code=cluster_name.lower().replace(" ", "_").replace("(", "").replace(")", ""),
                            relays=list(server.relays)
                        )
                    else:
                        self._clustered_servers[cluster_name].relays.extend(server.relays)
                    added_to_cluster = True
                    break
            if added_to_cluster:
                break

        # If not clustered, add as its own entry in clustered dict
        if not added_to_cluster:
            self._clustered_servers[server.display_name] = server

    def get_servers(self, clustered: bool = False) -> dict[str, Server]:
        """
        Get servers dictionary.
        
        Args:
            clustered: If True, return clustered servers, otherwise unclustered.
            
        Returns:
            Dictionary of server code to Server objects.
        """
        if clustered:
            return self._clustered_servers
        return self._servers

    def get_server_by_name(self, name: str, clustered: bool = False) -> Optional[Server]:
        """
        Find a server by its name or code.
        
        Args:
            name: Server name or code to search for.
            clustered: Whether to search in clustered servers.
            
        Returns:
            Server if found, None otherwise.
        """
        servers = self.get_servers(clustered)
        
        # Try exact code match first
        if name in servers:
            return servers[name]
        
        # Try name match
        name_lower = name.lower()
        for code, server in servers.items():
            if name_lower in server.name.lower() or name_lower in code.lower():
                return server
        
        return None
