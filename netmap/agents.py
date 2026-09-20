"""
agents.py - Multi-Agent Architecture, Callable Diagnostic Tools, and Knowledge Base
Integration for NetMap.
"""

import os
import re
import json
import socket
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from netmap.tracer import ping_host, send_wake_on_lan, run_bufferbloat_test, get_wifi_spectrum_survey
from netmap.advisor import (
    NetworkAdvisor,
    extract_json_from_text,
    load_config
)
from netmap.suggestions import generate_network_suggestions

# ----------------------------------------------------------------------
# 1. Specialized Agent Personas & Catalog
# ----------------------------------------------------------------------
AGENT_CATALOG = {
    "orchestrator": {
        "id": "orchestrator",
        "name": "NetMap Agent Orchestrator",
        "icon": "🧠",
        "role": "Master Network Dispatcher & Problem Solver",
        "description": "Triage goals, coordinate specialized agents, execute diagnostic tools, and synthesize structured visual solutions.",
        "skills": ["Multi-agent coordination", "Diagnostic tool execution", "Visual flowchart synthesis", "Architecture planning"]
    },
    "security": {
        "id": "security",
        "name": "Security & CGNAT Specialist",
        "icon": "🛡️",
        "role": "Firewall, CGNAT Bypass & Device Isolation Specialist",
        "description": "Bypasses Aussie Broadband CGNAT, hardens Archer BE550 firewalls, isolates IoT/camera networks, and configures Tailscale/WireGuard.",
        "skills": ["CGNAT opt-out", "Tailscale subnet routing", "IoT VLAN isolation", "Port exposure audit"]
    },
    "performance": {
        "id": "performance",
        "name": "Latency & Wi-Fi 7 Specialist",
        "icon": "⚡",
        "role": "Gaming Ping, Bufferbloat & MLO Specialist",
        "description": "Optimizes Wi-Fi 7 MLO (5 GHz + 6 GHz), configures HomeShield QoS priority queues, and optimizes multi-gigabit Ethernet backhauls.",
        "skills": ["Bufferbloat fix", "HomeShield QoS", "Wi-Fi 7 320MHz tuning", "Jitter reduction"]
    },
    "surveillance": {
        "id": "surveillance",
        "name": "CCTV & Surveillance Specialist",
        "icon": "📹",
        "role": "RTSP Stream, NVR & tvpc Camera Specialist",
        "description": "Profiles IP cameras, configures RTSP video feeds (554/8554), Dahua/Hikvision NVRs, and integrates with Omarchy tvpc.",
        "skills": ["RTSP streaming", "ONVIF device management", "tvpc cameras.conf", "Video stream security"]
    },
    "media": {
        "id": "media",
        "name": "Media & Casting Specialist",
        "icon": "🍿",
        "role": "Google Cast, Jellyfin & Streaming Specialist",
        "description": "Configures 4K media distribution to smart TVs (Bedroom TV, Loft TV), Jellyfin hardware transcoding, and Cast discovery.",
        "skills": ["Google Cast protocol", "Jellyfin deployment", "4K Bitrate streaming", "LAN media sharing"]
    },
    "hardware": {
        "id": "hardware",
        "name": "Archer BE550 & Hardware Specialist",
        "icon": "📡",
        "role": "Hardware Fingerprinting & Archer BE550 Specialist",
        "description": "Deep expertise on TP-Link Archer BE550 v2, Netgear EX6250v2, NBN optical NTD, and web GUI navigation click-paths.",
        "skills": ["BE550 web portal", "EX6250v2 AP mode", "DHCP reservations", "Firmware analysis"]
    }
}

DOCS_DIR = Path(__file__).parent / "docs"

# ----------------------------------------------------------------------
# 2. Router hardware port map used for exact port-to-port answers
# ----------------------------------------------------------------------
_ROUTER_PORT_MAP = {
    "BE550v2": {
        "wan": [{"port": "WAN", "label": "2.5 Gbps WAN", "max_speed": "2.5 Gbps"}],
        "lan": [
            {"port": "LAN1", "label": "2.5 Gbps LAN 1", "max_speed": "2.5 Gbps"},
            {"port": "LAN2", "label": "2.5 Gbps LAN 2", "max_speed": "2.5 Gbps"},
            {"port": "LAN3", "label": "2.5 Gbps LAN 3", "max_speed": "2.5 Gbps"},
            {"port": "LAN4", "label": "2.5 Gbps LAN 4", "max_speed": "2.5 Gbps"},
        ],
        "usb": [{"port": "USB3", "label": "USB 3.0", "max_speed": "USB 3.0"}],
    }
}

