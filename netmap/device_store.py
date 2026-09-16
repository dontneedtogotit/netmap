"""
device_store.py - Persistent store for per-device customized settings,
preset fields, and user-defined custom attributes.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

DEVICE_SETTINGS_FILE = Path(os.path.expanduser("~/.config/netmap/device_settings.json"))

PRESET_DEVICE_ROLES = [
    "Primary Workstation / PC",
    "Gaming Rig / Console",
    "CCTV Security Camera",
    "Network Video Recorder (NVR)",
    "Smart TV / Streaming Player",
    "Home Server / NAS",
    "Mesh WiFi Extender / AP",
    "Smartphone / Tablet",
    "Smart Home / IoT Device",
    "Network Switch / Router",
    "Virtual Machine / Container",
    "Other / Unspecified"
]

PRESET_LOCATIONS = [
    "Home Office / Desk",
    "Living Room",
    "Bedroom",
    "Loft / Upstairs",
    "Kitchen",
    "Garage / Workshop",
    "Driveway / Porch (Outdoor)",
    "Server Rack / Utility Closet",
    "Hallway",
    "Other"
]

PRESET_PRIORITIES = [
    "High (QoS Low Latency)",
    "Normal",
    "Low (Background / IoT)"
]

PRESET_SEGMENTS = [
    "Main LAN (Wi-Fi 7 / 5GHz)",
    "Wired Ethernet (2.5 Gbps)",
    "IoT Network (Isolated SSID)",
    "Guest Network",
    "Tailscale / WireGuard VPN"
]

def load_device_settings(profile_id: Optional[str] = None) -> Dict[str, Any]:
    """Load stored device settings keyed by identifier (MAC or IP), optionally scoped to a profile."""
    if profile_id:
        from netmap.profile_manager import get_profile_device_settings
        p_settings = get_profile_device_settings(profile_id)
        if p_settings:
            return p_settings
            
    if DEVICE_SETTINGS_FILE.exists():
        try:
            with open(DEVICE_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_device_settings(settings: Dict[str, Any], profile_id: Optional[str] = None):
    """Save device settings dictionary to file, and to profile if profile_id is provided."""
    DEVICE_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEVICE_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        
    if profile_id:
        from netmap.profile_manager import get_profile, save_profile
        p = get_profile(profile_id)
        if p:
            p["device_settings"] = settings
            save_profile(p)

def get_settings_for_device(mac: Optional[str], ip: Optional[str], profile_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve settings for a device by MAC address or IP address."""
    all_settings = load_device_settings(profile_id=profile_id)
    mac_upper = (mac or "").upper()
    if mac_upper and mac_upper in all_settings:
        return all_settings[mac_upper]
    if ip and ip in all_settings:
        return all_settings[ip]
    return {}

def update_settings_for_device(identifier: str, data: Dict[str, Any], profile_id: Optional[str] = None) -> Dict[str, Any]:
    """Update or set settings for a specific device identifier (MAC or IP)."""
    ident = identifier.strip().upper() if ":" in identifier else identifier.strip()
    all_settings = load_device_settings(profile_id=profile_id)
    
    current = all_settings.get(ident, {})
    
    # Update preset fields
    for field in ["alias", "role", "location", "priority", "network_segment", "ip_reservation", "notes"]:
        if field in data:
            current[field] = data[field]
            
    # Update custom arbitrary key-value fields
    if "custom_fields" in data and isinstance(data["custom_fields"], dict):
        current["custom_fields"] = data["custom_fields"]
    elif "custom_fields" not in current:
        current["custom_fields"] = {}
        
    all_settings[ident] = current
    save_device_settings(all_settings, profile_id=profile_id)
    
    if profile_id:
        from netmap.profile_manager import update_profile_device_settings
        update_profile_device_settings(profile_id, identifier, data)
        
    return current

