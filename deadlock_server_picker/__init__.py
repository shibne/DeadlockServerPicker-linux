"""
Deadlock Server Picker for Linux
A native Linux tool to block/unblock Deadlock game server relays using iptables.
"""

__version__ = "1.3.3"
__author__ = "Deadlock Server Picker"
from .regions import REGION_PRESETS, REGION_ALIASES, get_region_servers, get_all_regions
from .tui import ServerPickerTUI, run_tui

__all__ = [
    "REGION_PRESETS",
    "REGION_ALIASES",
    "get_region_servers",
    "get_all_regions",
    "ServerPickerTUI",
    "run_tui",
]