"""
schemas.py - Lightweight typed helpers for NetMap server request/response contracts.

This module provides small dataclass-based schemas and serialization helpers so
handlers can validate/coerce inputs instead of passing raw Dict[str, Any].
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class BaseSchema:
    """Base schema with dict conversion."""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class AgentSolveRequest(BaseSchema):
    goal: str = ""
    agent: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class DeviceSettingsRequest(BaseSchema):
    identifier: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    profile_id: Optional[str] = None


@dataclass
class RouterLoginRequest(BaseSchema):
    url: Optional[str] = None
    username: str = "admin"
    password: str = ""
    remember: bool = False


@dataclass
class ActionExecuteRequest(BaseSchema):
    type: str = ""
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigUpdateRequest(BaseSchema):
    ai_provider: Optional[str] = None
    mistral_api_key: Optional[str] = None
    mistral_model: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None


@dataclass
class ProfileRenameRequest(BaseSchema):
    name: str = ""


def _coerce_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_agent_solve(data: Dict[str, Any]) -> AgentSolveRequest:
    return AgentSolveRequest(
        goal=_coerce_str(data.get("goal")),
        agent=data.get("agent") if data.get("agent") else None,
        session_id=data.get("session_id") if data.get("session_id") else None,
    )


def parse_device_settings(data: Dict[str, Any]) -> DeviceSettingsRequest:
    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    return DeviceSettingsRequest(
        identifier=_coerce_str(data.get("identifier")),
        settings=settings,
        profile_id=data.get("profile_id") if data.get("profile_id") else None,
    )


def parse_router_login(data: Dict[str, Any]) -> RouterLoginRequest:
    return RouterLoginRequest(
        url=data.get("url") if data.get("url") else None,
        username=_coerce_str(data.get("username"), "admin"),
        password=_coerce_str(data.get("password")),
        remember=_coerce_bool(data.get("remember"), False),
    )


def parse_action_execute(data: Dict[str, Any]) -> ActionExecuteRequest:
    params = data.get("params") if isinstance(data.get("params"), dict) else {}
    return ActionExecuteRequest(
        type=_coerce_str(data.get("type")),
        params=params,
    )


def parse_config_update(data: Dict[str, Any]) -> ConfigUpdateRequest:
    return ConfigUpdateRequest(
        ai_provider=data.get("ai_provider") if data.get("ai_provider") else None,
        mistral_api_key=data.get("mistral_api_key") if data.get("mistral_api_key") else None,
        mistral_model=data.get("mistral_model") if data.get("mistral_model") else None,
        openrouter_api_key=data.get("openrouter_api_key") if data.get("openrouter_api_key") else None,
        openrouter_model=data.get("openrouter_model") if data.get("openrouter_model") else None,
        gemini_api_key=data.get("gemini_api_key") if data.get("gemini_api_key") else None,
        gemini_model=data.get("gemini_model") if data.get("gemini_model") else None,
    )


def parse_profile_rename(data: Dict[str, Any]) -> ProfileRenameRequest:
    return ProfileRenameRequest(name=_coerce_str(data.get("name")))