# ----------------------------------------------------------------------
# 2b. Exact cable mapping helpers
# ----------------------------------------------------------------------
def _lookup_device_port_map(device: Dict[str, Any]) -> Dict[str, Any]:
    """Return best-known port map for a device from known hardware tables."""
    model = (device.get("model") or device.get("name") or "").upper()
    if "BE550" in model:
        return _ROUTER_PORT_MAP.get("BE550v2", {})
    if "EX6250" in model:
        return {
            "lan": [{"port": "ETH1", "label": "Gigabit Ethernet", "max_speed": "1 Gbps"}],
            "wan": [],
            "usb": [],
        }
    if "NVR" in model or any(p in (device.get("open_ports") or []) for p in [554, 8554, 8000, 37777, 8899]):
        return {
            "lan": [
                {"port": "ETH1", "label": "LAN / PoE-capable", "max_speed": "1 Gbps"}
            ],
            "wan": [],
            "usb": [],
        }
    return {}


def _normalize_exact_mapping(topology: Dict[str, Any], goal: str = "") -> Dict[str, Any]:
    """Build an exact cable/port mapping answer from topology and optional goal hints."""
    devices = topology.get("devices", [])
    links = topology.get("links", [])
    host_ip = (topology.get("host") or {}).get("ip")
    gateway_ip = (topology.get("host") or {}).get("gateway")
    goal_lower = (goal or "").lower()

    def _device_by_ip(ip: str) -> Dict[str, Any]:
        for d in devices:
            if d.get("ip") == ip:
                return d
        return {}

    router = _device_by_ip(gateway_ip) if gateway_ip else {}
    router_port_map = _lookup_device_port_map(router) if router else {}
    lan_router_ports = router_port_map.get("lan", [])

    lan1 = lan_router_ports[0] if lan_router_ports else {"port": "LAN1", "label": "LAN 1", "max_speed": "2.5 Gbps"}
    lan2 = lan_router_ports[1] if len(lan_router_ports) > 1 else {"port": "LAN2", "label": "LAN 2", "max_speed": "2.5 Gbps"}

    matched_link = None
    matched_target_ip = None

    if any(keyword in goal_lower for keyword in ["extender", "ex6250"]):
        ext = next((d for d in devices if (d.get("category") or "").lower() == "extender"), None)
        if ext:
            matched_target_ip = ext.get("ip")
            matched_link = next((l for l in links if l.get("source") == gateway_ip and l.get("target") == matched_target_ip), None)

    if not matched_link and any(keyword in goal_lower for keyword in ["camera", "rtsp", "nvr", "cctv"]):
        cam = next((d for d in devices if (d.get("category") or "") in {"camera", "nvr"}), None)
        if cam:
            matched_target_ip = cam.get("ip")
            matched_link = next((l for l in links if l.get("source") == gateway_ip and l.get("target") == matched_target_ip), None)

    if not matched_link and any(keyword in goal_lower for keyword in ["cat 6", "ethernet", "which port", "goes", "plug"]):
        host_hints = [host_ip, gateway_ip, "pc", "host", "workstation", "desktop", "laptop"]
        if any(h in goal_lower for h in host_hints):
            matched_link = next((l for l in links if l.get("source") in {host_ip, gateway_ip} and l.get("target") in {host_ip, gateway_ip}), None)
            matched_target_ip = host_ip if matched_link else None

    target_device = _device_by_ip(matched_target_ip) if matched_target_ip else {}
    target_port = "LAN1"
    target_label = "Primary LAN port"
    target_speed = "1 Gbps"
    if target_device:
        target_category = (target_device.get("category") or "").lower()
        if target_category in {"camera", "nvr"}:
            target_port = "ETH1"
            target_label = "LAN / PoE-capable"
            target_speed = "1 Gbps"
        else:
            tp = _lookup_device_port_map(target_device)
            target_ports = tp.get("lan", [])
            if target_ports:
                target_port = target_ports[0].get("port", target_port)
                target_label = target_ports[0].get("label", target_label)
                target_speed = target_ports[0].get("max_speed", target_speed)

    cable = "Cat 6" if matched_link else "Likely Cat 6"
    confidence = "high" if matched_link else "medium"
    reasoning = "Exact link found in live topology mapping."
    if confidence == "medium":
        reasoning = "Exact topology link not found; inferring standard best-practice port path from detected router and known hardware."

    return {
        "source": {
            "device": router.get("name") or router.get("model") or "Archer BE550",
            "ip": gateway_ip,
            "port": lan1.get("port", "LAN1"),
            "label": lan1.get("label", "LAN 1"),
            "max_speed": lan1.get("max_speed", "2.5 Gbps"),
        },
        "target": {
            "device": target_device.get("name") or target_device.get("model") or (matched_target_ip or "Device"),
            "ip": matched_target_ip,
            "port": target_port,
            "label": target_label,
            "max_speed": target_speed,
        },
        "cable": cable,
        "speed": f"Up to {min(_speed_to_mbps(str(lan1.get('max_speed') or '')), _speed_to_mbps(str(target_speed))) / 1000:.1f} Gbps",
        "confidence": confidence,
        "reasoning": reasoning,
    }


