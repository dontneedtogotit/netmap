"""
server.py - Embedded local web server for NetMap GUI.
Serves static assets and provides REST API endpoints for scanning, diagnostics,
Mistral AI & OpenRouter configuration, network suggestions, device customization,
multi-agent orchestration, and technical documentation knowledge base.
"""

import http.server
import socketserver
import json
import os
import threading
import subprocess
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional

from netmap.scanner import perform_full_network_scan, get_local_host_info
from netmap.hardware import add_tvpc_camera, test_rtsp_stream
from netmap.tracer import (
    ping_host,
    get_network_metrics,
    send_wake_on_lan,
    run_bufferbloat_test,
    get_wifi_spectrum_survey
)
from netmap.advisor import (
    NetworkAdvisor,
    RECOMMENDED_FREE_MODELS,
    RECOMMENDED_MISTRAL_MODELS,
    RECOMMENDED_GEMINI_MODELS,
    load_config,
    save_config
)
from netmap.device_store import (
    load_device_settings,
    update_settings_for_device,
    PRESET_DEVICE_ROLES,
    PRESET_LOCATIONS,
    PRESET_PRIORITIES,
    PRESET_SEGMENTS
)
from netmap.suggestions import generate_network_suggestions
from netmap.agents import (
    AGENT_CATALOG,
    TOOL_DEFINITIONS,
    AGENT_ORCHESTRATOR,
    tool_ping,
    tool_portscan,
    tool_read_docs,
    tool_list_docs,
    tool_wake_on_lan,
    tool_bufferbloat,
    tool_wifi_spectrum,
    tool_router_audit
)
from netmap.router_client import (
    RouterClient,
    load_stored_credentials,
    save_stored_credentials,
    clear_stored_credentials
)
from netmap.router_analyzer import RouterAnalyzer

BASE_DIR = Path(__file__).parent
WEB_DIR = BASE_DIR / "web"

class NetMapState:
    def __init__(self):
        self.topology: Optional[Dict[str, Any]] = None
        self.active_profile_id: Optional[str] = None
        self.viewing_profile_id: Optional[str] = None
        self.is_scanning = False
        self.lock = threading.Lock()
        self.advisor = NetworkAdvisor()
        self.router_client: Optional[RouterClient] = None
        self.router_audit: Optional[Dict[str, Any]] = None

    def update_topology(self, topo: Dict[str, Any]):
        with self.lock:
            self.topology = topo
            if topo and "profile" in topo and topo["profile"].get("id"):
                self.active_profile_id = topo["profile"]["id"]
                if not self.viewing_profile_id:
                    self.viewing_profile_id = self.active_profile_id

    def get_topology(self) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self.topology

    def set_viewing_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            from netmap.profile_manager import get_profile
            p = get_profile(profile_id)
            if p:
                self.viewing_profile_id = profile_id
                if p.get("topology"):
                    self.topology = p["topology"]
                return p
            return None

    def refresh_device_settings_in_topology(self, identifier: str, new_settings: Dict[str, Any]):
        with self.lock:
            if not self.topology:
                return
            for dev in self.topology.get("devices", []):
                mac = (dev.get("mac") or "").upper()
                ip = dev.get("ip") or ""
                target_ident = identifier.strip().upper() if ":" in identifier else identifier.strip()
                if (mac and mac == target_ident) or (ip and ip == target_ident):
                    dev["user_settings"] = new_settings
                    if new_settings.get("alias"):
                        dev["original_name"] = dev.get("original_name") or dev.get("name")
                        dev["name"] = new_settings["alias"]
                    if new_settings.get("role"):
                        dev["custom_role"] = new_settings["role"]
                    if "custom_fields" in new_settings:
                        dev["custom_fields"] = new_settings["custom_fields"]

STATE = NetMapState()

class NetMapHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/status":
            self.handle_get_status()
        elif path == "/api/profiles":
            self.handle_get_profiles()
        elif path.startswith("/api/profiles/"):
            pid = path[len("/api/profiles/"):].strip("/")
            self.handle_get_profile(pid)
        elif path == "/api/wifi":
            self.handle_get_wifi()
        elif path == "/api/metrics":
            self.handle_get_metrics()
        elif path == "/api/router-settings":
            self.handle_get_router_settings()
        elif path == "/api/suggestions":
            self.handle_get_suggestions()
        elif path == "/api/devices/settings":
            self.handle_get_device_settings(query=query)
        elif path == "/api/config":
            self.handle_get_config()
        elif path == "/api/models":
            self.handle_get_models()
        elif path == "/api/agent/agents":
            self._send_json(AGENT_CATALOG)
        elif path == "/api/agent/tools":
            self._send_json(TOOL_DEFINITIONS)
        elif path == "/api/docs":
            topic = query.get("topic", [None])[0] or query.get("id", [None])[0]
            if topic:
                self._send_json(tool_read_docs(topic))
            else:
                self._send_json({"articles": tool_list_docs()})
        elif path == "/api/diagnostics/spectrum":
            self.handle_get_spectrum()
        elif path == "/api/router/audit":
            self.handle_get_router_audit()
        elif path == "/api/router/credentials":
            self.handle_get_router_credentials()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if path.startswith("/api/profiles/") and path.endswith("/select"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[1] == "profiles" and parts[3] == "select":
                self.handle_post_profile_select(parts[2])
                return
        elif path.startswith("/api/profiles/") and path.endswith("/rename"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[1] == "profiles" and parts[3] == "rename":
                self.handle_post_profile_rename(parts[2], data)
                return

        if path == "/api/scan":
            self.handle_post_scan()
        elif path == "/api/solve":
            self.handle_post_solve(data)
        elif path == "/api/agent/run":
            self.handle_post_agent_run(data)
        elif path == "/api/agent/chat":
            self.handle_post_agent_chat(data)
        elif path == "/api/agent/execute-action":
            self.handle_post_execute_action(data)
        elif path == "/api/router/login":
            self.handle_post_router_login(data)
        elif path == "/api/router/logout":
            self.handle_post_router_logout()
        elif path == "/api/router/credentials/clear":
            self.handle_post_router_credentials_clear()
        elif path == "/api/ping":
            self.handle_post_ping(data)
        elif path == "/api/portscan":
            self.handle_post_portscan(data)
        elif path == "/api/config":
            self.handle_post_config(data)
        elif path == "/api/devices/settings":
            self.handle_post_device_settings(data)
        elif path == "/api/devices/wol":
            self.handle_post_wol(data)
        elif path == "/api/camera/test":
            self.handle_post_camera_test(data)
        elif path == "/api/camera/add-tvpc":
            self.handle_post_camera_add_tvpc(data)
        elif path == "/api/diagnostics/bufferbloat":
            self.handle_post_bufferbloat(data)
        else:
            self.send_error(404, "Endpoint not found")

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/profiles/"):
            pid = path[len("/api/profiles/"):].strip("/")
            self.handle_delete_profile(pid)
        else:
            self.send_error(404, "Endpoint not found")

    def _send_json(self, data: Any, status: int = 200):
        content = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def handle_get_profiles(self):
        from netmap.profile_manager import list_profiles
        profiles = list_profiles(active_id=STATE.active_profile_id)
        self._send_json({
            "profiles": profiles,
            "active_profile_id": STATE.active_profile_id,
            "viewing_profile_id": STATE.viewing_profile_id or STATE.active_profile_id
        })

    def handle_get_profile(self, profile_id: str):
        from netmap.profile_manager import get_profile
        p = get_profile(profile_id)
        if not p:
            self._send_json({"error": "Profile not found"}, status=404)
            return
        self._send_json({
            "profile": p,
            "is_active": (p.get("id") == STATE.active_profile_id)
        })

    def handle_post_profile_select(self, profile_id: str):
        p = STATE.set_viewing_profile(profile_id)
        if not p:
            self._send_json({"error": "Profile not found"}, status=404)
            return
        self._send_json({
            "success": True,
            "profile": p,
            "topology": STATE.get_topology(),
            "is_active": (profile_id == STATE.active_profile_id)
        })

    def handle_post_profile_rename(self, profile_id: str, data: Dict[str, Any]):
        new_name = data.get("name", "").strip()
        if not new_name:
            self._send_json({"error": "New name required"}, status=400)
            return
        from netmap.profile_manager import rename_profile
        ok = rename_profile(profile_id, new_name)
        if not ok:
            self._send_json({"error": "Failed to rename profile"}, status=404)
            return
        topo = STATE.get_topology()
        if topo and topo.get("profile", {}).get("id") == profile_id:
            topo["profile"]["name"] = new_name
        self._send_json({"success": True, "name": new_name})

    def handle_delete_profile(self, profile_id: str):
        from netmap.profile_manager import delete_profile
        if profile_id == STATE.active_profile_id:
            self._send_json({"error": "Cannot delete currently connected active profile"}, status=400)
            return
        ok = delete_profile(profile_id)
        if not ok:
            self._send_json({"error": "Profile not found or could not be deleted"}, status=404)
            return
        if STATE.viewing_profile_id == profile_id:
            STATE.viewing_profile_id = STATE.active_profile_id
            if STATE.active_profile_id:
                STATE.set_viewing_profile(STATE.active_profile_id)
        self._send_json({"success": True})

    def handle_get_status(self):
        topo = STATE.get_topology()
        if not topo:
            topo = perform_full_network_scan()
            STATE.update_topology(topo)
        self._send_json({
            "scanning": STATE.is_scanning,
            "topology": topo,
            "active_profile_id": STATE.active_profile_id,
            "viewing_profile_id": STATE.viewing_profile_id or STATE.active_profile_id
        })

    def handle_get_wifi(self):
        host = get_local_host_info()
        self._send_json(host.get("wifi", {}))

    def handle_get_metrics(self):
        metrics = get_network_metrics()
        self._send_json(metrics)

    def handle_get_router_settings(self):
        topo = STATE.get_topology()
        if not topo:
            topo = perform_full_network_scan()
            STATE.update_topology(topo)
        self._send_json(topo.get("router_settings", {}))

    def handle_get_suggestions(self):
        topo = STATE.get_topology()
        if not topo:
            topo = perform_full_network_scan()
            STATE.update_topology(topo)
        suggestions = list(topo.get("suggestions") or generate_network_suggestions(topo))
        if STATE.router_audit and "findings" in STATE.router_audit:
            existing_ids = {s.get("id") for s in suggestions}
            for f in STATE.router_audit.get("findings", []):
                if f["id"] not in existing_ids:
                    suggestions.append({
                        "id": f["id"],
                        "category": f["category"],
                        "priority": f["severity"],
                        "badge": f["badge"],
                        "title": f["title"],
                        "description": f["description"],
                        "current_state": f["current_value"],
                        "recommended_state": f["recommended_value"],
                        "be550_path": f["router_path"],
                        "action_goal": f["ai_prompt"],
                        "steps": [f["fix_guidance"]]
                    })
        self._send_json({"suggestions": suggestions})

    def handle_get_device_settings(self, query=None):
        pid = None
        if query:
            pid = query.get("profile_id", [None])[0]
        if not pid:
            pid = STATE.viewing_profile_id or STATE.active_profile_id
        settings = load_device_settings(profile_id=pid)
        self._send_json({
            "profile_id": pid,
            "settings": settings,
            "presets": {
                "roles": PRESET_DEVICE_ROLES,
                "locations": PRESET_LOCATIONS,
                "priorities": PRESET_PRIORITIES,
                "segments": PRESET_SEGMENTS
            }
        })

    def handle_post_device_settings(self, data: Dict[str, Any]):
        ident = data.get("identifier", "").strip()
        settings = data.get("settings", {})
        pid = data.get("profile_id") or STATE.viewing_profile_id or STATE.active_profile_id
        if not ident:
            self._send_json({"error": "Device identifier (MAC or IP) required"}, status=400)
            return

        updated = update_settings_for_device(ident, settings, profile_id=pid)
        STATE.refresh_device_settings_in_topology(ident, updated)
        self._send_json({"success": True, "identifier": ident, "profile_id": pid, "settings": updated})

    def handle_get_config(self):
        cfg = load_config()
        
        m_key = cfg.get("mistral_api_key", "")
        m_masked = (m_key[:4] + "..." + m_key[-4:]) if len(m_key) > 8 else m_key
        
        or_key = cfg.get("openrouter_api_key", "")
        or_masked = (or_key[:6] + "..." + or_key[-4:]) if len(or_key) > 10 else or_key
        
        g_key = cfg.get("gemini_api_key", "")
        g_masked = (g_key[:4] + "..." + g_key[-4:]) if len(g_key) > 8 else g_key
        
        provider = cfg.get("ai_provider")
        if not provider:
            if g_key:
                provider = "gemini"
            elif m_key:
                provider = "mistral"
            elif or_key:
                provider = "openrouter"
            else:
                provider = "local"

        self._send_json({
            "ai_provider": provider,
            "mistral_has_key": bool(m_key),
            "mistral_masked_key": m_masked,
            "mistral_raw_key": m_key,
            "mistral_model": cfg.get("mistral_model", "mistral-small-latest"),
            "openrouter_has_key": bool(or_key),
            "openrouter_masked_key": or_masked,
            "openrouter_raw_key": or_key,
            "openrouter_model": cfg.get("openrouter_model", "deepseek/deepseek-v4-flash-0731:free"),
            "gemini_has_key": bool(g_key),
            "gemini_masked_key": g_masked,
            "gemini_raw_key": g_key,
            "gemini_model": cfg.get("gemini_model", "gemini-2.0-flash")
        })

    def handle_get_models(self):
        self._send_json({
            "mistral": RECOMMENDED_MISTRAL_MODELS,
            "openrouter": RECOMMENDED_FREE_MODELS,
            "gemini": RECOMMENDED_GEMINI_MODELS
        })

    def handle_post_scan(self):
        def _scan():
            STATE.is_scanning = True
            try:
                topo = perform_full_network_scan(profile_id=STATE.viewing_profile_id)
                STATE.update_topology(topo)
            finally:
                STATE.is_scanning = False

        threading.Thread(target=_scan, daemon=True).start()
        self._send_json({"status": "Scan started", "scanning": True})

    def handle_post_solve(self, data: Dict[str, Any]):
        goal = data.get("goal", "").strip()
        if not goal:
            self._send_json({"error": "No goal provided"}, status=400)
            return

        topo = STATE.get_topology()
        if not topo:
            topo = perform_full_network_scan()
            STATE.update_topology(topo)

        agent_id = data.get("agent")
        # Route through Agentic Orchestrator
        solution = AGENT_ORCHESTRATOR.run_agentic_workflow(goal, topo, requested_agent=agent_id)
        self._send_json(solution)

    def handle_post_agent_run(self, data: Dict[str, Any]):
        goal = data.get("goal", "").strip()
        agent_id = data.get("agent")
        if not goal:
            self._send_json({"error": "No goal provided"}, status=400)
            return

        topo = STATE.get_topology()
        if not topo:
            topo = perform_full_network_scan()
            STATE.update_topology(topo)

        result = AGENT_ORCHESTRATOR.run_agentic_workflow(goal, topo, requested_agent=agent_id)
        self._send_json(result)

    def handle_post_agent_chat(self, data: Dict[str, Any]):
        message = data.get("message", "").strip()
        session_id = data.get("session_id", "default_session")
        agent_id = data.get("agent")
        if not message:
            self._send_json({"error": "No message provided"}, status=400)
            return

        topo = STATE.get_topology()
        if not topo:
            topo = perform_full_network_scan()
            STATE.update_topology(topo)

        result = AGENT_ORCHESTRATOR.chat_multi_turn(session_id, message, topo, agent_id=agent_id)
        self._send_json(result)

    def handle_post_execute_action(self, data: Dict[str, Any]):
        action_type = data.get("type", "").strip()
        params = data.get("params", {})
        
        if action_type == "tool_ping":
            host = params.get("host", "192.168.0.1")
            count = int(params.get("count", 2))
            res = tool_ping(host, count=count)
            self._send_json({"success": True, "action": action_type, "result": res})
        elif action_type == "tool_portscan":
            ip = params.get("ip", "192.168.0.1")
            ports = params.get("ports")
            res = tool_portscan(ip, ports)
            self._send_json({"success": True, "action": action_type, "result": res})
        elif action_type == "tool_read_docs":
            topic = params.get("topic", "be550")
            res = tool_read_docs(topic)
            self._send_json({"success": True, "action": action_type, "result": res})
        elif action_type == "tool_wake_on_lan":
            mac = params.get("mac", "")
            res = tool_wake_on_lan(mac)
            self._send_json({"success": True, "action": action_type, "result": res})
        elif action_type == "tool_bufferbloat":
            target = params.get("target", "1.1.1.1")
            res = tool_bufferbloat(target=target)
            self._send_json({"success": True, "action": action_type, "result": res})
        elif action_type == "tool_wifi_spectrum":
            res = tool_wifi_spectrum()
            self._send_json({"success": True, "action": action_type, "result": res})
        elif action_type == "tool_router_audit":
            gw = params.get("gateway_url", "https://192.168.0.1")
            pwd = params.get("password", "")
            user = params.get("username", "admin")
            res = tool_router_audit(gateway_url=gw, password=pwd, username=user)
            self._send_json({"success": True, "action": action_type, "result": res})
        else:
            self._send_json({"error": f"Unknown action type '{action_type}'"}, status=400)

    def handle_get_router_audit(self):
        topo = STATE.get_topology()
        gw = topo.get("host", {}).get("gateway", "192.168.0.1") if topo else "192.168.0.1"
        gw_url = f"https://{gw}" if not str(gw).startswith("http") else str(gw)
        creds = load_stored_credentials(gw_url)
        self._send_json({
            "has_audit": STATE.router_audit is not None,
            "audit": STATE.router_audit or {},
            "authenticated": STATE.router_client is not None and STATE.router_client.stok is not None,
            "has_saved_creds": creds is not None,
            "saved_username": creds.get("username", "admin") if creds else "admin",
            "gateway_url": gw_url
        })

    def handle_get_router_credentials(self):
        topo = STATE.get_topology()
        gw = topo.get("host", {}).get("gateway", "192.168.0.1") if topo else "192.168.0.1"
        gw_url = f"https://{gw}" if not str(gw).startswith("http") else str(gw)
        creds = load_stored_credentials(gw_url)
        self._send_json({
            "has_saved_creds": creds is not None,
            "username": creds.get("username", "admin") if creds else "admin",
            "gateway_url": gw_url
        })

    def handle_post_router_login(self, data: Dict[str, Any]):
        topo = STATE.get_topology()
        default_gw = topo.get("host", {}).get("gateway", "192.168.0.1") if topo else "192.168.0.1"
        gw_url = data.get("url") or f"https://{default_gw}"
        user = data.get("username") or "admin"
        pwd = data.get("password", "")
        remember = bool(data.get("remember", False))

        if not pwd:
            saved = load_stored_credentials(gw_url)
            if saved and saved.get("password"):
                pwd = saved.get("password")
                user = saved.get("username", user)

        if not pwd:
            self._send_json({"success": False, "error": "Router password is required"}, status=400)
            return

        client = RouterClient(base_url=gw_url, username=user, password=pwd)
        login_res = client.login()
        if not login_res.get("success"):
            status_code = 401 if "password" in login_res.get("error", "").lower() else 400
            self._send_json(login_res, status=status_code)
            return

        if remember:
            save_stored_credentials(gw_url, user, pwd)

        STATE.router_client = client
        live_settings = client.fetch_live_settings()
        analyzer = RouterAnalyzer(live_settings, topology=topo)
        audit = analyzer.analyze()
        STATE.router_audit = audit

        if topo:
            topo["router_audit"] = audit
            existing_sugs = topo.get("suggestions", [])
            existing_ids = {s.get("id") for s in existing_sugs}
            for f in audit.get("findings", []):
                if f["id"] not in existing_ids:
                    existing_sugs.append({
                        "id": f["id"],
                        "category": f["category"],
                        "priority": f["severity"],
                        "badge": f["badge"],
                        "title": f["title"],
                        "description": f["description"],
                        "current_state": f["current_value"],
                        "recommended_state": f["recommended_value"],
                        "be550_path": f["router_path"],
                        "action_goal": f["ai_prompt"],
                        "steps": [f["fix_guidance"]]
                    })
            topo["suggestions"] = existing_sugs

        self._send_json({
            "success": True,
            "message": "Router logged in and settings audited successfully",
            "health_score": audit["health_score"],
            "grade": audit["grade"],
            "audit": audit,
            "settings": live_settings
        })

    def handle_post_router_logout(self):
        if STATE.router_client:
            try:
                STATE.router_client.logout()
            except Exception:
                pass
            STATE.router_client = None
        self._send_json({"success": True, "message": "Logged out from router session"})

    def handle_post_router_credentials_clear(self):
        topo = STATE.get_topology()
        default_gw = topo.get("host", {}).get("gateway", "192.168.0.1") if topo else "192.168.0.1"
        clear_stored_credentials(f"https://{default_gw}")
        clear_stored_credentials(f"http://{default_gw}")
        self._send_json({"success": True, "message": "Stored router credentials cleared"})

    def handle_post_ping(self, data: Dict[str, Any]):
        host = data.get("host", "").strip()
        if not host:
            self._send_json({"error": "No host specified"}, status=400)
            return
        res = ping_host(host, count=2)
        self._send_json(res)

    def handle_post_portscan(self, data: Dict[str, Any]):
        ip = data.get("ip", "").strip()
        ports_to_test = data.get("ports")
        res = tool_portscan(ip, ports_to_test)
        self._send_json(res)

    def handle_post_config(self, data: Dict[str, Any]):
        ai_provider = data.get("ai_provider")
        mistral_key = data.get("mistral_api_key")
        mistral_model = data.get("mistral_model")
        openrouter_key = data.get("openrouter_api_key")
        openrouter_model = data.get("openrouter_model")
        gemini_key = data.get("gemini_api_key")
        gemini_model = data.get("gemini_model")
        
        STATE.advisor.set_config(
            ai_provider=ai_provider,
            mistral_key=mistral_key,
            mistral_model=mistral_model,
            openrouter_key=openrouter_key,
            openrouter_model=openrouter_model,
            gemini_key=gemini_key,
            gemini_model=gemini_model
        )
        self._send_json({"success": True})

    def handle_get_spectrum(self):
        res = get_wifi_spectrum_survey()
        self._send_json(res)

    def handle_post_wol(self, data: Dict[str, Any]):
        mac = data.get("mac", "").strip()
        if not mac:
            self._send_json({"error": "MAC address required for Wake-on-LAN"}, status=400)
            return
        res = send_wake_on_lan(mac)
        self._send_json(res)

    def handle_post_camera_test(self, data: Dict[str, Any]):
        host = data.get("host") or data.get("ip", "").strip()
        port = int(data.get("port", 554))
        if not host:
            self._send_json({"error": "Host or IP required for camera stream test"}, status=400)
            return
        res = test_rtsp_stream(host, port=port)
        self._send_json(res)

    def handle_post_camera_add_tvpc(self, data: Dict[str, Any]):
        name = data.get("name", "").strip()
        url = data.get("url", "").strip()
        group = data.get("group", "Default").strip()
        enabled = data.get("enabled", "1")
        if not name or not url:
            self._send_json({"error": "Camera name and RTSP URL required"}, status=400)
            return
        res = add_tvpc_camera(name=name, url=url, group=group, enabled=enabled)
        self._send_json(res)

    def handle_post_bufferbloat(self, data: Dict[str, Any]):
        target = data.get("target", "1.1.1.1").strip() or "1.1.1.1"
        res = run_bufferbloat_test(target_ip=target)
        self._send_json(res)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

def run_server(port: int = 8765):
    server = ThreadedHTTPServer(("127.0.0.1", port), NetMapHandler)
    print(f"[NetMap] Server running on http://127.0.0.1:{port}")
    threading.Thread(target=lambda: STATE.update_topology(perform_full_network_scan()), daemon=True).start()
    server.serve_forever()

if __name__ == "__main__":
    run_server()
