"""
constants.py - Centralized timeout, retry, and network probe constants for NetMap.

Provides a single source of truth for I/O timeouts, retry policies, scan defaults,
and diagnostic parameters. Other modules should import from here instead of using
scattered magic numbers.
"""

from __future__ import annotations

from typing import Dict, Any

# ----------------------------------------------------------------------
# Timeouts (seconds)
# ----------------------------------------------------------------------
HTTP_REQUEST_TIMEOUT: float = 4.0
HTTP_LONG_REQUEST_TIMEOUT: float = 8.0
LLM_REQUEST_TIMEOUT: float = 22.0
PING_TIMEOUT_SECONDS: int = 2
PING_COUNT_DEFAULT: int = 2
WIFI_SCAN_TIMEOUT: int = 4
TRACEROUTE_TIMEOUT: int = 8
ARP_NEIGH_TIMEOUT: int = 2
ROUTER_LOGIN_TIMEOUT: float = 4.0
RTSP_PROBE_TIMEOUT: float = 2.0
BUFFERBLOAT_IDLE_PING_COUNT: int = 2
BUFFERBLOAT_LOAD_WARMUP_SECONDS: float = 0.3

# ----------------------------------------------------------------------
# Scan / Discovery
# ----------------------------------------------------------------------
SUBNET_SCAN_WORKERS: int = 50
PORT_PROBE_TIMEOUT: float = 0.12
PORT_PROBE_TIMEOUT_AGENT: float = 0.2
PORT_SCAN_DEFAULT_PORTS: list[int] = [
    80, 443, 53, 22, 554, 8554, 8000, 37777, 8899, 7443, 8080, 8009, 9000, 5353,
]
PORT_SCAN_AGENT_PORTS: list[int] = [
    21, 22, 53, 80, 443, 554, 8000, 8080, 8009, 8554, 8899, 9000, 37777,
]
AVAHI_BROWSE_TIMEOUT: int = 4

# ----------------------------------------------------------------------
# Retry / Backoff
# ----------------------------------------------------------------------
LLM_FALLBACK_MODELS_MAX_RETRIES: int = 3
LLM_FALLBACK_RETRY_DELAY_SECONDS: float = 1.0

# ----------------------------------------------------------------------
# Telemetry cache / freshness
# ----------------------------------------------------------------------
TELEMETRY_STALE_AFTER_SECONDS: int = 120

# ----------------------------------------------------------------------
# Hardcoded fallback / estimated data markers
# ----------------------------------------------------------------------
FALLBACK_WAN_INFO: Dict[str, Any] = {
    "ip": "117.20.69.236",
    "hostname": "117-20-69-236.751445.bne.nbn.aussiebb.net",
    "org": "AS4764 Aussie Fibre Pty Ltd (Aussie Broadband)",
    "city": "Brisbane",
    "region": "Queensland",
    "country": "AU",
    "isp": "Aussie Broadband",
    "technology": "NBN (National Broadband Network)",
    "cgnat_active": True,
    "estimated": True,
    "fallback_source": "defaults",
}

FALLBACK_WIFI_SURVEY_NETWORKS_2G: list[Dict[str, Any]] = [
    {
        "ssid": "BananaFarm",
        "bssid": "B8:FB:B3:01:02:03",
        "channel": 6,
        "frequency": "2437 MHz",
        "signal": 92,
        "security": "WPA2",
        "in_use": True,
        "estimated": True,
    },
    {
        "ssid": "Telstra_Guest_5B",
        "bssid": "A0:B1:C2:01:02:03",
        "channel": 6,
        "frequency": "2437 MHz",
        "signal": 45,
        "security": "WPA2",
        "in_use": False,
        "estimated": True,
    },
]

FALLBACK_WIFI_SURVEY_NETWORKS_5G: list[Dict[str, Any]] = [
    {
        "ssid": "BananaFarm",
        "bssid": "B8:FB:B3:01:02:04",
        "channel": 36,
        "frequency": "5180 MHz",
        "signal": 98,
        "security": "WPA3-SAE",
        "in_use": True,
        "estimated": True,
    },
    {
        "ssid": "Optus_Net_9A",
        "bssid": "CC:DD:EE:01:02:03",
        "channel": 44,
        "frequency": "5220 MHz",
        "signal": 52,
        "security": "WPA2",
        "in_use": False,
        "estimated": True,
    },
]

FALLBACK_WIFI_SURVEY_NETWORKS_6G: list[Dict[str, Any]] = [
    {
        "ssid": "BananaFarm_Wi-Fi7",
        "bssid": "B8:FB:B3:01:02:05",
        "channel": 37,
        "frequency": "6135 MHz",
        "signal": 94,
        "security": "WPA3",
        "in_use": False,
        "estimated": True,
    }
]

# ----------------------------------------------------------------------
# Router defaults
# ----------------------------------------------------------------------
DEFAULT_ROUTER_GATEWAY: str = "192.168.0.1"
DEFAULT_ROUTER_ADMIN_URL_HTTP: str = "http://192.168.0.1"
DEFAULT_ROUTER_ADMIN_URL_HTTPS: str = "https://192.168.0.1"
DEFAULT_ROUTER_USERNAME: str = "admin"
