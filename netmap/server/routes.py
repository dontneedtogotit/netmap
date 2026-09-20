"""
server/routes.py - Route handlers for NetMap server endpoints.

This module groups related API handlers into logical route handlers to
reduce complexity in the main server file and improve maintainability.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from netmap.server import STATE
from netmap.profile_manager import list_profiles, get_profile, rename_profile, delete_profile
from netmap.device_store import (
    load_device_settings,
    update_settings_for_device,
    PRESET_DEVICE_ROLES,
    PRESET_LOCATIONS,
    PRESET_PRIORITIES,
    PRESET_SEGMENTS,
)
from netmap.suggestions import generate_network_suggestions
from netmap.constants import DEFAULT_ROUTER_GATEWAY


class ProfileRoutes:
    @staticmethod
    def get_profiles() -> Dict[str, Any]:
        profiles = list_profiles(active_id=STATE.active_profile_id)
        return {
            "profiles": profiles,
            "active_profile_id": STATE.active_profile_id,
            "viewing_profile_id": STATE.viewing_profile_id or STATE.active_profile_id,
        }

    @staticmethod
    def get_profile(profile_id: str) -> Optional[Dict[str, Any]]:
        p = get_profile(profile_id)
        if not p:
            return None
        return {
            "profile": p,
            "is_active": (p.get("id") == STATE.active_profile_id),
        }

    @staticmethod
    def post_select(profile_id: str) -> Optional[Dict[str, Any]]:
        p = STATE.set_viewing_profile(profile_id)
        if not p:
            return None
        return {
            "success": True,
            "profile": p,
            "topology": STATE.get_topology(),
            "is_active": (profile_id == STATE.active_profile_id),
        }

    @staticmethod
    def post_rename(profile_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        new_name = (data.get("name") or "").strip()
        if not new_name:
            return {"error": "New name required"}, 400
        ok = rename_profile(profile_id, new_name)
        if not ok:
            return {"error": "Failed to rename profile"}, 404
        topo = STATE.get_topology()
        if topo and topo.get("profile", {}).get("id") == profile_id:
            topo["profile"]["name"] = new_name
        return {"success": True, "name": new_name}

    @staticmethod
    def delete(profile_id: str) -> Optional[Dict[str, Any]]:
        if profile_id == STATE.active_profile_id:
            return {"error": "Cannot delete currently connected active profile"}, 400
        ok = delete_profile(profile_id)
        if not ok:
            return None
        if STATE.viewing_profile_id == profile_id:
            STATE.viewing_profile_id = STATE.active_profile_id
            if STATE.active_profile_id:
                STATE.set_viewing_profile(STATE.active_profile_id)
        return {"success": True}


class DeviceRoutes:
    @staticmethod
    def get_settings(query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pid = None
        if query:
            pid = query.get("profile_id", [None])[0]
        if not pid:
            pid = STATE.viewing_profile_id or STATE.active_profile_id
        settings = load_device_settings(profile_id=pid)
        return {
            "profile_id": pid,
            "settings": settings,
            "presets": {
                "roles": PRESET_DEVICE_ROLES,
                "locations": PRESET_LOCATIONS,
                "priorities": PRESET_PRIORITIES,
                "segments": PRESET_SEGMENTS,
            },
        }

    @staticmethod
    def post_settings(data: Dict[str, Any]) -> Dict[str, Any]:
        ident = (data.get("identifier") or "").strip()
        settings = data.get("settings") or {}
        pid = data.get("profile_id") or STATE.viewing_profile_id or STATE.active_profile_id
        if not ident:
            return {"error": "Device identifier (MAC or IP) required"}, 400
        updated = update_settings_for_device(ident, settings, profile_id=pid)
        STATE.refresh_device_settings_in_topology(ident, updated)
        return {"success": True, "identifier": ident, "profile_id": pid, "settings": updated}


class SuggestionRoutes:
    @staticmethod
    def get_suggestions() -> Dict[str, Any]:
        topo = STATE.get_topology()
        if not topo:
            from netmap.scanner import perform_full_network_scan
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
                        "steps": [f["fix_guidance"]],
                    })
        return {"suggestions": suggestions}
