"""
telemetry_cache.py - Telemetry caching layer for NetMap.

Provides cached wrappers around expensive network discovery operations
with additive freshness metadata so existing payload shapes stay stable.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from netmap.tracer import get_public_wan_info, get_network_metrics, trace_route
from netmap.tracer import get_wifi_spectrum_survey
from netmap.constants import TELEMETRY_STALE_AFTER_SECONDS


class TelemetryCache:
    """Cache telemetry responses with additive freshness metadata."""

    def __init__(self, stale_after: int = TELEMETRY_STALE_AFTER_SECONDS) -> None:
        self.stale_after = stale_after
        self._wan: Dict[str, Any] = {}
        self._wan_ts: float = 0.0
        self._metrics: Dict[str, Any] = {}
        self._metrics_ts: float = 0.0
        self._traceroute: Dict[str, Any] = {}
        self._traceroute_ts: float = 0.0
        self._spectrum: Dict[str, Any] = {}
        self._spectrum_ts: float = 0.0

    def get_wan_info(self, force_refresh: bool = False) -> Dict[str, Any]:
        if force_refresh or self._is_stale(self._wan_ts) or not self._wan:
            self._wan = get_public_wan_info() or {}
            self._wan_ts = time.time()
        result = dict(self._wan)
        result["_freshness"] = self._freshness(self._wan_ts)
        return result

    def get_network_metrics(self, force_refresh: bool = False) -> Dict[str, Any]:
        if force_refresh or self._is_stale(self._metrics_ts) or not self._metrics:
            self._metrics = get_network_metrics() or {}
            self._metrics_ts = time.time()
        result = dict(self._metrics)
        result["_freshness"] = self._freshness(self._metrics_ts)
        return result

    def get_traceroute(self, target: str = "1.1.1.1", max_hops: int = 8, force_refresh: bool = False) -> Dict[str, Any]:
        if force_refresh or self._is_stale(self._traceroute_ts) or not self._traceroute:
            self._traceroute = {"hops": trace_route(target=target, max_hops=max_hops) or []}
            self._traceroute_ts = time.time()
        result = dict(self._traceroute)
        result["_freshness"] = self._freshness(self._traceroute_ts)
        return result

    def get_wifi_spectrum(self, force_refresh: bool = False) -> Dict[str, Any]:
        if force_refresh or self._is_stale(self._spectrum_ts) or not self._spectrum:
            self._spectrum = get_wifi_spectrum_survey() or {}
            self._spectrum_ts = time.time()
        result = dict(self._spectrum)
        result["_freshness"] = self._freshness(self._spectrum_ts)
        return result

    def _is_stale(self, timestamp: float) -> bool:
        return (time.time() - timestamp) > self.stale_after

    def _freshness(self, timestamp: float) -> Dict[str, Any]:
        age = round(time.time() - timestamp, 2) if timestamp else None
        return {
            "status": "stale" if self._is_stale(timestamp) else "fresh",
            "age_seconds": age,
            "stale_after_seconds": self.stale_after,
        }


TELEMETRY = TelemetryCache()
