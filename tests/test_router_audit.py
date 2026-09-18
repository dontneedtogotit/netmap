"""
test_router_audit.py - Unit and Integration Tests for Router Login, Settings Analysis,
and Improvement Recommendations.
"""

import unittest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from netmap.router_client import (
    rsa_encrypt_pkcs1,
    save_stored_credentials,
    load_stored_credentials,
    clear_stored_credentials,
    RouterClient
)
from netmap.router_analyzer import RouterAnalyzer
from netmap.agents import tool_router_audit, TOOL_DEFINITIONS
from netmap.server import NetMapHandler, STATE


class TestRouterClient(unittest.TestCase):
    def test_rsa_encrypt_pkcs1(self):
        # 1024-bit test key components
        n_hex = (
            "b4a7e4edd70e3c6168271645b7bc412118da7d473decb5fbfb5d637723b6ec091074728a39ff34fcdb3107fe"
            "c64149bf9ac3897c57eb2c70ac65e3804dd68a4c0a00b1cf9e519f6e314ca8b429e2a81a4583e8c0578c44f3"
            "06041ec1221ad4e7a63772a0c6820789d02644b95c01ea0b1938ca7b03ac0d3b3b8b5eeea139"
        )
        e_hex = "010001"
        plaintext = "mySuperSecretRouterPwd123"

        encrypted = rsa_encrypt_pkcs1(plaintext, n_hex, e_hex)
        self.assertIsInstance(encrypted, str)
        # 1024-bit modulus is 128 bytes -> 256 hex characters
        expected_len = (len(n_hex) + 1) // 2 * 2
        self.assertEqual(len(encrypted), expected_len)

    def test_credentials_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_creds_path = Path(tmpdir) / "router_credentials.json"
            with patch("netmap.router_client.CREDENTIALS_FILE", test_creds_path):
                save_stored_credentials("https://192.168.0.1", "admin", "secret123")
                self.assertTrue(test_creds_path.exists())

                # Verify file permissions mode 0600 (user read/write only)
                mode = os.stat(test_creds_path).st_mode & 0o777
                self.assertEqual(mode, 0o600)

                loaded = load_stored_credentials("https://192.168.0.1")
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded["username"], "admin")
                self.assertEqual(loaded["password"], "secret123")

                cleared = clear_stored_credentials("https://192.168.0.1")
                self.assertTrue(cleared)
                self.assertIsNone(load_stored_credentials("https://192.168.0.1"))

    @patch.object(RouterClient, "_post_form")
    def test_router_login_success(self, mock_post):
        valid_n_hex = (
            "b4a7e4edd70e3c6168271645b7bc412118da7d473decb5fbfb5d637723b6ec091074728a39ff34fcdb3107fe"
            "c64149bf9ac3897c57eb2c70ac65e3804dd68a4c0a00b1cf9e519f6e314ca8b429e2a81a4583e8c0578c44f3"
            "06041ec1221ad4e7a63772a0c6820789d02644b95c01ea0b1938ca7b03ac0d3b3b8b5eeea139"
        )
        # 1st call: fetch keys
        # 2nd call: login
        mock_post.side_effect = [
            (200, {
                "success": True,
                "data": {
                    "password": [valid_n_hex, "010001"]
                }
            }),
            (200, {
                "success": True,
                "data": {
                    "stok": "test_stok_token_abc123"
                }
            })
        ]

        client = RouterClient(base_url="https://192.168.0.1", password="testpassword")
        res = client.login()

        self.assertTrue(res["success"])
        self.assertEqual(res["stok"], "test_stok_token_abc123")
        self.assertEqual(client.stok, "test_stok_token_abc123")

    @patch.object(RouterClient, "_post_form")
    def test_router_login_failure_with_attempts(self, mock_post):
        valid_n_hex = (
            "b4a7e4edd70e3c6168271645b7bc412118da7d473decb5fbfb5d637723b6ec091074728a39ff34fcdb3107fe"
            "c64149bf9ac3897c57eb2c70ac65e3804dd68a4c0a00b1cf9e519f6e314ca8b429e2a81a4583e8c0578c44f3"
            "06041ec1221ad4e7a63772a0c6820789d02644b95c01ea0b1938ca7b03ac0d3b3b8b5eeea139"
        )
        mock_post.side_effect = [
            (200, {
                "success": True,
                "data": {
                    "password": [valid_n_hex, "010001"]
                }
            }),
            (200, {
                "success": False,
                "errorcode": "login failed",
                "data": {
                    "failureCount": 2,
                    "attemptsAllowed": 8
                }
            })
        ]

        client = RouterClient(base_url="https://192.168.0.1", password="wrongpassword")
        res = client.login()

        self.assertFalse(res["success"])
        self.assertIn("Incorrect router password", res["error"])
        self.assertEqual(res["failure_count"], 2)
        self.assertEqual(res["attempts_remaining"], 8)


