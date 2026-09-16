"""
suggestions.py - Network settings suggestion & recommendation engine for NetMap.
Analyzes live topology, router hardware (TP-Link Archer BE550 v2),
Aussie Broadband WAN/CGNAT, connected cameras/NVRs, and user-configured device roles.
"""

from typing import Dict, Any, List

def generate_network_suggestions(topology: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Evaluate the current network configuration and return prioritized recommendations.
    """
    suggestions = []
    
    wan = topology.get("wan", {})
    host = topology.get("host", {})
    wifi = host.get("wifi", {})
    devices = topology.get("devices", [])
    router_settings = topology.get("router_settings", {})
    has_cameras = topology.get("has_cameras", False) or any(d.get("category") in ["camera", "nvr"] for d in devices)
    has_extender = any(d.get("category") == "extender" or "EX6250" in d.get("model", "") for d in devices)
    
    # 1. CGNAT Inbound Traffic Warning & Fix
    if wan.get("cgnat_active", True):
        suggestions.append({
            "id": "sug-cgnat",
            "category": "Remote Access & Hosting",
            "priority": "critical",
            "badge": "High Impact",
            "title": "Aussie Broadband CGNAT Blocks Inbound Port Forwarding",
            "description": "Your public connection is behind Carrier-Grade NAT (CGNAT hop at 100.91.128.1). Incoming connections from the internet cannot reach your Archer BE550 router directly, preventing game server hosting, external CCTV viewing, and WireGuard VPN from working.",
            "current_state": "CGNAT Active (100.91.128.1 / RFC 6598)",
            "recommended_state": "Opt-out in MyAussie App (Free Public Dynamic IPv4) or Tailscale Tunnel",
            "be550_path": "External: MyAussie App > Service Settings > Opt-out CGNAT",
            "action_goal": "I want to host a game server and port forward through Aussie Broadband CGNAT",
            "steps": [
                "Open the MyAussie app on your smartphone or visit https://my.aussiebroadband.com.au",
                "Navigate to Service Settings > Connection Settings",
                "Toggle 'Opt-out of CGNAT' to ON (Free of charge, applies in ~15 minutes)",
                "Alternatively, install Tailscale on Omarchy to bypass CGNAT with zero port forwarding"
            ]
        })

    # 2. Camera & IoT Network Isolation
    if has_cameras:
        cams = [d for d in devices if d.get("category") in ["camera", "nvr"]]
        cam_names = ", ".join([d.get("name", d.get("ip")) for d in cams[:2]])
        suggestions.append({
            "id": "sug-iot-isolation",
            "category": "Network Security",
            "priority": "critical",
            "badge": "Security Alert",
            "title": "Isolate CCTV Cameras & Smart Devices on Dedicated IoT Network",
            "description": f"Security cameras ({cam_names}) and smart home hardware are sharing the main subnet with your personal workstations. Isolating them prevents lateral movement if camera firmware is compromised.",
            "current_state": "Shared Main Subnet (192.168.0.0/24)",
            "recommended_state": "Archer BE550 IoT Network (BananaFarm-IoT) with Device Isolation Enabled",
            "be550_path": "Wireless > IoT Network",
            "action_goal": "How do I isolate my security cameras and smart home IoT devices using Archer BE550 features?",
            "steps": [
                "Log in to Archer BE550 at https://192.168.0.1",
                "Navigate to Wireless > IoT Network",
                "Enable the IoT Network with SSID 'BananaFarm-IoT' (WPA2-Personal)",
                "Enable 'Device Isolation' so cameras cannot scan or probe your personal workstations"
            ]
        })

    # 3. Wi-Fi 7 & MLO Band Steering
    current_band = wifi.get("frequency", "5180 MHz")
    suggestions.append({
        "id": "sug-wifi7-mlo",
        "category": "Wireless Performance",
        "priority": "recommended",
        "badge": "Wi-Fi 7 Speed",
        "title": "Enable Multi-Link Operation (MLO) & 6 GHz 320 MHz Channels",
        "description": "The TP-Link Archer BE550 v2 supports Wi-Fi 7 (802.11be) with Multi-Link Operation (MLO). MLO allows compatible devices to transmit over 5 GHz and 6 GHz simultaneously for ultra-low jitter and multi-gigabit throughput.",
        "current_state": f"Connected to 5 GHz (Ch {wifi.get('channel', '36')}, {current_band})",
        "recommended_state": "Wi-Fi 7 MLO Network (5 GHz + 6 GHz aggregated) with WPA3-SAE",
        "be550_path": "Wireless > MLO Network",
        "action_goal": "I want to fix lag spikes, bufferbloat, and reduce my gaming ping",
        "steps": [
            "Open Archer BE550 portal: https://192.168.0.1",
            "Go to Wireless > MLO Network",
            "Enable MLO Network and set a dedicated SSID for Wi-Fi 7 devices",
            "Verify 6 GHz channel width is set to 320 MHz for maximum bandwidth"
        ]
    })

    # 4. Extender Latency Penalty Mitigation
    if has_extender:
        ext = next((d for d in devices if d.get("category") == "extender"), {})
        ext_ip = ext.get("ip", "192.168.0.76")
        suggestions.append({
            "id": "sug-extender-ap",
            "category": "Latency & Stability",
            "priority": "recommended",
            "badge": "Jitter Reduction",
            "title": "Convert Netgear EX6250v2 to Access Point (AP) via Ethernet Backhaul",
            "description": "Operating the Netgear EX6250v2 in wireless repeater mode incurs a 50% throughput reduction and introduces 10-25ms latency spikes. Connecting via Cat6 Ethernet to the Archer BE550 2.5G LAN port unlocks full gigabit speeds with zero jitter.",
            "current_state": f"Repeater Mode on {ext_ip} (Shared Wireless Backhaul)",
            "recommended_state": "Access Point (AP) Mode with Dedicated Cat6 Ethernet Backhaul",
            "be550_path": f"Netgear Admin: http://{ext_ip} > Setup > Wireless > Access Point",
            "action_goal": "How do I configure my Netgear EX6250v2 extender with my TP-Link Archer BE550 for best Wi-Fi coverage?",
            "steps": [
                f"Connect an Ethernet cable between Archer BE550 LAN port and Netgear EX6250v2 Gigabit port",
                f"Open http://{ext_ip} or http://mywifiext.local in your web browser",
                "Switch device operating mode from 'Extender' to 'Access Point Mode'",
                "Match SSID and password to BananaFarm for seamless roaming"
            ]
        })

    # 5. DHCP Static IP Reservation
    high_priority_devs = [d for d in devices if d.get("user_settings", {}).get("priority", "").startswith("High") or d.get("is_local_host")]
    hp_names = ", ".join([d.get("name", d.get("ip")) for d in high_priority_devs[:2]]) or "Omarchy Host"
    suggestions.append({
        "id": "sug-dhcp-reservation",
        "category": "Network Stability",
        "priority": "recommended",
        "badge": "Reliability",
        "title": "Set Permanent DHCP Address Reservations for Servers & Workstations",
        "description": f"Assign static address reservations for critical machines ({hp_names}) so local SSH connections, Jellyfin streaming, and port forwarding never fail after router reboots or DHCP renewal.",
        "current_state": "Dynamic DHCP Lease Pool (192.168.0.100 - 192.168.0.249)",
        "recommended_state": f"Reserved Static Leases on Archer BE550 (e.g. {host.get('ip', '192.168.0.5')})",
        "be550_path": "Advanced > Network > DHCP Server > Address Reservation",
        "action_goal": "How do I set static IP address reservation on my Archer BE550?",
        "steps": [
            "Open https://192.168.0.1 > Advanced > Network > DHCP Server > Address Reservation",
            f"Click '+ Add' and select MAC address {host.get('mac', 'Omarchy')}",
            f"Assign fixed IP {host.get('ip', '192.168.0.5')} and save",
            "Repeat for any NVR, smart TVs, or media servers"
        ]
    })

    # 6. Quality of Service (QoS) Prioritization
    suggestions.append({
        "id": "sug-qos",
        "category": "Gaming & Media",
        "priority": "optimization",
        "badge": "Bufferbloat Fix",
        "title": "Enable HomeShield QoS for Low-Latency Gaming & Media",
        "description": "Configure TP-Link HomeShield Quality of Service (QoS) on the Archer BE550 to give priority traffic handling to your Omarchy gaming workstation. This prevents ping spikes when other family members stream 4K movies or download large files.",
        "current_state": "Default Best-Effort FIFO Queue",
        "recommended_state": "High Priority QoS Rule for Omarchy Gaming PC",
        "be550_path": "HomeShield > QoS",
        "action_goal": "I want to fix lag spikes, bufferbloat, and reduce my gaming ping",
        "steps": [
            "Open https://192.168.0.1 and navigate to HomeShield > QoS",
            "Enable QoS and set your Aussie Broadband download/upload speed limits (e.g. 100/20 Mbps or 1000/50 Mbps)",
            f"Add {host.get('ip', '192.168.0.5')} to the 'High Priority' devices list",
            "Save and test with Waveform Bufferbloat Test"
        ]
    })

    # 7. Encrypted / Low-Latency DNS
    suggestions.append({
        "id": "sug-dns",
        "category": "Privacy & Speed",
        "priority": "optimization",
        "badge": "DNS Speed",
        "title": "Switch to Low-Latency Cloudflare (1.1.1.1) or Quad9 DNS",
        "description": "Default ISP DNS resolvers can be slower and lack privacy encryption. Cloudflare 1.1.1.1 and Quad9 9.9.9.9 offer sub-10ms DNS lookup times in Australia with built-in malicious domain blocking.",
        "current_state": f"ISP / Gateway DNS ({', '.join(host.get('dns', ['192.168.0.1']))})",
        "recommended_state": "Primary: 1.1.1.1, Secondary: 1.0.0.1 (or Quad9 9.9.9.9)",
        "be550_path": "Advanced > Network > Internet > Advanced Settings > Primary DNS",
        "action_goal": "How do I configure custom fast DNS on Archer BE550?",
        "steps": [
            "Open https://192.168.0.1 > Advanced > Network > Internet",
            "Click Advanced Settings under IPv4",
            "Set Primary DNS: 1.1.1.1 and Secondary DNS: 1.0.0.1",
            "Save settings to apply network-wide to all clients automatically"
        ]
    })

    return suggestions
