"""
profile_manager.py - Network Profile Manager for NetMap.
Manages network profiles based on connected Access Point (BSSID/SSID) or wired gateway,
persisting per-profile network topologies, device inventory, and custom device settings.
"""

import os
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

PROFILES_DIR = Path(os.path.expanduser("~/.config/netmap/profiles"))
LEGACY_DEVICE_SETTINGS_FILE = Path(os.path.expanduser("~/.config/netmap/device_settings.json"))

def _ensure_profiles_dir():
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

def sanitize_id(val: str) -> str:
    """Sanitize a string for safe filesystem and profile ID usage."""
    s = re.sub(r'[^a-zA-Z0-9_-]', '_', val.strip())
    return s.lower()

def get_profile_id_for_host(host_info: Dict[str, Any]) -> str:
    """
    Generate a deterministic profile ID from host Wi-Fi or gateway info.
    If Wi-Fi is connected, identifies by BSSID (access point MAC) and SSID.
    If wired Ethernet, identifies by Gateway MAC or Gateway IP.
    """
    wifi = host_info.get("wifi", {})
    bssid = (wifi.get("bssid") or "").strip().upper()
    ssid = (wifi.get("ssid") or "").strip()

    if bssid:
        bssid_clean = bssid.replace(":", "").lower()
        ssid_clean = sanitize_id(ssid) if ssid else "ap"
        return f"wifi_{ssid_clean}_{bssid_clean}"
    elif ssid:
        return f"wifi_{sanitize_id(ssid)}"
    
    gateway_mac = (host_info.get("gateway_mac") or "").strip().upper()
    if gateway_mac:
        return f"eth_{gateway_mac.replace(':', '').lower()}"
    
    gateway_ip = (host_info.get("gateway") or "").strip()
    if gateway_ip:
        return f"eth_{gateway_ip.replace('.', '_')}"

    return "network_default"

def get_default_profile_name(host_info: Dict[str, Any]) -> str:
    """Generate a clean human-readable name for the profile."""
    wifi = host_info.get("wifi", {})
    ssid = (wifi.get("ssid") or "").strip()
    bssid = (wifi.get("bssid") or "").strip().upper()

    if ssid:
        return ssid
    elif bssid:
        return f"Wi-Fi AP ({bssid})"
    
    gateway_ip = host_info.get("gateway")
    if gateway_ip:
        return f"Wired Network ({gateway_ip})"
    
    return "Local Network"

def get_profile_file_path(profile_id: str) -> Path:
    _ensure_profiles_dir()
    clean_id = sanitize_id(profile_id)
    return PROFILES_DIR / f"{clean_id}.json"

def get_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    """Load profile by profile_id."""
    path = get_profile_file_path(profile_id)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_profile(profile_data: Dict[str, Any]):
    """Save profile dictionary to file."""
    profile_id = profile_data.get("id")
    if not profile_id:
        return
    path = get_profile_file_path(profile_id)
    _ensure_profiles_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, indent=2)

def list_profiles(active_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all stored profiles with metadata summary.
    Sorted by last_seen_at descending.
    """
    _ensure_profiles_dir()
    profiles = []
    
    for f in PROFILES_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as pf:
                data = json.load(pf)
                pid = data.get("id") or f.stem
                topo = data.get("topology") or {}
                dev_count = len(topo.get("devices", []))
                
                profiles.append({
                    "id": pid,
                    "name": data.get("name") or pid,
                    "network_type": data.get("network_type", "wifi"),
                    "ssid": data.get("ssid", ""),
                    "bssid": data.get("bssid", ""),
                    "gateway": data.get("gateway", ""),
                    "subnet": data.get("subnet", ""),
                    "created_at": data.get("created_at", ""),
                    "last_seen_at": data.get("last_seen_at", ""),
                    "device_count": dev_count,
                    "is_active": (pid == active_id) if active_id else False
                })
        except Exception:
            continue

    profiles.sort(key=lambda x: x.get("last_seen_at", ""), reverse=True)
    return profiles

def _migrate_legacy_device_settings() -> Dict[str, Any]:
    """Read legacy global device_settings.json if it exists."""
    if LEGACY_DEVICE_SETTINGS_FILE.exists():
        try:
            with open(LEGACY_DEVICE_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def get_or_create_profile_for_host(host_info: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Find existing profile for the current host's connected AP or create a new profile.
    Returns (profile_data, is_new).
    """
    _ensure_profiles_dir()
    profile_id = get_profile_id_for_host(host_info)
    now_iso = datetime.now(timezone.utc).isoformat()
    
    existing = get_profile(profile_id)
    if existing:
        existing["last_seen_at"] = now_iso
        wifi = host_info.get("wifi", {})
        if wifi.get("ssid") and not existing.get("ssid"):
            existing["ssid"] = wifi.get("ssid")
        if wifi.get("bssid") and not existing.get("bssid"):
            existing["bssid"] = wifi.get("bssid")
        if host_info.get("gateway"):
            existing["gateway"] = host_info.get("gateway")
        save_profile(existing)
        return existing, False

    # Create new profile
    wifi = host_info.get("wifi", {})
    ssid = wifi.get("ssid", "")
    bssid = wifi.get("bssid", "")
    network_type = "wifi" if (ssid or bssid) else "ethernet"
    name = get_default_profile_name(host_info)
    gateway = host_info.get("gateway", "")
    ip = host_info.get("ip", "")
    subnet = ".".join(ip.split(".")[:3]) + ".0/24" if ip else ""

    # Check if there are legacy device settings to initialize
    initial_device_settings = _migrate_legacy_device_settings()

    new_profile = {
        "id": profile_id,
        "name": name,
        "network_type": network_type,
        "ssid": ssid,
        "bssid": bssid,
        "gateway": gateway,
        "subnet": subnet,
        "created_at": now_iso,
        "last_seen_at": now_iso,
        "device_settings": initial_device_settings,
        "topology": None,
        "notes": ""
    }

    save_profile(new_profile)
    return new_profile, True

def delete_profile(profile_id: str) -> bool:
    """Delete a profile by ID."""
    path = get_profile_file_path(profile_id)
    if path.exists():
        try:
            path.unlink()
            return True
        except Exception:
            return False
    return False

def rename_profile(profile_id: str, new_name: str) -> bool:
    """Rename a profile display name."""
    p = get_profile(profile_id)
    if not p:
        return False
    p["name"] = new_name.strip()
    save_profile(p)
    return True

def get_profile_device_settings(profile_id: str) -> Dict[str, Any]:
    """Retrieve device settings for a profile."""
    p = get_profile(profile_id)
    if p and "device_settings" in p:
        return p["device_settings"]
    return {}

def update_profile_device_settings(profile_id: str, identifier: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update settings for a device in a specific profile."""
    p = get_profile(profile_id)
    if not p:
        return {}
    
    if "device_settings" not in p:
        p["device_settings"] = {}

    ident = identifier.strip().upper() if ":" in identifier else identifier.strip()
    current = p["device_settings"].get(ident, {})

    for field in ["alias", "role", "location", "priority", "network_segment", "ip_reservation", "notes"]:
        if field in data:
            current[field] = data[field]

    if "custom_fields" in data and isinstance(data["custom_fields"], dict):
        current["custom_fields"] = data["custom_fields"]
    elif "custom_fields" not in current:
        current["custom_fields"] = {}

    p["device_settings"][ident] = current
    save_profile(p)
    return current
