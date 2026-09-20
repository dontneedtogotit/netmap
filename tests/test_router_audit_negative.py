"""
test_router_audit_negative.py - Negative-path tests for router client/analyzer/server.

Covers malformed RSA, missing endpoints, timeout behavior, empty settings,
and router action confirmation/saved-credential fallbacks.
"""

from __future__ import annotations

import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from netmap.router_client import RouterClient
from netmap.router_analyzer import RouterAnalyzer
from netmap.agents import tool_router_audit
from netmap.server import NetMapHandler, STATE


class TestRouterClientNegativePaths(unittest.TestCase):
    @patch.object(RouterClient, "_post_form")
    def test_malformed_rsa_key_returns_error(self, mock_post: MagicMock) -> None:
        mock_post.return_value = (
            200,
            {"success": True, "data": {"password": ["not-a-hex", "010001"]}},
        )
        client = RouterClient(base_url="https://192.168.0.1", password="password")
        res = client.login()
        self.assertFalse(res["success"])
        self.assertIn("RSA encryption failed", res["error"])

    @patch.object(RouterClient, "_post_form")
    def test_key_endpoint_missing_falls_back(self, mock_post: MagicMock) -> None:
        mock_post.return_value = (404, {"error": "not found"})
        with patch.object(RouterClient, "_try_http_basic_login", return_value={
            "success": False,
            "error": "HTTP authentication failed: 401 Unauthorized",
        }):
            client = RouterClient(base_url="https://192.168.0.1", password="password")
            res = client.login()
        self.assertFalse(res["success"])

    @patch.object(RouterClient, "_post_form")
    def test_login_timeout_surfaces_failure(self, mock_post: MagicMock) -> None:
        mock_post.return_value = (0, {"error": "router timeout"})
        with patch.object(
            RouterClient,
            "_try_http_basic_login",
            return_value={"success": False, "error": "HTTP authentication failed"},
        ):
            client = RouterClient(base_url="https://192.168.0.1", password="password")
            res = client.login()
        self.assertFalse(res["success"])
        self.assertTrue(
            "Login request failed" in res["error"] or "HTTP authentication failed" in res["error"]
        )


class TestRouterAnalyzerNegativePaths(unittest.TestCase):
    def test_empty_settings_returns_bounded_result(self) -> None:
        analyzer = RouterAnalyzer({}, topology={})
        result = analyzer.analyze()
        self.assertIn("health_score", result)
        self.assertIn("grade", result)
        self.assertIn("findings", result)
        self.assertGreaterEqual(result["health_score"], 0)
        self.assertLessEqual(result["health_score"], 100)

    def test_none_topology_does_not_crash(self) -> None:
        analyzer = RouterAnalyzer({"mlo_enabled": False}, topology=None)
        result = analyzer.analyze()
        self.assertIn("health_score", result)
        self.assertGreaterEqual(result["health_score"], 0)
        self.assertLessEqual(result["health_score"], 100)


class TestToolRouterAuditNegativePaths(unittest.TestCase):
    @patch("netmap.router_client.RouterClient.login")
    def test_malformed_keys_returns_failure(self, mock_login: MagicMock) -> None:
        mock_login.return_value = {"success": False, "error": "RSA encryption failed"}
        res = tool_router_audit(gateway_url="https://192.168.0.1", password="password")
        self.assertFalse(res["success"])

    @patch("netmap.router_client.RouterClient.login")
    @patch("netmap.router_client.RouterClient.fetch_live_settings")
    @patch("netmap.router_client.RouterClient.logout")
    def test_empty_live_settings_returns_success(
        self, mock_logout: MagicMock, mock_fetch: MagicMock, mock_login: MagicMock
    ) -> None:
        mock_login.return_value = {"success": True, "stok": "token"}
        mock_fetch.return_value = {}
        res = tool_router_audit(gateway_url="https://192.168.0.1", password="password")
        self.assertTrue(res["success"])
        self.assertIn("health_score", res)
        self.assertGreaterEqual(res["health_score"], 0)
        self.assertLessEqual(res["health_score"], 100)

    @patch("netmap.router_client.load_stored_credentials", return_value=None)
    def test_missing_password_returns_error(self, mock_load: MagicMock) -> None:
        res = tool_router_audit(gateway_url="https://192.168.0.1", password="")
        self.assertFalse(res["success"])
        self.assertIn("password required", res["error"].lower())


class TestServerRouterNegativePaths(unittest.TestCase):
    def test_get_router_audit_without_topology(self) -> None:
        STATE.update_topology({})
        handler = NetMapHandler.__new__(NetMapHandler)
        handler._send_json = MagicMock()
        handler.handle_get_router_audit()
        args = handler._send_json.call_args[0][0]
        self.assertIn("has_audit", args)
        self.assertEqual(args["gateway_url"], "https://192.168.0.1")

    def test_get_router_credentials_without_topology(self) -> None:
        STATE.update_topology({})
        with patch("netmap.server.load_stored_credentials", return_value=None):
            handler = NetMapHandler.__new__(NetMapHandler)
            handler._send_json = MagicMock()
            handler.handle_get_router_credentials()
            args = handler._send_json.call_args[0][0]
            self.assertIn("has_saved_creds", args)
            self.assertFalse(args["has_saved_creds"])

    @patch("netmap.router_client.RouterClient.login")
    @patch("netmap.router_client.RouterClient.fetch_live_settings")
    def test_router_login_failure_preserves_error_code(
        self, mock_fetch: MagicMock, mock_login: MagicMock
    ) -> None:
        mock_login.return_value = {
            "success": False,
            "error": "Incorrect router password",
            "failure_count": 1,
            "attempts_remaining": 5,
        }
        handler = NetMapHandler.__new__(NetMapHandler)
        handler._send_json = MagicMock()
        handler.handle_post_router_login(
            {"url": "https://192.168.0.1", "password": "wrong"}
        )
        status = handler._send_json.call_args[1].get("status", 200)
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main(verbosity=2)