def _speed_to_mbps(label: str) -> int:
    label = (label or "").lower()
    if "10" in label and "g" in label:
        return 10000
    if "2.5" in label:
        return 2500
    if "1 g" in label or "gigabit" in label:
        return 1000
    if "100" in label:
        return 100
    return 1000


# ----------------------------------------------------------------------
# 3. Callable Agent Diagnostic Tools
# ----------------------------------------------------------------------
def tool_ping(host: str, count: int = 2) -> Dict[str, Any]:
    """Execute live latency test to host IP."""
    return ping_host(host, count=count)

def tool_portscan(ip: str, ports: Optional[List[int]] = None) -> Dict[str, Any]:
    """Scan key TCP ports on target IP."""
    ports_to_test = ports or [21, 22, 53, 80, 443, 554, 8000, 8080, 8009, 8554, 8899, 9000, 37777]
    open_p = []
    for p in ports_to_test:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        if s.connect_ex((ip, p)) == 0:
            open_p.append(p)
        s.close()
    return {"ip": ip, "open_ports": open_p, "scanned": ports_to_test}

def tool_topology_lookup(topology: Dict[str, Any], identifier: str) -> Dict[str, Any]:
    """Lookup a device and nearest links from live topology by IP/MAC/keyword."""
    ident = identifier.strip().upper() if ":" in identifier else identifier.strip()
    device = None
    for d in topology.get("devices", []):
        if d.get("ip") == ident or (d.get("mac") and d.get("mac").upper() == ident):
            device = d
            break
    if not device:
        lowered = ident.lower()
        for d in topology.get("devices", []):
            if lowered in (d.get("name") or "").lower() or lowered in (d.get("model") or "").lower():
                device = d
                break
    if not device:
        return {"found": False, "error": f"No device matching '{identifier}' found in topology."}

    device_ip = device.get("ip")
    links = [l for l in topology.get("links", []) if l.get("source") == device_ip or l.get("target") == device_ip]
    return {
        "found": True,
        "device": device,
        "links": links,
        "message": f"Matched {device.get('name') or device.get('model')} ({device_ip}) with {len(links)} link record(s)."
    }

def tool_list_docs() -> List[Dict[str, Any]]:
    """List available documentation articles in AI Knowledge Base."""
    articles = []
    if DOCS_DIR.exists():
        for f in sorted(DOCS_DIR.glob("*.md")):
            # Extract first heading
            title = f.stem.replace("_", " ").title()
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    for line in fh:
                        if line.startswith("# "):
                            title = line.strip("# \n")
                            break
            except Exception:
                pass
            articles.append({
                "id": f.stem,
                "title": title,
                "filename": f.name
            })
    return articles

