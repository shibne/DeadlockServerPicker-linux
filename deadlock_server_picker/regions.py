"""
Regional server presets for Deadlock Server Picker.
"""

# Server codes grouped by region
REGION_PRESETS = {
    "North America": {
        "description": "All US and Canada servers",
        "servers": [
            "iad",    # Sterling, Virginia (US East)
            "ord",    # Chicago, Illinois
            "atl",    # Atlanta, Georgia
            "dfw",    # Dallas, Texas
            "lax",    # Los Angeles, California
            "sea",    # Seattle, Washington
        ]
    },
    "North America East": {
        "description": "US East Coast servers",
        "servers": [
            "iad",    # Sterling, Virginia
            "ord",    # Chicago, Illinois
            "atl",    # Atlanta, Georgia
        ]
    },
    "North America West": {
        "description": "US West Coast servers",
        "servers": [
            "dfw",    # Dallas, Texas
            "lax",    # Los Angeles, California
            "sea",    # Seattle, Washington
        ]
    },
    "South America": {
        "description": "Central and South American servers",
        "servers": [
            "gru",    # Sao Paulo, Brazil
            "eze",    # Buenos Aires, Argentina
            "scl",    # Santiago, Chile
            "lim",    # Lima, Peru
        ]
    },
    "Europe West": {
        "description": "Western European servers",
        "servers": [
            "lhr",    # London, England
            "fra",    # Frankfurt, Germany
            "par",    # Paris, France
            "ams",    # Amsterdam, Netherlands
            "ams4",   # Multiplay Amsterdam
            "mad",    # Madrid, Spain
        ]
    },
    "Europe East": {
        "description": "Eastern European servers",
        "servers": [
            "sto",    # Stockholm, Sweden
            "sto2",   # Stockholm - Bromma
            "vie",    # Vienna, Austria
            "waw",    # Warsaw, Poland
        ]
    },
    "Europe": {
        "description": "All European servers",
        "servers": [
            "lhr",    # London
            "fra",    # Frankfurt
            "par",    # Paris
            "ams",    # Amsterdam
            "ams4",   # Multiplay Amsterdam
            "mad",    # Madrid
            "sto",    # Stockholm
            "sto2",   # Stockholm - Bromma
            "vie",    # Vienna
            "waw",    # Warsaw
        ]
    },
    "Asia": {
        "description": "Asian servers (excluding China)",
        "servers": [
            "sgp",    # Singapore
            "hkg",    # Hong Kong
            "hkg4",   # Multiplay Hong Kong
            "tyo",    # Tokyo, Japan
            "seo",    # Seoul, South Korea
            "bom2",   # Mumbai, India
            "maa2",   # Chennai, India
        ]
    },
    "Asia Pacific": {
        "description": "Asia Pacific including Australia",
        "servers": [
            "sgp",    # Singapore
            "hkg",    # Hong Kong
            "hkg4",   # Multiplay Hong Kong
            "tyo",    # Tokyo, Japan
            "seo",    # Seoul, South Korea
            "syd",    # Sydney, Australia
        ]
    },
    "China": {
        "description": "Chinese servers (Perfect World & others)",
        "servers": [
            "pwg",    # Perfect World Guangdong
            "pwj",    # Perfect World Tianjin
            "pwu",    # Perfect World Hebei
            "pww",    # Perfect World Wuhan
            "pwz",    # Perfect World Zhejiang
            "shb",    # Perfect World Shanghai
            "ctum",   # Alibaba Chengdu Mobile
            "pekm",   # Alibaba Beijing Mobile
            "pvgm",   # Alibaba Shanghai Mobile
            "tgdm",   # Tencent Guangzhou Mobile
            "ctut",   # Alibaba Chengdu Telecom
            "pekt",   # Alibaba Beijing Telecom
            "pvgt",   # Alibaba Shanghai Telecom
            "tgdt",   # Tencent Guangzhou Telecom
            "ctuu",   # Alibaba Chengdu Unicom
            "peku",   # Alibaba Beijing Unicom
            "pvgu",   # Alibaba Shanghai Unicom
            "tgdu",   # Tencent Guangzhou Unicom
        ]
    },
    "India": {
        "description": "Indian servers",
        "servers": [
            "bom2",   # Mumbai
            "maa2",   # Chennai
        ]
    },
    "Japan": {
        "description": "Japanese servers",
        "servers": [
            "tyo",    # Tokyo
        ]
    },
    "Korea": {
        "description": "Korean servers",
        "servers": [
            "seo",    # Seoul
        ]
    },
    "Oceania": {
        "description": "Australia and nearby",
        "servers": [
            "syd",    # Sydney, Australia
        ]
    },
    "Middle East": {
        "description": "Middle Eastern servers",
        "servers": [
            "dxb",    # Dubai, UAE
        ]
    },
    "Africa": {
        "description": "African servers",
        "servers": [
            "jnb",    # Johannesburg, South Africa
        ]
    },
}

# Short aliases for regions
REGION_ALIASES = {
    "na": "North America",
    "nae": "North America East",
    "naeast": "North America East",
    "naw": "North America West",
    "nawest": "North America West",
    "sa": "South America",
    "eu": "Europe",
    "euw": "Europe West",
    "eue": "Europe East",
    "asia": "Asia",
    "apac": "Asia Pacific",
    "cn": "China",
    "china": "China",
    "in": "India",
    "india": "India",
    "jp": "Japan",
    "japan": "Japan",
    "kr": "Korea",
    "korea": "Korea",
    "oce": "Oceania",
    "au": "Oceania",
    "me": "Middle East",
    "af": "Africa",
}


def get_region_servers(region_name: str) -> list[str]:
    """
    Get server codes for a region.
    
    Args:
        region_name: Region name or alias.
        
    Returns:
        List of server codes, empty if region not found.
    """
    # Check alias first
    if region_name.lower() in REGION_ALIASES:
        region_name = REGION_ALIASES[region_name.lower()]
    
    # Look up region
    if region_name in REGION_PRESETS:
        return REGION_PRESETS[region_name]["servers"]
    
    # Case-insensitive search
    for name, data in REGION_PRESETS.items():
        if name.lower() == region_name.lower():
            return data["servers"]
    
    return []


def get_all_regions() -> dict:
    """Get all region presets."""
    return REGION_PRESETS.copy()


def get_region_description(region_name: str) -> str:
    """Get description for a region."""
    if region_name.lower() in REGION_ALIASES:
        region_name = REGION_ALIASES[region_name.lower()]
    
    if region_name in REGION_PRESETS:
        return REGION_PRESETS[region_name]["description"]
    
    return ""
