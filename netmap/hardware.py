"""
hardware.py - Hardware fingerprinting, device profiling, camera/NVR detection,
and router settings definitions for NetMap.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List

KNOWN_ROUTER_MODELS = {
    "BE550v2": {
        "name": "TP-Link Archer BE550 v2",
        "category": "router",
        "description": "Wi-Fi 7 Tri-Band Router (BE9300)",
        "icon": "router",
        "vendor": "TP-Link",
        "bands": ["2.4 GHz (574 Mbps)", "5 GHz (2880 Mbps)", "6 GHz (5760 Mbps)"],
        "ports": "1x 2.5 Gbps WAN, 4x 2.5 Gbps LAN, 1x USB 3.0",
        "features": [
            "Wi-Fi 7 (802.11be)",
            "Multi-Link Operation (MLO)",
            "320 MHz Channel Width (6 GHz)",
            "EasyMesh Compatible",
            "TP-Link HomeShield & QoS",
            "VPN Server & Client (WireGuard / OpenVPN)",
            "Dedicated IoT Network with Device Isolation"
        ],
        "default_admin_url": "https://192.168.0.1",
        "default_login_user": "admin",
        "management_paths": {
            "virtual_servers": "Advanced > NAT Forwarding > Virtual Servers",
            "dhcp_reservation": "Advanced > Network > DHCP Server > Address Reservation",
            "qos": "HomeShield > QoS",
            "easymesh": "Advanced > EasyMesh",
            "iot_network": "Wireless > IoT Network",
            "wireguard_vpn": "Advanced > VPN Server > WireGuard",
            "firmware_update": "Advanced > System > Firmware Update"
        },
        "management_tips": "Access admin portal at https://192.168.0.1 to configure NAT Virtual Servers, Address Reservation, QoS, or IoT Network."
    }
}

KNOWN_EXTENDER_MODELS = {
    "EX6250v2": {
        "name": "NETGEAR AC1750 Mesh WiFi Extender (EX6250v2)",
        "category": "extender",
        "description": "Dual-Band 802.11ac Mesh Extender",
        "icon": "wifi-repeater",
        "vendor": "NETGEAR",
        "bands": ["2.4 GHz (450 Mbps)", "5 GHz (1300 Mbps)"],
        "ports": "1x Gigabit Ethernet port",
        "features": [
            "Mesh Smart Roaming (One WiFi Name)",
            "FastLane Technology (dedicated backhaul)",
            "Access Point (AP) Mode Support"
        ],
        "default_admin_url": "http://192.168.0.76",
        "management_tips": "Access at http://192.168.0.76 or mywifiext.local. Switch to Access Point (AP) mode via Ethernet for zero latency penalty."
    }
}

# Known MAC OUI prefixes for Vendors, Cameras, NVRs, Smart TVs, and PCs
KNOWN_OUI_PREFIXES = {
    "B8:FB:B3": {"vendor": "TP-Link Systems Inc.", "category": "router", "default_model": "Archer BE550 v2"},
    "34:98:B5": {"vendor": "NETGEAR Inc.", "category": "extender", "default_model": "Mesh Extender EX6250v2"},
    
    # Cameras & NVRs
    "28:57:BE": {"vendor": "Hikvision Digital Technology", "category": "camera", "default_model": "Hikvision IP Camera / NVR"},
    "44:19:B6": {"vendor": "Hikvision Digital Technology", "category": "camera", "default_model": "Hikvision IP Camera"},
    "BC:AD:28": {"vendor": "Hikvision Digital Technology", "category": "camera", "default_model": "Hikvision IP Camera"},
    "48:EA:63": {"vendor": "Uniview / Hikvision", "category": "camera", "default_model": "IP Security Camera"},
    "3C:EF:8C": {"vendor": "Dahua Technology", "category": "camera", "default_model": "Dahua IP Camera / NVR"},
    "4C:11:BF": {"vendor": "Dahua Technology", "category": "camera", "default_model": "Dahua Security Camera"},
    "E0:50:8B": {"vendor": "Dahua Technology", "category": "camera", "default_model": "Dahua / Amcrest Camera"},
    "EC:71:DB": {"vendor": "Reolink Innovation", "category": "camera", "default_model": "Reolink IP Camera / NVR"},
    "F0:45:DA": {"vendor": "Reolink Innovation", "category": "camera", "default_model": "Reolink Camera"},
    "00:40:8C": {"vendor": "Axis Communications", "category": "camera", "default_model": "Axis Network Camera"},
    "AC:CC:8E": {"vendor": "Axis Communications", "category": "camera", "default_model": "Axis Network Camera"},
    "00:09:18": {"vendor": "Hanwha Techwin (Samsung)", "category": "camera", "default_model": "Hanwha WiseNet Camera"},
    "50:C7:BF": {"vendor": "TP-Link Tapo", "category": "camera", "default_model": "Tapo Security Camera"},
    "68:FF:7B": {"vendor": "TP-Link Tapo", "category": "camera", "default_model": "Tapo Smart Cam"},
    "2C:AA:8E": {"vendor": "Wyze Labs", "category": "camera", "default_model": "Wyze Cam"},
    "78:8A:20": {"vendor": "Ubiquiti Inc.", "category": "nvr", "default_model": "UniFi CloudKey / Protect NVR"},
    "24:A4:3C": {"vendor": "Ubiquiti Inc.", "category": "camera", "default_model": "UniFi Protect Camera"},
    "50:8A:06": {"vendor": "Anker / Eufy", "category": "camera", "default_model": "Eufy Security Device"},

    # TVs and PCs
    "DC:E5:5B": {"vendor": "Shenzhen SEI Robotics / Google", "category": "smart_tv", "default_model": "Android TV / Chromecast"},
    "30:FD:38": {"vendor": "Google LLC / Liteon", "category": "smart_tv", "default_model": "Chromecast"},
    "50:76:AF": {"vendor": "Intel Corporate", "category": "pc", "default_model": "PC / Server"},
    "FC:F1:36": {"vendor": "Samsung Electronics", "category": "mobile", "default_model": "Samsung Galaxy / Smart Device"},
    "B8:27:EB": {"vendor": "Raspberry Pi Foundation", "category": "iot", "default_model": "Raspberry Pi"},
    "DC:A6:32": {"vendor": "Raspberry Pi Foundation", "category": "iot", "default_model": "Raspberry Pi 4"},
    "E4:5F:01": {"vendor": "Raspberry Pi Foundation", "category": "iot", "default_model": "Raspberry Pi 4/5"},
    "00:11:32": {"vendor": "Synology Inc.", "category": "nas", "default_model": "DiskStation NAS"},
    "00:15:5D": {"vendor": "Microsoft Hyper-V", "category": "vm", "default_model": "Virtual Machine"},
    "52:54:00": {"vendor": "QEMU / KVM", "category": "vm", "default_model": "KVM Virtual Machine"},
    "08:00:27": {"vendor": "PCS Systemtechnik (VirtualBox)", "category": "vm", "default_model": "VirtualBox VM"},
}

CAMERA_NVR_PORTS = {
    554: "RTSP (Live Video Stream)",
    8554: "RTSP Alternative (Live Video Stream)",
    8000: "Hikvision / DVR / Media Service",
    37777: "Dahua / Amcrest NVR Private Port",
    37778: "Dahua / Amcrest RTSP Stream",
    8899: "ONVIF Device Management",
    7443: "UniFi Protect HTTPS",
    7444: "UniFi Protect Video Stream",
    9000: "Reolink Media / Device Discovery",
    81: "Blue Iris NVR Web Interface",
    8081: "MotionEye / Camera Web Stream",
    8082: "MJPEG Video Stream"
}

def load_tvpc_cameras(conf_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """Parse configured CCTV cameras from ~/.config/tvpc/cameras.conf if available."""
    cameras = []
    conf_path = conf_file or os.path.expanduser("~/.config/tvpc/cameras.conf")
    if os.path.exists(conf_path):
        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("|")
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        url = parts[1].strip()
                        cameras.append({
                            "name": name,
                            "url": url,
                            "group": parts[5] if len(parts) > 5 else "Default",
                            "enabled": parts[8] if len(parts) > 8 else "1"
                        })
        except Exception:
            pass
    return cameras

def add_tvpc_camera(name: str, url: str, group: str = "Default", enabled: str = "1", conf_file: Optional[str] = None) -> Dict[str, Any]:
    """Add or update a camera entry in ~/.config/tvpc/cameras.conf."""
    if conf_file:
        conf_path = Path(conf_file)
        conf_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        conf_dir = Path(os.path.expanduser("~/.config/tvpc"))
        conf_dir.mkdir(parents=True, exist_ok=True)
        conf_path = conf_dir / "cameras.conf"

    existing_lines = []
    if conf_path.exists():
        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                existing_lines = f.readlines()
        except Exception:
            existing_lines = []

    clean_name = name.strip()
    clean_url = url.strip()
    clean_group = group.strip() or "Default"
    clean_enabled = "1" if enabled in [True, "1", 1] else "0"

    # Line format: name|url||||group|||enabled
    formatted_entry = f"{clean_name}|{clean_url}||||{clean_group}|||{clean_enabled}\n"

    updated = False
    new_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        parts = stripped.split("|")
        if len(parts) >= 2:
            entry_name = parts[0].strip()
            entry_url = parts[1].strip()
            if entry_name.lower() == clean_name.lower() or entry_url == clean_url:
                new_lines.append(formatted_entry)
                updated = True
                continue
        new_lines.append(line)

    if not updated:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(formatted_entry)

    with open(conf_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return {
        "success": True,
        "action": "updated" if updated else "added",
        "name": clean_name,
        "url": clean_url,
        "group": clean_group,
        "enabled": clean_enabled,
        "conf_file": str(conf_path)
    }

def test_rtsp_stream(host_or_ip: str, port: int = 554, timeout: float = 2.0) -> Dict[str, Any]:
    """
    Test connectivity to an RTSP camera stream via TCP handshake and RTSP OPTIONS request.
    """
    import socket
    import time

    start_time = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host_or_ip, port))
        connect_latency_ms = round((time.time() - start_time) * 1000, 2)

        # Send standard RTSP OPTIONS probe
        probe = f"OPTIONS rtsp://{host_or_ip}:{port}/ RTSP/1.0\r\nCSeq: 1\r\nUser-Agent: NetMap-Omarchy/1.0\r\n\r\n"
        s.sendall(probe.encode("utf-8"))

        response = s.recv(1024).decode("utf-8", errors="ignore")

        first_line = response.split("\r\n")[0] if response else ""
        is_rtsp = "RTSP/1.0" in first_line
        status_code = 0
        if is_rtsp:
            parts = first_line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                status_code = int(parts[1])

        return {
            "success": True,
            "host": host_or_ip,
            "port": port,
            "latency_ms": connect_latency_ms,
            "is_rtsp": is_rtsp,
            "status_code": status_code,
            "status_line": first_line,
            "message": f"Connected ({connect_latency_ms}ms) - {first_line or 'Port open'}"
        }
    except socket.timeout:
        return {
            "success": False,
            "host": host_or_ip,
            "port": port,
            "latency_ms": None,
            "error": "Connection timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "host": host_or_ip,
            "port": port,
            "latency_ms": None,
            "error": str(e)
        }
    finally:
        try:
            s.close()
        except Exception:
            pass


def identify_device(
    mac: str,
    ip: str,
    hostname: Optional[str] = None,
    mdns_info: Optional[Dict[str, Any]] = None,
    http_banner: Optional[str] = None,
    open_ports: Optional[list] = None
) -> Dict[str, Any]:
    """
    Profile and identify a device using multiple heuristics:
    MAC OUI, mDNS/Avahi tags, Camera/NVR ports, HTTP banners, and IP roles.
    """
    mac_upper = (mac or "").upper()
    prefix = ":".join(mac_upper.split(":")[:3]) if mac_upper else ""
    
    oui_info = KNOWN_OUI_PREFIXES.get(prefix, {})
    vendor = oui_info.get("vendor", "Unknown Vendor")
    category = oui_info.get("category", "unknown")
    name = hostname or oui_info.get("default_model", f"Device ({ip})")
    model = oui_info.get("default_model", "")
    description = ""
    specs = {}

    mdns_info = mdns_info or {}
    open_ports = open_ports or []

    # Check for Camera / NVR based on open ports
    cam_ports_found = [p for p in open_ports if p in CAMERA_NVR_PORTS]
    if cam_ports_found:
        if 37777 in cam_ports_found or 8000 in cam_ports_found or 7443 in cam_ports_found or 81 in cam_ports_found:
            category = "nvr"
            name = f"NVR / Video Recorder ({ip})"
            description = f"Network Video Recorder (Active Ports: {', '.join(str(p) for p in cam_ports_found)})"
        elif 554 in cam_ports_found or 8554 in cam_ports_found or 8899 in cam_ports_found:
            category = "camera"
            name = f"IP Camera ({ip})"
            description = f"CCTV / RTSP Security Camera (Ports: {', '.join(str(p) for p in cam_ports_found)})"

    # Check for configured tvpc cameras matching this IP
    tvpc_cams = load_tvpc_cameras()
    for tc in tvpc_cams:
        if ip in tc.get("url", ""):
            category = "camera"
            name = f"CCTV: {tc.get('name')} ({ip})"
            description = f"Security Camera configured in tvpc (RTSP: {tc.get('url')})"

    # Check for Chromecast / Google TV mDNS
    if "fn" in mdns_info:
        name = mdns_info["fn"]
        category = "smart_tv"
        model = mdns_info.get("md", "Chromecast / Google TV")
        description = f"Google Cast Device: {name}"

    # Check for Netgear Extender mDNS or model
    if mdns_info.get("modelname") in KNOWN_EXTENDER_MODELS or "EX6250" in mdns_info.get("modelname", ""):
        m_key = "EX6250v2"
        ext_info = KNOWN_EXTENDER_MODELS.get(m_key, {})
        name = ext_info.get("name", "NETGEAR Extender EX6250v2")
        model = "EX6250v2"
        category = "extender"
        description = ext_info.get("description", "Mesh WiFi Extender")
        specs = ext_info

    # Check for Router at gateway IP (e.g. 192.168.0.1) or HTTP banner
    if ip == "192.168.0.1" or (http_banner and "BE550" in http_banner):
        category = "router"
        router_spec = KNOWN_ROUTER_MODELS.get("BE550v2")
        if router_spec:
            name = router_spec["name"]
            model = "BE550v2"
            description = router_spec["description"]
            specs = router_spec

    # Heuristics based on open ports if still unknown
    if category == "unknown":
        if 22 in open_ports and 80 not in open_ports:
            category = "pc"
            name = f"Linux/Unix Host ({ip})"
        elif 8009 in open_ports:
            category = "smart_tv"
            name = f"Cast Device ({ip})"
        elif 80 in open_ports or 443 in open_ports:
            category = "network_device"
            name = f"Web Device ({ip})"

    return {
        "ip": ip,
        "mac": mac_upper,
        "vendor": vendor,
        "category": category,
        "name": name,
        "model": model,
        "description": description,
        "specs": specs,
        "open_ports": open_ports,
        "camera_ports": cam_ports_found,
        "mdns": mdns_info
    }