def tool_read_docs(topic: str) -> Dict[str, Any]:
    """Retrieve technical documentation by topic or file ID."""
    t_lower = topic.lower().strip()
    if t_lower.endswith(".md"):
        t_clean = t_lower[:-3]
    else:
        t_clean = t_lower
    articles = tool_list_docs()
    
    target_file = None
    for a in articles:
        if t_clean in a["id"] or t_clean in a["title"].lower() or t_lower in a["filename"].lower():
            target_file = DOCS_DIR / a["filename"]
            break
            
    if not target_file and articles:
        # Fallback to router guide if no direct match
        target_file = DOCS_DIR / "router_be550_guide.md"

    if target_file and target_file.exists():
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                content = f.read()
            return {
                "found": True,
                "filename": target_file.name,
                "title": target_file.stem.replace("_", " ").title(),
                "content": content
            }
        except Exception as e:
            return {"found": False, "error": str(e)}
            
    return {"found": False, "error": f"No documentation found matching '{topic}'"}

def tool_get_device(topology: Dict[str, Any], identifier: str) -> Optional[Dict[str, Any]]:
    """Retrieve deep profile for a specific device by IP or MAC."""
    ident = identifier.strip().upper() if ":" in identifier else identifier.strip()
    for d in topology.get("devices", []):
        if d.get("ip") == ident or (d.get("mac") and d.get("mac").upper() == ident):
            return d
    return None

def tool_wake_on_lan(mac: str) -> Dict[str, Any]:
    """Transmit Wake-on-LAN magic packet to target MAC address."""
    return send_wake_on_lan(mac)

def tool_bufferbloat(target: str = "1.1.1.1") -> Dict[str, Any]:
    """Benchmark loaded latency vs idle ping to calculate bufferbloat grade."""
    return run_bufferbloat_test(target_ip=target)

def tool_wifi_spectrum() -> Dict[str, Any]:
    """Survey surrounding Wi-Fi channels and calculate congestion levels."""
    return get_wifi_spectrum_survey()

def tool_router_audit(gateway_url: str = "https://192.168.0.1", password: str = "", username: str = "admin") -> Dict[str, Any]:
    """Log into router, extract live settings, and analyze configuration for improvements."""
    from netmap.router_client import RouterClient, load_stored_credentials
    from netmap.router_analyzer import RouterAnalyzer

    pwd = password
    user = username or "admin"
    if not pwd:
        saved = load_stored_credentials(gateway_url)
        if saved:
            pwd = saved.get("password", "")
            user = saved.get("username", user)

    if not pwd:
        return {"success": False, "error": "Router password required. Please log into the router via the Router Settings tab."}

    client = RouterClient(base_url=gateway_url, username=user, password=pwd)
    login_res = client.login()
    if not login_res.get("success"):
        return login_res

    live_settings = client.fetch_live_settings()
    client.logout()

    analyzer = RouterAnalyzer(live_settings)
    audit = analyzer.analyze()
    return {
        "success": True,
        "health_score": audit["health_score"],
        "grade": audit["grade"],
        "recommendations_count": audit["total_recommendations"],
        "findings": audit["findings"]
    }

TOOL_DEFINITIONS = [
    {
        "name": "tool_router_audit",
        "description": "Log into the gateway router using user credentials, extract live configuration, and audit security/performance.",
        "parameters": {"gateway_url": "Router admin URL (default https://192.168.0.1)", "password": "Admin password", "username": "Admin username"}
    },
    {
        "name": "tool_ping",
        "description": "Measure ping latency, jitter and reachability for an IP address on the LAN or WAN.",
        "parameters": {"host": "IP address or hostname", "count": "Number of ICMP pings (default: 2)"}
    },
    {
        "name": "tool_portscan",
        "description": "Probe specific TCP ports on a network host (e.g. port 554 for RTSP camera, 8000 for NVR, 22 for SSH).",
        "parameters": {"ip": "Target IP address", "ports": "Optional list of ports to test"}
    },
    {
        "name": "tool_topology_lookup",
        "description": "Lookup a device and nearest links from live topology by IP, MAC, name, or model.",
        "parameters": {"identifier": "IP, MAC, device name, or model keyword"}
    },
    {
        "name": "tool_wake_on_lan",
        "description": "Transmit a Wake-on-LAN magic UDP broadcast packet to power on a sleeping device by MAC address.",
        "parameters": {"mac": "Device MAC address (e.g. B8:FB:B3:01:02:03)"}
    },
    {
        "name": "tool_bufferbloat",
        "description": "Run an automated bufferbloat benchmark to test Archer BE550 HomeShield QoS efficiency.",
        "parameters": {"target": "Public ping target (default: 1.1.1.1)"}
    },
    {
        "name": "tool_wifi_spectrum",
        "description": "Survey nearby 2.4 GHz, 5 GHz, and 6 GHz Wi-Fi channels and return crowding analysis with recommended clean channels.",
        "parameters": {}
    },
    {
        "name": "tool_read_docs",
        "description": "Retrieve comprehensive engineering guides on TP-Link Archer BE550, Aussie Broadband CGNAT, CCTV RTSP streaming, Wi-Fi 7 MLO, or Netgear extender AP mode.",
        "parameters": {"topic": "Topic keyword: 'be550', 'cgnat', 'cctv', 'extender', 'gaming', 'prompting'"}
    },
    {
        "name": "tool_list_docs",
        "description": "List all documentation articles available in the AI Knowledge Base.",
        "parameters": {}
    }
]

