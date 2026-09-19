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
    {"id": "deepseek/deepseek-v4-flash-0731:free", "name": "DeepSeek V4 Flash (Free & Fast)"},
    {"id": "nvidia/nemotron-3.5-lightning:free", "name": "NVIDIA Nemotron 3.5 Lightning (Free)"},
    {"id": "liquid/lfm-2.5-2.6b:free", "name": "Liquid LFM 2.5 (Free & Ultra Fast)"},
    {"id": "poolside/laguna-s-2.1:free", "name": "Laguna S 2.1 (Free)"},
    {"id": "qwen/qwen3.8-27b:free", "name": "Qwen 3.8 27B (Free)"}
]

FALLBACK_OPENROUTER_FREE_MODELS = [
    "deepseek/deepseek-v4-flash-0731:free",
    "nvidia/nemotron-3.5-lightning:free",
    "liquid/lfm-2.5-2.6b:free"
]

RECOMMENDED_MISTRAL_MODELS = [
    {"id": "mistral-small-latest", "name": "Mistral Small (Fast, Cost-Effective & Smart)"},
    {"id": "mistral-large-latest", "name": "Mistral Large (Flagship Reasoning & Networking)"},
    {"id": "codestral-latest", "name": "Codestral (Networking, Config & Code Specialized)"},
    {"id": "open-mistral-nemo", "name": "Mistral NeMo 12B (Fast Open Weights)"},
    {"id": "ministral-8b-latest", "name": "Ministral 8B (Ultra Low Latency Edge)"}
]

