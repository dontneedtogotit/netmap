"""
advisor.py - Intelligent Network Problem Solver & Setup Advisor for NetMap.
Supports Mistral AI API, OpenRouter API (with free / Kilo Code models),
local expert heuristics, and produces structured Visual and Text responses.
"""

import os
import json
import re
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional

CONFIG_FILE = Path(os.path.expanduser("~/.config/netmap/config.json"))

RECOMMENDED_FREE_MODELS = [
    {"id": "qwen/qwen-2.5-coder-32b-instruct:free", "name": "Qwen 2.5 Coder 32B (Free / Kilo Code)"},
    {"id": "deepseek/deepseek-r1:free", "name": "DeepSeek R1 Reasoning (Free)"},
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B Instruct (Free)"},
    {"id": "google/gemini-2.0-flash-exp:free", "name": "Gemini 2.0 Flash Exp (Free)"},
    {"id": "mistralai/mistral-small-24b-instruct-2501:free", "name": "Mistral Small 24B (Free)"}
]

RECOMMENDED_MISTRAL_MODELS = [
    {"id": "mistral-small-latest", "name": "Mistral Small (Fast, Cost-Effective & Smart)"},
    {"id": "mistral-large-latest", "name": "Mistral Large (Flagship Reasoning & Networking)"},
    {"id": "codestral-latest", "name": "Codestral (Networking, Config & Code Specialized)"},
    {"id": "open-mistral-nemo", "name": "Mistral NeMo 12B (Fast Open Weights)"},
    {"id": "ministral-8b-latest", "name": "Ministral 8B (Ultra Low Latency Edge)"}
]

