"""
Wine/Proton process detection for Deadlock.
Helps verify that Deadlock is running under Wine/Proton for firewall compatibility.
"""

import os
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class DeadlockProcess:
    """Information about a detected Deadlock process."""
    pid: int
    name: str
    wine_prefix: Optional[str]
    is_proton: bool
    steam_runtime: bool
    
    @property
    def description(self) -> str:
        """Get human-readable description."""
        parts = [f"PID {self.pid}"]
        if self.is_proton:
            parts.append("Proton")
        elif self.wine_prefix:
            parts.append("Wine")
        if self.steam_runtime:
            parts.append("Steam Runtime")
        return " | ".join(parts)


def detect_deadlock_processes() -> list[DeadlockProcess]:
    """
    Detect running Deadlock processes.
    
    Returns:
        List of detected Deadlock processes.
    """
    processes = []
    
    # Common process names for Deadlock
    deadlock_names = [
        "project8.exe",  # Deadlock's internal name
        "deadlock.exe",
        "citadel.exe",
    ]
    
    try:
        # Use pgrep to find Wine processes
        result = subprocess.run(
            ["pgrep", "-a", "-f", "wine|proton"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        for line in result.stdout.splitlines():
            line_lower = line.lower()
            
            # Check if this is a Deadlock process
            is_deadlock = any(name in line_lower for name in deadlock_names)
            if not is_deadlock:
                continue
            
            parts = line.split(maxsplit=1)
            if len(parts) < 2:
                continue
            
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            
            cmdline = parts[1]
            
            # Detect Proton
            is_proton = "proton" in line_lower or "steamapps/common/proton" in line_lower
            
            # Detect Steam Runtime
            steam_runtime = "steam-runtime" in line_lower or "pressure-vessel" in line_lower
            
            # Try to find Wine prefix
            wine_prefix = None
            if "WINEPREFIX=" in cmdline:
                # Extract WINEPREFIX from command line
                for part in cmdline.split():
                    if part.startswith("WINEPREFIX="):
                        wine_prefix = part.split("=", 1)[1]
                        break
            elif is_proton:
                # Proton prefixes are usually in compatdata
                wine_prefix = _find_proton_prefix(pid)
            
            processes.append(DeadlockProcess(
                pid=pid,
                name="Deadlock",
                wine_prefix=wine_prefix,
                is_proton=is_proton,
                steam_runtime=steam_runtime
            ))
    
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        # pgrep not available
        pass
    except Exception:
        pass
    
    return processes


def _find_proton_prefix(pid: int) -> Optional[str]:
    """Try to find Proton prefix from process environment."""
    try:
        env_path = f"/proc/{pid}/environ"
        if os.path.exists(env_path):
            with open(env_path, 'rb') as f:
                environ = f.read().decode('utf-8', errors='ignore')
            
            for var in environ.split('\x00'):
                if var.startswith("STEAM_COMPAT_DATA_PATH="):
                    return var.split("=", 1)[1]
                if var.startswith("WINEPREFIX="):
                    return var.split("=", 1)[1]
    except (PermissionError, FileNotFoundError):
        pass
    
    return None


def detect_wine_installed() -> dict[str, bool]:
    """
    Check what Wine-related components are installed.
    
    Returns:
        Dictionary of component -> installed status.
    """
    import shutil
    
    return {
        "wine": shutil.which("wine") is not None,
        "wine64": shutil.which("wine64") is not None,
        "proton": _detect_proton_installed(),
        "steam": shutil.which("steam") is not None,
    }


def _detect_proton_installed() -> bool:
    """Check if Proton is installed via Steam."""
    steam_paths = [
        os.path.expanduser("~/.steam/root/steamapps/common"),
        os.path.expanduser("~/.local/share/Steam/steamapps/common"),
    ]
    
    for steam_path in steam_paths:
        if os.path.exists(steam_path):
            # Check for any Proton installation
            try:
                for entry in os.listdir(steam_path):
                    if entry.lower().startswith("proton"):
                        return True
            except PermissionError:
                pass
    
    return False


def check_deadlock_status() -> dict:
    """
    Get comprehensive Deadlock/Wine status.
    
    Returns:
        Dictionary with status information.
    """
    processes = detect_deadlock_processes()
    components = detect_wine_installed()
    
    return {
        "deadlock_running": len(processes) > 0,
        "processes": processes,
        "wine_installed": components.get("wine", False),
        "proton_installed": components.get("proton", False),
        "steam_installed": components.get("steam", False),
        "components": components,
    }
