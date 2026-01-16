"""
Server geolocation data for Deadlock servers.
Maps server codes to their approximate geographic locations.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GeoLocation:
    """Geographic location information."""
    city: str
    country: str
    region: str
    latitude: float
    longitude: float
    
    @property
    def display_name(self) -> str:
        """Get human-readable location name."""
        return f"{self.city}, {self.country}"
    
    @property
    def coords(self) -> tuple[float, float]:
        """Get (lat, lon) tuple."""
        return (self.latitude, self.longitude)


# Server code to location mapping
# Based on Steam relay network documentation and known datacenter locations
SERVER_LOCATIONS: dict[str, GeoLocation] = {
    # North America
    "iad": GeoLocation("Ashburn", "USA", "North America", 39.0438, -77.4874),
    "ord": GeoLocation("Chicago", "USA", "North America", 41.8781, -87.6298),
    "atl": GeoLocation("Atlanta", "USA", "North America", 33.7490, -84.3880),
    "lax": GeoLocation("Los Angeles", "USA", "North America", 34.0522, -118.2437),
    "sea": GeoLocation("Seattle", "USA", "North America", 47.6062, -122.3321),
    "dfw": GeoLocation("Dallas", "USA", "North America", 32.7767, -96.7970),
    "eze": GeoLocation("Buenos Aires", "Argentina", "South America", -34.6037, -58.3816),
    "gru": GeoLocation("São Paulo", "Brazil", "South America", -23.5505, -46.6333),
    "scl": GeoLocation("Santiago", "Chile", "South America", -33.4489, -70.6693),
    "lim": GeoLocation("Lima", "Peru", "South America", -12.0464, -77.0428),
    
    # Europe
    "ams": GeoLocation("Amsterdam", "Netherlands", "Europe", 52.3676, 4.9041),
    "fra": GeoLocation("Frankfurt", "Germany", "Europe", 50.1109, 8.6821),
    "lhr": GeoLocation("London", "UK", "Europe", 51.5074, -0.1278),
    "mad": GeoLocation("Madrid", "Spain", "Europe", 40.4168, -3.7038),
    "sto": GeoLocation("Stockholm", "Sweden", "Europe", 59.3293, 18.0686),
    "vie": GeoLocation("Vienna", "Austria", "Europe", 48.2082, 16.3738),
    "waw": GeoLocation("Warsaw", "Poland", "Europe", 52.2297, 21.0122),
    "par": GeoLocation("Paris", "France", "Europe", 48.8566, 2.3522),
    
    # Asia
    "sgp": GeoLocation("Singapore", "Singapore", "Asia", 1.3521, 103.8198),
    "hkg": GeoLocation("Hong Kong", "China", "Asia", 22.3193, 114.1694),
    "tyo": GeoLocation("Tokyo", "Japan", "Asia", 35.6762, 139.6503),
    "icn": GeoLocation("Seoul", "South Korea", "Asia", 37.5665, 126.9780),
    "bom": GeoLocation("Mumbai", "India", "Asia", 19.0760, 72.8777),
    "maa": GeoLocation("Chennai", "India", "Asia", 13.0827, 80.2707),
    "dxb": GeoLocation("Dubai", "UAE", "Middle East", 25.2048, 55.2708),
    "pwg": GeoLocation("Guangzhou", "China", "Asia", 23.1291, 113.2644),
    "pwj": GeoLocation("Shanghai", "China", "Asia", 31.2304, 121.4737),
    "pwu": GeoLocation("Chengdu", "China", "Asia", 30.5728, 104.0668),
    "pww": GeoLocation("Wuhan", "China", "Asia", 30.5928, 114.3055),
    "pwz": GeoLocation("Tianjin", "China", "Asia", 39.3434, 117.3616),
    
    # Oceania
    "syd": GeoLocation("Sydney", "Australia", "Oceania", -33.8688, 151.2093),
    
    # Africa
    "jnb": GeoLocation("Johannesburg", "South Africa", "Africa", -26.2041, 28.0473),
    
    # Russia & CIS
    "mos": GeoLocation("Moscow", "Russia", "Russia", 55.7558, 37.6173),
    "mos2": GeoLocation("Moscow", "Russia", "Russia", 55.7558, 37.6173),
}


def get_server_location(code: str) -> Optional[GeoLocation]:
    """
    Get geographic location for a server code.
    
    Args:
        code: Server code (e.g., 'iad', 'sgp').
        
    Returns:
        GeoLocation or None if not found.
    """
    return SERVER_LOCATIONS.get(code.lower())


def get_all_locations() -> dict[str, GeoLocation]:
    """Get all server locations."""
    return SERVER_LOCATIONS.copy()


def get_locations_by_region(region: str) -> list[tuple[str, GeoLocation]]:
    """
    Get all server locations in a geographic region.
    
    Args:
        region: Region name (e.g., 'North America', 'Europe', 'Asia').
        
    Returns:
        List of (code, location) tuples.
    """
    return [
        (code, loc) for code, loc in SERVER_LOCATIONS.items()
        if loc.region.lower() == region.lower()
    ]


def generate_ascii_map(servers_status: dict[str, bool], width: int = 80) -> str:
    """
    Generate a simple ASCII world map showing server locations.
    
    Args:
        servers_status: Dictionary of server code -> blocked status.
        width: Map width in characters.
        
    Returns:
        ASCII art map string.
    """
    # Simple ASCII world map representation
    # This is a very simplified representation
    height = width // 3
    
    # Create empty map
    map_chars = [[' ' for _ in range(width)] for _ in range(height)]
    
    # Define continental boundaries (very simplified)
    # Format: (y_min, y_max, x_min, x_max) as percentages of map size
    continents = {
        "North America": (0.1, 0.5, 0.05, 0.30),
        "South America": (0.5, 0.9, 0.15, 0.35),
        "Europe": (0.15, 0.45, 0.40, 0.55),
        "Africa": (0.35, 0.75, 0.40, 0.60),
        "Asia": (0.1, 0.6, 0.55, 0.95),
        "Oceania": (0.6, 0.85, 0.75, 0.95),
        "Russia": (0.05, 0.25, 0.50, 0.95),
    }
    
    # Draw continental outlines with dots
    for region, (y_min, y_max, x_min, x_max) in continents.items():
        y1 = int(y_min * height)
        y2 = int(y_max * height)
        x1 = int(x_min * width)
        x2 = int(x_max * width)
        
        # Draw border dots
        for x in range(x1, x2, 3):
            if 0 <= y1 < height and 0 <= x < width:
                map_chars[y1][x] = '·'
            if 0 <= y2 - 1 < height and 0 <= x < width:
                map_chars[y2 - 1][x] = '·'
        for y in range(y1, y2, 2):
            if 0 <= y < height and 0 <= x1 < width:
                map_chars[y][x1] = '·'
            if 0 <= y < height and 0 <= x2 - 1 < width:
                map_chars[y][x2 - 1] = '·'
    
    # Place servers on map
    for code, loc in SERVER_LOCATIONS.items():
        # Convert lat/lon to map coordinates
        # Longitude: -180 to 180 -> 0 to width
        # Latitude: 90 to -90 -> 0 to height
        x = int(((loc.longitude + 180) / 360) * width)
        y = int(((90 - loc.latitude) / 180) * height)
        
        # Clamp to bounds
        x = max(0, min(width - 1, x))
        y = max(0, min(height - 1, y))
        
        # Get status
        blocked = servers_status.get(code, False)
        char = '●' if blocked else '○'
        
        if 0 <= y < height and 0 <= x < width:
            map_chars[y][x] = char
    
    # Convert to string
    return '\n'.join(''.join(row) for row in map_chars)


def format_location_table(servers_status: dict[str, bool]) -> str:
    """
    Format a table showing server locations with status.
    
    Args:
        servers_status: Dictionary of server code -> blocked status.
        
    Returns:
        Formatted table string.
    """
    lines = []
    lines.append(f"{'Code':<6} {'City':<20} {'Country':<15} {'Status':<10}")
    lines.append("-" * 55)
    
    for code in sorted(SERVER_LOCATIONS.keys()):
        loc = SERVER_LOCATIONS[code]
        blocked = servers_status.get(code, False)
        status = "BLOCKED" if blocked else "ALLOWED"
        lines.append(f"{code:<6} {loc.city:<20} {loc.country:<15} {status:<10}")
    
    return '\n'.join(lines)