RECOMMENDED_GEMINI_MODELS = [
    {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash (Fast & Highly Capable)"},
    {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash (Production Fast)"},
    {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro (Flagship Reasoning)"}
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
        openrouter_model: Optional[str] = None,
        gemini_key: Optional[str] = None,
        gemini_model: Optional[str] = None
    ):
        cfg = load_config()
        self.ai_provider = ai_provider or cfg.get("ai_provider", "mistral" if cfg.get("mistral_api_key") else ("openrouter" if cfg.get("openrouter_api_key") else ("gemini" if cfg.get("gemini_api_key") else "local")))
        self.mistral_key = mistral_key or cfg.get("mistral_api_key") or os.environ.get("MISTRAL_API_KEY", "")
        self.mistral_model = mistral_model or cfg.get("mistral_model") or "mistral-small-latest"
        self.openrouter_key = openrouter_key or cfg.get("openrouter_api_key") or os.environ.get("OPENROUTER_API_KEY", "")
        self.openrouter_model = openrouter_model or cfg.get("openrouter_model") or "deepseek/deepseek-v4-flash-0731:free"
        self.gemini_key = gemini_key or cfg.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")
        self.gemini_model = gemini_model or cfg.get("gemini_model") or "gemini-2.0-flash"

    def set_config(
        self,
        ai_provider: Optional[str] = None,
        mistral_key: Optional[str] = None,
        mistral_model: Optional[str] = None,
        openrouter_key: Optional[str] = None,
        openrouter_model: Optional[str] = None,
        gemini_key: Optional[str] = None,
        gemini_model: Optional[str] = None
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
        if gemini_key is not None:
            self.gemini_key = gemini_key
            cfg["gemini_api_key"] = gemini_key
        if gemini_model is not None:
            self.gemini_model = gemini_model
            cfg["gemini_model"] = gemini_model
        save_config(cfg)

    def solve(
        self,
        goal: str,
        topology: Dict[str, Any],
        diagnostic_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Produce a tailored solution for the user's problem.
        Checks active AI provider (Gemini, Mistral AI, or OpenRouter), queries LLM with full
        topology, user-configured device context, and diagnostic telemetry, and falls back to
        the local expert rules.
        """
        cfg = load_config()
        provider = self.ai_provider or cfg.get("ai_provider", "local")

        # 1. Gemini Provider
        if provider == "gemini" and self.gemini_key:
            llm_result = self._solve_with_gemini(goal, topology, diagnostic_context)
            if llm_result:
                return llm_result

        # 2. Mistral AI Provider
        elif provider == "mistral" and self.mistral_key:
            llm_result = self._solve_with_mistral(goal, topology, diagnostic_context)
            if llm_result:
                return llm_result

        # 3. OpenRouter Provider
        elif provider == "openrouter" and self.openrouter_key:
            llm_result = self._solve_with_openrouter(goal, topology, diagnostic_context)
            if llm_result:
                return llm_result

        # 4. Local expert rule-based solver
        return self._solve_with_local_expert(goal, topology, diagnostic_context)

    def _build_system_prompt(
        self,
        topology: Dict[str, Any],
        diagnostic_context: Optional[Dict[str, Any]] = None
    ) -> str:
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

        diag_section = ""
        if diagnostic_context:
            diag_items = []
            if diagnostic_context.get("tool_results"):
                diag_items.append(f"LIVE DIAGNOSTIC TOOL FINDINGS:\n{json.dumps(diagnostic_context['tool_results'], indent=2)}")
            if diagnostic_context.get("retrieved_docs"):
                rdoc = diagnostic_context["retrieved_docs"]
                content_sample = rdoc.get("content", "")[:2000]
                diag_items.append(f"RELEVANT TECHNICAL DOCUMENTATION ({rdoc.get('title', 'Guide')}):\n{content_sample}")
            if diagnostic_context.get("conversation_history"):
                diag_items.append(f"RECENT CONVERSATION HISTORY:\n{json.dumps(diagnostic_context['conversation_history'], indent=2)}")
            if diag_items:
                diag_section = "\n\n" + "\n\n".join(diag_items) + "\n"

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
            f"- Discovered Devices & User Configured Settings: {json.dumps(device_context_list, indent=1)}"
            f"{diag_section}\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Base your diagnosis and solutions DIRECTLY on the live topology, connected devices, and diagnostic tool findings.\n"
            "2. If tool results show latency/jitter numbers or open ports, cite them explicitly (e.g. 'Ping to gateway is 0.4ms', 'Open port 554 RTSP found on 192.168.0.136').\n"
            "3. Provide explicit, concrete, step-by-step instructions with exact Archer BE550 GUI menu paths (e.g. 'Advanced > Network > Internet > Advanced Settings') and copyable Linux terminal commands where appropriate.\n"
            "4. Under Aussie Broadband CGNAT (100.91.128.1), explain how to bypass it (MyAussie app 1-click opt-out or Tailscale peer-to-peer WireGuard tunnel).\n"
            "5. Always generate BOTH rich visual diagrams (nodes & links flowchart and valid Mermaid code) and concrete numbered steps with markdown formatting.\n"
            "6. Return raw valid JSON only matching the schema below.\n\n"
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

    def _solve_with_mistral(
        self,
        goal: str,
        topology: Dict[str, Any],
        diagnostic_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Query official Mistral AI API with JSON mode and visual diagram enforcement."""
        try:
            url = "https://api.mistral.ai/v1/chat/completions"
            system_prompt = self._build_system_prompt(topology, diagnostic_context)
            
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

    def _solve_with_openrouter(
        self,
        goal: str,
        topology: Dict[str, Any],
        diagnostic_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Query OpenRouter API using free or selected model with fallback retry."""
        models_to_try = [self.openrouter_model] if self.openrouter_model else []
        for fb in FALLBACK_OPENROUTER_FREE_MODELS:
            if fb not in models_to_try:
                models_to_try.append(fb)

        system_prompt = self._build_system_prompt(topology, diagnostic_context)
        url = "https://openrouter.ai/api/v1/chat/completions"

        for model in models_to_try:
            try:
                payload = {
                    "model": model,
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

                with urllib.request.urlopen(req, timeout=22) as res:
                    body = json.loads(res.read().decode("utf-8"))
                    choice = body["choices"][0]["message"]["content"]
                    parsed = extract_json_from_text(choice)
                    if parsed:
                        parsed["ai_engine"] = f"OpenRouter ({model})"
                        if model != self.openrouter_model:
                            self.openrouter_model = model
                            cfg = load_config()
                            cfg["openrouter_model"] = model
                            save_config(cfg)
                        return parsed
            except Exception as e:
                print(f"[NetMap] OpenRouter model '{model}' query failed ({e}). Trying fallback...")
                continue
        return None

    def _solve_with_gemini(
        self,
        goal: str,
        topology: Dict[str, Any],
        diagnostic_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Query Google Gemini API directly."""
        try:
            model = self.gemini_model or "gemini-2.0-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
            system_prompt = self._build_system_prompt(topology, diagnostic_context)
            prompt_text = f"{system_prompt}\n\nUser Problem/Goal: {goal}\n\nRespond strictly with valid JSON conforming to the schema."
            
            payload = {
                "contents": [
                    {
                        "parts": [{"text": prompt_text}]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=22) as res:
                body = json.loads(res.read().decode("utf-8"))
                choice = body["candidates"][0]["content"]["parts"][0]["text"]
                parsed = extract_json_from_text(choice)
                if parsed:
                    parsed["ai_engine"] = f"Google Gemini ({model})"
                    return parsed
        except Exception as e:
            print(f"[NetMap] Google Gemini API query failed ({e}). Falling back to next solver.")
        return None

    def _solve_with_local_expert(
        self,
        goal: str,
        topology: Dict[str, Any],
        diagnostic_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Comprehensive local rule-based expert solver."""
        goal_lower = goal.lower().strip()
        
        if any(w in goal_lower for w in ["camera", "nvr", "cctv", "rtsp", "onvif", "tvpc", "surveillance", "video recorder"]):
            res = self._solve_cameras_nvr(goal, topology, diagnostic_context)
        elif any(w in goal_lower for w in ["port forward", "game server", "minecraft", "palworld", "valheim", "host a server", "host server", "forward port", "open port"]):
            res = self._solve_port_forwarding(goal, topology, diagnostic_context)
        elif any(w in goal_lower for w in ["ping", "lag", "latency", "bufferbloat", "gaming", "delay", "jitter", "packet loss", "qos"]):
            res = self._solve_gaming_latency(goal, topology, diagnostic_context)
        elif any(w in goal_lower for w in ["stream", "plex", "jellyfin", "media server", "bedroom tv", "loft tv", "movies", "tv", "cast"]):
            res = self._solve_media_streaming(goal, topology, diagnostic_context)
        elif any(w in goal_lower for w in ["extender", "mesh", "ex6250", "repeater", "ap mode"]):
            res = self._solve_mesh_extender(goal, topology, diagnostic_context)
        elif any(w in goal_lower for w in ["wifi slow", "slow in", "kitchen", "dead zone", "weak signal", "wifi coverage", "range", "room", "signal"]):
            res = self._solve_wifi_coverage_deadzones(goal, topology, diagnostic_context)
        elif any(w in goal_lower for w in ["spectrum", "channel", "interference", "congestion", "frequency", "crowded", "6ghz", "320mhz", "mlo"]):
            res = self._solve_wifi_spectrum_interference(goal, topology, diagnostic_context)
        elif any(w in goal_lower for w in ["dns", "domain", "lookup", "resolv", "cant open website", "slow loading", "cloudflare", "quad9", "1.1.1.1"]):
            res = self._solve_dns_issues(goal, topology, diagnostic_context)
        elif any(w in goal_lower for w in ["smart light", "smart plug", "tuya", "smart home", "wont connect", "pairing", "esp8266", "shelly", "smart switch"]):
            res = self._solve_smart_home_iot(goal, topology, diagnostic_context)
        elif any(w in goal_lower for w in ["printer", "airprint", "brother", "epson", "canon", "hp", "cups", "avahi", "scanner"]):
            res = self._solve_network_printer(goal, topology, diagnostic_context)
        elif any(w in goal_lower for w in ["drops", "disconnecting", "unstable", "ip conflict", "renew", "lease", "keeps losing connection"]):
            res = self._solve_device_drops(goal, topology, diagnostic_context)
        elif any(w in goal_lower for w in ["vpn", "wireguard", "remote access", "access outside", "away from home", "tailscale"]):
            res = self._solve_remote_access(goal, topology, diagnostic_context)
        elif any(w in goal_lower for w in ["secure", "isolate", "iot", "guest", "firewall", "hacked", "security", "vlan"]):
            res = self._solve_security_iot(goal, topology, diagnostic_context)
        else:
            res = self._solve_general(goal, topology, diagnostic_context)
            
        res["ai_engine"] = "Local Network Expert"
        return res

    def _solve_cameras_nvr(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

    def _solve_port_forwarding(
        self,
        goal: str,
        topology: Dict[str, Any],
        diagnostic_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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

    def _solve_gaming_latency(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        host = topology.get("host", {})
        warnings = []
        if diagnostic_context and diagnostic_context.get("tool_results", {}).get("ping"):
            p = diagnostic_context["tool_results"]["ping"]
            avg = p.get("avg", "14.2")
            jitter = p.get("mdev", "0.8")
            warnings.append({
                "type": "tip",
                "title": f"Live Gaming Ping to {p.get('host', 'Cloudflare 1.1.1.1')}: {avg} ms",
                "text": f"Measured live latency: Avg {avg} ms, Min {p.get('min', '-')} ms, Max {p.get('max', '-')} ms, Jitter ±{jitter} ms (Packet loss: {p.get('packet_loss', '0%')})."
            })
        if diagnostic_context and diagnostic_context.get("tool_results", {}).get("bufferbloat"):
            bb = diagnostic_context["tool_results"]["bufferbloat"]
            warnings.append({
                "type": "warning" if bb.get("grade") in ["D", "F"] else "tip",
                "title": f"Bufferbloat Benchmark: Grade {bb.get('grade', 'B')}",
                "text": f"Idle latency: {bb.get('idle_latency_ms', '-')} ms | Loaded latency: {bb.get('loaded_latency_ms', '-')} ms | Bufferbloat delay: +{bb.get('bufferbloat_ms', '-')} ms."
            })
        warnings.append({
            "type": "tip",
            "title": "Netgear EX6250v2 Extender Warning",
            "text": "Your network contains a Netgear EX6250v2 extender. In standard repeater mode, traffic passing through an extender suffers a 50% throughput penalty and 10-25ms jitter spikes. Make sure your gaming device connects directly to the Archer BE550."
        })

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

    def _solve_media_streaming(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

    def _solve_mesh_extender(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

    def _solve_remote_access(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

    def _solve_security_iot(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

    def _solve_wifi_coverage_deadzones(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        host = topology.get("host", {})
        router = topology.get("router", {})
        extender = next((d for d in topology.get("devices", []) if d.get("category") == "extender"), None)
        ext_ip = extender.get("ip", "192.168.0.76") if extender else "192.168.0.76"

        warnings = [
            {
                "type": "caution",
                "title": "High Frequency Attenuation (5 GHz / 6 GHz Walls)",
                "text": "The Archer BE550 broadcasts Wi-Fi 7 across 2.4 GHz, 5 GHz, and 6 GHz. While 5 GHz & 6 GHz offer gigabit throughput, their high frequency waves suffer rapid attenuation through walls, tiles, and kitchen appliances (refrigerators, microwaves). 2.4 GHz penetrates solid barriers much better."
            }
        ]

        steps = [
            {
                "step": 1,
                "title": "Check Live Wi-Fi Signal Strength & Current Connected Band",
                "details": "Run this command on your Omarchy workstation or laptop to measure current RSSI signal dBm and frequency band:\n"
                           "- **-30 to -65 dBm**: Excellent to Good signal.\n"
                           "- **-70 to -85 dBm**: Weak signal, prone to packet drops and high jitter.",
                "command": "nmcli dev wifi list | grep -E 'SSID|BananaFarm|\\*' || iw dev $(ip route show default | awk '{print $5}') link"
            },
            {
                "step": 2,
                "title": "Relocate Netgear EX6250v2 Extender (Halfway Rule)",
                "details": f"Your detected Netgear EX6250v2 is currently at `{ext_ip}`.\n"
                           "**Critical Mistake to Avoid**: Do NOT place the extender directly inside the dead zone / kitchen! It will receive a degraded signal and retransmit that slow signal.\n"
                           "**Correct Placement**: Place the extender exactly halfway between your main Archer BE550 router and the kitchen/dead zone, where it still gets at least 3 signal bars from the router.",
                "command": None
            },
            {
                "step": 3,
                "title": "Maximum Speed: Switch Netgear Extender to Access Point (AP) Mode",
                "details": "When running as a wireless repeater, the extender cuts throughput by 50% due to half-duplex retransmission.\n"
                           "1. Run an Ethernet Cat6 cable from the Archer BE550 2.5G port to the Netgear EX6250v2.\n"
                           f"2. Log in at **[http://{ext_ip}](http://{ext_ip})** (or `http://mywifiext.local`).\n"
                           "3. Switch mode from Extender to **Access Point (AP) Mode**.\n"
                           "4. Match SSID to `BananaFarm` with the same password for seamless roaming with 100% gigabit speeds.",
                "command": None
            },
            {
                "step": 4,
                "title": "Adjust Archer BE550 Transmit Power & Channel Width",
                "details": "1. Open the Archer BE550 Web GUI: **[https://192.168.0.1](https://192.168.0.1)**.\n"
                           "2. Go to **Wireless > Wireless Settings**.\n"
                           "3. Ensure **Transmit Power** is set to **High** on 2.4 GHz, 5 GHz, and 6 GHz.\n"
                           "4. Set 2.4 GHz Channel Width to **20 MHz** (prevents adjacent channel interference).\n"
                           "5. Enable **Smart Connect** if you want client devices to roam automatically between bands.",
                "command": None
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "Wi-Fi Range & Dead Zone Optimization Architecture",
            "nodes": [
                {"id": "router", "label": "Archer BE550 (Main)", "sub": "192.168.0.1 (High Power)", "icon": "📡", "color": "#7dcfff"},
                {"id": "extender", "label": "Netgear EX6250v2", "sub": f"Halfway Point ({ext_ip})", "icon": "📶", "color": "#7aa2f7"},
                {"id": "deadzone", "label": "Kitchen / Dead Zone", "sub": "Smart Devices & Phones", "icon": "🍳", "color": "#9ece6a"}
            ],
            "links": [
                {"from": "router", "to": "extender", "label": "Cat6 Backhaul (or 5GHz Link)"},
                {"from": "extender", "to": "deadzone", "label": "Full Coverage Wi-Fi"}
            ]
        }

        mermaid = (
            "graph LR\n"
            "  BE550[Archer BE550 192.168.0.1] -->|Cat6 Ethernet Backhaul / 5GHz| EX6250[Netgear EX6250v2 AP Mode]\n"
            "  EX6250 -->|Clean 5GHz/2.4GHz Signal| Kitchen[Kitchen / Remote Room Devices]"
        )

        router_config_card = {
            "page": "Wireless > Wireless Settings",
            "fields": [
                {"label": "2.4 GHz Transmit Power", "value": "High (Channel Width 20 MHz)"},
                {"label": "5 GHz Transmit Power", "value": "High (Channel Width 80/160 MHz)"},
                {"label": "6 GHz Band", "value": "Enabled (Wi-Fi 7 320 MHz MLO)"},
                {"label": "Smart Connect", "value": "Enabled (or Dedicated 5G/6G SSID)"}
            ]
        }

        return {
            "category": "Wi-Fi Coverage & Signal Optimization",
            "goal": goal,
            "summary": "Step-by-step instructions to eliminate Wi-Fi dead zones, optimize extender placement, and tune the Archer BE550 transmit power.",
            "warnings": warnings,
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "router_config_card": router_config_card,
            "highlight_nodes": ["192.168.0.1", ext_ip, host.get("ip", "192.168.0.5")],
            "best_practices": [
                "Place the extender roughly halfway between router and dead zone, never in the dead zone itself.",
                "Ethernet AP mode provides 100% full speed with zero packet retransmission overhead.",
                "For appliances like smart fridges, connect them exclusively to the 2.4 GHz band."
            ]
        }

    def _solve_wifi_spectrum_interference(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        spec = diagnostic_context.get("tool_results", {}).get("wifi_spectrum", {}) if diagnostic_context else {}
        clean_ch = spec.get("recommended_channels", [1, 6, 11, 36, 149])
        
        warnings = [
            {
                "type": "tip",
                "title": "Wi-Fi Channel Crowding & Overlap Analysis",
                "text": f"Surrounding Wi-Fi survey detected {spec.get('total_networks_detected', 8)} nearby wireless networks. In urban areas, neighbor routers on 2.4 GHz channels 2-5 or 7-10 cause destructive co-channel interference. Recommended clean channels: {clean_ch}."
            }
        ]

        steps = [
            {
                "step": 1,
                "title": "Set 2.4 GHz Band to Non-Overlapping Channels (1, 6, or 11)",
                "details": "1. Open **[https://192.168.0.1](https://192.168.0.1)**.\n"
                           "2. Go to **Wireless > Wireless Settings > 2.4 GHz**.\n"
                           "3. Set **Channel Width** to `20 MHz` (never use 40 MHz on 2.4 GHz as it occupies 80% of the entire spectrum).\n"
                           f"4. Set **Channel** to `{clean_ch[0] if clean_ch else 6}` (avoid Auto if neighbor routers crowd the band).",
                "command": None
            },
            {
                "step": 2,
                "title": "Configure Clean 5 GHz DFS / UNII-3 Channels",
                "details": "1. Go to **Wireless > Wireless Settings > 5 GHz**.\n"
                           "2. Set **Channel Width** to `80 MHz` or `160 MHz`.\n"
                           "3. Choose channel `36` (UNII-1) or `149` (UNII-3). If living away from airports and radar, enabling **DFS Channels (52-144)** unlocks completely uncongested spectrum.",
                "command": None
            },
            {
                "step": 3,
                "title": "Enable Wi-Fi 7 Multi-Link Operation (MLO) & 320 MHz Channels",
                "details": "The TP-Link Archer BE550 supports **Wi-Fi 7 MLO**:\n"
                           "1. In the router portal, navigate to **Wireless > MLO Network**.\n"
                           "2. Enable **MLO (Multi-Link Operation)**.\n"
                           "3. This binds 5 GHz and 6 GHz simultaneously, transmitting packets across both bands concurrently so that momentary interference on one band produces zero lag on the other.",
                "command": None
            },
            {
                "step": 4,
                "title": "Live Wireless Channel Scan via Linux Terminal",
                "details": "Inspect all neighboring BSSIDs, frequencies, and signal strengths directly from your Omarchy workstation:",
                "command": "sudo iw dev $(ip route show default | awk '{print $5}') scan | grep -E 'SSID|freq:|signal:|DS Parameter set' | head -n 30"
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "Archer BE550 Tri-Band Spectrum Allocation",
            "nodes": [
                {"id": "b24", "label": "2.4 GHz (Legacy & IoT)", "sub": "Ch 1, 6, 11 (20 MHz)", "icon": "📶", "color": "#e0af68"},
                {"id": "b5", "label": "5 GHz (High Speed)", "sub": "Ch 36-48 / 149-161 (160 MHz)", "icon": "⚡", "color": "#7dcfff"},
                {"id": "b6", "label": "6 GHz Wi-Fi 7 MLO", "sub": "Ch 37-197 (320 MHz Ultra Clean)", "icon": "🚀", "color": "#bb9af7"}
            ],
            "links": [
                {"from": "b24", "to": "b5", "label": "Band Steering"},
                {"from": "b5", "to": "b6", "label": "Wi-Fi 7 MLO Concurrent Aggregation"}
            ]
        }

        mermaid = (
            "graph TD\n"
            "  Router[Archer BE550 Tri-Band]\n"
            "  Router --> B24[2.4 GHz: Channel 1/6/11 @ 20MHz for IoT]\n"
            "  Router --> B5[5 GHz: Channel 36/149 @ 160MHz for PCs]\n"
            "  Router --> B6[6 GHz: PSC Channels @ 320MHz MLO for Wi-Fi 7]"
        )

        router_config_card = {
            "page": "Wireless > Wireless Settings & MLO Network",
            "fields": [
                {"label": "2.4 GHz Channel", "value": "1, 6, or 11 (Width: 20 MHz)"},
                {"label": "5 GHz Channel", "value": "36 or 149 (Width: 80/160 MHz)"},
                {"label": "6 GHz Channel Width", "value": "320 MHz"},
                {"label": "MLO Network", "value": "Enabled (BananaFarm-MLO)"}
            ]
        }

        return {
            "category": "Wi-Fi Spectrum & Interference Tuning",
            "goal": goal,
            "summary": "Surveillance and spectrum optimization for clean, non-overlapping channels on your Archer BE550 tri-band setup.",
            "warnings": warnings,
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "router_config_card": router_config_card,
            "highlight_nodes": ["192.168.0.1"],
            "best_practices": [
                "Never use 40 MHz channel width on 2.4 GHz; it creates overlapping interference with all neighboring networks.",
                "Wi-Fi 7 MLO enables simultaneous transmission on 5 GHz + 6 GHz for zero-lag gaming and streaming."
            ]
        }

    def _solve_dns_issues(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        wan = topology.get("wan", {})
        host = topology.get("host", {})
        
        warnings = [
            {
                "type": "tip",
                "title": "Upgrade from Unencrypted ISP DNS Resolvers",
                "text": "By default, Aussie Broadband routes DNS through ISP resolvers (100.91.x.x). Switching to Cloudflare (1.1.1.1) or Quad9 (9.9.9.9) reduces lookup times from ~45ms down to <10ms and prevents ISP DNS hijacking and logging."
            }
        ]

        steps = [
            {
                "step": 1,
                "title": "Configure High-Speed DNS on TP-Link Archer BE550",
                "details": "Configure custom resolvers for your entire local network in one place:\n"
                           "1. Open **[https://192.168.0.1](https://192.168.0.1)** in your browser.\n"
                           "2. Navigate to **Advanced > Network > Internet**.\n"
                           "3. Scroll down and expand **Advanced Settings**.\n"
                           "4. Toggle **Primary DNS** to Manual and enter `1.1.1.1` (Cloudflare) or `9.9.9.9` (Quad9 malware blocking).\n"
                           "5. Toggle **Secondary DNS** to Manual and enter `1.0.0.1` (or `149.112.112.112`).\n"
                           "6. Click **Save**.",
                "command": None
            },
            {
                "step": 2,
                "title": "Benchmark DNS Query Latency on Omarchy",
                "details": "Test lookup speed comparing your gateway, Cloudflare, and Quad9:",
                "command": "dig @1.1.1.1 google.com | grep 'Query time' && dig @9.9.9.9 google.com | grep 'Query time'"
            },
            {
                "step": 3,
                "title": "Flush System DNS Resolver Cache",
                "details": "Flush cached DNS records on your Omarchy Linux workstation:",
                "command": "sudo resolvectl flush-caches && resolvectl status"
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "DNS Lookup Architecture: Fast Anycast Resolution",
            "nodes": [
                {"id": "client", "label": "Omarchy / Phone", "sub": "DNS Query (UDP/TCP 53)", "icon": "💻", "color": "#9ece6a"},
                {"id": "router", "label": "Archer BE550", "sub": "192.168.0.1 (Relay)", "icon": "📡", "color": "#7dcfff"},
                {"id": "dns", "label": "Cloudflare Anycast", "sub": "1.1.1.1 / 9.9.9.9 (<10ms)", "icon": "⚡", "color": "#bb9af7"}
            ],
            "links": [
                {"from": "client", "to": "router", "label": "Local DNS Query"},
                {"from": "router", "to": "dns", "label": "Sub-10ms Anycast Lookup"}
            ]
        }

        mermaid = (
            "graph LR\n"
            "  Client[Omarchy Client] -->|DNS Query Port 53| Router[Archer BE550 Gateway]\n"
            "  Router -->|Low-Latency Anycast| Cloudflare[Cloudflare 1.1.1.1 / Quad9 9.9.9.9]"
        )

        router_config_card = {
            "page": "Advanced > Network > Internet > Advanced Settings",
            "fields": [
                {"label": "Primary DNS", "value": "1.1.1.1 (Cloudflare Anycast)"},
                {"label": "Secondary DNS", "value": "1.0.0.1 (or 9.9.9.9 Quad9)"}
            ]
        }

        return {
            "category": "DNS & Domain Resolution",
            "goal": goal,
            "summary": "Configure fast Anycast DNS resolvers (1.1.1.1 / 9.9.9.9) on your Archer BE550 to eliminate lookup delay across all network devices.",
            "warnings": warnings,
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "router_config_card": router_config_card,
            "highlight_nodes": ["192.168.0.1", host.get("ip", "192.168.0.5")],
            "best_practices": [
                "Cloudflare 1.1.1.1 has Anycast servers located in Brisbane and Sydney with typical latencies < 10ms.",
                "Quad9 9.9.9.9 automatically blocks phishing and malware domains at the DNS resolver level."
            ]
        }

    def _solve_smart_home_iot(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        warnings = [
            {
                "type": "caution",
                "title": "2.4 GHz Only Chipset Limitation (ESP8266 / Tuya)",
                "text": "95% of smart home plugs, bulbs, and sensors use legacy 2.4 GHz Wi-Fi chips that cannot see 5 GHz or 6 GHz SSIDs, and will fail to pair if WPA3-Personal (SAE) or band-steering is enabled."
            }
        ]

        steps = [
            {
                "step": 1,
                "title": "Enable Dedicated IoT Network on Archer BE550",
                "details": "1. Open **[https://192.168.0.1](https://192.168.0.1)** in your browser.\n"
                           "2. Navigate to **Wireless > IoT Network**.\n"
                           "3. Toggle **IoT Network** to ON.\n"
                           "4. Network Name (SSID): Set to `BananaFarm-IoT`.\n"
                           "5. Security: Select **WPA2-Personal (AES)** (do not select WPA3).\n"
                           "6. Band: Select **2.4 GHz Only**.",
                "command": None
            },
            {
                "step": 2,
                "title": "Enable Device Isolation for IoT Security",
                "details": "In the same **Wireless > IoT Network** menu, check **Device Isolation**.\n"
                           "This ensures smart appliances can communicate out to the cloud for app controls, but are strictly blocked from scanning or attacking workstations on your primary LAN.",
                "command": None
            },
            {
                "step": 3,
                "title": "Pairing Tip: Connect Smartphone to 2.4 GHz IoT Network Temporarily",
                "details": "During initial discovery in the Tuya / Smart Life / Home Assistant app, ensure your phone is temporarily connected to `BananaFarm-IoT` so mDNS discovery packets can reach the device.",
                "command": None
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "Smart Home IoT Network Isolation",
            "nodes": [
                {"id": "iot", "label": "Smart Plugs & Bulbs", "sub": "BananaFarm-IoT (2.4GHz)", "icon": "💡", "color": "#e0af68"},
                {"id": "router", "label": "Archer BE550 Firewall", "sub": "Device Isolation Active", "icon": "📡", "color": "#7dcfff"},
                {"id": "pc", "label": "Workstation / LAN", "sub": "192.168.0.5 (Protected)", "icon": "💻", "color": "#9ece6a"}
            ],
            "links": [
                {"from": "iot", "to": "router", "label": "Internet Cloud Control Only"},
                {"from": "router", "to": "pc", "label": "Lateral Traffic Blocked"}
            ]
        }

        mermaid = (
            "graph TD\n"
            "  IoT[Smart Bulbs & Plugs] -->|Isolated 2.4GHz SSID| BE550[Archer BE550 IoT Network]\n"
            "  BE550 -->|Internet Control| Cloud[Smart App Cloud]\n"
            "  BE550 -.-x|Blocked Isolation| PC[Primary Workstations 192.168.0.5]"
        )

        router_config_card = {
            "page": "Wireless > IoT Network",
            "fields": [
                {"label": "IoT SSID", "value": "BananaFarm-IoT"},
                {"label": "Wireless Band", "value": "2.4 GHz Only"},
                {"label": "Security", "value": "WPA2-Personal (AES)"},
                {"label": "Device Isolation", "value": "Enabled"}
            ]
        }

        return {
            "category": "Smart Home & IoT Devices",
            "goal": goal,
            "summary": "Resolve IoT pairing failures by enabling a dedicated 2.4 GHz IoT Network with WPA2-Personal and Device Isolation on the Archer BE550.",
            "warnings": warnings,
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "router_config_card": router_config_card,
            "highlight_nodes": ["192.168.0.1"],
            "best_practices": [
                "Never connect smart bulbs or budget IoT cameras to your primary Wi-Fi network.",
                "Ensure WPA3 is disabled on the IoT SSID as older chips do not support SAE authentication."
            ]
        }

    def _solve_network_printer(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        host = topology.get("host", {})
        devices = topology.get("devices", [])
        printer = next((d for d in devices if d.get("category") == "printer" or "print" in d.get("name", "").lower()), None)
        pr_ip = printer.get("ip", "192.168.0.210") if printer else "192.168.0.210"

        steps = [
            {
                "step": 1,
                "title": "Assign Static DHCP Reservation in Archer BE550",
                "details": f"Network printers drop offline when their dynamic DHCP lease changes IP address:\n"
                           f"1. Open **[https://192.168.0.1](https://192.168.0.1)**.\n"
                           "2. Go to **Advanced > Network > DHCP Server > Address Reservation**.\n"
                           f"3. Click **Add**, find your printer ({pr_ip}), and lock it to a permanent static IP.",
                "command": None
            },
            {
                "step": 2,
                "title": "Verify AP Isolation is Disabled on Primary Wi-Fi",
                "details": "If **AP Isolation** is enabled, wireless clients cannot see the printer:\n"
                           "1. In the router portal, go to **Wireless > Wireless Settings**.\n"
                           "2. Ensure **AP Isolation** is **Disabled** on the 2.4 GHz and 5 GHz main bands.",
                "command": None
            },
            {
                "step": 3,
                "title": "Discover Printer via mDNS / Avahi on Omarchy",
                "details": "Use mDNS / Bonjour to search for broadcasted IPP, JetDirect (9100), or AirPrint services:",
                "command": "avahi-browse -art | grep -E 'printer|ipp|_pdl-datastream' || lpinfo -v"
            },
            {
                "step": 4,
                "title": "Test Raw Print Port Reachability",
                "details": "Verify TCP port 9100 (RAW) and port 631 (IPP) are accepting connections:",
                "command": f"nc -zv -w 2 {pr_ip} 9100 631"
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "Local Network Printer Discovery Pipeline",
            "nodes": [
                {"id": "pc", "label": "Omarchy / Mac / Phone", "sub": "CUPS / AirPrint", "icon": "💻", "color": "#9ece6a"},
                {"id": "router", "label": "Archer BE550", "sub": "DHCP Reserved IP", "icon": "📡", "color": "#7dcfff"},
                {"id": "printer", "label": "Network Printer", "sub": f"Static {pr_ip} (Port 9100)", "icon": "🖨️", "color": "#e0af68"}
            ],
            "links": [
                {"from": "pc", "to": "router", "label": "mDNS Discovery (Port 5353)"},
                {"from": "router", "to": "printer", "label": "IPP / JetDirect RAW Stream"}
            ]
        }

        mermaid = (
            "graph LR\n"
            f"  Client[Omarchy Workstation] -->|mDNS Avahi Discovery| Router[Archer BE550]\n"
            f"  Router -->|Port 9100 / 631 IPP| Printer[Network Printer {pr_ip}]"
        )

        router_config_card = {
            "page": "Advanced > Network > DHCP Server > Address Reservation",
            "fields": [
                {"label": "Device Name", "value": "Network Printer"},
                {"label": "Assigned IP", "value": pr_ip},
                {"label": "AP Isolation", "value": "Disabled (Wireless Settings)"}
            ]
        }

        return {
            "category": "Network Printer & Scanner Setup",
            "goal": goal,
            "summary": "Fix printer offline errors, set up permanent static IP reservations, and enable cross-device AirPrint/CUPS discovery.",
            "warnings": [],
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "router_config_card": router_config_card,
            "highlight_nodes": ["192.168.0.1", pr_ip],
            "best_practices": [
                "Always set a static DHCP reservation for printers to avoid IP reassignment after router reboots.",
                "Ensure both printer and PCs are on the main Wi-Fi band (not the isolated IoT band)."
            ]
        }

    def _solve_device_drops(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        host = topology.get("host", {})
        gw = host.get("gateway", "192.168.0.1")

        steps = [
            {
                "step": 1,
                "title": "Increase DHCP Lease Time to 48 Hours (2880 Minutes)",
                "details": "Frequent connection drops often occur when DHCP leases expire too quickly (e.g. 120 minutes):\n"
                           f"1. Open **[https://{gw}](https://{gw})** in your browser.\n"
                           "2. Go to **Advanced > Network > DHCP Server**.\n"
                           "3. Set **Address Lease Time** to `2880` minutes (48 hours).\n"
                           "4. Click **Save**.",
                "command": None
            },
            {
                "step": 2,
                "title": "Bind Problematic Device to Static IP Reservation",
                "details": "In the same menu under **Address Reservation**, click **Add** and reserve a static IP for the device experiencing disconnects.",
                "command": None
            },
            {
                "step": 3,
                "title": "Force DHCP Lease Renewal & Restart Network Manager",
                "details": "Flush existing IP configuration and request a clean DHCP lease:",
                "command": "sudo systemctl restart NetworkManager && ip route show"
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "DHCP Lease & Connection Stability Pipeline",
            "nodes": [
                {"id": "router", "label": "Archer BE550 DHCP Server", "sub": "Lease: 2880 min (48h)", "icon": "📡", "color": "#7dcfff"},
                {"id": "client", "label": "Client Device", "sub": "Static Reserved IP", "icon": "📱", "color": "#9ece6a"}
            ],
            "links": [
                {"from": "router", "to": "client", "label": "Stable DHCP ACK (No Conflict)"}
            ]
        }

        mermaid = (
            "graph LR\n"
            f"  Router[Archer BE550 DHCP 48h Lease] -->|Static Reserved IP| Client[Connected Client Device]"
        )

        return {
            "category": "Connection Stability & IP Management",
            "goal": goal,
            "summary": "Eliminate random connection drops by extending DHCP lease times and binding devices to permanent address reservations.",
            "warnings": [],
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "highlight_nodes": [gw],
            "best_practices": [
                "Avoid setting manual static IPs on devices directly; always use router DHCP address reservations instead."
            ]
        }

    def _solve_general(self, goal: str, topology: Dict[str, Any], diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        router = topology.get("router", {})
        wan = topology.get("wan", {})
        host = topology.get("host", {})
        devices = topology.get("devices", [])
        gw = host.get("gateway", "192.168.0.1")
        
        warnings = [
            {
                "type": "tip",
                "title": f"Live Network Telemetry: {len(devices)} Connected Devices",
                "text": f"Gateway: {router.get('name', 'Archer BE550')} ({gw}), Host IP: {host.get('ip', '192.168.0.5')} on interface {host.get('interface', 'wlan0')}, ISP: {wan.get('isp', 'Aussie Broadband')} (CGNAT: {'Active' if wan.get('cgnat_active', True) else 'Disabled'})."
            }
        ]

        steps = [
            {
                "step": 1,
                "title": "Verify Gateway & Upstream WAN Reachability",
                "details": "Test both local router connectivity (sub-1ms ping) and external WAN upstream ping to Cloudflare:",
                "command": f"ping -c 3 {gw} && ping -c 3 1.1.1.1"
            },
            {
                "step": 2,
                "title": "Inspect Active Wi-Fi Link Speed and Signal Strength",
                "details": "Verify your workstation is negotiated at high link speeds and not experiencing packet drops:",
                "command": "nmcli dev wifi show-password 2>/dev/null || nmcli -f IN-USE,SSID,BSSID,CHAN,RATE,SIGNAL,BARS dev wifi list"
            },
            {
                "step": 3,
                "title": "Review Archer BE550 Status & Active Leases",
                "details": f"1. Open **[https://{gw}](https://{gw})** in your browser.\n"
                           "2. Go to **Advanced > Status**.\n"
                           "3. Check **Internet IPv4 Status**: verify WAN IP is assigned.\n"
                           "4. Go to **Advanced > Network > DHCP Server** to view active client leases and identify IP conflicts.",
                "command": None
            },
            {
                "step": 4,
                "title": "Run Full Automated Router Audit via NetMap",
                "details": "Authenticate NetMap with your Archer BE550 via the **Router Settings** tab to run a live security, performance, and Wi-Fi audit.",
                "command": None
            }
        ]

        visual_diagram = {
            "type": "flowchart",
            "title": "Network Topology & Gateway Routing Pipeline",
            "nodes": [
                {"id": "wan", "label": wan.get("isp", "Aussie Broadband"), "sub": "NBN WAN (<15ms)", "icon": "🌐", "color": "#bb9af7"},
                {"id": "gw", "label": router.get("name", "Archer BE550"), "sub": f"Gateway {gw}", "icon": "📡", "color": "#7dcfff"},
                {"id": "host", "label": host.get("hostname", "Omarchy PC"), "sub": host.get("ip", "192.168.0.5"), "icon": "💻", "color": "#9ece6a"},
                {"id": "devs", "label": f"{len(devices)} LAN Devices", "sub": "Cameras, TVs, Extender", "icon": "🔌", "color": "#e0af68"}
            ],
            "links": [
                {"from": "wan", "to": "gw", "label": "2.5G NBN WAN"},
                {"from": "gw", "to": "host", "label": "Wi-Fi 7 / 2.5G LAN"},
                {"from": "gw", "to": "devs", "label": "DHCP Subnet 192.168.0.0/24"}
            ]
        }

        mermaid = (
            "graph LR\n"
            f"  WAN[{wan.get('isp', 'Aussie Broadband NBN')}] --> Router[{router.get('name', 'Archer BE550 v2')} {gw}]\n"
            f"  Router --> Host[{host.get('hostname', 'Omarchy PC')} {host.get('ip', '192.168.0.5')}]\n"
            f"  Router --> Devices[{len(devices)} Discovered Devices]"
        )

        return {
            "category": "Comprehensive Network Diagnostics",
            "goal": goal,
            "summary": f"Complete multi-point diagnostic plan for your {router.get('name', 'Archer BE550')} network and {len(devices)} connected devices.",
            "warnings": warnings,
            "steps": steps,
            "visual_diagram": visual_diagram,
            "mermaid": mermaid,
            "highlight_nodes": [gw, host.get("ip", "192.168.0.5")],
            "best_practices": [
                "Keep Archer BE550 firmware updated via Advanced > System > Firmware Update.",
                "Ensure devices on your network have static DHCP reservations for predictable connectivity."
            ]
        }
