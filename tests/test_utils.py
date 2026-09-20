"""
tests/test_utils.py - Shared test utilities for NetMap tests.

Provides helpers to reduce duplication and flakiness across integration tests:
- ephemeral port allocation
- common test topologies
- reusable server lifecycle helpers
"""

from __future__ import annotations

import socket
import threading
import time
import urllib.request
import json
from typing import Dict, Any, Optional

from netmap.server import ThreadedHTTPServer, NetMapHandler, STATE


def get_available_port() -> int:
    """Bind to port 0 and return the assigned free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestServer:
    """Lightweight wrapper around ThreadedHTTPServer for tests."""

    def __init__(self, port: Optional[int] = None) -> None:
        self.port = port or get_available_port()
        self.server = ThreadedHTTPServer(("127.0.0.1", self.port), NetMapHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def wait_ready(self, seconds: float = 0.3) -> None:
        time.sleep(seconds)

    def shutdown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def get(self, path: str) -> Dict[str, Any]:
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read().decode("utf-8"))

    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read().decode("utf-8"))


SAMPLE_TOPOLOGY: Dict[str, Any] = {
    "wan": {"isp": "Aussie Broadband", "cgnat_active": True},
    "host": {
        "ip": "127.0.0.1",
        "gateway": "192.168.0.1",
        "mac": "B8:FB:B3:01:02:03",
    },
    "router": {"name": "Archer BE550 v2"},
    "router_settings": {"hardware": {"model_name": "Archer BE550 v2"}},
    "devices": [
        {
            "ip": "127.0.0.1",
            "mac": "B8:FB:B3:01:02:03",
            "name": "Workstation",
            "category": "host",
        },
        {
            "ip": "192.168.0.136",
            "mac": "28:57:BE:11:22:33",
            "name": "Cam 1",
            "category": "camera",
            "open_ports": [554],
        },
    ],
}


def seed_state() -> None:
    STATE.update_topology(SAMPLE_TOPOLOGY)