class TestRouterAnalyzer(unittest.TestCase):
    def test_health_score_and_improvements(self):
        raw_settings = {
            "remote_management": True,       # Critical: -15
            "mlo_enabled": False,            # Warning: -8
            "channel_width_6ghz": "160MHz",  # Recommended: -6
            "upnp_enabled": True,            # Recommended: -5
            "qos_enabled": False,            # Recommended: -10
            "dns_servers": ["192.168.0.1"]   # Recommended: -6
        }
        topology = {
            "has_cameras": True,
            "host": {"ip": "192.168.0.5", "mac": "08:71:90:10:32:04", "dns": ["192.168.0.1"]},
            "wan": {"cgnat_active": True},
            "devices": [{"category": "camera", "name": "Driveway Cam"}]
        }

        analyzer = RouterAnalyzer(raw_settings, topology=topology)
        result = analyzer.analyze()

        self.assertIn("health_score", result)
        self.assertIn("grade", result)
        self.assertLess(result["health_score"], 80)
        self.assertGreater(result["total_recommendations"], 0)
        self.assertGreater(result["critical_count"], 0)

        finding_ids = [f["id"] for f in result["findings"]]
        self.assertIn("sec-remote-mgmt", finding_ids)
        self.assertIn("wifi-mlo-disabled", finding_ids)
        self.assertIn("sec-iot-isolation", finding_ids)
        self.assertIn("qos-bufferbloat", finding_ids)
        self.assertIn("wan-cgnat-blocked", finding_ids)

    def test_perfect_settings_yields_high_score(self):
        clean_settings = {
            "remote_management": False,
            "mlo_enabled": True,
            "channel_width_6ghz": "320MHz",
            "upnp_enabled": False,
            "qos_enabled": True,
            "dns_servers": ["1.1.1.1", "1.0.0.1"],
            "iot_isolation_enabled": True,
            "dhcp_reservations": [{"ip": "192.168.0.5", "mac": "08:71:90:10:32:04"}]
        }
        clean_topology = {
            "has_cameras": True,
            "host": {"ip": "192.168.0.5", "mac": "08:71:90:10:32:04", "dns": ["1.1.1.1"]},
            "wan": {"cgnat_active": False},
            "devices": []
        }

        analyzer = RouterAnalyzer(clean_settings, topology=clean_topology)
        result = analyzer.analyze()

        self.assertEqual(result["health_score"], 100)
        self.assertEqual(result["grade"], "A+")
        self.assertEqual(result["critical_count"], 0)


class TestAgentToolIntegration(unittest.TestCase):
    def test_tool_definition_exists(self):
        tool_names = [t["name"] for t in TOOL_DEFINITIONS]
        self.assertIn("tool_router_audit", tool_names)

    @patch("netmap.router_client.RouterClient.login")
    @patch("netmap.router_client.RouterClient.fetch_live_settings")
    @patch("netmap.router_client.RouterClient.logout")
    def test_tool_router_audit_execution(self, mock_logout, mock_fetch, mock_login):
        mock_login.return_value = {"success": True, "stok": "token123"}
        mock_fetch.return_value = {
            "mlo_enabled": True,
            "channel_width_6ghz": "320MHz"
        }

        res = tool_router_audit(gateway_url="https://192.168.0.1", password="validpwd")
        self.assertTrue(res["success"])
        self.assertIn("health_score", res)
        self.assertIn("grade", res)


class TestServerRouterEndpoints(unittest.TestCase):
    def test_server_router_audit_and_credentials(self):
        handler = NetMapHandler.__new__(NetMapHandler)
        handler._send_json = MagicMock()

        handler.handle_get_router_audit()
        handler._send_json.assert_called_once()
        args = handler._send_json.call_args[0][0]
        self.assertIn("has_audit", args)
        self.assertIn("gateway_url", args)

        handler._send_json.reset_mock()
        handler.handle_get_router_credentials()
        handler._send_json.assert_called_once()
        args2 = handler._send_json.call_args[0][0]
        self.assertIn("has_saved_creds", args2)

    @patch("netmap.router_client.RouterClient.login")
    @patch("netmap.router_client.RouterClient.fetch_live_settings")
    def test_server_post_router_login(self, mock_fetch, mock_login):
        mock_login.return_value = {"success": True, "stok": "abc"}
        mock_fetch.return_value = {"mlo_enabled": False}

        handler = NetMapHandler.__new__(NetMapHandler)
        handler._send_json = MagicMock()

        handler.handle_post_router_login({
            "url": "https://192.168.0.1",
            "password": "valid_password",
            "remember": False
        })

        handler._send_json.assert_called_once()
        resp = handler._send_json.call_args[0][0]
        self.assertTrue(resp["success"])
        self.assertIn("health_score", resp)
        self.assertIn("audit", resp)


if __name__ == "__main__":
    unittest.main()