def load_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(cfg: Dict[str, Any]):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Resilient parser that extracts JSON even if surrounded by markdown or commentary."""
    text = text.strip()
    # If directly JSON
    try:
        return json.loads(text)
    except Exception:
        pass
        
    # Strip markdown ```json ... ``` blocks
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
            
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass
            
    return None

class NetworkAdvisor:
    def __init__(
        self,
        ai_provider: Optional[str] = None,
        mistral_key: Optional[str] = None,
        mistral_model: Optional[str] = None,
        openrouter_key: Optional[str] = None,
        openrouter_model: Optional[str] = None
    ):
        cfg = load_config()
        self.ai_provider = ai_provider or cfg.get("ai_provider", "mistral" if cfg.get("mistral_api_key") else ("openrouter" if cfg.get("openrouter_api_key") else "local"))
        self.mistral_key = mistral_key or cfg.get("mistral_api_key") or os.environ.get("MISTRAL_API_KEY", "")
        self.mistral_model = mistral_model or cfg.get("mistral_model") or "mistral-small-latest"
        self.openrouter_key = openrouter_key or cfg.get("openrouter_api_key") or os.environ.get("OPENROUTER_API_KEY", "")
        self.openrouter_model = openrouter_model or cfg.get("openrouter_model") or "qwen/qwen-2.5-coder-32b-instruct:free"

    def set_config(
        self,
        ai_provider: Optional[str] = None,
        mistral_key: Optional[str] = None,
        mistral_model: Optional[str] = None,
        openrouter_key: Optional[str] = None,
        openrouter_model: Optional[str] = None
    ):
        cfg = load_config()
        if ai_provider is not None:
            self.ai_provider = ai_provider
            cfg["ai_provider"] = ai_provider
        if mistral_key is not None:
            self.mistral_key = mistral_key
            cfg["mistral_api_key"] = mistral_key
        if mistral_model is not None:
            self.mistral_model = mistral_model
            cfg["mistral_model"] = mistral_model
        if openrouter_key is not None:
            self.openrouter_key = openrouter_key
            cfg["openrouter_api_key"] = openrouter_key
        if openrouter_model is not None:
            self.openrouter_model = openrouter_model
            cfg["openrouter_model"] = openrouter_model
        save_config(cfg)

    def solve(self, goal: str, topology: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produce a tailored solution for the user's problem.
        Checks active AI provider (Mistral AI or OpenRouter), queries LLM with full
        topology and user-configured device context, and falls back to local expert rules.
        """
        cfg = load_config()
        provider = self.ai_provider or cfg.get("ai_provider", "local")

        # 1. Mistral AI Provider
        if provider == "mistral" and self.mistral_key:
            llm_result = self._solve_with_mistral(goal, topology)
            if llm_result:
                return llm_result

        # 2. OpenRouter Provider
        elif provider == "openrouter" and self.openrouter_key:
            llm_result = self._solve_with_openrouter(goal, topology)
            if llm_result:
                return llm_result

        # Fallback to provider with valid key if preferred wasn't chosen explicitly
        if self.mistral_key and provider != "local":
            llm_result = self._solve_with_mistral(goal, topology)
            if llm_result:
                return llm_result
        elif self.openrouter_key and provider != "local":
            llm_result = self._solve_with_openrouter(goal, topology)
            if llm_result:
                return llm_result

        # 3. Local expert rule-based solver
        return self._solve_with_local_expert(goal, topology)

    def _build_system_prompt(self, topology: Dict[str, Any]) -> str:
        router_settings = topology.get("router_settings", {})
        devices = topology.get("devices", [])
        wan = topology.get("wan", {})
        host = topology.get("host", {})
        
        # Format devices with their user-customized preset & custom fields
        device_context_list = []
        for d in devices:
            dev_dict = {
                "ip": d.get("ip"),
                "mac": d.get("mac"),
                "name": d.get("name"),
                "category": d.get("category"),
                "vendor": d.get("vendor"),
                "ports": d.get("open_ports")
            }
            # Add user customized settings & dynamic fields
            user_s = d.get("user_settings", {})
            if user_s:
                dev_dict["user_defined_role"] = user_s.get("role")
                dev_dict["user_defined_location"] = user_s.get("location")
                dev_dict["user_defined_priority"] = user_s.get("priority")
                dev_dict["user_defined_vlan_segment"] = user_s.get("network_segment")
                dev_dict["user_notes"] = user_s.get("notes")
                dev_dict["custom_fields"] = user_s.get("custom_fields", {})
            device_context_list.append(dev_dict)

        router_audit = topology.get("router_audit") or {}
        audit_line = f"- Authenticated Router Audit & Health Score: {json.dumps({'health_score': router_audit.get('health_score'), 'grade': router_audit.get('grade'), 'findings': router_audit.get('findings', [])})}\n" if router_audit else ""

        return (
            "You are NetMap AI, an expert network engineer running natively on Omarchy Linux.\n"
            "The user will ask a network question, optimization goal, or troubleshooting request.\n"
            "You must provide a structured JSON response containing BOTH detailed text recommendations and VISUAL diagram specifications.\n\n"
            "EXACT LIVE NETWORK TOPOLOGY, HARDWARE & USER CONTEXT:\n"
            f"- Primary Router: {json.dumps(router_settings.get('hardware', {}))}\n"
            f"- Router LAN Settings: {json.dumps(router_settings.get('lan_settings', {}))}\n"
            f"- Wi-Fi Settings: {json.dumps(router_settings.get('wifi_settings', {}))}\n"
            f"- WAN / NBN Modem Settings: {json.dumps(router_settings.get('wan_modem_settings', {}))}\n"
            f"- Archer BE550 Web GUI Paths: {json.dumps(router_settings.get('admin_navigation_paths', {}))}\n"
            f"{audit_line}"
            f"- Host Machine: {json.dumps({'hostname': host.get('hostname'), 'ip': host.get('ip'), 'interface': host.get('interface'), 'wifi': host.get('wifi')})}\n"
            f"- Discovered Devices & User Configured Settings: {json.dumps(device_context_list, indent=1)}\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Take into account any user-defined device roles, locations, QoS priorities, and custom fields (e.g. if a device is designated 'Primary Gaming PC', give it high QoS priority; if 'CCTV Camera', isolate it on IoT VLAN).\n"
            "2. Under Aussie Broadband CGNAT (100.91.128.1), explain how to bypass it (MyAussie 1-click opt-out, or Tailscale peer-to-peer WireGuard tunnel).\n"
            "3. You MUST provide VISUAL DIAGRAM specifications alongside the text recommendations.\n"
            "4. Return raw valid JSON only matching the schema below.\n\n"
            "JSON SCHEMA:\n"
            "{\n"
            "  \"category\": \"string (e.g. Camera & NVR Setup, Port Forwarding, Gaming Optimization)\",\n"
            "  \"goal\": \"string\",\n"
            "  \"summary\": \"string\",\n"
            "  \"warnings\": [{\"type\": \"caution|warning|tip\", \"title\": \"string\", \"text\": \"string\"}],\n"
            "  \"steps\": [{\"step\": 1, \"title\": \"string\", \"details\": \"string with markdown links\", \"command\": \"optional bash command or null\"}],\n"
            "  \"visual_diagram\": {\n"
            "    \"type\": \"flowchart\",\n"
            "    \"title\": \"string (visual diagram title)\",\n"
            "    \"nodes\": [{\"id\": \"id1\", \"label\": \"Title\", \"sub\": \"Port / Details\", \"icon\": \"emoji\", \"color\": \"#hex\"}],\n"
            "    \"links\": [{\"from\": \"id1\", \"to\": \"id2\", \"label\": \"protocol / traffic description\"}]\n"
            "  },\n"
            "  \"mermaid\": \"string (valid Mermaid graph TD or flowchart LR code, e.g. 'graph LR\\n  A[Client] --> B[BE550 Router]')\",\n"
            "  \"router_config_card\": {\n"
            "    \"page\": \"Exact path in Archer BE550 Web GUI\",\n"
            "    \"fields\": [{\"label\": \"Field Name\", \"value\": \"Exact recommended value\"}]\n"
            "  },\n"
            "  \"highlight_nodes\": [\"192.168.0.x\"],\n"
            "  \"best_practices\": [\"string\"]\n"
            "}"
        )

    def _solve_with_mistral(self, goal: str, topology: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Query official Mistral AI API with JSON mode and visual diagram enforcement."""
        try:
            url = "https://api.mistral.ai/v1/chat/completions"
            system_prompt = self._build_system_prompt(topology)
            
            payload = {
                "model": self.mistral_model or "mistral-small-latest",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Problem/Goal: {goal}"}
                ],
                "response_format": {"type": "json_object"}
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.mistral_key}",
                    "Content-Type": "application/json"
                }
            )

            with urllib.request.urlopen(req, timeout=22) as res:
                body = json.loads(res.read().decode("utf-8"))
                choice = body["choices"][0]["message"]["content"]
                parsed = extract_json_from_text(choice)
                if parsed:
                    parsed["ai_engine"] = f"Mistral AI ({self.mistral_model})"
                    return parsed
        except Exception as e:
            print(f"[NetMap] Mistral API query failed ({e}). Falling back to next solver.")
        return None

    def _solve_with_openrouter(self, goal: str, topology: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Query OpenRouter API using free or selected model."""
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            system_prompt = self._build_system_prompt(topology)

            payload = {
                "model": self.openrouter_model or "qwen/qwen-2.5-coder-32b-instruct:free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Problem/Goal: {goal}"}
                ],
                "response_format": {"type": "json_object"}
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:8765",
                    "X-Title": "NetMap Omarchy"
                }
            )

            with urllib.request.urlopen(req, timeout=20) as res:
                body = json.loads(res.read().decode("utf-8"))
                choice = body["choices"][0]["message"]["content"]
                parsed = extract_json_from_text(choice)
                if parsed:
                    parsed["ai_engine"] = f"OpenRouter ({self.openrouter_model})"
                    return parsed
        except Exception as e:
            print(f"[NetMap] OpenRouter API query failed ({e}). Falling back to local advisor.")
        return None

    def _solve_with_local_expert(self, goal: str, topology: Dict[str, Any]) -> Dict[str, Any]:
        """Local rule-based expert solver."""
        goal_lower = goal.lower().strip()
        
        if any(w in goal_lower for w in ["camera", "nvr", "cctv", "rtsp", "onvif", "tvpc", "surveillance", "video recorder"]):
            res = self._solve_cameras_nvr(goal, topology)
        elif any(w in goal_lower for w in ["port forward", "game server", "minecraft", "palworld", "valheim", "host a server", "host server", "forward port", "open port"]):
            res = self._solve_port_forwarding(goal, topology)
        elif any(w in goal_lower for w in ["ping", "lag", "latency", "bufferbloat", "gaming", "delay", "jitter"]):
            res = self._solve_gaming_latency(goal, topology)
        elif any(w in goal_lower for w in ["stream", "plex", "jellyfin", "media server", "bedroom tv", "loft tv", "movies", "tv"]):
            res = self._solve_media_streaming(goal, topology)
        elif any(w in goal_lower for w in ["extender", "mesh", "ex6250", "wifi coverage", "dead zone", "roaming", "range"]):
            res = self._solve_mesh_extender(goal, topology)
        elif any(w in goal_lower for w in ["vpn", "wireguard", "remote access", "access outside", "away from home", "tailscale"]):
            res = self._solve_remote_access(goal, topology)
        elif any(w in goal_lower for w in ["secure", "isolate", "iot", "guest", "firewall", "hacked", "security"]):
            res = self._solve_security_iot(goal, topology)
        else:
            res = self._solve_general(goal, topology)
            
        res["ai_engine"] = "Local Network Expert"
        return res

    def _solve_cameras_nvr(self, goal: str, topology: Dict[str, Any]) -> Dict[str, Any]:
        wan = topology.get("wan", {})
        host = topology.get("host", {})
        devices = topology.get("devices", [])
        is_cgnat = wan.get("cgnat_active", True)
        
        cams = [d for d in devices if d.get("category") == "camera"]
        nvrs = [d for d in devices if d.get("category") == "nvr"]
        highlight_ips = [d.get("ip") for d in cams + nvrs if d.get("ip")]
        if not highlight_ips:
            highlight_ips = ["192.168.0.1", host.get("ip", "192.168.0.5")]

        warnings = []
        if is_cgnat:
            warnings.append({
                "type": "caution",
                "title": "Aussie Broadband CGNAT Blocks Inbound RTSP/CCTV Streams",
                "text": "Your connection is behind Carrier-Grade NAT (CGNAT at 100.91.128.1). Remote CCTV viewing from mobile data will fail unless you opt-out in the MyAussie app or use a secure tunnel like Tailscale."
            })

        steps = [
            {
                "step": 1,
                "title": "Local RTSP Stream Testing via Omarchy (tvpc)",
                "details": "You have `tvpc cameras` configured on your Omarchy host (`~/.config/tvpc/cameras.conf`).\n"
                           "To view live CCTV camera feeds or test RTSP streams directly on your Omarchy workstation, use the TVPC launcher or mpv:",
                "command": "mpv --profile=low-latency rtsp://admin:password@<CAMERA-IP>:554/stream"
            },
            {
                "step": 2,
                "title": "Isolate Cameras on Archer BE550 IoT Network",
                "details": "Security cameras should never share the main LAN with your personal computers:\n"
                           "1. Open **[https://192.168.0.1](https://192.168.0.1)** in your browser.\n"
                           "2. Go to **Wireless > IoT Network**.\n"
                           "3. Enable the **IoT Network** (e.g. `BananaFarm-IoT`) with WPA2-Personal.\n"
                           "4. Enable **Device Isolation** so cameras cannot scan or access workstations on `192.168.0.5`.",
                "command": None
            },
            {
                "step": 3,
                "title": "Remote Camera Access without Port Forwarding (Tailscale / WireGuard)",
                "details": "Directly port forwarding RTSP port 554 exposes your cameras to brute-force web scanners and fails under AussieBB CGNAT.\n"
                           "Install **Tailscale** on Omarchy or your NVR to view your cameras securely from your phone anywhere:",
                "command": "sudo pacman -S tailscale && sudo systemctl enable --now tailscaled && sudo tailscale up"
            },
            {
                "step": 4,
                "title": "If Using NVR Web Portal (Port Forwarding on Archer BE550)",
                "details": "If you need direct external access:\n"
                           "1. Opt out of CGNAT in the **MyAussie App** (Services > Connection Settings > Opt-out CGNAT).\n"
                           "2. In the Archer BE550, go to **Advanced > NAT Forwarding > Virtual Servers**.\n"
                           "3. Forward Port `8000` or `554` to your camera/NVR internal IP.",
                "command": None
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "CCTV Camera & NVR Data Flow",
            "nodes": [
                {"id": "cam", "label": "IP Camera / RTSP", "sub": "Port 554 / 8554", "icon": "📹", "color": "#e0af68"},
                {"id": "router", "label": "Archer BE550 Router", "sub": "IoT Isolation Network", "icon": "📡", "color": "#7dcfff"},
                {"id": "nvr", "label": "NVR / tvpc Host", "sub": "192.168.0.5 (Recording)", "icon": "📼", "color": "#9ece6a"},
                {"id": "remote", "label": "Remote Phone / TV", "sub": "Tailscale Encrypted Stream", "icon": "📱", "color": "#bb9af7"}
            ],
            "links": [
                {"from": "cam", "to": "router", "label": "RTSP (H.264)"},
                {"from": "router", "to": "nvr", "label": "Recording Stream"},
                {"from": "nvr", "to": "remote", "label": "Encrypted VPN Tunnel"}
            ]
        }

        mermaid = (
            "graph LR\n"
            "  Cam[IP Camera RTSP:554] -->|Isolated SSID| Router[Archer BE550 IoT Network]\n"
            "  Router -->|Local Stream| NVR[NVR / Omarchy Host]\n"
            "  NVR -->|Tailscale VPN| Phone[Remote Viewing Device]"
        )

        router_config_card = {
            "page": "Advanced > NAT Forwarding > Virtual Servers",
            "fields": [
                {"label": "Service Type", "value": "CCTV_NVR"},
                {"label": "External Port", "value": "8000 (or 554)"},
                {"label": "Internal IP", "value": cams[0]["ip"] if cams else "192.168.0.136"},
                {"label": "Internal Port", "value": "8000 (or 554)"},
                {"label": "Protocol", "value": "TCP / UDP"}
            ]
        }

        return {
            "category": "Camera & NVR Setup",
            "goal": goal,
            "summary": "Step-by-step setup to connect, isolate, and stream CCTV cameras and NVR video securely.",
            "warnings": warnings,
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "router_config_card": router_config_card,
            "highlight_nodes": highlight_ips,
            "best_practices": [
                "Keep cameras on the dedicated Archer BE550 IoT Network to prevent lateral movement.",
                "Never leave default manufacturer passwords (admin/admin or admin/123456) on cameras.",
                "Use Tailscale or WireGuard instead of raw port forwarding for video streams to prevent camera hijacking."
            ]
        }

    def _solve_port_forwarding(self, goal: str, topology: Dict[str, Any]) -> Dict[str, Any]:
        wan = topology.get("wan", {})
        host = topology.get("host", {})
        is_cgnat = wan.get("cgnat_active", True)
        
        warnings = []
        if is_cgnat:
            warnings.append({
                "type": "caution",
                "title": "Aussie Broadband CGNAT Detected (Carrier-Grade NAT)",
                "text": "Your connection is currently behind Carrier-Grade NAT (CGNAT hop at 100.91.128.1). Incoming traffic from the raw internet cannot reach your router. Traditional port forwarding will not work until CGNAT is opted out or a tunnel is used."
            })

        steps = [
            {
                "step": 1,
                "title": "Opt-Out of CGNAT (Free via Aussie Broadband)",
                "details": "Aussie Broadband allows you to remove CGNAT for free with a single toggle:\n"
                           "1. Open the **MyAussie app** on your phone or go to [my.aussiebroadband.com.au](https://my.aussiebroadband.com.au)\n"
                           "2. Select your Broadband service.\n"
                           "3. Navigate to **Service Settings / Connection Settings**.\n"
                           "4. Toggle **Opt-out of CGNAT** to ON.\n"
                           "5. Once confirmed, restart your router or kick the session to obtain a public dynamic IPv4 address!",
                "command": None
            },
            {
                "step": 2,
                "title": "Alternative: Zero-Port Forwarding with Tailscale or Cloudflare",
                "details": "If you prefer not to expose open ports to the public internet, install **Tailscale** on your Omarchy host:\n"
                           "Tailscale automatically traverses CGNAT with zero port forwarding.",
                "command": "sudo pacman -S tailscale && sudo systemctl enable --now tailscaled && sudo tailscale up"
            },
            {
                "step": 3,
                "title": "Reserve Static IP on TP-Link Archer BE550",
                "details": f"1. Open **[https://192.168.0.1](https://192.168.0.1)** in your browser.\n"
                           f"2. Go to **Advanced > Network > DHCP Server > Address Reservation**.\n"
                           f"3. Click **Add**, select your Omarchy host (MAC: `{host.get('mac')}`), and assign IP `{host.get('ip')}`.",
                "command": None
            },
            {
                "step": 4,
                "title": "Configure Virtual Server (Port Forward) in Archer BE550",
                "details": "In the TP-Link Archer BE550 management portal:\n"
                           "1. Go to **Advanced > NAT Forwarding > Virtual Servers**.\n"
                           "2. Click **+ Add**.\n"
                           "3. Service Type: Name your server (e.g., GameServer / Minecraft).\n"
                           "4. External Port: `25565` (or target port).\n"
                           f"5. Internal IP: `{host.get('ip')}`\n"
                           "6. Internal Port: `25565`\n"
                           "7. Protocol: `TCP` or `ALL`.\n"
                           "8. Click **Save**.",
                "command": None
            },
            {
                "step": 5,
                "title": "Allow Port in Local Linux Firewall (ufw)",
                "details": "Ensure your Omarchy Linux firewall allows the incoming traffic.",
                "command": "sudo ufw allow 25565/tcp && sudo ufw reload"
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "Port Forwarding Path & CGNAT Bypass",
            "nodes": [
                {"id": "internet", "label": "Internet Player", "sub": "External Traffic", "icon": "🌐", "color": "#bb9af7"},
                {"id": "cgnat", "label": "AussieBB Exchange", "sub": "CGNAT Opt-Out Enabled", "icon": "🏢", "color": "#e0af68"},
                {"id": "router", "label": "Archer BE550 v2", "sub": "NAT Virtual Server :25565", "icon": "📡", "color": "#7dcfff"},
                {"id": "host", "label": "Omarchy Host", "sub": f"{host.get('ip', '192.168.0.5')} (Game Server)", "icon": "💻", "color": "#9ece6a"}
            ],
            "links": [
                {"from": "internet", "to": "cgnat", "label": "Public WAN :25565"},
                {"from": "cgnat", "to": "router", "label": "Direct Public IPv4"},
                {"from": "router", "to": "host", "label": "Virtual Server Forward"}
            ]
        }

        mermaid = (
            "graph LR\n"
            "  User[External Player] -->|Port 25565| Aussie[AussieBB Dynamic IPv4]\n"
            "  Aussie --> Router[Archer BE550 Virtual Server]\n"
            "  Router --> Host[Omarchy Game Server :25565]"
        )

        router_config_card = {
            "page": "Advanced > NAT Forwarding > Virtual Servers",
            "fields": [
                {"label": "Service Type", "value": "GameServer"},
                {"label": "External Port", "value": "25565"},
                {"label": "Internal IP", "value": host.get("ip", "192.168.0.5")},
                {"label": "Internal Port", "value": "25565"},
                {"label": "Protocol", "value": "ALL (TCP/UDP)"}
            ]
        }

        return {
            "category": "Port Forwarding & Server Hosting",
            "goal": goal,
            "summary": "Complete setup to host servers on your TP-Link Archer BE550 v2 and bypass Aussie Broadband CGNAT.",
            "warnings": warnings,
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "router_config_card": router_config_card,
            "highlight_nodes": ["192.168.0.1", host.get("ip", "192.168.0.5")],
            "best_practices": [
                "Always reserve an IP address before forwarding ports so DHCP renewals don't break your forward rule.",
                "Opting out of CGNAT with Aussie Broadband takes less than 15 minutes and requires no payment.",
                "For friends-only gaming servers, Tailscale is safer and faster to configure than opening public ports."
            ]
        }

    def _solve_gaming_latency(self, goal: str, topology: Dict[str, Any]) -> Dict[str, Any]:
        host = topology.get("host", {})
        warnings = [
            {
                "type": "tip",
                "title": "Netgear EX6250v2 Extender Warning",
                "text": "Your network contains a Netgear EX6250v2 extender. In standard repeater mode, traffic passing through an extender suffers a 50% throughput penalty and 10-25ms jitter spikes. Make sure your gaming device connects directly to the Archer BE550."
            }
        ]

        steps = [
            {
                "step": 1,
                "title": "Connect to Archer BE550 5 GHz or 6 GHz Wi-Fi 7",
                "details": "Connect directly to the 5 GHz or 6 GHz band of `BananaFarm` to achieve lower jitter and sub-1ms ping to the gateway.",
                "command": "nmcli dev wifi list"
            },
            {
                "step": 2,
                "title": "Enable QoS (Quality of Service) on Archer BE550",
                "details": "1. Open **[https://192.168.0.1](https://192.168.0.1)**.\n"
                           "2. Navigate to **HomeShield > QoS**.\n"
                           "3. Add your Omarchy PC (`" + host.get("ip", "192.168.0.5") + "`) to **High Priority** devices to prevent bufferbloat when other devices stream 4K video.",
                "command": None
            },
            {
                "step": 3,
                "title": "Best Latency Solution: 2.5 Gbps Ethernet LAN Port",
                "details": "The TP-Link Archer BE550 features four **2.5 Gbps LAN ports**. A direct Cat6 Ethernet cable eliminates all wireless jitter and drops local latency to 0.2ms.",
                "command": None
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "Low-Latency Gaming Data Path",
            "nodes": [
                {"id": "pc", "label": "Omarchy Gaming PC", "sub": "192.168.0.5", "icon": "💻", "color": "#9ece6a"},
                {"id": "router", "label": "Archer BE550 Router", "sub": "HomeShield QoS Priority", "icon": "📡", "color": "#7dcfff"},
                {"id": "ntd", "label": "NBN NTD (Modem)", "sub": "2.5G WAN Port", "icon": "📦", "color": "#bb9af7"},
                {"id": "game", "label": "Game Servers (Brisbane / Sydney)", "sub": "< 15ms AussieBB Peering", "icon": "🎮", "color": "#e0af68"}
            ],
            "links": [
                {"from": "pc", "to": "router", "label": "2.5G Ethernet / Wi-Fi 7"},
                {"from": "router", "to": "ntd", "label": "QoS High Priority Queue"},
                {"from": "ntd", "to": "game", "label": "Fast NBN Path"}
            ]
        }

        mermaid = (
            "graph LR\n"
            "  PC[Omarchy Gaming PC] -->|2.5G LAN / Wi-Fi 7| BE550[Archer BE550 HomeShield QoS]\n"
            "  BE550 -->|Prioritized Queue| NTD[NBN Optical NTD]\n"
            "  NTD -->|AussieBB Peering| GameServer[Game Server < 15ms]"
        )

        return {
            "category": "Gaming & Latency Optimization",
            "goal": goal,
            "summary": "Optimizing gaming latency and jitter on your Archer BE550 Wi-Fi 7 connection.",
            "warnings": warnings,
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "highlight_nodes": ["192.168.0.1", host.get("ip", "192.168.0.5")],
            "best_practices": [
                "Always play on 5 GHz, 6 GHz, or wired Ethernet; avoid 2.4 GHz for gaming.",
                "Ensure your PC is not roaming to the Netgear EX6250v2 extender when in range of the main BE550 router.",
                "Aussie Broadband offers low latency with Brisbane peering; average ping to Cloudflare 1.1.1.1 should be ~10-25ms."
            ]
        }

    def _solve_media_streaming(self, goal: str, topology: Dict[str, Any]) -> Dict[str, Any]:
        devices = topology.get("devices", [])
        host = topology.get("host", {})
        tvs = [d for d in devices if d.get("category") == "smart_tv" or "TV" in d.get("name", "")]
        tv_names = ", ".join([f"{d.get('name')} ({d.get('ip')})" for d in tvs]) if tvs else "Bedroom TV & Loft TV"

        steps = [
            {
                "step": 1,
                "title": "Install Jellyfin on Omarchy Host",
                "details": f"Target Google Cast Devices: **{tv_names}**.\nInstall Jellyfin Server and Web frontend:",
                "command": "sudo pacman -S jellyfin-server jellyfin-web && sudo systemctl enable --now jellyfin"
            },
            {
                "step": 2,
                "title": "Allow Jellyfin Port in Firewall",
                "details": "Allow incoming media streams on port 8096:",
                "command": "sudo ufw allow 8096/tcp && sudo ufw reload"
            },
            {
                "step": 3,
                "title": "Cast to Bedroom TV & Loft TV",
                "details": f"1. Open **http://{host.get('ip')}:8096** in your browser.\n"
                           "2. Add your media libraries.\n"
                           "3. Click the **Cast icon** in Jellyfin Web or Chromium and choose **Bedroom TV** or **Loft TV** for instant 4K playback.",
                "command": None
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "Media Streaming Data Flow",
            "nodes": [
                {"id": "jellyfin", "label": "Jellyfin Media Server", "sub": f"{host.get('ip', '192.168.0.5')}:8096", "icon": "🍿", "color": "#9ece6a"},
                {"id": "router", "label": "Archer BE550 (Wi-Fi 7)", "sub": "High Throughput 5GHz", "icon": "📡", "color": "#7dcfff"},
                {"id": "tv1", "label": "Bedroom TV (Chromecast)", "sub": "192.168.0.153 (Port 8009)", "icon": "📺", "color": "#e0af68"},
                {"id": "tv2", "label": "Loft TV (Chromecast)", "sub": "192.168.0.188 (Port 8009)", "icon": "📺", "color": "#e0af68"}
            ],
            "links": [
                {"from": "jellyfin", "to": "router", "label": "Direct H.264/HEVC Stream"},
                {"from": "router", "to": "tv1", "label": "Google Cast"},
                {"from": "router", "to": "tv2", "label": "Google Cast"}
            ]
        }

        mermaid = (
            "graph TD\n"
            "  MediaServer[Jellyfin Server :8096] -->|High-Bitrate 5GHz| Router[Archer BE550]\n"
            "  Router -->|Cast Protocol :8009| TV1[Bedroom TV]\n"
            "  Router -->|Cast Protocol :8009| TV2[Loft TV]"
        )

        return {
            "category": "Home Media Server & Streaming",
            "goal": goal,
            "summary": f"Setup Jellyfin media streaming tailored for your detected Chromecast TVs ({tv_names}).",
            "warnings": [],
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "highlight_nodes": [d.get("ip") for d in tvs if d.get("ip")] + [host.get("ip", "192.168.0.5")],
            "best_practices": [
                "Jellyfin supports hardware transcoding with Intel QuickSync or NVIDIA NVENC.",
                "Keep the media server wired to the Archer BE550 2.5G LAN ports for stutter-free 4K Bitrate streaming."
            ]
        }

    def _solve_mesh_extender(self, goal: str, topology: Dict[str, Any]) -> Dict[str, Any]:
        extender = next((d for d in topology.get("devices", []) if d.get("category") == "extender"), None)
        ext_ip = extender.get("ip", "192.168.0.76") if extender else "192.168.0.76"

        steps = [
            {
                "step": 1,
                "title": "Access Netgear EX6250v2 Admin Portal",
                "details": f"Open **[http://{ext_ip}](http://{ext_ip})** or `http://mywifiext.local` in your browser.",
                "command": None
            },
            {
                "step": 2,
                "title": "Optimal Setup: Access Point (AP) Mode via Ethernet Backhaul",
                "details": "1. Connect an Ethernet cable from the Archer BE550 2.5G port to the Netgear EX6250v2 Gigabit port.\n"
                           "2. In the Netgear portal, switch operation mode to **Access Point (AP) Mode**.\n"
                           "3. Match SSID and password to `BananaFarm`.\n"
                           "This eliminates wireless repeating degradation and provides full gigabit coverage!",
                "command": None
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "Extender Ethernet Backhaul vs Mesh",
            "nodes": [
                {"id": "router", "label": "Archer BE550 (Main)", "sub": "192.168.0.1", "icon": "📡", "color": "#7dcfff"},
                {"id": "extender", "label": "Netgear EX6250v2", "sub": f"{ext_ip} (AP Mode)", "icon": "📶", "color": "#7aa2f7"},
                {"id": "clients", "label": "Extended Area Devices", "sub": "Smart TVs & Phones", "icon": "📱", "color": "#9ece6a"}
            ],
            "links": [
                {"from": "router", "to": "extender", "label": "Cat6 Ethernet Backhaul (1Gbps)"},
                {"from": "extender", "to": "clients", "label": "FastLane 5GHz Wireless"}
            ]
        }

        mermaid = (
            "graph LR\n"
            "  Router[Archer BE550 2.5G LAN] ===|Cat6 Ethernet Backhaul 1Gbps| Extender[Netgear EX6250v2 AP Mode]\n"
            "  Extender -.->|Seamless Roaming Wi-Fi| Clients[Smart TVs & Mobile Devices]"
        )

        return {
            "category": "Mesh & Extender Optimization",
            "goal": goal,
            "summary": "Configuring your Netgear EX6250v2 extender for seamless performance with the TP-Link Archer BE550.",
            "warnings": [],
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "highlight_nodes": ["192.168.0.1", ext_ip],
            "best_practices": [
                "Place the extender roughly halfway between the Archer BE550 and your dead zone.",
                "Ethernet AP mode provides 100% full speed with zero jitter."
            ]
        }

    def _solve_remote_access(self, goal: str, topology: Dict[str, Any]) -> Dict[str, Any]:
        steps = [
            {
                "step": 1,
                "title": "Install Tailscale on Omarchy (CGNAT Bypass)",
                "details": "Because Aussie Broadband uses CGNAT (`100.91.128.1`), Tailscale establishes secure encrypted WireGuard tunnels using peer-to-peer NAT traversal without opening any router ports.",
                "command": "sudo pacman -S tailscale && sudo systemctl enable --now tailscaled && sudo tailscale up"
            },
            {
                "step": 2,
                "title": "Enable Subnet Routing (Access Entire Home LAN)",
                "details": "Advertise the entire home subnet so you can reach your Archer BE550 router (192.168.0.1) or cameras while away:",
                "command": "sudo tailscale up --advertise-routes=192.168.0.0/24"
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "Tailscale Remote Access via CGNAT Traversal",
            "nodes": [
                {"id": "phone", "label": "Travel Laptop / Phone", "sub": "Outside Network (4G/5G)", "icon": "📱", "color": "#bb9af7"},
                {"id": "derp", "label": "Tailscale STUN / DERP", "sub": "P2P NAT Traversal", "icon": "🔒", "color": "#e0af68"},
                {"id": "host", "label": "Omarchy Subnet Router", "sub": "192.168.0.5", "icon": "💻", "color": "#9ece6a"},
                {"id": "lan", "label": "Home Network LAN", "sub": "192.168.0.0/24 (Router & Cameras)", "icon": "📡", "color": "#7dcfff"}
            ],
            "links": [
                {"from": "phone", "to": "derp", "label": "Encrypted WireGuard"},
                {"from": "derp", "to": "host", "label": "CGNAT Punch-through"},
                {"from": "host", "to": "lan", "label": "Subnet Access"}
            ]
        }

        mermaid = (
            "graph LR\n"
            "  Remote[Travel Device / Phone] -->|WireGuard Tunnel| STUN[Tailscale NAT Punchthrough]\n"
            "  STUN -->|CGNAT Traversal| Omarchy[Omarchy Subnet Router 192.168.0.5]\n"
            "  Omarchy --> LAN[Home LAN 192.168.0.0/24]"
        )

        return {
            "category": "Remote Access & VPN",
            "goal": goal,
            "summary": "Zero-config remote access to your home network bypassing Aussie Broadband CGNAT.",
            "warnings": [],
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "highlight_nodes": ["192.168.0.1", topology.get("host", {}).get("ip", "192.168.0.5")],
            "best_practices": ["Tailscale uses WireGuard under the hood for maximum speed and security."]
        }

    def _solve_security_iot(self, goal: str, topology: Dict[str, Any]) -> Dict[str, Any]:
        steps = [
            {
                "step": 1,
                "title": "Enable IoT Network on TP-Link Archer BE550",
                "details": "1. Open **[https://192.168.0.1](https://192.168.0.1)**.\n"
                           "2. Go to **Wireless > IoT Network**.\n"
                           "3. Enable the IoT network with a distinct SSID (e.g. `BananaFarm-IoT`).\n"
                           "4. Enable device isolation so smart devices, cameras, and IoT cannot reach your personal PC.",
                "command": None
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "Archer BE550 IoT Network Isolation",
            "nodes": [
                {"id": "iot", "label": "Smart Cams / IoT", "sub": "Isolated IoT SSID", "icon": "🔌", "color": "#e0af68"},
                {"id": "router", "label": "Archer BE550 Firewall", "sub": "VLAN & Device Isolation", "icon": "📡", "color": "#7dcfff"},
                {"id": "host", "label": "Omarchy Workstation", "sub": "Secure Private LAN", "icon": "💻", "color": "#9ece6a"}
            ],
            "links": [
                {"from": "iot", "to": "router", "label": "Restricted Internet Only"},
                {"from": "router", "to": "host", "label": "Traffic Blocked (Protected)"}
            ]
        }

        mermaid = (
            "graph TD\n"
            "  IoT[Smart Cameras & IoT] -->|Isolated SSID| BE550[Archer BE550 Firewall]\n"
            "  BE550 -->|Internet Only| WAN[Internet]\n"
            "  BE550 -.-x|Blocked Lateral Access| Workstation[Omarchy Workstation 192.168.0.5]"
        )

        return {
            "category": "Network Security & IoT Isolation",
            "goal": goal,
            "summary": "Securing your network and isolating smart devices using Archer BE550 features.",
            "warnings": [],
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "highlight_nodes": ["192.168.0.1"],
            "best_practices": ["Never connect unverified smart appliances or cheap cameras to your main LAN."]
        }

    def _solve_general(self, goal: str, topology: Dict[str, Any]) -> Dict[str, Any]:
        router = topology.get("router", {})
        wan = topology.get("wan", {})
        host = topology.get("host", {})
        
        return {
            "category": "Network Setup & Troubleshooting",
            "goal": goal,
            "summary": f"Tailored configuration guidance for your {router.get('name', 'TP-Link Archer BE550')} on {wan.get('isp', 'Aussie Broadband')}.",
            "warnings": [
                {
                    "type": "tip",
                    "title": "Active Network Environment",
                    "text": f"Gateway: {router.get('name')} (192.168.0.1), ISP: {wan.get('isp')} (CGNAT Active), Workstation: {host.get('ip')} ({host.get('wifi', {}).get('ssid')})."
                }
            ],
            "steps": [
                {
                    "step": 1,
                    "title": "Inspect Gateway Router Settings",
                    "details": f"Open **[https://192.168.0.1](https://192.168.0.1)** to inspect wireless bands, DHCP reservations, and firewall rules.",
                    "command": None
                }
            ],
            "visual_diagram": {
                "type": "flowchart",
                "title": "Network Hierarchy",
                "nodes": [
                    {"id": "wan", "label": wan.get("isp", "Aussie Broadband"), "sub": "NBN Upstream", "icon": "🌐", "color": "#bb9af7"},
                    {"id": "router", "label": "Archer BE550", "sub": "192.168.0.1", "icon": "📡", "color": "#7dcfff"},
                    {"id": "host", "label": "Omarchy PC", "sub": host.get("ip", "192.168.0.5"), "icon": "💻", "color": "#9ece6a"}
                ],
                "links": [
                    {"from": "wan", "to": "router", "label": "NBN 2.5G WAN"},
                    {"from": "router", "to": "host", "label": "Wi-Fi 7 / 5GHz"}
                ]
            },
            "mermaid": (
                "graph LR\n"
                "  WAN[Aussie Broadband NBN] --> Router[Archer BE550 v2]\n"
                "  Router --> Host[Omarchy Linux Workstation]"
            ),
            "highlight_nodes": ["192.168.0.1", host.get("ip", "192.168.0.5")],
            "best_practices": ["Configure your Mistral AI API key or OpenRouter API key in Settings to unlock live customized reasoning."]
        }