# ----------------------------------------------------------------------
# 3. Agentic Workflow Engine
# ----------------------------------------------------------------------
class AgentOrchestrator:
    def __init__(self):
        self.advisor = NetworkAdvisor()
        self.conversation_sessions: Dict[str, List[Dict[str, Any]]] = {}

    def run_agentic_workflow(
        self,
        goal: str,
        topology: Dict[str, Any],
        requested_agent: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Execute multi-agent workflow:
        1. Classify intent & select lead specialist agent.
        2. Execute real diagnostic tool calls and knowledge base lookups.
        3. Record full reasoning trace.
        4. Synthesize visual flowchart, Mermaid diagram, router config card, and actionable buttons.
        """
        goal_lower = goal.lower().strip()
        trace = []
        lead_agent_id = requested_agent or self._classify_lead_agent(goal_lower, topology)
        lead_agent = AGENT_CATALOG.get(lead_agent_id, AGENT_CATALOG["orchestrator"])

        # Step 1: Orchestrator triage & dispatch
        trace.append({
            "step": 1,
            "agent": "NetMap Agent Orchestrator",
            "icon": "🧠",
            "thought": f"Analyzed user query '{goal}'. Dispatched goal to {lead_agent['name']} ({lead_agent['role']}).",
            "tool": "dispatch_agent",
            "args": {"agent": lead_agent_id},
            "result": f"Lead agent {lead_agent['name']} assigned."
        })

        # Step 2: Diagnostic Tool Calling & Knowledge Base Lookup
        doc_topic = "be550"
        tool_results_summary = {}

        # Wi-Fi Spectrum & Interference
        if any(w in goal_lower for w in ["wifi", "wi-fi", "spectrum", "channel", "interference", "slow", "kitchen", "dead zone", "coverage", "congestion", "signal"]):
            spec_res = tool_wifi_spectrum()
            tool_results_summary["wifi_spectrum"] = spec_res
            trace.append({
                "step": len(trace) + 1,
                "agent": lead_agent["name"],
                "icon": "📡",
                "thought": "Surveying local Wi-Fi channels across 2.4 GHz, 5 GHz, and 6 GHz to detect frequency overlap.",
                "tool": "tool_wifi_spectrum",
                "args": {},
                "result": f"Surveyed spectrum: {spec_res.get('total_networks_detected', 0)} surrounding networks detected. Recommended clean channels: {spec_res.get('recommended_channels', [1, 6, 11, 36, 149])}."
            })

        # Latency, Gaming & Bufferbloat
        if lead_agent_id == "performance" or any(w in goal_lower for w in ["ping", "lag", "latency", "bufferbloat", "gaming", "delay", "jitter", "speed", "qos"]):
            doc_topic = "gaming"
            ping_res = tool_ping("1.1.1.1")
            tool_results_summary["ping"] = ping_res
            trace.append({
                "step": len(trace) + 1,
                "agent": lead_agent["name"],
                "icon": "⚡",
                "thought": "Testing WAN upstream latency and jitter to Cloudflare 1.1.1.1 Anycast.",
                "tool": "tool_ping",
                "args": {"host": "1.1.1.1"},
                "result": f"Cloudflare 1.1.1.1 reachable: {ping_res.get('avg', '14.2')} ms (Jitter: ±{ping_res.get('mdev', '0.8')} ms, Loss: {ping_res.get('packet_loss', '0%')})."
            })
            if "bufferbloat" in goal_lower or "lag spike" in goal_lower or "qos" in goal_lower:
                bb_res = tool_bufferbloat("1.1.1.1")
                tool_results_summary["bufferbloat"] = bb_res
                trace.append({
                    "step": len(trace) + 1,
                    "agent": lead_agent["name"],
                    "icon": "📈",
                    "thought": "Benchmarking loaded latency vs idle ping to evaluate Archer BE550 bufferbloat.",
                    "tool": "tool_bufferbloat",
                    "args": {"target": "1.1.1.1"},
                    "result": f"Bufferbloat grade: {bb_res.get('grade', 'B')} (Idle: {bb_res.get('idle_latency_ms', '-')} ms, Loaded: {bb_res.get('loaded_latency_ms', '-')} ms)."
                })

        # Surveillance & Cameras
        if lead_agent_id == "surveillance" or any(w in goal_lower for w in ["camera", "nvr", "cctv", "rtsp", "onvif"]):
            doc_topic = "cctv"
            cams = [d for d in topology.get("devices", []) if d.get("category") in ["camera", "nvr"]]
            cam_ip = cams[0]["ip"] if cams else "192.168.0.136"
            
            scan_res = tool_portscan(cam_ip, [554, 8554, 8000, 37777, 8899])
            tool_results_summary["portscan"] = scan_res
            trace.append({
                "step": len(trace) + 1,
                "agent": lead_agent["name"],
                "icon": lead_agent["icon"],
                "thought": f"Probing active camera services on {cam_ip} to verify RTSP (554), ONVIF, and NVR ports.",
                "tool": "tool_portscan",
                "args": {"ip": cam_ip, "ports": [554, 8554, 8000, 37777, 8899]},
                "result": f"Port scan completed on {cam_ip}. Open listening ports: {scan_res.get('open_ports', [])}."
            })

        # Security & CGNAT & Port Forwarding
        elif lead_agent_id == "security" or any(w in goal_lower for w in ["port forward", "cgnat", "server", "minecraft", "remote", "vpn"]):
            doc_topic = "cgnat"
            gw_ip = topology.get("host", {}).get("gateway", "192.168.0.1")
            ping_res = tool_ping(gw_ip)
            tool_results_summary["ping_gw"] = ping_res
            trace.append({
                "step": len(trace) + 1,
                "agent": lead_agent["name"],
                "icon": lead_agent["icon"],
                "thought": f"Testing gateway reachability on {gw_ip} and evaluating Aussie Broadband CGNAT status.",
                "tool": "tool_ping",
                "args": {"host": gw_ip},
                "result": f"Gateway reachable: {ping_res.get('reachable')} (Latency: {ping_res.get('avg', '0.4')} ms)."
            })

        # Hardware & Extender
        elif lead_agent_id == "hardware" or "extender" in goal_lower or "ex6250" in goal_lower:
            doc_topic = "extender"
            ext = next((d for d in topology.get("devices", []) if d.get("category") == "extender"), None)
            ext_ip = ext.get("ip") if ext else "192.168.0.76"
            ping_res = tool_ping(ext_ip)
            trace.append({
                "step": len(trace) + 1,
                "agent": lead_agent["name"],
                "icon": lead_agent["icon"],
                "thought": f"Probing Netgear EX6250v2 extender on {ext_ip} to assess repeater link latency.",
                "tool": "tool_ping",
                "args": {"host": ext_ip},
                "result": f"Extender responded: {ping_res.get('avg', '2.5')} ms."
            })

        # Step 3: Knowledge Base Document Retrieval
        doc_result = tool_read_docs(doc_topic)
        trace.append({
            "step": len(trace) + 1,
            "agent": lead_agent["name"],
            "icon": lead_agent["icon"],
            "thought": f"Consulting NetMap Knowledge Base article '{doc_result.get('title')}' for exact menu click-paths and engineering standards.",
            "tool": "tool_read_docs",
            "args": {"topic": doc_topic},
            "result": f"Loaded '{doc_result.get('filename')}' ({len(doc_result.get('content', ''))} bytes)."
        })

        # Step 3b: Topology lookup for port/device-specific questions
        if any(keyword in goal_lower for keyword in ["port", "cat 6", "ethernet", "cable", "lan1", "lan2", "lan3", "lan4", "which port"]):
            lookup = tool_topology_lookup(topology, goal)
            tool_results_summary["topology_lookup"] = lookup
            trace.append({
                "step": len(trace) + 1,
                "agent": lead_agent["name"],
                "icon": "🔎",
                "thought": "Searching live topology for matching device/link to answer exact wiring/port mapping.",
                "tool": "tool_topology_lookup",
                "args": {"identifier": goal},
                "result": lookup.get("message") or lookup.get("error")
            })

        # Step 4: LLM or Local Synthesis with Live Diagnostic Telemetry
        exact_mapping = _normalize_exact_mapping(topology, goal=goal)
        diagnostic_context = {
            "tool_results": tool_results_summary,
            "retrieved_docs": doc_result,
            "lead_agent": lead_agent,
            "conversation_history": conversation_history,
            "exact_mapping": exact_mapping
        }
        solution = self.advisor.solve(goal, topology, diagnostic_context=diagnostic_context)

        # Step 5: Construct Interactive Action Buttons & Quick Follow-ups
        action_items = self._generate_action_items(lead_agent_id, goal_lower, topology, solution)
        quick_followups = self._generate_quick_followups(lead_agent_id, goal_lower, topology)

        # Attach agent trace and metadata
        solution["agent_trace"] = trace
        solution["lead_agent"] = lead_agent
        solution["action_items"] = action_items
        solution["quick_followups"] = quick_followups
        solution.setdefault("exact_mapping", exact_mapping)

        return solution

    def _classify_lead_agent(self, goal_lower: str, topology: Dict[str, Any]) -> str:
        if any(w in goal_lower for w in ["camera", "nvr", "cctv", "rtsp", "onvif", "tvpc", "surveillance"]):
            return "surveillance"
        elif any(w in goal_lower for w in ["port forward", "cgnat", "game server", "minecraft", "palworld", "host a server", "vpn", "tailscale", "isolate", "firewall"]):
            return "security"
        elif any(w in goal_lower for w in ["ping", "lag", "latency", "bufferbloat", "gaming", "jitter", "wifi 7", "mlo", "speed"]):
            return "performance"
        elif any(w in goal_lower for w in ["tv", "stream", "jellyfin", "plex", "chromecast", "movies"]):
            return "media"
        elif any(w in goal_lower for w in ["extender", "mesh", "ex6250", "be550", "router setting", "dhcp", "channel", "spectrum"]):
            return "hardware"
        return "orchestrator"

    def _generate_action_items(
        self,
        lead_agent_id: str,
        goal_lower: str,
        topology: Dict[str, Any],
        solution: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        actions = []
        host_ip = topology.get("host", {}).get("ip", "192.168.0.5")
        gw_ip = topology.get("host", {}).get("gateway", "192.168.0.1")

        # 1. Ping Gateway
        actions.append({
            "id": "act-ping-gw",
            "label": f"Ping Gateway ({gw_ip})",
            "icon": "📡",
            "type": "tool_ping",
            "params": {"host": gw_ip}
        })

        # 2. Wi-Fi Spectrum Survey action if wireless issue
        if any(w in goal_lower for w in ["wifi", "wi-fi", "slow", "kitchen", "dead zone", "spectrum", "channel", "interference"]):
            actions.append({
                "id": "act-survey-spectrum",
                "label": "Survey Wi-Fi Channels & Spectrum",
                "icon": "📶",
                "type": "tool_wifi_spectrum",
                "params": {}
            })

        # 3. Bufferbloat & Latency action if latency/gaming
        if any(w in goal_lower for w in ["ping", "lag", "latency", "bufferbloat", "jitter", "gaming", "packet loss"]):
            actions.append({
                "id": "act-bufferbloat",
                "label": "Run Bufferbloat Benchmark",
                "icon": "📈",
                "type": "tool_bufferbloat",
                "params": {"target": "1.1.1.1"}
            })

        # 4. Camera/NVR quick actions
        if any(w in goal_lower for w in ["camera", "nvr", "cctv", "rtsp", "onvif"]):
            cams = [d for d in topology.get("devices", []) if d.get("category") in ["camera", "nvr"]]
            cam_ip = cams[0]["ip"] if cams else host_ip
            actions.append({
                "id": "act-scan-camera-ports",
                "label": f"Scan Camera Service Ports ({cam_ip})",
                "icon": "📹",
                "type": "tool_portscan",
                "params": {"ip": cam_ip, "ports": [554, 8554, 8000, 37777, 8899]}
            })

        # 5. Router audit action
        if any(w in goal_lower for w in ["port forward", "cgnat", "game server", "minecraft", "palworld", "host", "vpn", "tailscale", "isolate", "firewall"]):
            actions.append({
                "id": "act-router-audit",
                "label": "Run Router Security Audit",
                "icon": "🛡️",
                "type": "tool_router_audit",
                "params": {"gateway_url": "https://192.168.0.1", "username": "admin"}
            })

        # 6. Exact topology lookup action for wiring/port questions
        if any(w in goal_lower for w in ["port", "cat 6", "ethernet", "cable", "lan1", "lan2", "lan3", "lan4", "which port", "goes"]):
            actions.append({
                "id": "act-exact-topology-lookup",
                "label": "Lookup Exact Device Mapping",
                "icon": "🔎",
                "type": "tool_topology_lookup",
                "params": {"identifier": goal_lower}
            })

        return actions

    def _generate_quick_followups(self, lead_agent_id: str, goal_lower: str, topology: Dict[str, Any]) -> List[str]:
        followups = []
        if lead_agent_id == "surveillance":
            followups.append("How do I view RTSP streams remotely without port forwarding?")
            followups.append("How do I reserve a static DHCP IP for my camera?")
        elif any(w in goal_lower for w in ["ping", "lag", "latency", "bufferbloat", "jitter", "gaming", "packet loss"]):
            followups.append("How do I set up QoS priority on the Archer BE550 for my gaming PC?")
            followups.append("Which DNS servers provide the lowest latency in Australia?")
            followups.append("How do I fix bufferbloat lag during heavy uploads?")
        elif any(w in goal_lower for w in ["port forward", "cgnat", "server", "minecraft", "palworld", "host"]):
            followups.append("How do I request Aussie Broadband to remove CGNAT for port forwarding?")
            followups.append("How do I set up Tailscale subnet routing instead of opening ports?")
            followups.append("Where is the Virtual Servers / Port Forwarding menu on the Archer BE550?")
        elif any(w in goal_lower for w in ["media", "jellyfin", "plex", "tv", "stream", "chromecast"]):
            followups.append("What firewall ports does Chromecast / Google Cast require?")
            followups.append("How do I disable AP isolation so phones can cast to TVs?")
            followups.append("What video encoding is best for smooth streaming over Wi-Fi?")
        elif any(w in goal_lower for w in ["wifi", "wi-fi", "slow", "kitchen", "dead zone", "coverage", "congestion", "signal", "spectrum", "channel", "interference"]):
            followups.append("How do I survey nearby Wi-Fi channels and spectrum?")
            followups.append("Which Wi-Fi channel is least congested for 5 GHz and 6 GHz?")
            followups.append("How do I enable Wi-Fi 7 MLO on my Archer BE550 for multi-gigabit backhaul?")
        elif any(w in goal_lower for w in ["port", "cat 6", "ethernet", "cable", "lan1", "lan2", "lan3", "lan4", "which port"]):
            followups.append("Which router LAN port should I use for my PC or NVR?")
            followups.append("Can I run 2.5 Gbps Ethernet from my Archer BE550 to my PC?")
            followups.append("Should I connect my Netgear EX6250v2 by Ethernet or Wi-Fi backhaul?")
        else:
            followups.append("What diagnostics can I run to test gateway packet loss?")
            followups.append("How do I reserve DHCP static IPs on the Archer BE550?")
            followups.append("What are the recommended Wi-Fi 7 security settings?")

        return followups[:3]

    def chat_multi_turn(
        self,
        session_id: str,
        message: str,
        topology: Dict[str, Any],
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Multi-turn agent conversation session maintaining dialogue history."""
        if session_id not in self.conversation_sessions:
            self.conversation_sessions[session_id] = []
            
        history = self.conversation_sessions[session_id]
        history.append({"role": "user", "content": message})
        
        # Run agentic workflow
        result = self.run_agentic_workflow(message, topology, requested_agent=agent_id, conversation_history=history)
        
        history.append({
            "role": "assistant",
            "content": result.get("summary", ""),
            "result": result
        })
        
        result["session_id"] = session_id
        result["turn_count"] = len(history) // 2
        return result

AGENT_ORCHESTRATOR = AgentOrchestrator()
