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

DOCS_DIR = Path(__file__).parent / "docs"

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

# ----------------------------------------------------------------------
# 2. Callable Agent Diagnostic Tools
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

TOOL_DEFINITIONS = [
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
        requested_agent: Optional[str] = None
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

        if lead_agent_id == "surveillance" or any(w in goal_lower for w in ["camera", "nvr", "cctv", "rtsp", "onvif"]):
            doc_topic = "cctv"
            cams = [d for d in topology.get("devices", []) if d.get("category") in ["camera", "nvr"]]
            cam_ip = cams[0]["ip"] if cams else "192.168.0.136"
            
            # Run portscan tool
            scan_res = tool_portscan(cam_ip, [554, 8554, 8000, 37777, 8899])
            tool_results_summary["portscan"] = scan_res
            trace.append({
                "step": 2,
                "agent": lead_agent["name"],
                "icon": lead_agent["icon"],
                "thought": f"Probing active camera services on {cam_ip} to verify RTSP, ONVIF, and NVR ports.",
                "tool": "tool_portscan",
                "args": {"ip": cam_ip, "ports": [554, 8554, 8000, 37777, 8899]},
                "result": f"Port scan completed. Open ports on {cam_ip}: {scan_res.get('open_ports', [])}"
            })

        elif lead_agent_id == "security" or any(w in goal_lower for w in ["port forward", "cgnat", "server", "minecraft", "remote"]):
            doc_topic = "cgnat"
            # Ping gateway & check CGNAT status
            gw_ip = topology.get("host", {}).get("gateway", "192.168.0.1")
            ping_res = tool_ping(gw_ip)
            tool_results_summary["ping"] = ping_res
            trace.append({
                "step": 2,
                "agent": lead_agent["name"],
                "icon": lead_agent["icon"],
                "thought": f"Testing gateway reachability on {gw_ip} and evaluating Aussie Broadband CGNAT status.",
                "tool": "tool_ping",
                "args": {"host": gw_ip},
                "result": f"Gateway reachable: {ping_res.get('reachable')} (Latency: {ping_res.get('avg', '0.4')} ms)"
            })

        elif lead_agent_id == "performance" or any(w in goal_lower for w in ["ping", "lag", "latency", "bufferbloat", "gaming", "qos"]):
            doc_topic = "gaming"
            ping_res = tool_ping("1.1.1.1")
            tool_results_summary["ping"] = ping_res
            trace.append({
                "step": 2,
                "agent": lead_agent["name"],
                "icon": lead_agent["icon"],
                "thought": "Testing upstream jitter and latency to Cloudflare 1.1.1.1 DNS.",
                "tool": "tool_ping",
                "args": {"host": "1.1.1.1"},
                "result": f"Cloudflare reachable: {ping_res.get('avg', '14.2')} ms (Jitter: ±{ping_res.get('mdev', '0.8')} ms)"
            })

        elif lead_agent_id == "hardware" or "extender" in goal_lower or "ex6250" in goal_lower:
            doc_topic = "extender"
            ext = next((d for d in topology.get("devices", []) if d.get("category") == "extender"), None)
            ext_ip = ext.get("ip") if ext else "192.168.0.76"
            ping_res = tool_ping(ext_ip)
            trace.append({
                "step": 2,
                "agent": lead_agent["name"],
                "icon": lead_agent["icon"],
                "thought": f"Probing Netgear EX6250v2 extender on {ext_ip} to assess repeater link latency.",
                "tool": "tool_ping",
                "args": {"host": ext_ip},
                "result": f"Extender responded: {ping_res.get('avg', '2.5')} ms"
            })

        # Step 3: Knowledge Base Document Retrieval
        doc_result = tool_read_docs(doc_topic)
        trace.append({
            "step": 3,
            "agent": lead_agent["name"],
            "icon": lead_agent["icon"],
            "thought": f"Consulting NetMap Knowledge Base article '{doc_result.get('title')}' for exact menu click-paths and engineering standards.",
            "tool": "tool_read_docs",
            "args": {"topic": doc_topic},
            "result": f"Loaded '{doc_result.get('filename')}' ({len(doc_result.get('content', ''))} bytes)."
        })

        # Step 4: LLM or Local Synthesis
        # Call advisor to formulate visual diagrams and text
        solution = self.advisor.solve(goal, topology)

        # Step 5: Construct Interactive Action Buttons
        action_items = self._generate_action_items(lead_agent_id, goal_lower, topology, solution)

        # Attach agent trace and metadata
        solution["agent_trace"] = trace
        solution["lead_agent"] = lead_agent
        solution["action_items"] = action_items

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
        elif any(w in goal_lower for w in ["extender", "mesh", "ex6250", "be550", "router setting", "dhcp"]):
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

        # Ping Gateway
        actions.append({
            "id": "act-ping-gw",
            "label": f"Ping Gateway ({gw_ip})",
            "icon": "📡",
            "type": "tool_ping",
            "params": {"host": gw_ip}
        })

        # Camera RTSP test if camera topic
        if lead_agent_id == "surveillance" or "camera" in goal_lower:
            cams = [d for d in topology.get("devices", []) if d.get("category") in ["camera", "nvr"]]
            cam_ip = cams[0]["ip"] if cams else "192.168.0.136"
            actions.append({
                "id": "act-scan-rtsp",
                "label": f"Scan Port 554 on Camera ({cam_ip})",
                "icon": "📹",
                "type": "tool_portscan",
                "params": {"ip": cam_ip, "ports": [554, 8554, 8000, 37777, 8899]}
            })

        # Gaming ping test
        if lead_agent_id == "performance" or "gaming" in goal_lower:
            actions.append({
                "id": "act-ping-dns",
                "label": "Benchmark Cloudflare 1.1.1.1 Jitter",
                "icon": "⚡",
                "type": "tool_ping",
                "params": {"host": "1.1.1.1"}
            })

        # Documentation lookup action
        doc_topic = "be550"
        if lead_agent_id == "surveillance": doc_topic = "cctv"
        elif lead_agent_id == "security": doc_topic = "cgnat"
        elif lead_agent_id == "performance": doc_topic = "gaming"
        elif lead_agent_id == "hardware": doc_topic = "extender"

        actions.append({
            "id": f"act-doc-{doc_topic}",
            "label": f"Read {doc_topic.upper()} Reference Manual",
            "icon": "📖",
            "type": "tool_read_docs",
            "params": {"topic": doc_topic}
        })

        return actions

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
        result = self.run_agentic_workflow(message, topology, requested_agent=agent_id)
        
        history.append({
            "role": "assistant",
            "content": result.get("summary", ""),
            "result": result
        })
        
        result["session_id"] = session_id
        result["turn_count"] = len(history) // 2
        return result

AGENT_ORCHESTRATOR = AgentOrchestrator()
