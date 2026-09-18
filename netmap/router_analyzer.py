"""
router_analyzer.py - Comprehensive Router Settings Analyzer & Recommendation Engine.
Analyzes authenticated router configuration (TP-Link Archer BE550 v2 / general gateways),
evaluates security posture, wireless tuning, IoT isolation, and bufferbloat/QoS,
and generates prioritized improvement recommendations with exact GUI navigation click-paths.
"""

from typing import Dict, Any, List, Optional


class RouterAnalyzer:
    """
    Evaluates router configuration against networking, performance, and security standards.
    Outputs a quantitative Health Score (0-100) and prioritized actionable recommendations.
    """

    def __init__(self, router_settings: Dict[str, Any], topology: Optional[Dict[str, Any]] = None):
        self.settings = router_settings or {}
        self.topology = topology or {}

    def analyze(self) -> Dict[str, Any]:
        """Run full evaluation and return score, breakdown, and suggestions."""
        findings: List[Dict[str, Any]] = []
        score = 100

        wan_s = self.settings.get("wan_status") or self.settings.get("network_status") or {}
        internet = self.settings.get("internet", {})
        status_all = self.settings.get("status_all", {})
        topo_wan = self.topology.get("wan", {})
        topo_host = self.topology.get("host", {})
        devices = self.topology.get("devices", [])
        has_cameras = self.topology.get("has_cameras", False) or any(d.get("category") in ["camera", "nvr"] for d in devices)

        # -------------------------------------------------------------
        # 1. SECURITY & ACCESS CONTROL
        # -------------------------------------------------------------
        # Check remote web management
        remote_mgmt = self.settings.get("remote_management", False)
        if remote_mgmt:
            score -= 15
            findings.append({
                "id": "sec-remote-mgmt",
                "category": "Security & Access",
                "severity": "critical",
                "badge": "High Vulnerability",
                "title": "Remote Web Management Exposed to Public Internet",
                "description": "The router administration web portal is accessible from external public IP addresses on the WAN interface, leaving it vulnerable to automated brute-force attacks.",
                "current_value": "Enabled on WAN",
                "recommended_value": "Disabled (Local Subnet Only)",
                "router_path": "Advanced > System > Administration > Remote Management",
                "fix_guidance": "Disable Remote Management in the router administration portal. Only manage the router from the local LAN or via an encrypted WireGuard/Tailscale VPN.",
                "ai_prompt": "How do I secure the Archer BE550 administration portal and disable public WAN management?"
            })

        # Check UPnP (Universal Plug and Play)
        upnp_state = self.settings.get("upnp_enabled", True)
        if upnp_state:
            score -= 5
            findings.append({
                "id": "sec-upnp-exposure",
                "category": "Security & Access",
                "severity": "recommended",
                "badge": "Port Exposure",
                "title": "UPnP Enabled Without Restriction",
                "description": "Universal Plug and Play allows any local device or potentially compromised smart device to open inbound firewall ports without administrative approval.",
                "current_value": "UPnP Active",
                "recommended_value": "Disabled or Restricted to Trusted Workstations",
                "router_path": "Advanced > NAT Forwarding > UPnP",
                "fix_guidance": "Disable UPnP and use explicit Virtual Server port forwarding rules for specific services only.",
                "ai_prompt": "What are the security risks of UPnP on Archer BE550 and how do I configure port forwarding manually?"
            })

        # -------------------------------------------------------------
        # 2. WI-FI 7 & WIRELESS PERFORMANCE
        # -------------------------------------------------------------
        mlo_active = self.settings.get("mlo_enabled", False)
        # BE550 supports Wi-Fi 7 MLO
        if not mlo_active:
            score -= 8
            findings.append({
                "id": "wifi-mlo-disabled",
                "category": "Wireless & Wi-Fi 7",
                "severity": "warning",
                "badge": "Wi-Fi 7 Speed",
                "title": "Wi-Fi 7 Multi-Link Operation (MLO) is Inactive",
                "description": "Your Archer BE550 v2 router supports Wi-Fi 7 MLO, which binds 5 GHz and 6 GHz bands into an aggregated multi-gigabit link with sub-millisecond switching and jitter elimination.",
                "current_value": "MLO Network Disabled",
                "recommended_value": "MLO Network Enabled (WPA3-SAE)",
                "router_path": "Wireless > MLO Network",
                "fix_guidance": "Go to Wireless > MLO Network, toggle MLO to Enabled, specify an SSID, and set security to WPA3-SAE.",
                "ai_prompt": "Explain how to enable and optimize Wi-Fi 7 MLO network on TP-Link Archer BE550 v2."
            })

        width_6ghz = self.settings.get("channel_width_6ghz", "160MHz")
        if width_6ghz != "320MHz":
            score -= 6
            findings.append({
                "id": "wifi-6ghz-width",
                "category": "Wireless & Wi-Fi 7",
                "severity": "recommended",
                "badge": "Throughput Boost",
                "title": "6 GHz Band Channel Width Limited to 160 MHz",
                "description": "Wi-Fi 7 achieves peak throughput of up to 5760 Mbps on the 6 GHz band by utilizing ultra-wide 320 MHz channels. The current channel width is operating at half capacity.",
                "current_value": f"6 GHz Channel Width: {width_6ghz}",
                "recommended_value": "320 MHz (Ultra-Wide)",
                "router_path": "Wireless > Wireless Settings > 6GHz > Channel Width",
                "fix_guidance": "Navigate to Wireless > Wireless Settings > 6GHz, set Channel Width to 320 MHz, and click Save.",
                "ai_prompt": "How do I configure 320 MHz channel width on Archer BE550 6GHz band?"
            })

        # -------------------------------------------------------------
        # 3. IOT & CCTV CAMERA NETWORK ISOLATION
        # -------------------------------------------------------------
        iot_isolated = self.settings.get("iot_isolation_enabled", False)
        if has_cameras and not iot_isolated:
            score -= 15
            findings.append({
                "id": "sec-iot-isolation",
                "category": "Network Security",
                "severity": "critical",
                "badge": "Security Alert",
                "title": "CCTV Cameras & IoT Devices Not Isolated from Workstations",
                "description": "Surveillance cameras (RTSP 554) and smart home devices share the main LAN with your personal Omarchy workstations. If a camera firmware vulnerability is exploited, attackers can access your workstation subnet.",
                "current_value": "Shared Subnet (192.168.0.0/24)",
                "recommended_value": "Archer BE550 IoT Network with Device Isolation",
                "router_path": "Wireless > IoT Network",
                "fix_guidance": "Enable the dedicated IoT Network, set an SSID (e.g. BananaFarm-IoT), check 'Device Isolation', and migrate camera devices.",
                "ai_prompt": "Guide me through isolating my security cameras on Archer BE550 IoT network."
            })

        # -------------------------------------------------------------
        # 4. LOW-LATENCY ENCRYPTED DNS
        # -------------------------------------------------------------
        dns_list = self.settings.get("dns_servers") or topo_host.get("dns", [])
        uses_fast_dns = any(d in ["1.1.1.1", "1.0.0.1", "9.9.9.9", "149.112.112.112"] for d in dns_list)
        if not uses_fast_dns:
            score -= 6
            findings.append({
                "id": "net-dns-optimization",
                "category": "DNS & Privacy",
                "severity": "recommended",
                "badge": "DNS Speed",
                "title": "Router Relying on Default Unencrypted ISP DNS",
                "description": "Your router is relaying DNS requests through standard ISP resolvers. Upgrading to Cloudflare 1.1.1.1 or Quad9 9.9.9.9 reduces lookup latency across all devices and protects against ISP DNS hijacking.",
                "current_value": f"Current DNS: {', '.join(dns_list) if dns_list else 'Default ISP'}",
                "recommended_value": "Primary: 1.1.1.1, Secondary: 1.0.0.1 (or 9.9.9.9)",
                "router_path": "Advanced > Network > Internet > Advanced Settings > Primary DNS",
                "fix_guidance": "Open Advanced > Network > Internet, expand Advanced Settings, set Primary DNS to 1.1.1.1 and Secondary to 1.0.0.1.",
                "ai_prompt": "What are the fastest DNS servers for Aussie Broadband in Australia and how to set them in Archer BE550?"
            })

        # -------------------------------------------------------------
        # 5. GAMING & BUFFERBLOAT (HOMESHIELD QOS)
        # -------------------------------------------------------------
        qos_enabled = self.settings.get("qos_enabled", False)
        if not qos_enabled:
            score -= 10
            findings.append({
                "id": "qos-bufferbloat",
                "category": "Gaming & Latency",
                "severity": "recommended",
                "badge": "Bufferbloat Fix",
                "title": "TP-Link HomeShield QoS Disabled",
                "description": "Quality of Service (QoS) is inactive. Under heavy network traffic (e.g. 4K streaming or large game downloads), queue delays on your router can cause 50-150ms ping spikes in competitive online games.",
                "current_value": "QoS Disabled (FIFO Buffer)",
                "recommended_value": "HomeShield QoS Enabled with Gaming PC High Priority",
                "router_path": "HomeShield > QoS",
                "fix_guidance": "Navigate to HomeShield > QoS, toggle QoS to On, enter your ISP bandwidth limits (e.g. 1000/50 Mbps), and add your gaming workstation to High Priority.",
                "ai_prompt": "How do I configure TP-Link HomeShield QoS to get an A+ bufferbloat rating for gaming?"
            })

        # -------------------------------------------------------------
        # 6. STATIC DHCP LEASE RESERVATION
        # -------------------------------------------------------------
        reservations = self.settings.get("dhcp_reservations", [])
        host_ip = topo_host.get("ip", "192.168.0.5")
        host_mac = topo_host.get("mac", "")
        has_host_res = any(r.get("ip") == host_ip or (host_mac and r.get("mac") == host_mac) for r in reservations)
        if not has_host_res:
            score -= 4
            findings.append({
                "id": "dhcp-reservation-missing",
                "category": "Network Stability",
                "severity": "optimization",
                "badge": "IP Reliability",
                "title": "Workstation Has Dynamic DHCP Lease Instead of Static Reservation",
                "description": f"The host machine ({host_ip}) does not have a permanent DHCP address reservation in the router. An IP change after a router reboot will disrupt SSH tunnels, Samba file shares, and port forwarding.",
                "current_value": "Dynamic DHCP Lease",
                "recommended_value": f"Reserved Static Lease: {host_ip} ({host_mac or 'Omarchy'})",
                "router_path": "Advanced > Network > DHCP Server > Address Reservation",
                "fix_guidance": f"Go to Advanced > Network > DHCP Server > Address Reservation, click + Add, enter MAC {host_mac or 'Omarchy MAC'}, assign IP {host_ip}, and click Save.",
                "ai_prompt": "Step-by-step instructions to bind static DHCP IP on Archer BE550."
            })

        # -------------------------------------------------------------
        # 7. AUSSIE BROADBAND CGNAT WAN
        # -------------------------------------------------------------
        is_cgnat = topo_wan.get("cgnat_active", False)
        if is_cgnat:
            findings.append({
                "id": "wan-cgnat-blocked",
                "category": "Remote Access & WAN",
                "severity": "warning",
                "badge": "CGNAT Inbound Block",
                "title": "Upstream Carrier-Grade NAT (CGNAT) Active",
                "description": "Your public WAN IPv4 is behind an Aussie Broadband CGNAT gateway (100.64.0.0/10). Inbound port forwarding configured on your Archer BE550 cannot be reached from the public internet.",
                "current_value": "CGNAT Active (Aussie Broadband)",
                "recommended_value": "Opt-Out via MyAussie App (Dynamic Public IPv4)",
                "router_path": "External: MyAussie Portal > Service Settings > Opt-out CGNAT",
                "fix_guidance": "Open the MyAussie app on your smartphone, navigate to Service Settings > Connection Settings, and toggle 'Opt-out CGNAT' to ON (free of charge).",
                "ai_prompt": "How do I bypass Aussie Broadband CGNAT for game servers or remote desktop?"
            })

        # Clamp score to [0, 100]
        final_score = max(0, min(100, score))

        # Letter grade calculation
        if final_score >= 95:
            grade = "A+"
        elif final_score >= 88:
            grade = "A"
        elif final_score >= 80:
            grade = "B"
        elif final_score >= 70:
            grade = "C"
        elif final_score >= 60:
            grade = "D"
        else:
            grade = "F"

        return {
            "health_score": final_score,
            "grade": grade,
            "total_recommendations": len(findings),
            "critical_count": sum(1 for f in findings if f["severity"] == "critical"),
            "warning_count": sum(1 for f in findings if f["severity"] == "warning"),
            "recommended_count": sum(1 for f in findings if f["severity"] == "recommended"),
            "optimization_count": sum(1 for f in findings if f["severity"] == "optimization"),
            "findings": findings
        }
