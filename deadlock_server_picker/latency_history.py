"""
Latency history tracking for Deadlock servers.
Records ping results over time for analysis.
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class LatencyRecord:
    """Single latency measurement."""
    timestamp: str
    latency_ms: Optional[int]
    success: bool


@dataclass  
class ServerHistory:
    """Latency history for a server."""
    server_code: str
    records: list[LatencyRecord]
    
    @property
    def avg_latency(self) -> Optional[float]:
        """Get average latency from successful pings."""
        successful = [r.latency_ms for r in self.records if r.success and r.latency_ms is not None]
        if not successful:
            return None
        return sum(successful) / len(successful)
    
    @property
    def min_latency(self) -> Optional[int]:
        """Get minimum latency from successful pings."""
        successful = [r.latency_ms for r in self.records if r.success and r.latency_ms is not None]
        if not successful:
            return None
        return min(successful)
    
    @property
    def max_latency(self) -> Optional[int]:
        """Get maximum latency from successful pings."""
        successful = [r.latency_ms for r in self.records if r.success and r.latency_ms is not None]
        if not successful:
            return None
        return max(successful)
    
    @property
    def success_rate(self) -> float:
        """Get ping success rate (0.0 to 1.0)."""
        if not self.records:
            return 0.0
        return sum(1 for r in self.records if r.success) / len(self.records)


class LatencyHistoryManager:
    """Manages latency history storage and retrieval."""
    
    DEFAULT_CONFIG_DIR = "~/.config/deadlock-server-picker"
    HISTORY_FILENAME = "latency_history.json"
    MAX_RECORDS_PER_SERVER = 100  # Keep last 100 measurements
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize history manager.
        
        Args:
            config_dir: Custom config directory path.
        """
        if config_dir:
            self.config_dir = os.path.expanduser(config_dir)
        else:
            self.config_dir = os.path.expanduser(self.DEFAULT_CONFIG_DIR)
        
        self.history_path = os.path.join(self.config_dir, self.HISTORY_FILENAME)
        self._history: dict[str, ServerHistory] = {}
        self._loaded = False
    
    def _ensure_config_dir(self) -> None:
        """Ensure config directory exists."""
        os.makedirs(self.config_dir, exist_ok=True)
    
    def _load(self) -> None:
        """Load history from file."""
        if self._loaded:
            return
        
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, 'r') as f:
                    data = json.load(f)
                
                for code, hist_data in data.items():
                    records = [
                        LatencyRecord(
                            timestamp=r['timestamp'],
                            latency_ms=r.get('latency_ms'),
                            success=r.get('success', r.get('latency_ms') is not None)
                        )
                        for r in hist_data.get('records', [])
                    ]
                    self._history[code] = ServerHistory(
                        server_code=code,
                        records=records
                    )
            except (json.JSONDecodeError, KeyError, TypeError):
                self._history = {}
        
        self._loaded = True
    
    def _save(self) -> None:
        """Save history to file."""
        self._ensure_config_dir()
        
        data = {}
        for code, hist in self._history.items():
            data[code] = {
                'server_code': code,
                'records': [asdict(r) for r in hist.records]
            }
        
        with open(self.history_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def record_latency(self, server_code: str, latency_ms: Optional[int]) -> None:
        """
        Record a latency measurement.
        
        Args:
            server_code: Server code (e.g., 'iad', 'lax').
            latency_ms: Latency in milliseconds, or None if failed.
        """
        self._load()
        
        if server_code not in self._history:
            self._history[server_code] = ServerHistory(
                server_code=server_code,
                records=[]
            )
        
        record = LatencyRecord(
            timestamp=datetime.now().isoformat(),
            latency_ms=latency_ms,
            success=latency_ms is not None
        )
        
        self._history[server_code].records.append(record)
        
        # Trim old records
        if len(self._history[server_code].records) > self.MAX_RECORDS_PER_SERVER:
            self._history[server_code].records = \
                self._history[server_code].records[-self.MAX_RECORDS_PER_SERVER:]
        
        self._save()
    
    def record_batch(self, results: dict[str, Optional[int]]) -> None:
        """
        Record multiple latency measurements at once.
        
        Args:
            results: Dictionary mapping server codes to latencies.
        """
        self._load()
        
        timestamp = datetime.now().isoformat()
        
        for server_code, latency_ms in results.items():
            if server_code not in self._history:
                self._history[server_code] = ServerHistory(
                    server_code=server_code,
                    records=[]
                )
            
            record = LatencyRecord(
                timestamp=timestamp,
                latency_ms=latency_ms,
                success=latency_ms is not None
            )
            
            self._history[server_code].records.append(record)
            
            # Trim old records
            if len(self._history[server_code].records) > self.MAX_RECORDS_PER_SERVER:
                self._history[server_code].records = \
                    self._history[server_code].records[-self.MAX_RECORDS_PER_SERVER:]
        
        self._save()
    
    def get_history(self, server_code: str) -> Optional[ServerHistory]:
        """
        Get latency history for a server.
        
        Args:
            server_code: Server code.
            
        Returns:
            ServerHistory or None if no history.
        """
        self._load()
        return self._history.get(server_code)
    
    def get_all_histories(self) -> dict[str, ServerHistory]:
        """Get all server histories."""
        self._load()
        return self._history.copy()
    
    def get_summary(self, server_code: str) -> Optional[dict]:
        """
        Get summary statistics for a server.
        
        Args:
            server_code: Server code.
            
        Returns:
            Dictionary with avg, min, max, success_rate, or None.
        """
        history = self.get_history(server_code)
        if not history or not history.records:
            return None
        
        return {
            'server_code': server_code,
            'measurements': len(history.records),
            'avg_latency': round(history.avg_latency, 1) if history.avg_latency else None,
            'min_latency': history.min_latency,
            'max_latency': history.max_latency,
            'success_rate': round(history.success_rate * 100, 1)
        }
    
    def get_best_servers(self, count: int = 5) -> list[tuple[str, float]]:
        """
        Get servers with lowest average latency.
        
        Args:
            count: Number of servers to return.
            
        Returns:
            List of (server_code, avg_latency) tuples.
        """
        self._load()
        
        servers_with_avg = []
        for code, hist in self._history.items():
            avg = hist.avg_latency
            if avg is not None:
                servers_with_avg.append((code, avg))
        
        servers_with_avg.sort(key=lambda x: x[1])
        return servers_with_avg[:count]
    
    def clear_history(self, server_code: Optional[str] = None) -> None:
        """
        Clear latency history.
        
        Args:
            server_code: Specific server to clear, or None for all.
        """
        self._load()
        
        if server_code:
            if server_code in self._history:
                del self._history[server_code]
        else:
            self._history = {}
        
        self._save()
